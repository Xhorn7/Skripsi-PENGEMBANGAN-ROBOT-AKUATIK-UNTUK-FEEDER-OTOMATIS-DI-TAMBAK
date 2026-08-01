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
    2. RadioLink       -> abstraksi NRF24 (pyrf24) + AUTO-FALLBACK ke MockRadio
                          kalau dijalankan di PC tanpa pyrf24/NRF (mode SIMULASI).
                          Juga merutekan sinyal balik "ON [Moves]" & "FIN
                          [Moves]:[Dist]" serta telemetri MPU.
    3. plan_coverage / plan_command_queue
                       -> terjemahkan tambak persegi menjadi jalur sapuan, lalu
                          menjadi ANTREAN perintah FW/CW/CCW yang dikemudikan
                          Pengendali Utama.
    4. CommandRunner   -> pelaksana pola Request-Response: kirim perintah,
                          tunggu "ON" (kirim ulang bila lewat 1 detik), tunggu
                          "FIN", lanjut perintah berikutnya.
    5. ActivityLogger  -> catat semua aktivitas + export ke CSV/TXT.

CATATAN KEJUJURAN TEKNIS:
    Nilai RPM & kecepatan pada gauge adalah ESTIMASI dari PWM throttle yang
    SEHARUSNYA dijalankan robot untuk perintah yang sedang berlangsung — bukan
    hasil ukur sensor RPM. Yang REAL/terukur: ACK radio, sinyal ON/FIN dari
    robot, dan sudut MPU yang dikirim balik lewat telemetri.
