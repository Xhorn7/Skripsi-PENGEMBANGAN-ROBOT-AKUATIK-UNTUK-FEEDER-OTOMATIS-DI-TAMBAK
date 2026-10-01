"""
feeder_core.py  —  Lapisan BACKEND untuk GUI Feeder Robot Akuatik
==================================================================

Modul ini SENGAJA dipisah dari GUI (feeder_gui.py) mengikuti prinsip
Separation of Concerns. Tujuannya (relevan utk dokumentasi SDLC):

    - GUI  = presentasi (tombol, gauge, log view)
    - Core = logika: radio link, estimasi telemetri, pencatatan aktivitas

Kelas & fungsi utama:

    1. RobotCommand    -> satu paket Sinyal Kendali "[Moves]:[Dist]" sesuai
                          "Dokumen Spesifikasi Teknis — Robot Akuatik untuk
                          Tambak Ikan" (FW / CW / CCW / STOP).
    2. RadioLink       -> abstraksi NRF24 (pyrf24) yang bisa DIPINDAH mode
                          REAL <-> SIMULASI saat aplikasi berjalan
                          (set_mode); mode SIMULASI memakai MockRadio.
                          Juga merutekan sinyal balik "ON [Moves]" & "FIN
                          [Moves]:[Dist]" serta telemetri MPU.
    3. plan_coverage / plan_command_queue
                       -> terjemahkan tambak persegi menjadi jalur sapuan, lalu
                          menjadi ANTREAN perintah FW/CW/CCW yang dikemudikan
                          Pengendali Utama.
    4. CommandRunner   -> pelaksana pola Request-Response: kirim perintah,
                          tunggu "ON" (kirim ulang bila lewat 1 detik), tunggu
                          "FIN", lanjut perintah berikutnya.
    5. ActivityLogger  -> catat semua aktivitas, export ke CSV/TXT, dan
                          AUTO-SIMPAN tiap baris ke berkas TXT. Berkas log yang
                          lebih tua dari LOG_RETENTION_DAYS dibuang otomatis
                          (purge_old_logs) supaya kartu SD Raspberry Pi aman.

CATATAN KEJUJURAN TEKNIS:
    Nilai RPM & kecepatan pada gauge adalah ESTIMASI dari PWM throttle yang
    SEHARUSNYA dijalankan robot untuk perintah yang sedang berlangsung — bukan
    hasil ukur sensor RPM. Yang REAL/terukur: ACK radio, sinyal ON/FIN dari
    robot, dan sudut MPU yang dikirim balik lewat telemetri NRF (tanpa kabel
    serial — MPU tidak lagi butuh port USB).
"""

from __future__ import annotations

import csv
import math
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Optional


# =====================================================================
# KONSTANTA — WAJIB SAMA dengan firmware Finalnew.ino agar estimasi valid
# =====================================================================

LANE_WIDTH_M      = 1.0     # jarak antar lintasan (m)
ROBOT_SPEED_MPS   = 0.135   # kecepatan robot @ CRUISE_PWM (m/s), WAJIB sama dengan firmware
CRUISE_PWM        = 1300    # throttle jelajah (us)
STOP_PWM          = 1000    # throttle diam/arming (us)
FULL_PWM          = 2000    # throttle penuh (us)
SIGNAL_TIMEOUT_MS = 3000    # failsafe robot: stop bila tak ada sinyal

# Parameter estimasi RPM (KASAR — silakan kalibrasi sesuai motor nyata).
# RPM_est = throttle_fraction * MOTOR_KV * BATTERY_V
MOTOR_KV          = 2200.0  # KV motor brushless (rpm/volt)
BATTERY_V         = 11.1    # tegangan baterai (3S LiPo)

HEARTBEAT_INTERVAL_S = 0.5  # interval PING (harus < SIGNAL_TIMEOUT_MS)

# --- Telemetri balik (komunikasi 2 arah, half-duplex "gantian") ---
# Robot mengirim MPU ke alamat ini setelah menerima PING; Pi mendengarkan
# sebentar sesudah tiap PING untuk menangkapnya. Format ASCII: "R=..;P=..;Y=.."
TELEMETRY_ADDR   = b"00002"   # alamat balik Robot -> Pi (beda dari perintah "00001")
TELEMETRY_POLL_S = 0.07       # lama Pi mendengarkan telemetri tiap siklus (s)
TELEMETRY_STALE_S = 2.0       # telemetri dianggap basi bila > ini (s)
# Bidang ";S=<kode>" di ekor paket adalah status kesehatan MPU dari firmware.
# Opsional, supaya firmware lama yang belum mengirimnya tetap terbaca.
_TEL_RE = re.compile(r"R=(-?[\d.]+);P=(-?[\d.]+);Y=(-?[\d.]+)(?:;S=(\d))?")

# Kode status MPU -> (sudut boleh dipercaya?, penjelasan untuk operator).
# ESP32 di robot umumnya sudah terpasang & tidak bisa dicolok Serial, jadi
# diagnosa dikirim lewat radio dan diterjemahkan di sini.
MPU_STATUS = {
    0: (False, "Bus I2C sehat (pull-up ada) tapi MPU tidak menjawab — "
               "SDA & SCL kemungkinan TERTUKAR, atau chip MPU rusak"),
    1: (True,  ""),
    2: (False, "MPU terdeteksi di 0x69, bukan 0x68 — pin AD0 modul ke-HIGH. "
               "Sambungkan AD0 ke GND"),
    3: (True,  "Gyro belum terkalibrasi — yaw akan merayap. Diamkan robot "
               "sebentar, firmware mengkalibrasi sendiri"),
    4: (False, "MPU meng-ACK tapi data tidak keluar — kabel I2C goyang, "
               "terlalu panjang, atau catu 3.3V drop"),
    5: (False, "SDA & SCL diam di LOW (tanpa pull-up) — modul MPU tidak "
               "bertenaga: cek 3.3V, GND, dan solderan kabel SDA/SCL"),
}
MPU_STATUS_UNKNOWN = (False, "Status MPU tidak dikenali")


# =====================================================================
# PROTOKOL SINYAL KENDALI
# Acuan: "Dokumen Spesifikasi Teknis — Robot Akuatik untuk Tambak Ikan",
#        bab SKEMA KOMUNIKASI. Skema mengikuti DJI Tello SDK 2.0.
# =====================================================================
#
#   Pengendali Utama -> Body Robot : "[Moves]:[Dist]"   mis. "FW:100"
#   Body Robot -> Pengendali Utama : "ON [Moves]"       tiap 1 detik selama gerak
#                                    "FIN [Moves]:[Dist]" saat gerakan selesai
#
#   Bila "ON [Moves]" tidak diterima dalam 1 detik, Pengendali Utama
#   menganggap perintah GAGAL dan mengirim ulang perintah tersebut.
#
# Daftar perintah (tabel pada dokumen spesifikasi):
#   FW    10-200  maju lurus ke depan          (satuan sentimeter)
#   CW     1-180  putar searah jarum jam       (ke kanan, satuan derajat)
#   CCW    1-180  putar berlawanan jarum jam   (ke kiri,  satuan derajat)
#   STOP       0  hentikan motor (berhenti darurat)

MOVE_FW   = "FW"
MOVE_CW   = "CW"
MOVE_CCW  = "CCW"
MOVE_STOP = "STOP"

# Rentang [Dist] yang sah per perintah -> (min, maks, satuan)
MOVE_RANGE = {
    MOVE_FW:   (10, 200, "cm"),
    MOVE_CW:   (1, 180, "derajat"),
    MOVE_CCW:  (1, 180, "derajat"),
    MOVE_STOP: (0, 0, ""),
}

MOVE_LABEL = {
    MOVE_FW:   "Maju",
    MOVE_CW:   "Putar kanan",
    MOVE_CCW:  "Putar kiri",
    MOVE_STOP: "Berhenti",
}

# --- Satuan pada ANTARMUKA (bukan pada protokol) ---
# Operator berpikir dalam METER saat memerintah "maju", sementara paket FW pada
# protokol tetap sentimeter 10-200 cm. Jarak dalam meter dipecah otomatis oleh
# split_forward() menjadi beberapa paket FW yang sah.
MANUAL_FW_MIN_M = 0.1     # < 10 cm tidak bisa diperintahkan (batas bawah FW)
MANUAL_FW_MAX_M = 50.0    # batas wajar sekali tekan (= 25 paket FW:200)
MANUAL_FW_STEP_M = 0.5    # loncatan tombol -/+ pada kartu MANUAL

MPU_LOG_INTERVAL_S = 1.0  # jarak antar-catatan saat log MPU dinyalakan

ON_TIMEOUT_S   = 1.0    # batas tunggu "ON [Moves]" sebelum perintah dikirim ulang
CMD_MAX_RETRY  = 5      # jumlah percobaan kirim ulang sebelum menyerah
FIN_MARGIN_S   = 6.0    # toleransi tambahan saat menunggu "FIN [Moves]:[Dist]"
TURN_RATE_DPS  = 60.0   # perkiraan laju putar robot (derajat/detik) utk estimasi durasi
RX_POLL_S      = 0.05   # jendela dengar sekali pump (s)

