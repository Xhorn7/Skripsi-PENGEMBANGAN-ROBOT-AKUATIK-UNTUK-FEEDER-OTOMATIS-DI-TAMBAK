"""
feeder_core.py  —  Lapisan BACKEND untuk GUI Feeder Robot Akuatik
==================================================================

Modul ini SENGAJA dipisah dari GUI (feeder_gui.py) mengikuti prinsip
Separation of Concerns. Tujuannya (relevan utk dokumentasi SDLC):

    - GUI  = presentasi (tombol, gauge, log view)
    - Core = logika: radio link, estimasi telemetri, pencatatan aktivitas

Tiga kelas utama:

    1. RadioLink       -> abstraksi NRF24 (pyrf24) + AUTO-FALLBACK ke MockRadio
                          kalau dijalankan di PC tanpa pyrf24/NRF (mode SIMULASI).
    2. MissionEstimator-> "cermin" (mirror) timeline pola zigzag dari firmware
                          ESP32 (Finalnew.ino). Karena komunikasi 1 arah dan
                          tidak ada sensor RPM, telemetri di GUI adalah ESTIMASI
                          yang dihitung dari nilai PWM throttle yang SEHARUSNYA
                          dijalankan robot pada detik ke-t sebuah misi.
    3. ActivityLogger  -> catat semua aktivitas + export ke CSV/TXT.

CATATAN KEJUJURAN TEKNIS:
    Nilai RPM & kecepatan yang ditampilkan adalah ESTIMASI, BUKAN hasil ukur.
    Robot sekarang tidak mengirim telemetri balik dan tidak punya sensor RPM.
    Yang REAL/terukur hanyalah: keberadaan modul NRF & apakah robot meng-ACK.
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
TURN_90_MS        = 1500    # durasi belok ~90 derajat (ms)
CRUISE_PWM        = 1300    # throttle jelajah (us)
STOP_PWM          = 1000    # throttle diam/arming (us)
FULL_PWM          = 2000    # throttle penuh (us)
SIGNAL_TIMEOUT_MS = 3000    # failsafe robot: stop bila tak ada sinyal

# Jeda antar-fase (delay) di firmware, ms
DELAY_AFTER_LANE  = 500
DELAY_AFTER_TURN  = 300
DELAY_AFTER_SHIFT = 300
DELAY_END_UTURN   = 500

# Parameter estimasi RPM (KASAR — silakan kalibrasi sesuai motor nyata).
# RPM_est = throttle_fraction * MOTOR_KV * BATTERY_V
MOTOR_KV          = 2200.0  # KV motor brushless (rpm/volt)
BATTERY_V         = 11.1    # tegangan baterai (3S LiPo)

HEARTBEAT_INTERVAL_S = 0.5  # interval PING (harus < SIGNAL_TIMEOUT_MS)


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

    # ---- lifecycle -------------------------------------------------

    def begin(self) -> bool:
        """Inisialisasi radio. Return True bila modul (real/mock) siap."""
        try:
            from pyrf24 import RF24, RF24_PA_LOW, RF24_250KBPS  # type: ignore

            radio = RF24(self.ce_pin, self.csn_pin)
            if not radio.begin():
                raise RuntimeError("radio.begin() gagal — cek wiring NRF")

            radio.open_tx_pipe(self.address)
            radio.setPALevel(RF24_PA_LOW)
            radio.setDataRate(RF24_250KBPS)
            radio.setChannel(0x76)

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
    """Radio tiruan untuk mode SIMULASI. write() mengembalikan status ACK."""

    def __init__(self):
        self.robot_online = True

    def write(self, payload: bytes) -> bool:
        # Robot 'online' -> selalu ACK. Bisa dimatikan untuk demo kegagalan.
        return bool(self.robot_online)


# =====================================================================
# 2. MISSION ESTIMATOR  —  cermin timeline zigzag firmware
# =====================================================================

class Phase(Enum):
    IDLE   = "IDLE"
    CRUISE = "JELAJAH (lurus)"
    TURN   = "BELOK 90"
    SHIFT  = "GESER LANE"
    PAUSE  = "JEDA (stop)"
    DONE   = "SELESAI"


@dataclass
class PhaseSegment:
    duration_ms: float
    phase: Phase
    left_pwm: int
    right_pwm: int
    lane: int            # jalur ke berapa (1-based); 0 kalau bukan cruise
    total_lanes: int


@dataclass
class TelemetrySnapshot:
    phase: Phase
    lane: int
    total_lanes: int
    left_pwm: int
    right_pwm: int
    elapsed_ms: float
    total_ms: float

    @property
    def progress(self) -> float:
        if self.total_ms <= 0:
            return 0.0
        return max(0.0, min(1.0, self.elapsed_ms / self.total_ms))

    @property
    def left_rpm(self) -> float:
        return estimate_rpm(self.left_pwm)

    @property
    def right_rpm(self) -> float:
        return estimate_rpm(self.right_pwm)

    @property
    def left_speed(self) -> float:
        return estimate_speed_mps(self.left_pwm)

    @property
    def right_speed(self) -> float:
        return estimate_speed_mps(self.right_pwm)


class MissionEstimator:
    """
    Membangun daftar segmen fase (PhaseSegment) yang MENCERMINKAN urutan
    gerak di Finalnew.ino untuk MODE=AUTO, lalu bisa ditanya 'pada detik ke-t
    robot lagi ngapain & PWM-nya berapa'.

    Ini membuat gauge RPM/speed di GUI bergerak realtime SINKRON dengan misi
    yang benar-benar sedang dijalankan robot — walau datanya estimasi.
    """

    def __init__(self, panjang_m: float, lebar_m: float,
                 speed_mps: float = ROBOT_SPEED_MPS,
                 lane_width_m: float = LANE_WIDTH_M):
        self.panjang_m = panjang_m
        self.lebar_m = lebar_m
        # speed & lane width kini bisa diatur dari GUI (dikirim ke robot lewat
        # SPD/LW); fallback ke konstanta bila nilai tak valid.
        self.speed_mps = speed_mps if (speed_mps and speed_mps > 0) else ROBOT_SPEED_MPS
        self.lane_width_m = lane_width_m if (lane_width_m and lane_width_m > 0) else LANE_WIDTH_M
        self.segments: list[PhaseSegment] = []
        self.total_ms = 0.0
        self.n_lanes = 0
        self._build()

    def _build(self) -> None:
        if self.panjang_m <= 0 or self.lebar_m <= 0:
            return

        n_lanes = int(math.ceil(self.lebar_m / self.lane_width_m))
        lane_ms = (self.panjang_m / self.speed_mps) * 1000.0
        shift_ms = (self.lane_width_m / self.speed_mps) * 1000.0
        self.n_lanes = n_lanes

        segs: list[PhaseSegment] = []

        def add(dur, phase, lp, rp, lane=0):
            if dur > 0:
                segs.append(PhaseSegment(dur, phase, lp, rp, lane, n_lanes))

        for lane in range(n_lanes):
            # Jelajah lurus 1 jalur (kedua motor ~CRUISE)
            add(lane_ms, Phase.CRUISE, CRUISE_PWM, CRUISE_PWM, lane + 1)
            add(DELAY_AFTER_LANE, Phase.PAUSE, STOP_PWM, STOP_PWM, lane + 1)

            if lane < n_lanes - 1:
                # U-turn = belok kanan 90 (L maju, R stop)
                add(TURN_90_MS, Phase.TURN, CRUISE_PWM, STOP_PWM, lane + 1)
                add(DELAY_AFTER_TURN, Phase.PAUSE, STOP_PWM, STOP_PWM, lane + 1)
                # geser 1 lane (kedua motor ~CRUISE)
                add(shift_ms, Phase.SHIFT, CRUISE_PWM, CRUISE_PWM, lane + 1)
                add(DELAY_AFTER_SHIFT, Phase.PAUSE, STOP_PWM, STOP_PWM, lane + 1)
                # belok kanan 90 lagi (total 180)
                add(TURN_90_MS, Phase.TURN, CRUISE_PWM, STOP_PWM, lane + 1)
                add(DELAY_END_UTURN, Phase.PAUSE, STOP_PWM, STOP_PWM, lane + 1)

        self.segments = segs
        self.total_ms = sum(s.duration_ms for s in segs)

    def snapshot_at(self, elapsed_ms: float) -> TelemetrySnapshot:
        """Kondisi robot (estimasi) pada waktu elapsed_ms sejak misi mulai."""
        if not self.segments:
            return TelemetrySnapshot(Phase.IDLE, 0, 0, STOP_PWM, STOP_PWM,
                                     elapsed_ms, self.total_ms)

        if elapsed_ms >= self.total_ms:
            last = self.segments[-1]
            return TelemetrySnapshot(Phase.DONE, last.total_lanes,
                                     last.total_lanes, STOP_PWM, STOP_PWM,
                                     self.total_ms, self.total_ms)

        acc = 0.0
        for seg in self.segments:
            if elapsed_ms < acc + seg.duration_ms:
                return TelemetrySnapshot(seg.phase, seg.lane, seg.total_lanes,
                                         seg.left_pwm, seg.right_pwm,
                                         elapsed_ms, self.total_ms)
            acc += seg.duration_ms

        return TelemetrySnapshot(Phase.DONE, self.n_lanes, self.n_lanes,
                                 STOP_PWM, STOP_PWM, self.total_ms, self.total_ms)

    def summary(self) -> dict:
        return {
            "panjang_m": self.panjang_m,
            "lebar_m": self.lebar_m,
            "speed_mps": self.speed_mps,
            "lane_width_m": self.lane_width_m,
            "n_lanes": self.n_lanes,
            "total_ms": self.total_ms,
            "total_s": round(self.total_ms / 1000.0, 1),
        }


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

    # arah belok pertama = arah U-turn pertama (dikirim ke robot sbg DIR)
    first_turn = next((s.direction for s in steps if s.kind == "turn"), "R")

    est = MissionEstimator(panjang_m, lebar_m, spd, lw)
    return CoveragePlan(panjang_m, lebar_m, lw, spd, start_corner, first_turn,
                        n_lanes, steps, pts, total, round(est.total_ms / 1000.0, 1))


def encode_mission(plan: CoveragePlan) -> bytes:
    """
    Susun paket misi untuk robot. Kompatibel-mundur dgn firmware lama
    (P/L/MODE tetap di depan) dan menambah SPD/LW/DIR yang diabaikan bila
    firmware belum mendukung.
        P=<panjang>;L=<lebar>;MODE=AUTO;SPD=<m/s>;LW=<m>;DIR=<R|L>
    """
    return (f"P={plan.panjang_m:g};L={plan.lebar_m:g};MODE=AUTO;"
            f"SPD={plan.speed_mps:g};LW={plan.lane_width_m:g};"
            f"DIR={plan.first_turn}").encode()


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
    ok = link.send_retry(b"P=10;L=4;MODE=AUTO")
    print(f"Kirim misi -> ACK={ok}  robot_reachable={link.robot_reachable()}")

    # PATH PLANNER — terjemahkan tambak -> segmen maju/belok
    print("\n== Path planner (tambak 10x4, lane 1m, mulai Kiri-Bawah) ==")
    plan = plan_coverage(10, 4, lane_width_m=1.0, speed_mps=0.5, start_corner="BL")
    print(f"n_lanes={plan.n_lanes}  first_turn={plan.first_turn}  "
          f"jarak={plan.total_distance_m:.1f} m  est={plan.est_time_s}s")
    print("Paket ->", encode_mission(plan).decode())
    for i, st in enumerate(plan.steps, 1):
        print(f"  {i:2d}. {st.human()}")

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

    # MissionEstimator (memakai speed & lane width sama dgn plan)
    est = MissionEstimator(panjang_m=10, lebar_m=4)
    print("\nRingkasan misi:", est.summary())
    print(f"Jumlah segmen fase: {len(est.segments)}")

    print("\nProbe telemetri estimasi di beberapa titik waktu:")
    for t in (0, 5000, 20500, 22000, 24000, est.total_ms + 1):
        s = est.snapshot_at(t)
        print(f"  t={t/1000:6.1f}s | {s.phase.value:14s} | "
              f"lane {s.lane}/{s.total_lanes} | "
              f"L={s.left_pwm} R={s.right_pwm} | "
              f"RPM L={s.left_rpm:6.0f} R={s.right_rpm:6.0f} | "
              f"prog={s.progress*100:4.0f}%")

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