"""

from __future__ import annotations

import csv
import math
import random
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
ROBOT_SPEED_MPS   = 0.5     # kecepatan robot @ CRUISE_PWM (m/s)
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
_TEL_RE = re.compile(r"R=(-?[\d.]+);P=(-?[\d.]+);Y=(-?[\d.]+)")


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

    Kalau pyrf24 tidak tersedia (mis. di Windows) ATAU modul NRF gagal begin(),
    otomatis pindah ke MODE SIMULASI memakai MockRadio, sehingga GUI tetap
    bisa dikembangkan & didemokan tanpa hardware.
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

        # telemetri balik (roll, pitch, yaw) hasil poll terakhir
        self.telemetry_addr = TELEMETRY_ADDR
        self._telemetry: tuple[float, float, float] | None = None
        self._telemetry_ts: float = 0.0

        # --- Sinyal balik protokol kendali: "ON [Moves]" & "FIN [Moves]:[Dist]" ---
        self._last_on: tuple[str, float] | None = None      # (move, waktu terima)
        self._fin_inbox: list[tuple[str, int]] = []          # antrean FIN belum diambil
        self._rx_lock = threading.Lock()

    # ---- lifecycle -------------------------------------------------

    def begin(self) -> bool:
        """Inisialisasi radio. Return True bila modul (real/mock) siap."""
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
            return True

        except Exception:
            # pyrf24 tidak ada / NRF tidak terdeteksi -> mode simulasi
            self._radio = MockRadio()
            self.simulation = True
            self.module_present = True   # modul "virtual" dianggap ada
            return True

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
                self._fin_inbox.append((m.group(1), int(m.group(2))))
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

    def take_fin(self) -> tuple[str, int] | None:
        """Ambil (dan buang) satu sinyal 'FIN [Moves]:[Dist]' dari antrean."""
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
        elif not self._outbox and now >= self._next_tel:
            # telemetri MPU dibatasi lajunya (mirip TELEMETRY_INTERVAL_MS firmware)
            self._next_tel = now + 0.1
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


def plan_coverage(panjang_m: float, lebar_m: float,
                  lane_width_m: float = LANE_WIDTH_M,
                  speed_mps: float = ROBOT_SPEED_MPS,
                  start_corner: str = "BL") -> CoveragePlan:
    """
    Bangun jalur sapuan zigzag (boustrophedon) untuk tambak persegi.

    Koordinat: x menyusuri LEBAR (0..lebar), y menyusuri PANJANG (0..panjang).
    Robot menjelajah lurus arah-y tiap lintasan, lalu U-turn menggeser sejauh
    lane_width arah-x. Arah belok U-turn BERSELANG-SELING (kanan-kanan lalu
    kiri-kiri, dst) supaya benar-benar menyapu seluruh lebar — bukan bolak-balik
    di kolom yang sama.
    """
    if start_corner not in CORNER_LABEL:
        start_corner = "BL"
    lw = lane_width_m if (lane_width_m and lane_width_m > 0) else LANE_WIDTH_M
    spd = speed_mps if (speed_mps and speed_mps > 0) else ROBOT_SPEED_MPS

    if panjang_m <= 0 or lebar_m <= 0:
        return CoveragePlan(panjang_m, lebar_m, lw, spd, start_corner,
                            "R", 0, [], [], 0.0, 0.0)

    n_lanes = max(1, int(math.ceil(lebar_m / lw)))

    x_left = start_corner in ("BL", "TL")     # mulai di sisi kiri (x=0)?
    bottom = start_corner in ("BL", "BR")     # mulai di sisi bawah (y=0)?
    x0 = 0.0 if x_left else lebar_m
    y0 = 0.0 if bottom else panjang_m
    step = lw if x_left else -lw              # arah geser antar-lintasan

    # ---- bangun waypoints (titik belok) ----
    pts = [(x0, y0)]
    cur = (x0, y0)
    for k in range(n_lanes):
        other_y = panjang_m if cur[1] == 0.0 else 0.0     # ujung seberang
        cur = (cur[0], other_y)
        pts.append(cur)
        if k < n_lanes - 1:
            nx = min(max(cur[0] + step, 0.0), lebar_m)     # geser + jaga dlm tambak
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
                        n_lanes, steps, pts, total, round(est_s, 1))


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
                if fin[0] == cmd.move:
                    self._log("SELESAI", f"FIN {fin[0]}:{fin[1]} — {cmd.human()} tuntas")
                    return True
                fin = self.link.take_fin()

        self._log("PERINGATAN",
                  f"Tidak ada 'FIN {cmd.move}' dalam {limit:.0f} detik — dianggap gagal")
        return False


# =====================================================================
# 3. ACTIVITY LOGGER  —  catat & export
# =====================================================================

@dataclass
class LogEvent:
    ts: str
    category: str
    message: str


class ActivityLogger:
    """Catat aktivitas robot/GUI dengan timestamp, bisa diekspor CSV/TXT."""

    def __init__(self, on_new: Optional[Callable[[LogEvent], None]] = None):
        self.events: list[LogEvent] = []
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
        if self._on_new:
            self._on_new(ev)
        return ev

    def clear(self) -> None:
        with self._lock:
            self.events.clear()

    def export_csv(self, path: str) -> None:
        with self._lock, open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "kategori", "pesan"])
            for ev in self.events:
                w.writerow([ev.ts, ev.category, ev.message])

    def export_txt(self, path: str) -> None:
        with self._lock, open(path, "w", encoding="utf-8") as f:
            f.write("=== LOG AKTIVITAS ROBOT FEEDER AKUATIK ===\n\n")
            for ev in self.events:
                f.write(f"[{ev.ts}] ({ev.category}) {ev.message}\n")


# =====================================================================
# 4. MPU SERIAL READER  —  baca data MPU6050 dari ESP32 via USB Serial
# =====================================================================
#
# Sumber: Test Part/MPU Test/mpu/mpu.ino  yang mencetak tiap 200 ms:
#   Angle -> X: <x>   Y: <y>   Z(Yaw): <z>   | Gyro -> X: <gx> Y: <gy> Z: <gz>
#
# Ini jalur data TERPISAH dari NRF (lewat kabel USB). Cocok untuk fase
# KALIBRASI / UJI BENCH saat board tertambat. Datanya REAL (hasil sensor),
# beda dengan telemetri estimasi. Saat robot berlayar tanpa kabel, data MPU
# realtime butuh telemetri NRF 2 arah (iterasi berikutnya).

# Regex parser untuk format baris mpu.ino
_ANGLE_RE = re.compile(
    r"Angle\s*->\s*X:\s*(-?[\d.]+)\s*Y:\s*(-?[\d.]+)\s*Z\(Yaw\):\s*(-?[\d.]+)")
_GYRO_RE = re.compile(
    r"Gyro\s*->\s*X:\s*(-?[\d.]+)\s*Y:\s*(-?[\d.]+)\s*Z:\s*(-?[\d.]+)")


@dataclass
class MPUReading:
    angle_x: float = 0.0   # roll
    angle_y: float = 0.0   # pitch
    angle_z: float = 0.0   # yaw / heading
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0
    ts: float = 0.0        # time.monotonic()


def parse_mpu_line(line: str) -> Optional[MPUReading]:
    """Parse 1 baris serial dari mpu.ino. Return None bila format tak cocok."""
    a = _ANGLE_RE.search(line)
    if not a:
        return None
    r = MPUReading(angle_x=float(a.group(1)),
                   angle_y=float(a.group(2)),
                   angle_z=float(a.group(3)),
                   ts=time.monotonic())
    g = _GYRO_RE.search(line)
    if g:
        r.gyro_x, r.gyro_y, r.gyro_z = (float(g.group(1)),
                                        float(g.group(2)),
                                        float(g.group(3)))
    return r


class MPUSerialReader:
    """
    Baca MPU6050 dari ESP32 lewat serial USB (pyserial).
    Kalau pyserial tak ada / port gagal dibuka, bisa jalan MODE SIMULASI
    (yaw bergerak sinusoidal) supaya GUI tetap dapat didemokan.
    """

    def __init__(self, on_reading: Optional[Callable[[MPUReading], None]] = None):
        self.on_reading = on_reading
        self.latest = MPUReading()
        self.connected = False
        self.simulation = False
        self.port = ""
        self._ser = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    # ---- koneksi ---------------------------------------------------

    def start_real(self, port: str, baud: int = 115200) -> tuple[bool, str]:
        """Buka serial sungguhan. Return (ok, pesan)."""
        self.stop()
        try:
            import serial  # type: ignore
        except ImportError:
            return False, "pyserial belum terpasang (pip install pyserial)"
        try:
            self._ser = serial.Serial(port, baud, timeout=1)
        except Exception as e:
            return False, f"gagal buka {port}: {e}"

        self.port = port
        self.simulation = False
        self.connected = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        return True, f"MPU terhubung di {port} @ {baud}"

    def start_sim(self) -> tuple[bool, str]:
        """Mode simulasi (tanpa hardware)."""
        self.stop()
        self.port = "SIM"
        self.simulation = True
        self.connected = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._sim_loop, daemon=True)
        self._thread.start()
        return True, "MPU mode SIMULASI (data buatan)"

    def stop(self) -> None:
        self._stop.set()
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
        self.connected = False

    # ---- loop pembaca ---------------------------------------------

    def _emit(self, reading: MPUReading) -> None:
        self.latest = reading
        if self.on_reading:
            self.on_reading(reading)

    def _read_loop(self) -> None:
        while not self._stop.is_set() and self._ser is not None:
            try:
                raw = self._ser.readline().decode("utf-8", "ignore").strip()
            except Exception:
                break
            if not raw:
                continue
            reading = parse_mpu_line(raw)
            if reading:
                self._emit(reading)
        self.connected = False

    def _sim_loop(self) -> None:
        t0 = time.monotonic()
        while not self._stop.is_set():
            t = time.monotonic() - t0
            yaw = 30.0 * math.sin(t * 0.4)                 # ayun -30..30
            self._emit(MPUReading(
                angle_x=2.0 * math.sin(t * 1.1) + random.uniform(-0.3, 0.3),
                angle_y=1.5 * math.cos(t * 0.9) + random.uniform(-0.3, 0.3),
                angle_z=yaw,
                gyro_x=random.uniform(-1, 1),
                gyro_y=random.uniform(-1, 1),
                gyro_z=12.0 * math.cos(t * 0.4),
                ts=time.monotonic()))
            time.sleep(0.2)


# =====================================================================
# SELF-TEST  —  jalankan `python feeder_core.py` untuk verifikasi logika
# =====================================================================

if __name__ == "__main__":
    print("== SELF-TEST feeder_core ==\n")

    # RadioLink (akan fallback ke simulasi di PC)
    link = RadioLink()
    link.begin()
    print(f"Radio siap. Simulasi={link.simulation} "
          f"module_present={link.module_present}")

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

    # cek pola belok berselang-seling (R,R,L,L,R,R,...) untuk boustrophedon benar
    turns = [s.direction for s in plan.steps if s.kind == "turn"]
    assert turns == ["R", "R", "L", "L", "R", "R"], f"pola belok salah: {turns}"
    fwd = [round(s.meters, 3) for s in plan.steps if s.kind == "forward"]
    assert fwd == [10, 1, 10, 1, 10, 1, 10], f"jarak segmen salah: {fwd}"
    # titik awal harus di sudut kiri-bawah (0,0)
    assert plan.waypoints[0] == (0.0, 0.0)
    # arah belok pertama tiap sudut
    assert plan_coverage(10, 4, start_corner="BR").first_turn == "L"
    assert plan_coverage(10, 4, start_corner="TR").first_turn == "R"
    # speed lebih cepat -> waktu lebih singkat
    assert plan_coverage(10, 4, speed_mps=1.0).est_time_s < plan.est_time_s
    print("  [OK] pola belok berselang-seling & encoding valid")

    # Estimasi PWM/RPM per jenis perintah (dasar gauge di GUI)
    print("\nEstimasi throttle per perintah:")
    for mv in (MOVE_FW, MOVE_CW, MOVE_CCW, MOVE_STOP):
        lp, rp = pwm_for_move(mv)
        print(f"  {mv:5s} -> PWM L={lp} R={rp} | "
              f"RPM L={estimate_rpm(lp):6.0f} R={estimate_rpm(rp):6.0f}")
    assert pwm_for_move(MOVE_CW) == (CRUISE_PWM, STOP_PWM)
    assert pwm_for_move(MOVE_CCW) == (STOP_PWM, CRUISE_PWM)
    assert pwm_for_move(MOVE_STOP) == (STOP_PWM, STOP_PWM)

    # MPU parser
    sample = ("Angle -> X: 1.23\tY: -4.56\tZ(Yaw): 88.90   "
              "| Gyro -> X: 0.10\tY: -0.20\tZ: 12.30")
    r = parse_mpu_line(sample)
    print(f"\nParse MPU: roll={r.angle_x} pitch={r.angle_y} yaw={r.angle_z} " # type: ignore
          f"gyroZ={r.gyro_z}") # type: ignore
    assert r and abs(r.angle_z - 88.90) < 1e-6, "parser MPU gagal"

    # ActivityLogger
    log = ActivityLogger()
    log.log("MISI", "Misi 10x4 dikirim")
    log.log("STATUS", "Robot ACK OK")
    print(f"Log tercatat: {len(log.events)} event")
    print("== SELF-TEST selesai ==")