_ON_RE  = re.compile(r"^ON\s+([A-Z]+)")
_FIN_RE = re.compile(r"^FIN\s+([A-Z]+)\s*:\s*(-?\d+)")


# =====================================================================
# Util konversi PWM -> throttle/RPM/speed
# =====================================================================

def throttle_fraction(pwm_us: int) -> float:
    """0.0 (1000us) .. 1.0 (2000us)."""
    frac = (pwm_us - STOP_PWM) / (FULL_PWM - STOP_PWM)
    return max(0.0, min(1.0, frac))


def estimate_rpm(pwm_us: int, motor_kv: float = MOTOR_KV,
                 battery_v: float = BATTERY_V) -> float:
    """Estimasi RPM (kasar, linear terhadap throttle)."""
    return throttle_fraction(pwm_us) * motor_kv * battery_v


def estimate_speed_mps(pwm_us: int) -> float:
    """Estimasi kecepatan 1 sisi baling-baling (m/s), diacu ke CRUISE_PWM."""
    ref = throttle_fraction(CRUISE_PWM)
    if ref <= 0:
        return 0.0
    return ROBOT_SPEED_MPS * (throttle_fraction(pwm_us) / ref)


def pwm_for_move(move: str) -> tuple[int, int]:
    """
    PWM (kiri, kanan) yang SEHARUSNYA dijalankan robot untuk sebuah perintah.

    Dipakai GUI untuk menggerakkan gauge RPM/kecepatan selama perintah berjalan.
    ESC unidirectional -> putar = differential thrust (satu motor stop).
        CW  (kanan) : motor kiri maju,  motor kanan stop
        CCW (kiri)  : motor kiri stop,  motor kanan maju
    """
    if move == MOVE_FW:
        return CRUISE_PWM, CRUISE_PWM
    if move == MOVE_CW:
        return CRUISE_PWM, STOP_PWM
    if move == MOVE_CCW:
        return STOP_PWM, CRUISE_PWM
    return STOP_PWM, STOP_PWM


# =====================================================================
# 0. PERINTAH ROBOT  —  satu paket Sinyal Kendali "[Moves]:[Dist]"
# =====================================================================

@dataclass
class RobotCommand:
    """Satu perintah kendali sesuai dokumen spesifikasi teknis."""
    move: str
    dist: int = 0

    def encode(self) -> bytes:
        return f"{self.move}:{self.dist}".encode()

    def human(self) -> str:
        if self.move == MOVE_STOP:
            return "Berhenti"
        unit = MOVE_RANGE.get(self.move, (0, 0, ""))[2]
        return f"{MOVE_LABEL.get(self.move, self.move)} {self.dist} {unit}".strip()

    def validate(self) -> tuple[bool, str]:
        """Cek [Dist] terhadap rentang pada tabel perintah."""
        if self.move not in MOVE_RANGE:
            return False, f"Perintah '{self.move}' tidak dikenal"
        lo, hi, unit = MOVE_RANGE[self.move]
        if not (lo <= self.dist <= hi):
            return False, (f"{self.move} hanya menerima {lo}-{hi} {unit} "
                           f"(diberi {self.dist})")
        return True, "OK"

    def expected_duration_s(self, speed_mps: float = ROBOT_SPEED_MPS) -> float:
        """Perkiraan lama eksekusi — dipakai sebagai batas tunggu sinyal FIN."""
        spd = speed_mps if speed_mps and speed_mps > 0 else ROBOT_SPEED_MPS
        if self.move == MOVE_FW:
            return (self.dist / 100.0) / spd
        if self.move in (MOVE_CW, MOVE_CCW):
            return self.dist / TURN_RATE_DPS
        return 0.0


def stop_command() -> RobotCommand:
    """Perintah berhenti darurat (STOP:0)."""
    return RobotCommand(MOVE_STOP, 0)


def split_forward(meters: float) -> list[RobotCommand]:
    """
    Pecah jarak lurus (meter) menjadi beberapa perintah FW yang MASUK rentang
    10-200 cm. Pembagian dibuat RATA supaya tidak menyisakan potongan kecil
    yang di bawah batas minimum (mis. 10.05 m -> 6 x 167 cm, bukan 5x200 + 5cm).
    Sisa < 10 cm diabaikan karena tidak bisa diperintahkan.
    """
    cm_total = meters * 100.0
    lo, hi, _ = MOVE_RANGE[MOVE_FW]
    if cm_total < lo:
        return []
    n = max(1, int(math.ceil(cm_total / hi)))
    chunk = int(round(cm_total / n))
    chunk = max(lo, min(hi, chunk))
    return [RobotCommand(MOVE_FW, chunk) for _ in range(n)]


def turn_command(degrees: float, direction: str) -> RobotCommand | None:
    """
    Perintah putar. direction "R" (kanan) -> CW, "L" (kiri) -> CCW.
    Sudut dibulatkan & dijepit ke rentang 1-180 derajat; 0 derajat -> None.
    """
    move = MOVE_CW if direction.upper().startswith("R") else MOVE_CCW
    lo, hi, _ = MOVE_RANGE[move]
    deg = int(round(abs(degrees)))
    if deg < lo:
        return None
    return RobotCommand(move, min(deg, hi))


# =====================================================================
# 1. RADIO LINK  (real pyrf24  ->  fallback MockRadio)
# =====================================================================

class RadioLink:
    """
    Abstraksi koneksi NRF24. Meniru perilaku receiverArduino.py:
        - open_tx_pipe, PA_LOW, 250KBPS, channel 0x76
        - radio.write() return True  => paket + AUTO-ACK diterima => ROBOT HIDUP

    Dua mode, dan operator bisa BERPINDAH kapan saja lewat set_mode():
        SIMULASI -> MockRadio (robot tiruan); dipakai sebagai DEFAULT aplikasi
                    supaya demo & pengembangan aman tanpa hardware.
        REAL     -> modul NRF24 sungguhan lewat pyrf24.
    Bila mode REAL diminta tapi pyrf24/NRF tidak ada, koneksi otomatis kembali
    ke SIMULASI dan set_mode() melaporkan kegagalannya (bukan diam-diam).
    """

    def __init__(self, address: bytes = b"00001",
                 ce_pin: int = 24, csn_pin: int = 0):
        self.address = address
        self.ce_pin = ce_pin
        self.csn_pin = csn_pin

        self._lock = threading.Lock()
        self._radio = None
        self.simulation = False        # True bila memakai MockRadio
        self.module_present = False     # modul NRF terdeteksi (begin OK)
        self.last_ack_ms: float = 0.0   # millis() terakhir robot meng-ACK
        self.tx_enabled = True          # gate: boleh mengirim atau tidak
        self.last_error = ""            # alasan gagal masuk mode REAL

        # telemetri balik (roll, pitch, yaw) hasil poll terakhir
        self.telemetry_addr = TELEMETRY_ADDR
        self._telemetry: tuple[float, float, float] | None = None
        self._telemetry_ts: float = 0.0
        # Kode status MPU pada paket terakhir. Default 1 (sehat) supaya
        # firmware lama yang belum mengirim ";S=" tidak memicu alarm palsu.
        self._telemetry_status: int = 1

        # --- Sinyal balik protokol kendali: "ON [Moves]" & "FIN [Moves]:[Dist]" ---
        self._last_on: tuple[str, float] | None = None      # (move, waktu terima)
        # Antrean FIN belum diambil, berikut WAKTU TERIMA-nya. Cap waktu itu
        # wajib: robot mengulang FIN beberapa kali supaya tidak hilang, jadi
        # FIN basi milik perintah sebelumnya harus bisa dibuang — kalau tidak,
        # dua perintah sejenis berturut-turut (mis. FW:200 lalu FW:200) bisa
        # membuat perintah kedua langsung dianggap selesai.
        self._fin_inbox: list[tuple[str, int, float]] = []
        self._rx_lock = threading.Lock()

    # ---- lifecycle -------------------------------------------------

    def begin(self, force_sim: bool = False) -> bool:
        """
        Inisialisasi radio. Return True bila modul (real/mock) siap.

        force_sim=True  -> langsung MockRadio, pyrf24 tidak disentuh sama sekali.
        force_sim=False -> coba NRF sungguhan, jatuh ke MockRadio bila gagal.
        """
        if force_sim:
            self._use_mock()
            return True
        try:
            from pyrf24 import RF24, RF24_PA_LOW, RF24_250KBPS  # type: ignore

            radio = RF24(self.ce_pin, self.csn_pin)
            if not radio.begin():
                raise RuntimeError("radio.begin() gagal — cek wiring NRF")

            radio.open_tx_pipe(self.address)
            radio.open_rx_pipe(1, self.telemetry_addr)  # pipe telemetri balik (Robot->Pi)
            radio.setPALevel(RF24_PA_LOW)
            radio.setDataRate(RF24_250KBPS)
            radio.setChannel(0x76)
            radio.stopListening()   # default mode TX (kirim perintah/PING)

            self._radio = radio
            self.simulation = False
            self.module_present = True
            self.last_error = ""
            return True

        except Exception as e:
            # pyrf24 tidak ada / NRF tidak terdeteksi -> mode simulasi
            self.last_error = str(e) or e.__class__.__name__
            self._use_mock()
            return True

    def _use_mock(self) -> None:
        """Pasang robot tiruan sebagai lawan bicara (mode SIMULASI)."""
        self._radio = MockRadio()
        self.simulation = True
        self.module_present = True       # modul "virtual" dianggap ada

    def set_mode(self, simulation: bool) -> tuple[bool, str]:
        """
        Pindah mode REAL <-> SIMULASI selagi aplikasi berjalan (tombol MODE di
        bilah atas GUI). Radio lama dilepas, sisa sinyal ON/FIN & telemetri
        dibersihkan supaya tidak tercampur antar-mode.

        Return (berhasil sesuai permintaan?, pesan untuk log/dialog).
        """
        with self._lock:
            old, self._radio = self._radio, None
            try:
                if old is not None and hasattr(old, "powerDown"):
                    old.powerDown()
            except Exception:
                pass

        self.clear_rx_state()
        self._telemetry = None
        self._telemetry_ts = 0.0
        self._telemetry_status = 1
        self.last_ack_ms = 0.0
        self.last_error = ""

        self.begin(force_sim=simulation)

        if simulation:
            return True, "Mode SIMULASI aktif — lawan bicara robot virtual"
        if self.simulation:
            why = f" ({self.last_error})" if self.last_error else ""
            return False, ("Mode REAL gagal: pyrf24/modul NRF tidak tersedia"
                           f"{why} — kembali ke SIMULASI")
        return True, "Mode REAL aktif — perintah dikirim ke NRF24 sungguhan"

    # ---- kirim -----------------------------------------------------

    def send(self, payload: bytes) -> bool:
        """
        Kirim 1 paket. Return True bila robot meng-ACK (robot terjangkau).
        Menghormati gate tx_enabled (untuk fitur 'matikan NRF' di GUI).
        """
        if not self.tx_enabled or self._radio is None:
            return False
        with self._lock:
            ok = bool(self._radio.write(payload))
        if ok:
            self.last_ack_ms = time.monotonic() * 1000.0
        return ok

    def send_retry(self, payload: bytes, tries: int = 5,
                   gap_s: float = 0.05) -> bool:
        """Kirim beberapa kali (atasi paket drop). True bila minimal 1 ACK."""
        ok = False
        for _ in range(tries):
            if self.send(payload):
                ok = True
            time.sleep(gap_s)
        return ok

    # ---- perintah kendali ------------------------------------------

    def send_command(self, cmd: "RobotCommand") -> bool:
        """Kirim 1 paket Sinyal Kendali '[Moves]:[Dist]'. True bila di-ACK."""
        return self.send(cmd.encode())

    # ---- RX pump (komunikasi 2 arah, gantian TX/RX) ----------------

    def pump(self, poll_s: float = RX_POLL_S) -> int:
        """
        Buka jendela dengar selama poll_s, baca SEMUA paket yang masuk, lalu
        kembali ke mode TX. Setiap paket dirutekan menurut awalannya:

            "ON [Moves]"          -> tanda robot sedang menjalankan perintah
            "FIN [Moves]:[Dist]"  -> tanda perintah selesai dieksekusi
            "R=..;P=..;Y=.."      -> telemetri MPU (fitur tambahan, di luar spek)

        Return jumlah paket yang berhasil diproses. Kegagalan RX tidak fatal
        (mis. API radio berbeda) — cukup dianggap 'tidak ada paket'.
        """
        if self._radio is None:
            return 0
        packets: list[bytes] = []
        with self._lock:
            try:
                self._radio.startListening()
                deadline = time.monotonic() + poll_s
                while time.monotonic() < deadline:
                    if self._radio.available():
                        packets.append(bytes(self._radio.read(32)))
                    else:
                        time.sleep(0.002)
            except Exception:
                pass
            finally:
                try:
                    self._radio.stopListening()
                except Exception:
                    pass

        n = 0
        for raw in packets:
            if self._route_packet(raw):
                n += 1
        return n

    def _route_packet(self, raw: bytes) -> bool:
        try:
            text = raw.split(b"\x00", 1)[0].decode("ascii", "ignore").strip()
        except Exception:
            return False
        if not text:
            return False

        # Paket apa pun dari robot membuktikan link hidup.
        self.last_ack_ms = time.monotonic() * 1000.0

        m = _FIN_RE.match(text)
        if m:
            with self._rx_lock:
                self._fin_inbox.append((m.group(1), int(m.group(2)),
                                        time.monotonic()))
            return True

        m = _ON_RE.match(text)
        if m:
            with self._rx_lock:
                self._last_on = (m.group(1), time.monotonic())
            return True

        m = _TEL_RE.search(text)
        if m:
            self._telemetry = (float(m.group(1)), float(m.group(2)),
                               float(m.group(3)))
            # None = firmware lama tanpa bidang S -> anggap sehat (kode 1)
            self._telemetry_status = int(m.group(4)) if m.group(4) else 1
            self._telemetry_ts = time.monotonic()
            return True
        return False

    def ping(self, poll_s: float = TELEMETRY_POLL_S) -> bool:
        """
        Satu siklus heartbeat half-duplex: kirim PING (jaga failsafe robot)
        lalu dengar sebentar untuk menangkap sinyal balik robot.
        Return True bila robot meng-ACK PING.
        """
        ok = self.send(b"PING")
        self.pump(poll_s)
        return ok

    # kompatibilitas nama lama (dipakai versi GUI sebelumnya)
    ping_and_poll_telemetry = ping

    # ---- akses sinyal balik ----------------------------------------

    def last_on(self) -> tuple[str, float] | None:
        """('FW', waktu_monotonic) dari sinyal 'ON [Moves]' terakhir."""
        with self._rx_lock:
            return self._last_on

    def saw_on(self, move: str, since: float) -> bool:
        """True bila 'ON <move>' diterima setelah waktu `since`."""
        with self._rx_lock:
            last = self._last_on
        return bool(last and last[0] == move and last[1] >= since)

    def take_fin(self) -> tuple[str, int, float] | None:
        """
        Ambil (dan buang) satu sinyal 'FIN [Moves]:[Dist]' dari antrean,
        beserta waktu terimanya. Pemanggil WAJIB memeriksa waktu itu terhadap
        saat perintahnya dikirim — robot mengulang FIN, jadi antrean bisa
        berisi kiriman ulang milik perintah sebelumnya.
        """
        with self._rx_lock:
            if self._fin_inbox:
                return self._fin_inbox.pop(0)
        return None

    def clear_rx_state(self) -> None:
        """Bersihkan sisa ON/FIN lama sebelum memulai perintah baru."""
        with self._rx_lock:
            self._last_on = None
            self._fin_inbox.clear()

    def get_telemetry(self) -> tuple[float, float, float] | None:
        """(roll, pitch, yaw) terbaru bila belum basi, else None."""
        if self._telemetry is None:
            return None
        if (time.monotonic() - self._telemetry_ts) > TELEMETRY_STALE_S:
            return None
        return self._telemetry

    def telemetry_status(self) -> int:
        """Kode status MPU pada paket terakhir (lihat MPU_STATUS)."""
        return self._telemetry_status

    def telemetry_is_valid(self) -> bool:
        """
        False bila firmware melaporkan sudutnya tidak bisa dipercaya — mis.
        MPU tidak menjawab I2C, sehingga angka yang terkirim hanya nilai beku.
        """
        return MPU_STATUS.get(self._telemetry_status, MPU_STATUS_UNKNOWN)[0]

    def telemetry_problem(self) -> str:
        """Penjelasan masalah MPU untuk operator; "" bila tidak ada masalah."""
        return MPU_STATUS.get(self._telemetry_status, MPU_STATUS_UNKNOWN)[1]

    def get_telemetry_stamped(self) -> tuple[tuple[float, float, float], float] | None:
        """
        Seperti get_telemetry(), tapi disertai WAKTU TERIMA paketnya. Dipakai
        MPUMonitor untuk membedakan data baru dari data lama yang masih
        tersimpan — supaya log tidak berisi baris kembar.
        """
        tel = self.get_telemetry()
        return None if tel is None else (tel, self._telemetry_ts)

    # ---- status ----------------------------------------------------

    def robot_reachable(self, timeout_ms: float = SIGNAL_TIMEOUT_MS) -> bool:
        """True bila ada ACK dalam timeout_ms terakhir."""
        if self.last_ack_ms == 0.0:
            return False
        return (time.monotonic() * 1000.0 - self.last_ack_ms) < timeout_ms

    # ---- kontrol simulasi (dipakai GUI untuk demo tanpa HW) --------

    def set_sim_robot_reachable(self, reachable: bool) -> None:
        if isinstance(self._radio, MockRadio):
            self._radio.robot_online = reachable


class MockRadio:
    """
    Radio tiruan untuk mode SIMULASI — sekaligus TIRUAN BODY ROBOT.

    Ia meniru perilaku firmware sesuai dokumen spesifikasi teknis:
        - menerima "[Moves]:[Dist]",
        - membalas "ON [Moves]" tiap 1 detik selama gerakan berlangsung,
        - membalas "FIN [Moves]:[Dist]" saat gerakan selesai,
        - "STOP:0" menghentikan gerakan seketika,
    ditambah telemetri MPU buatan saat sedang menganggur. Dengan begini
    seluruh alur Request-Response bisa diuji & didemokan tanpa hardware.
    """

    def __init__(self):
        self.robot_online = True
        self._listening = False
        self._t0 = time.monotonic()

        self._outbox: list[bytes] = []       # paket menunggu dibaca Pi
        self._move: str | None = None        # perintah yang sedang dijalankan
        self._dist = 0
        self._finish_at = 0.0                # kapan gerakan selesai
        self._next_on = 0.0                  # jadwal kirim "ON [Moves]"
        self._next_tel = 0.0                 # jadwal kirim telemetri MPU

    # --- sisi TX (Pi -> robot tiruan) ---

    def write(self, payload: bytes, *args, **kwargs) -> bool:
        if not self.robot_online:
            return False
        try:
            text = bytes(payload).split(b"\x00", 1)[0].decode("ascii", "ignore").strip()
        except Exception:
            return True

        if text.startswith("PING"):
            return True

        if ":" in text:
            move, _, dist_s = text.partition(":")
            move = move.strip().upper()
            try:
                dist = int(float(dist_s.strip()))
            except ValueError:
                return True

            if move == MOVE_STOP:
                self._move = None
                self._outbox.append(b"FIN STOP:0")
                return True

            if self._move is not None:
                return True          # sedang sibuk -> perintah baru diabaikan

            dur = RobotCommand(move, dist).expected_duration_s()
            now = time.monotonic()
            self._move, self._dist = move, dist
            self._finish_at = now + max(dur, 0.3)
            self._next_on = now      # "ON" pertama dikirim segera
        return True

    # --- sisi RX (robot tiruan -> Pi) ---

    def _tick(self) -> None:
        now = time.monotonic()
        if self._move is not None:
            if now >= self._finish_at:
                self._outbox.append(f"FIN {self._move}:{self._dist}".encode())
                self._move = None
            elif now >= self._next_on:
                self._next_on = now + 1.0
                self._outbox.append(f"ON {self._move}".encode())

        # Telemetri MPU tetap dikirim SAAT BERGERAK, bukan cuma saat menganggur
        # — persis firmware Finalnew.ino yang menyelipkannya tiap 200 ms di sela
        # paket masuk. Kalau tidak begitu, panel sensor mode SIMULASI akan mati
        # justru ketika heading paling perlu dipantau.
        if now >= self._next_tel:
            self._next_tel = now + 0.2
            t = now - self._t0
            roll = 2.0 * math.sin(t * 1.1)
            pitch = 1.5 * math.cos(t * 0.9)
            yaw = 40.0 * math.sin(t * 0.5)      # heading berayun -40..40
            self._outbox.append(f"R={roll:.1f};P={pitch:.1f};Y={yaw:.1f}".encode())

    def startListening(self) -> None:
        self._listening = True

    def stopListening(self) -> None:
        self._listening = False

    def available(self) -> bool:
        if not (self._listening and self.robot_online):
            return False
        self._tick()
        return bool(self._outbox)

    def read(self, length: int = 32) -> bytes:
        if self._outbox:
            return self._outbox.pop(0)
        return b""



# =====================================================================
# 2b. PATH PLANNER  —  terjemahkan tambak persegi -> daftar segmen
#     "maju x meter / belok y derajat" (pola boustrophedon/zigzag)
# =====================================================================
#
# Ini mewujudkan arahan: aplikasi memasukkan dimensi tambak + titik awal +
# lebar lintasan + speed, lalu menerjemahkannya menjadi PATH eksplisit yang
# harus diikuti robot. Hasilnya dipakai untuk:
#     - visualisasi jalur di GUI (kanvas),
#     - daftar langkah "Maju .. m / Belok .. derajat",
#     - encode paket misi yang dikirim ke robot (encode_mission).

# Titik awal (sudut tambak) -> label untuk GUI.
CORNER_LABEL = {
    "BL": "Kiri-Bawah", "BR": "Kanan-Bawah",
    "TL": "Kiri-Atas", "TR": "Kanan-Atas",
}


@dataclass
class PathStep:
    """Satu langkah path: maju sekian meter, atau belok sekian derajat."""
    kind: str                 # "forward" | "turn"
    meters: float = 0.0
    degrees: float = 0.0
    direction: str = ""       # "R" (kanan) | "L" (kiri) untuk turn

    def human(self) -> str:
        if self.kind == "forward":
            return f"Maju {self.meters:.1f} m"
        arah = "kanan" if self.direction == "R" else "kiri"
        return f"Belok {arah} {self.degrees:.0f} derajat"


@dataclass
class CoveragePlan:
    panjang_m: float
    lebar_m: float
    lane_width_m: float
    speed_mps: float
    start_corner: str
    first_turn: str           # arah belok pertama "R"/"L" (dikirim ke robot)
    n_lanes: int
    steps: list               # list[PathStep]
    waypoints: list           # list[(x, y)] meter, utk kanvas
    total_distance_m: float
    est_time_s: float
    lane_spacing_m: float = 0.0   # jarak antar-sumbu jalur (<= lane_width_m)


def plan_coverage(panjang_m: float, lebar_m: float,
                  lane_width_m: float = LANE_WIDTH_M,
                  speed_mps: float = ROBOT_SPEED_MPS,
                  start_corner: str = "BL") -> CoveragePlan:
    """
    Bangun jalur sapuan zigzag (boustrophedon) untuk tambak persegi.

    Koordinat: x menyusuri LEBAR (0..lebar), y menyusuri PANJANG (0..panjang).
    Robot menjelajah lurus arah-y tiap lintasan, lalu U-turn menggeser sejauh
    satu spasi jalur arah-x. Arah belok U-turn BERSELANG-SELING (kanan-kanan
    lalu kiri-kiri, dst) supaya benar-benar menyapu seluruh lebar — bukan
    bolak-balik di kolom yang sama.

    GEOMETRI JALUR — jalur pertama & terakhir MENEMPEL di tepi tambak.
    Lebar dibagi menjadi n_bands = ceil(lebar / lebar_lintasan) pita, lalu
    jalur ditaruh di setiap GARIS PEMBATAS pita — termasuk kedua tepi tambak.
    Jadi jumlah jalur = n_bands + 1, dengan spasi = lebar / n_bands (selalu
    <= lebar lintasan yang diminta).

        lebar 2 m, lintasan 1 m  ->  n_bands = 2, 3 jalur di x = 0, 1, 2

    Konsekuensinya: robot melintas tepat di sisi dinding tambak, dan sapuan
    jalur tepi separuhnya jatuh di luar tambak. Ini pilihan yang DISENGAJA
    supaya jalur pada preview benar-benar mencapai ujung kotak di kedua sisi.
    """
    if start_corner not in CORNER_LABEL:
        start_corner = "BL"
    lw = lane_width_m if (lane_width_m and lane_width_m > 0) else LANE_WIDTH_M
    spd = speed_mps if (speed_mps and speed_mps > 0) else ROBOT_SPEED_MPS

    if panjang_m <= 0 or lebar_m <= 0:
        return CoveragePlan(panjang_m, lebar_m, lw, spd, start_corner,
                            "R", 0, [], [], 0.0, 0.0)

    # Pita sapuan dulu, baru jalurnya. Jalur ditaruh di SETIAP garis pembatas
    # pita — termasuk x=0 dan x=lebar — sehingga jumlahnya n_bands + 1 dan
    # jalur pertama & terakhir menempel di tepi tambak.
    n_bands = max(1, int(math.ceil(lebar_m / lw)))
    n_lanes = n_bands + 1
    spacing = lebar_m / n_bands               # selalu <= lebar lintasan

    x_left = start_corner in ("BL", "TL")     # mulai di sisi kiri (x=0)?
    bottom = start_corner in ("BL", "BR")     # mulai di sisi bawah (y=0)?
    x0 = 0.0 if x_left else lebar_m
    y0 = 0.0 if bottom else panjang_m
    step = spacing if x_left else -spacing    # arah geser antar-lintasan

    # ---- bangun waypoints (titik belok) ----
    pts = [(x0, y0)]
    cur = (x0, y0)
    for k in range(n_lanes):
        other_y = panjang_m if cur[1] == 0.0 else 0.0     # ujung seberang
        cur = (cur[0], other_y)
        pts.append(cur)
        if k < n_lanes - 1:
            # geser satu spasi, jaga tetap di dalam tambak
            nx = min(max(cur[0] + step, 0.0), lebar_m)
            cur = (nx, cur[1])
            pts.append(cur)

    # ---- turunkan langkah maju/belok dari waypoints ----
    steps: list[PathStep] = []
    prev_h = None
    total = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        vx, vy = b[0] - a[0], b[1] - a[1]
        dist = math.hypot(vx, vy)
        if dist < 1e-9:
            continue
        if prev_h is not None:
            cross = prev_h[0] * vy - prev_h[1] * vx   # z cross product
            dot = prev_h[0] * vx + prev_h[1] * vy
            ang = math.degrees(math.atan2(abs(cross), dot))
            if ang > 1e-6:
                direction = "R" if cross < 0 else "L"   # searah jarum jam = kanan
                steps.append(PathStep("turn", degrees=round(ang), direction=direction))
        steps.append(PathStep("forward", meters=dist))
        total += dist
        prev_h = (vx, vy)

    # arah belok pertama = arah U-turn pertama
    first_turn = next((s.direction for s in steps if s.kind == "turn"), "R")

    # Estimasi waktu diturunkan dari ANTREAN PERINTAH yang akan benar-benar
    # dikirim (FW/CW/CCW), bukan dari timeline internal firmware.
    est_s = queue_duration_s(_steps_to_commands(steps), spd)
    return CoveragePlan(panjang_m, lebar_m, lw, spd, start_corner, first_turn,
                        n_lanes, steps, pts, total, round(est_s, 1),
                        lane_spacing_m=spacing)


def _steps_to_commands(steps: list) -> list[RobotCommand]:
    """PathStep (maju meter / belok derajat) -> perintah kendali FW/CW/CCW."""
    cmds: list[RobotCommand] = []
    for st in steps:
        if st.kind == "forward":
            cmds.extend(split_forward(st.meters))
        else:
            c = turn_command(st.degrees, st.direction)
            if c is not None:
                cmds.append(c)
    return cmds


def plan_command_queue(plan: CoveragePlan) -> list[RobotCommand]:
    """
    Terjemahkan rencana sapuan menjadi ANTREAN PERINTAH KENDALI (FW/CW/CCW)
    sesuai tabel perintah pada dokumen spesifikasi teknis.

    Perbedaan penting dengan versi sebelumnya: seluruh pola zigzag kini disusun
    dan dikemudikan oleh PENGENDALI UTAMA (Raspberry Pi), bukan lagi ditanam di
    firmware. Robot hanya mengeksekusi satu perintah gerak dalam satu waktu dan
    melapor lewat "ON [Moves]" / "FIN [Moves]:[Dist]".

    Karena FW dibatasi 10-200 cm, lintasan panjang otomatis dipecah menjadi
    beberapa perintah FW yang berurutan.
    """
    return _steps_to_commands(plan.steps)


def queue_duration_s(cmds: list[RobotCommand],
                     speed_mps: float = ROBOT_SPEED_MPS) -> float:
    """Perkiraan total waktu eksekusi sebuah antrean perintah (detik)."""
    return sum(c.expected_duration_s(speed_mps) for c in cmds)


# =====================================================================
# 2c. COMMAND RUNNER  —  pelaksana pola Request-Response
# =====================================================================
#
# Alur untuk SATU perintah (persis seperti diagram pada dokumen spesifikasi):
#
#   1. Pi mengirim "[Moves]:[Dist]".
#   2. Pi menunggu "ON [Moves]" maksimal 1 detik.
#      -> tidak datang: perintah dianggap GAGAL, dikirim ULANG (maks 5x).
#   3. Robot terus mengirim "ON [Moves]" tiap 1 detik selama bergerak.
#   4. Robot mengirim "FIN [Moves]:[Dist]" -> perintah selesai, lanjut ke
#      perintah berikutnya dalam antrean.
#
# Selama menunggu, Pi tetap menyelipkan PING agar failsafe robot (stop bila
# tak ada sinyal 3 detik) tidak ikut terpicu.


class RunStatus(Enum):
    IDLE     = "SIAP"
    SENDING  = "MENGIRIM PERINTAH"
    RUNNING  = "ROBOT BERGERAK"
    RETRYING = "KIRIM ULANG"
    DONE     = "SELESAI"
    ABORTED  = "DIBATALKAN"
    FAILED   = "GAGAL"


@dataclass
class RunnerState:
    status: RunStatus = RunStatus.IDLE
    index: int = 0                       # perintah ke-berapa (1-based)
    total: int = 0
    command: Optional[RobotCommand] = None
    attempt: int = 0
    label: str = ""                      # nama sesi, mis. "MISI" / "MANUAL"
    cmd_started: float = 0.0             # time.monotonic() saat perintah dikirim
    cmd_expected_s: float = 0.0
    message: str = ""

    @property
    def running(self) -> bool:
        return self.status in (RunStatus.SENDING, RunStatus.RUNNING,
                               RunStatus.RETRYING)

    @property
    def queue_progress(self) -> float:
        if self.total <= 0:
            return 0.0
        done = max(0, self.index - 1)
        frac = 0.0
        if self.cmd_expected_s > 0 and self.status == RunStatus.RUNNING:
            frac = min(1.0, (time.monotonic() - self.cmd_started) / self.cmd_expected_s)
        if self.status in (RunStatus.DONE,):
            return 1.0
        return max(0.0, min(1.0, (done + frac) / self.total))

    def pwm(self) -> tuple[int, int]:
        """PWM (kiri, kanan) yang diperkirakan sedang dijalankan robot."""
        if self.status == RunStatus.RUNNING and self.command is not None:
            return pwm_for_move(self.command.move)
        return STOP_PWM, STOP_PWM


class CommandRunner:
    """
    Menjalankan antrean RobotCommand di thread terpisah dengan pola
    Request-Response. Aman dipakai bersama heartbeat GUI karena semua akses
    radio melewati kunci internal RadioLink.
    """

    def __init__(self, link: RadioLink,
                 logger: Optional["ActivityLogger"] = None,
                 on_change: Optional[Callable[[RunnerState], None]] = None,
                 speed_mps: float = ROBOT_SPEED_MPS):
        self.link = link
        self.logger = logger
        self.on_change = on_change
        self.speed_mps = speed_mps

        self.state = RunnerState()
        self._thread: Optional[threading.Thread] = None
        self._abort = threading.Event()

    # ---- util ------------------------------------------------------

    def _log(self, cat: str, msg: str) -> None:
        if self.logger:
            self.logger.log(cat, msg)

    def _emit(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self.state, k, v)
        if self.on_change:
            self.on_change(self.state)

    def is_busy(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ---- API -------------------------------------------------------

    def run(self, commands: list[RobotCommand], label: str = "MISI") -> tuple[bool, str]:
        """Mulai menjalankan antrean. Return (dimulai?, pesan)."""
        if self.is_busy():
            return False, "Masih ada perintah berjalan — hentikan dulu (STOP)."
        valid = [c for c in commands if c.validate()[0]]
        if not valid:
            return False, "Tidak ada perintah yang sah untuk dikirim."

        self._abort.clear()
        self.link.clear_rx_state()
        self.state = RunnerState(status=RunStatus.SENDING, total=len(valid),
                                 label=label)
        self._thread = threading.Thread(target=self._loop, args=(valid,),
                                        daemon=True)
        self._thread.start()
        return True, f"{len(valid)} perintah dijalankan"

    def abort(self) -> bool:
        """
        Berhenti darurat: kirim STOP:0 berulang & batalkan sisa antrean.
        Dikirim langsung dari thread pemanggil supaya tidak menunggu giliran.
        """
        self._abort.set()
        ok = self.link.send_retry(stop_command().encode())
        self._emit(status=RunStatus.ABORTED, command=None,
                   message="STOP terkirim" if ok else "STOP GAGAL (cek NRF)")
        return ok

    # ---- inti ------------------------------------------------------

    def _loop(self, commands: list[RobotCommand]) -> None:
        for i, cmd in enumerate(commands, 1):
            if self._abort.is_set():
                break
            self._emit(index=i, command=cmd, attempt=0,
                       cmd_expected_s=cmd.expected_duration_s(self.speed_mps),
                       status=RunStatus.SENDING)
            if not self._run_one(cmd):
                if not self._abort.is_set():
                    self._emit(status=RunStatus.FAILED,
                               message=f"Perintah {cmd.encode().decode()} gagal")
                    self._log("GAGAL", f"Perintah {cmd.encode().decode()} tidak "
                                       "direspon robot — antrean dihentikan")
                    self.link.send_retry(stop_command().encode())
                return

        if self._abort.is_set():
            self._emit(status=RunStatus.ABORTED, command=None,
                       message="Dibatalkan operator")
            self._log("STOP", f"{self.state.label} dibatalkan operator")
        else:
            self._emit(status=RunStatus.DONE, command=None,
                       message="Seluruh perintah selesai")
            self._log(self.state.label, f"SELESAI — {len(commands)} perintah "
                                        "tereksekusi")

    def _run_one(self, cmd: RobotCommand) -> bool:
        """Kirim 1 perintah, tunggu ON (retry bila perlu), lalu tunggu FIN."""
        text = cmd.encode().decode()

        # --- fase 1: kirim & tunggu "ON [Moves]" (maks 1 detik) ---
        for attempt in range(1, CMD_MAX_RETRY + 1):
            if self._abort.is_set():
                return False
            self._emit(attempt=attempt,
                       status=RunStatus.SENDING if attempt == 1 else RunStatus.RETRYING)

            t_send = time.monotonic()
            acked = self.link.send_command(cmd)
            self._log("KIRIM", f"[{text}] percobaan {attempt}"
                               f" — {'ACK' if acked else 'TANPA ACK'}")

            deadline = t_send + ON_TIMEOUT_S
            while time.monotonic() < deadline:
                if self._abort.is_set():
                    return False
                self.link.pump(RX_POLL_S)
                if self.link.saw_on(cmd.move, since=t_send):
                    self._emit(status=RunStatus.RUNNING,
                               cmd_started=time.monotonic(),
                               message=f"{cmd.human()} sedang dijalankan")
                    self._log("GERAK", f"ON {cmd.move} diterima — {cmd.human()}")
                    break
            else:
                self._log("PERINGATAN",
                          f"Tidak ada 'ON {cmd.move}' dalam {ON_TIMEOUT_S:.0f} detik"
                          f" — perintah [{text}] dikirim ulang")
                continue
            break
        else:
            return False   # habis percobaan, robot tidak pernah merespon

        # --- fase 2: tunggu "FIN [Moves]:[Dist]" ---
        limit = cmd.expected_duration_s(self.speed_mps) * 2.0 + FIN_MARGIN_S
        deadline = time.monotonic() + limit
        next_ping = 0.0
        while time.monotonic() < deadline:
            if self._abort.is_set():
                return False
            # sisipkan PING supaya failsafe robot (3 detik tanpa sinyal) aman
            if time.monotonic() >= next_ping:
                next_ping = time.monotonic() + HEARTBEAT_INTERVAL_S
                self.link.send(b"PING")
            self.link.pump(RX_POLL_S)

            fin = self.link.take_fin()
            while fin is not None:
                # Hanya FIN yang tiba SESUDAH perintah ini dikirim yang sah.
                # Robot mengulang FIN agar tidak hilang, jadi kiriman ulang
                # milik perintah sebelumnya bisa saja masih menyusul.
                if fin[0] == cmd.move and fin[2] >= t_send:
                    self._log("SELESAI", f"FIN {fin[0]}:{fin[1]} — {cmd.human()} tuntas")
                    return True
                fin = self.link.take_fin()

        self._log("PERINGATAN",
                  f"Tidak ada 'FIN {cmd.move}' dalam {limit:.0f} detik — dianggap gagal")
        return False


# =====================================================================
# 3. ACTIVITY LOGGER  —  catat & export
# =====================================================================

LOG_DIR_NAME = "logs"      # folder auto-simpan, dibuat di samping berkas kode
LOG_HEADER = "=== LOG AKTIVITAS ROBOT FEEDER AKUATIK ==="

# Berkas log lebih tua dari ini dibuang otomatis. Raspberry Pi memakai kartu SD
# berkapasitas terbatas dan log MPU menulis ~1 baris/detik, jadi tanpa
# pembersihan folder logs/ akan menggelembung tanpa batas.
LOG_RETENTION_DAYS = 3
LOG_PURGE_INTERVAL_S = 6 * 3600     # jeda pemeriksaan ulang selagi aplikasi hidup


def default_log_dir() -> str:
    """Folder tujuan auto-simpan; dibuat bila belum ada."""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOG_DIR_NAME)
    os.makedirs(base, exist_ok=True)
    return base


def default_log_path(prefix: str = "log_feeder") -> str:
    """Nama berkas auto-simpan bercap waktu, mis. logs/log_feeder_20260810_143000.txt"""
    return os.path.join(default_log_dir(),
                        f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}.txt")


def purge_old_logs(days: int = LOG_RETENTION_DAYS,
                   directory: str | None = None,
                   keep: str | None = None) -> tuple[list[str], list[str]]:
    """
    Hapus berkas .txt di folder log yang umurnya melebihi `days` hari.

    keep = berkas yang sedang ditulis (jangan pernah dihapus, sekalipun jam
    sistem melompat). Return (nama berkas terhapus, pesan kegagalan) — pemanggil
    yang memutuskan cara melaporkannya.
    """
    base = directory or default_log_dir()
    batas = time.time() - max(0, days) * 86400.0
    terhapus: list[str] = []
    gagal: list[str] = []
    try:
        isi = os.listdir(base)
    except OSError as e:
        return terhapus, [f"folder log tak terbaca: {e}"]

    keep_abs = os.path.abspath(keep) if keep else None
    for nama in isi:
        if not nama.lower().endswith(".txt"):
            continue
        path = os.path.join(base, nama)
        if keep_abs and os.path.abspath(path) == keep_abs:
            continue
        try:
            if os.path.isfile(path) and os.path.getmtime(path) < batas:
                os.remove(path)
                terhapus.append(nama)
        except OSError as e:
            gagal.append(f"{nama}: {e}")
    return terhapus, gagal


@dataclass
class LogEvent:
    ts: str
    category: str
    message: str

    def line(self) -> str:
        return f"[{self.ts}] ({self.category}) {self.message}"


class ActivityLogger:
    """
    Catat aktivitas robot/GUI dengan timestamp.

    Tiga cara menyimpan:
        - export_csv / export_txt : simpan sekali seluruh isi log,
        - AUTO-SIMPAN (set_autosave): tiap baris langsung ditulis ke berkas TXT
          begitu terjadi, jadi catatan uji lapangan tetap utuh walau aplikasi
          ditutup paksa atau Raspberry Pi kehilangan daya.
    """

    def __init__(self, on_new: Optional[Callable[[LogEvent], None]] = None):
        self.events: list[LogEvent] = []
        self.autosave_path: str | None = None   # None = auto-simpan mati
        self.autosave_error = ""                # alasan auto-simpan berhenti
        self._on_new = on_new
        self._lock = threading.Lock()

    def log(self, category: str, message: str) -> LogEvent:
        ev = LogEvent(
            ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            category=category,
            message=message,
        )
        with self._lock:
            self.events.append(ev)
            path = self.autosave_path
        if path:
            self._append(path, ev.line() + "\n")
        if self._on_new:
            self._on_new(ev)
        return ev

    def clear(self) -> None:
        with self._lock:
            self.events.clear()

    # ---- auto-simpan TXT -------------------------------------------

    def set_autosave(self, path: str | None,
                     include_backlog: bool = True) -> tuple[bool, str]:
        """
        Nyalakan/matikan auto-simpan. path=None mematikannya.
        Berkas dibuka mode APPEND supaya berkas lama tidak tertimpa.
        Return (berhasil?, pesan untuk log).
        """
        if not path:
            self.autosave_path = None
            self.autosave_error = ""
            return True, "Auto-simpan TXT dimatikan"

        with self._lock:
            backlog = list(self.events) if include_backlog else []
        head = (f"{LOG_HEADER}\n"
                f"# sesi dimulai {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(head)
                for ev in backlog:
                    f.write(ev.line() + "\n")
        except Exception as e:
            self.autosave_path = None
            self.autosave_error = str(e)
            return False, f"Auto-simpan TXT gagal: {e}"

        self.autosave_path = path
        self.autosave_error = ""
        return True, f"Auto-simpan TXT aktif -> {path}"

    def _append(self, path: str, text: str) -> None:
        """
        Tambah satu baris ke berkas auto-simpan. Berkas dibuka-tutup tiap baris
        supaya isinya sudah tersimpan di disk walau aplikasi mati mendadak
        (laju log ~1 baris/detik, jadi biayanya tidak berarti).
        """
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            # jangan bikin log spam / bikin thread pemanggil mati — cukup
            # matikan auto-simpan dan biarkan GUI menampilkan sebabnya.
            self.autosave_path = None
            self.autosave_error = str(e)

    # ---- ekspor sekali jalan ---------------------------------------

    def export_csv(self, path: str) -> None:
        with self._lock, open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "kategori", "pesan"])
            for ev in self.events:
                w.writerow([ev.ts, ev.category, ev.message])

    def export_txt(self, path: str) -> None:
        with self._lock, open(path, "w", encoding="utf-8") as f:
            f.write(f"{LOG_HEADER}\n\n")
            for ev in self.events:
                f.write(ev.line() + "\n")


# =====================================================================
# 4. MPU MONITOR  —  sudut MPU6050 yang dikirim ROBOT lewat NRF
# =====================================================================
#
# Revisi Agustus 2026: MPU TIDAK LAGI dibaca lewat kabel USB / port serial.
# Robot menyisipkan sudutnya pada telemetri balik NRF ("R=..;P=..;Y=..") setiap
# kali Pengendali Utama mengirim PING, jadi datanya mengalir SENDIRI di latar
# belakang selama heartbeat hidup — operator tidak perlu memilih port apa pun.
#
#   Robot --(NRF, alamat 00002)--> RadioLink.pump() --> RadioLink.get_telemetry()
#                                            |
#                                       MPUMonitor.poll()  --> tampilan + log
#
# MPUMonitor hanya menambahkan dua hal di atas RadioLink: menyimpan cuplikan
# terakhir (beserta sumber & umur data) dan MENCATATNYA ke ActivityLogger bila
# tombol "Log MPU" dinyalakan operator.


@dataclass
class MPUSample:
    """Satu cuplikan sudut MPU dari telemetri robot."""
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    ts: float = 0.0          # time.monotonic() saat diterima
    source: str = "NRF"      # "NRF" (radio nyata) | "SIMULASI" (robot virtual)
    valid: bool = True       # False bila sudut tidak bisa dipercaya
    problem: str = ""        # penjelasan masalah MPU dari firmware; "" = sehat

    def human(self) -> str:
        s = (f"Roll={self.roll:.1f} Pitch={self.pitch:.1f} "
             f"Yaw={self.yaw:.1f}")
        if self.problem:
            s += f"  << {self.problem}"
        return s

    @property
    def age_s(self) -> float:
        return max(0.0, time.monotonic() - self.ts)


class MPUMonitor:
    """
    Pemantau sudut MPU dari telemetri NRF, berjalan di latar belakang.

    poll() dipanggil berkala oleh pemilik (GUI tiap ~120 ms, atau loop CLI).
    Bila log_enabled aktif, tiap MPU_LOG_INTERVAL_S detik satu baris dicatat ke
    ActivityLogger — dan ikut terbawa ke berkas auto-simpan TXT bila menyala.
    """

    def __init__(self, link: RadioLink,
                 logger: Optional["ActivityLogger"] = None,
                 interval_s: float = MPU_LOG_INTERVAL_S):
        self.link = link
        self.logger = logger
        self.interval_s = interval_s

        self.log_enabled = False
        self.latest: Optional[MPUSample] = None   # None = belum/tidak ada data
        self.samples = 0                          # jumlah cuplikan diterima
        self.logged = 0                           # jumlah baris tercatat
        self._last_log = 0.0
        self._last_ts = -1.0                      # cap waktu paket terakhir

    # ---- kendali ---------------------------------------------------

    def set_logging(self, enabled: bool) -> str:
        """Nyalakan/matikan pencatatan MPU. Return pesan untuk log."""
        self.log_enabled = bool(enabled)
        self._last_log = 0.0        # baris pertama langsung tercatat
        return ("Log MPU AKTIF — sudut dicatat tiap "
                f"{self.interval_s:g} detik" if self.log_enabled
                else "Log MPU dimatikan")

    def connected(self) -> bool:
        """True bila ada telemetri segar (belum kedaluwarsa)."""
        return self.link.get_telemetry() is not None

    # ---- inti ------------------------------------------------------

    def poll(self) -> Optional[MPUSample]:
        """
        Ambil telemetri terbaru; catat ke log bila diminta.
        Return cuplikan terbaru, atau None bila data belum ada / sudah basi.

        poll() dipanggil jauh lebih sering daripada laju telemetri, jadi paket
        yang SAMA akan terlihat berkali-kali. Hanya paket BARU yang dihitung &
        dicatat supaya log tidak berisi baris kembar.
        """
        stamped = self.link.get_telemetry_stamped()
        if stamped is None:
            self.latest = None
            return None

        (roll, pitch, yaw), ts = stamped
        sample = MPUSample(roll=roll, pitch=pitch, yaw=yaw, ts=ts,
                           source="SIMULASI" if self.link.simulation else "NRF",
                           valid=self.link.telemetry_is_valid(),
                           problem=self.link.telemetry_problem())
        self.latest = sample

        baru = ts != self._last_ts
        self._last_ts = ts
        if not baru:
            return sample
        self.samples += 1

        if self.log_enabled and self.logger is not None:
            now = time.monotonic()
            if (now - self._last_log) >= self.interval_s:
                self._last_log = now
                self.logged += 1
                self.logger.log(f"MPU-{sample.source}", sample.human())
        return sample


# =====================================================================
# SELF-TEST  —  jalankan `python feeder_core.py` untuk verifikasi logika
# =====================================================================

if __name__ == "__main__":
    print("== SELF-TEST feeder_core ==\n")

    # RadioLink — aplikasi kini MULAI di mode SIMULASI (default), dan bisa
    # dipindah ke REAL lewat set_mode() dari tombol MODE di GUI.
    link = RadioLink()
    link.begin(force_sim=True)
    print(f"Radio siap. Simulasi={link.simulation} "
          f"module_present={link.module_present}")
    assert link.simulation is True, "default aplikasi harus mode SIMULASI"

    # Telemetri 2 arah (gantian TX/RX) — di simulasi MockRadio membalas MPU
    link.ping()
    tel = link.get_telemetry()
    print(f"Poll telemetri -> {tel}")
    assert tel is not None and len(tel) == 3, "telemetri tidak ter-parse"
    print("  [OK] komunikasi 2 arah (telemetri MPU) tertangkap")

    # ---- PROTOKOL SINYAL KENDALI (dokumen spesifikasi teknis) ----
    print("\n== Protokol perintah [Moves]:[Dist] ==")
    assert RobotCommand(MOVE_FW, 100).encode() == b"FW:100"
    assert RobotCommand(MOVE_CCW, 90).encode() == b"CCW:90"
    assert stop_command().encode() == b"STOP:0"
    assert RobotCommand(MOVE_FW, 5).validate()[0] is False,  "FW<10 harus ditolak"
    assert RobotCommand(MOVE_FW, 201).validate()[0] is False, "FW>200 harus ditolak"
    assert RobotCommand(MOVE_CW, 181).validate()[0] is False, "CW>180 harus ditolak"
    assert RobotCommand(MOVE_CW, 180).validate()[0] is True
    # lintasan panjang dipecah rata & tetap dalam rentang 10-200 cm
    chunks = split_forward(10.0)
    assert [c.dist for c in chunks] == [200] * 5, [c.dist for c in chunks]
    chunks = split_forward(2.05)
    assert len(chunks) == 2 and all(10 <= c.dist <= 200 for c in chunks)
    assert split_forward(0.05) == [], "jarak < 10 cm tak bisa diperintahkan"
    assert turn_command(90, "R").move == MOVE_CW    # type: ignore
    assert turn_command(90, "L").move == MOVE_CCW   # type: ignore
    print("  [OK] encoding, validasi rentang & pemecahan FW benar")

    # PATH PLANNER — terjemahkan tambak -> segmen maju/belok
    print("\n== Path planner (tambak 10x4, lane 1m, mulai Kiri-Bawah) ==")
    plan = plan_coverage(10, 4, lane_width_m=1.0, speed_mps=0.5, start_corner="BL")
    print(f"n_lanes={plan.n_lanes}  first_turn={plan.first_turn}  "
          f"jarak={plan.total_distance_m:.1f} m  est={plan.est_time_s}s")
    for i, st in enumerate(plan.steps, 1):
        print(f"  {i:2d}. {st.human()}")

    queue = plan_command_queue(plan)
    print(f"\nAntrean perintah kendali ({len(queue)} paket), "
          f"~{queue_duration_s(queue, plan.speed_mps):.0f} s:")
    print("  " + "  ".join(c.encode().decode() for c in queue[:12]) + " ...")
    assert all(c.validate()[0] for c in queue), "ada perintah di luar rentang"
    assert queue[0].encode() == b"FW:200"
    assert any(c.move == MOVE_CW for c in queue) and any(c.move == MOVE_CCW for c in queue)

    # ---- Request-Response penuh melawan robot tiruan (MockRadio) ----
    print("\n== Uji Request-Response (robot tiruan) ==")
    log = ActivityLogger()
    runner = CommandRunner(link, logger=log, speed_mps=1.0)
    started, msg = runner.run([RobotCommand(MOVE_FW, 50),
                               RobotCommand(MOVE_CW, 90)], label="UJI")
    print(f"  mulai: {started} ({msg})")
    t_wait = time.monotonic()
    while runner.is_busy() and time.monotonic() - t_wait < 30:
        time.sleep(0.05)
    print(f"  status akhir: {runner.state.status.value} — {runner.state.message}")
    assert runner.state.status is RunStatus.DONE, "siklus ON/FIN tidak tuntas"
    assert any(e.category == "SELESAI" for e in log.events), "sinyal FIN tak tercatat"
    print("  [OK] siklus kirim -> ON -> FIN berjalan untuk seluruh antrean")

    # ---- FIN basi tidak boleh menyelesaikan perintah berikutnya ----
    # Robot mengulang FIN supaya paketnya tidak hilang. Kiriman ulang milik
    # perintah SEBELUMNYA bisa menyusul setelah perintah berikutnya dikirim;
    # kalau jenis geraknya sama (mis. FW:200 lalu FW:200), tanpa cap waktu
    # perintah kedua akan langsung dianggap tuntas padahal robot belum jalan.
    print("\n== FIN basi (kiriman ulang) tidak menipu perintah berikutnya ==")
    lk = RadioLink()
    lk.begin(force_sim=True)
    lk.clear_rx_state()
    lk._route_packet(b"FIN FW:200\x00")          # FIN lama, sebelum perintah baru
    t_perintah_baru = time.monotonic()
    stale = lk.take_fin()
    assert stale is not None and stale[0] == "FW"
    assert stale[2] < t_perintah_baru, "cap waktu FIN tidak terekam"
    time.sleep(0.01)
    lk._route_packet(b"FIN FW:200\x00")          # FIN sungguhan, sesudahnya
    fresh = lk.take_fin()
    assert fresh is not None and fresh[2] >= t_perintah_baru
    print(f"  FIN basi  ts={stale[2] - t_perintah_baru:+.3f}s -> DITOLAK")
    print(f"  FIN segar ts={fresh[2] - t_perintah_baru:+.3f}s -> diterima")
    print("  [OK] hanya FIN yang tiba sesudah perintah dikirim yang dihitung")

    # cek pola belok berselang-seling (R,R,L,L,R,R,...) untuk boustrophedon benar
    turns = [s.direction for s in plan.steps if s.kind == "turn"]
    assert turns == ["R", "R", "L", "L", "R", "R", "L", "L"], f"pola belok salah: {turns}"
    fwd = [round(s.meters, 3) for s in plan.steps if s.kind == "forward"]
    assert fwd == [10, 1, 10, 1, 10, 1, 10, 1, 10], f"jarak segmen salah: {fwd}"
    # Jalur menempel di kedua tepi, jadi titik awal Kiri-Bawah tepat di (0, 0)
    # dan jumlah jalur = ceil(lebar/lintasan) + 1.
    assert plan.lane_spacing_m == 1.0, plan.lane_spacing_m
    assert plan.n_lanes == 5, plan.n_lanes
    assert plan.waypoints[0] == (0.0, 0.0), plan.waypoints[0]
    # arah belok pertama tiap sudut
    assert plan_coverage(10, 4, start_corner="BR").first_turn == "L"
    assert plan_coverage(10, 4, start_corner="TR").first_turn == "R"
    # speed lebih cepat -> waktu lebih singkat
    assert plan_coverage(10, 4, speed_mps=1.0).est_time_s < plan.est_time_s
    print("  [OK] pola belok berselang-seling & encoding valid")

    # ---- Jalur wajib MENEMPEL di kedua tepi tambak ----
    # Bug lama: jalur pertama menempel tepi lalu digeser sejauh lane_width,
    # sehingga sisi seberang tidak pernah dijadikan jalur (tambak 2x2 m hanya
    # tersapu separuh). Sekarang jalur ada di SETIAP pembatas pita, termasuk
    # x=0 dan x=lebar.
    print("\n== Jalur menempel di kedua tepi tambak ==")
    for P, L, lw, corner in [(2, 2, 1, "BR"), (10, 4, 1, "BL"),
                             (5, 3, 1, "BL"), (4, 2, 2, "BR"), (6, 1, 1, "BL")]:
        pl = plan_coverage(P, L, lw, 0.5, corner)
        sumbu = sorted({round(x, 6) for x, _ in pl.waypoints})
        spasi = pl.lane_spacing_m
        assert len(sumbu) == pl.n_lanes, (sumbu, pl.n_lanes)
        assert spasi <= lw + 1e-9, "spasi jalur melebihi lebar lintasan"
        assert abs(sumbu[0]) < 1e-9, "jalur pertama tidak menempel tepi kiri"
        assert abs(sumbu[-1] - L) < 1e-9, "jalur terakhir tidak menempel tepi kanan"
        # tiap jalur berjarak tepat satu spasi dari tetangganya
        for a, b in zip(sumbu, sumbu[1:]):
            assert abs((b - a) - spasi) < 1e-9, (sumbu, spasi)
        print(f"  {P:g}x{L:g} m, lintasan {lw:g} m -> {pl.n_lanes} jalur, "
              f"spasi {spasi:g} m, x={sumbu} (0 s/d {L:g} m)")
    print("  [OK] jalur pertama & terakhir tepat di tepi, spasi <= lebar lintasan")

    # Estimasi PWM/RPM per jenis perintah (dasar gauge di GUI)
    print("\nEstimasi throttle per perintah:")
    for mv in (MOVE_FW, MOVE_CW, MOVE_CCW, MOVE_STOP):
        lp, rp = pwm_for_move(mv)
        print(f"  {mv:5s} -> PWM L={lp} R={rp} | "
              f"RPM L={estimate_rpm(lp):6.0f} R={estimate_rpm(rp):6.0f}")
    assert pwm_for_move(MOVE_CW) == (CRUISE_PWM, STOP_PWM)
    assert pwm_for_move(MOVE_CCW) == (STOP_PWM, CRUISE_PWM)
    assert pwm_for_move(MOVE_STOP) == (STOP_PWM, STOP_PWM)

    # ---- Perintah MAJU dalam METER (satuan antarmuka MANUAL) ----
    print("\n== Maju dalam meter -> paket FW 10-200 cm ==")
    for meters in (0.5, 1.0, 3.0, 12.5):
        cmds = split_forward(meters)
        total_cm = sum(c.dist for c in cmds)
        print(f"  {meters:5.2f} m -> {len(cmds)} paket "
              f"({'  '.join(c.encode().decode() for c in cmds[:4])}"
              f"{' ...' if len(cmds) > 4 else ''}) = {total_cm} cm")
        assert all(c.validate()[0] for c in cmds), "paket FW di luar rentang"
        assert abs(total_cm - meters * 100) <= len(cmds), "jarak total melenceng"
    assert split_forward(MANUAL_FW_MIN_M), "batas bawah manual harus bisa dikirim"
    assert len(split_forward(MANUAL_FW_MAX_M)) == 25
    print("  [OK] jarak meter dipecah rata & tetap sah")

    # ---- MPU lewat telemetri NRF (tanpa port serial) ----
    print("\n== MPU monitor (telemetri NRF, latar belakang) ==")
    log = ActivityLogger()
    mpu = MPUMonitor(link, logger=log, interval_s=0.2)
    print("  " + mpu.set_logging(True))
    for _ in range(4):
        link.ping()
        s = mpu.poll()
        time.sleep(0.25)
    assert mpu.latest is not None, "telemetri MPU tidak sampai ke monitor"
    print(f"  cuplikan terakhir: {mpu.latest.human()} "
          f"(sumber {mpu.latest.source}, umur {mpu.latest.age_s:.2f} s)")
    assert mpu.logged >= 2, "log MPU tidak berjalan"
    assert all(e.category == "MPU-SIMULASI" for e in log.events)
    mpu.set_logging(False)
    n_before = len(log.events)
    link.ping(); mpu.poll()
    assert len(log.events) == n_before, "log MPU masih menulis setelah dimatikan"
    print("  [OK] sudut MPU mengalir sendiri & toggle log berfungsi")

    # ---- ActivityLogger + AUTO-SIMPAN TXT ----
    print("\n== Auto-simpan log ke TXT ==")
    log = ActivityLogger()
    log.log("MISI", "Misi 10x4 dikirim")
    auto_path = default_log_path("selftest")
    ok, msg = log.set_autosave(auto_path)
    print("  " + msg)
    assert ok, msg
    log.log("STATUS", "Robot ACK OK")
    isi = open(auto_path, encoding="utf-8").read()
    assert "Misi 10x4 dikirim" in isi, "catatan lama tidak ikut tersimpan"
    assert "Robot ACK OK" in isi, "catatan baru tidak ikut tersimpan"
    ok, msg = log.set_autosave(None)
    log.log("STATUS", "setelah auto-simpan mati")
    assert "setelah auto-simpan mati" not in open(auto_path, encoding="utf-8").read()
    print(f"  [OK] {len(log.events)} event tercatat, berkas TXT terisi realtime")

    # ---- Pembersihan berkas log lama (jaga kartu SD Raspberry Pi) ----
    print(f"\n== Retensi log {LOG_RETENTION_DAYS} hari ==")
    lama = os.path.join(default_log_dir(), "selftest_lama.txt")
    with open(lama, "w", encoding="utf-8") as f:
        f.write("berkas uji berumur 5 hari\n")
    tua = time.time() - 5 * 86400
    os.utime(lama, (tua, tua))                       # pura-pura berumur 5 hari
    terhapus, gagal = purge_old_logs(keep=auto_path)
    print(f"  terhapus: {terhapus}  gagal: {gagal}")
    assert "selftest_lama.txt" in terhapus, "berkas 5 hari harus dibuang"
    assert os.path.exists(auto_path), "berkas hari ini TIDAK boleh ikut terhapus"
    assert not gagal, gagal
    os.remove(auto_path)
    print("  [OK] berkas > 3 hari dibuang, berkas baru & yang sedang dipakai aman")

    # ---- Pindah mode REAL <-> SIMULASI ----
    print("\n== Tombol MODE (REAL / SIMULASI) ==")
    ok, msg = link.set_mode(simulation=False)     # di PC tanpa NRF -> gagal
    print(f"  minta REAL   -> ok={ok}: {msg}")
    assert link.module_present, "harus tetap ada modul (nyata atau virtual)"
    ok, msg = link.set_mode(simulation=True)
    print(f"  minta SIMULASI -> ok={ok}: {msg}")
    assert ok and link.simulation, "gagal kembali ke SIMULASI"
    link.ping()
    assert link.get_telemetry() is not None, "radio tidak hidup setelah pindah mode"
    print("  [OK] perpindahan mode aman & radio langsung hidup lagi")

    print("\n== SELF-TEST selesai ==")
