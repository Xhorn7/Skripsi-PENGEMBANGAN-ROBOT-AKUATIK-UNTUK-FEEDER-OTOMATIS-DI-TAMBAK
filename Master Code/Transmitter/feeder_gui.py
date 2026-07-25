"""
feeder_gui.py  —  GUI Kontrol Robot Feeder Akuatik  (CustomTkinter)
====================================================================

Pengganti versi CLI (receiverArduino.py). Dijalankan di RASPBERRY PI
(punya GPIO utk NRF24), tapi otomatis MODE SIMULASI di PC tanpa NRF.

Fitur (sesuai requirement):
    1. Input Panjang & Lebar tambak (meter) -> kirim misi AUTO.
    2. Status koneksi NRF: modul terdeteksi & robot terjangkau (REAL, via ACK).
    3. Kontrol komponen manual (aktif utk yg bisa dikontrol 1 arah,
       monitor utk yg butuh firmware 2 arah).
    4. Telemetri realtime (ESTIMASI): fase, RPM & speed baling-baling L/R.
    5. Semua aktivitas tercatat & bisa diekspor ke CSV/TXT.

Cara jalan:
    pip install customtkinter
    python feeder_gui.py

Arsitektur: GUI ini hanya presentasi; semua logika ada di feeder_core.py.
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError:
    raise SystemExit(
        "customtkinter belum terpasang.\n"
        "Jalankan:  pip install customtkinter"
    )

from feeder_core import (
    ActivityLogger,
    CoveragePlan,
    CORNER_LABEL,
    LogEvent,
    MissionEstimator,
    MPUReading,
    MPUSerialReader,
    Phase,
    RadioLink,
    HEARTBEAT_INTERVAL_S,
    LANE_WIDTH_M,
    ROBOT_SPEED_MPS,
    MOTOR_KV,
    BATTERY_V,
    encode_mission,
    estimate_rpm,
    plan_coverage,
    FULL_PWM,
    STOP_PWM,
)

# label sudut (GUI) -> kode titik awal (BL/BR/TL/TR)
LABEL_TO_CORNER = {v: k for k, v in CORNER_LABEL.items()}

# ---- warna status -----------------------------------------------------
COLOR_OK    = "#2ecc71"   # hijau
COLOR_WARN  = "#f39c12"   # oranye
COLOR_BAD   = "#e74c3c"   # merah
COLOR_IDLE  = "#7f8c8d"   # abu

RPM_MAX = estimate_rpm(FULL_PWM)   # skala penuh utk normalisasi gauge


class FeederGUI(ctk.CTk):
    UI_TICK_MS = 100   # frekuensi refresh gauge/status (ms)

    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Feeder Robot Akuatik — Panel Kontrol (SDLC Prototyping)")
        self.geometry("1120x860")
        self.minsize(1000, 760)

        # ---- state ----
        self.link = RadioLink()
        self.logger = ActivityLogger(on_new=self._on_log_event)
        self.estimator: MissionEstimator | None = None
        self.mission_start: float | None = None
        self.mission_running = False
        self.heartbeat_enabled = True
        self.motor_armed = True          # False = motor dimatikan (STOP terkirim)

        # perencanaan jalur (path planning)
        self.plan: CoveragePlan | None = None
        self.start_corner = "BL"         # titik awal robot (sudut tambak)
        self._active_entry: ctk.CTkEntry | None = None   # target keypad

        # MPU (jalur serialUSB terpisah dari NRF)
        self.mpu = MPUSerialReader()
        self.mpu_record = False          # rekam pembacaan MPU ke log
        self._last_mpu_log = 0.0
        import sys
        self._default_port = "COM11" if sys.platform.startswith("win") else "/dev/ttyUSB0"

        self._build_ui()

        # init radio (real/sim) + heartbeat thread
        self.link.begin()
        self._refresh_conn_badge()
        self.logger.log("SISTEM", "GUI start — mode " +
                        ("SIMULASI (tanpa NRF)" if self.link.simulation else "REAL (NRF aktif)"))

        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        self.after(self.UI_TICK_MS, self._ui_tick)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ==================================================================
    # BUILD UI
    # ==================================================================

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---------- KOLOM KIRI: kontrol ----------
        left = ctk.CTkScrollableFrame(self, width=360, label_text="KONTROL & PERENCANAAN")
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        self._build_mission_panel(left)
        self._build_keypad_panel(left)          # keypad numerik (layar sentuh)
        self._build_plan_panel(left)            # kanvas preview + daftar segmen
        self._build_component_panel(left)
        self._build_sim_panel(left)

        # tampilkan preview jalur awal setelah UI siap
        self.after(200, self._refresh_plan)

        # ---------- KOLOM KANAN: status + telemetri + MPU + log ----------
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(3, weight=1)

        self._build_status_panel(right)
        self._build_telemetry_panel(right)
        self._build_mpu_panel(right)
        self._build_log_panel(right)

    # ---- panel misi --------------------------------------------------

    def _num_row(self, parent, label, placeholder, default=""):
        """Baris input angka + pelacakan fokus (agar keypad tahu target)."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(row, text=label, width=104, anchor="w").pack(side="left")
        e = ctk.CTkEntry(row, placeholder_text=placeholder)
        e.pack(side="left", fill="x", expand=True)
        if default:
            e.insert(0, default)
        e.bind("<FocusIn>", lambda ev, en=e, nm=label: self._set_active_entry(en, nm))
        e.bind("<KeyRelease>", lambda ev: self._refresh_plan())
        return e

    def _build_mission_panel(self, parent):
        f = ctk.CTkFrame(parent)
        f.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(f, text="MISI TAMBAK (persegi)", font=("", 15, "bold")).pack(pady=(8, 2))
        ctk.CTkLabel(f, text="ketuk kolom lalu pakai keypad di bawah",
                     font=("", 10), text_color=COLOR_IDLE).pack(pady=(0, 4))

        self.entry_panjang = self._num_row(f, "Panjang (m)", "mis. 10", "10")
        self.entry_lebar = self._num_row(f, "Lebar (m)", "mis. 4", "4")
        self.entry_lanew = self._num_row(f, "Lebar lintasan (m)", "mis. 1", "1")
        self.entry_speed = self._num_row(f, "Kecepatan (m/s)", "mis. 0.5", "0.5")

        # titik awal robot (sudut tambak)
        row_c = ctk.CTkFrame(f, fg_color="transparent")
        row_c.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(row_c, text="Titik awal", width=104, anchor="w").pack(side="left")
        self.opt_corner = ctk.CTkOptionMenu(
            row_c, values=list(CORNER_LABEL.values()), command=self._on_corner_select)
        self.opt_corner.set(CORNER_LABEL[self.start_corner])
        self.opt_corner.pack(side="left", fill="x", expand=True)

        row3 = ctk.CTkFrame(f, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkLabel(row3, text="Mode", width=104, anchor="w").pack(side="left")
        ctk.CTkLabel(row3, text="AUTO (zigzag)", anchor="w",
                     text_color=COLOR_OK).pack(side="left")

        self.btn_preview = ctk.CTkButton(f, text="⟳  PREVIEW JALUR",
                                         fg_color=COLOR_WARN, hover_color="#d68910",
                                         command=self._refresh_plan)
        self.btn_preview.pack(fill="x", padx=10, pady=(6, 4))

        self.btn_send = ctk.CTkButton(f, text="▶  KIRIM MISI",
                                      fg_color=COLOR_OK, hover_color="#27ae60",
                                      command=self._on_send_mission)
        self.btn_send.pack(fill="x", padx=10, pady=(2, 4))

        self.btn_stop = ctk.CTkButton(f, text="■  STOP MISI",
                                      fg_color=COLOR_BAD, hover_color="#c0392b",
                                      command=self._on_stop_mission)
        self.btn_stop.pack(fill="x", padx=10, pady=(0, 10))

    # ---- keypad numerik (untuk layar sentuh tanpa keyboard) ----------

    def _build_keypad_panel(self, parent):
        f = ctk.CTkFrame(parent)
        f.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(f, text="KEYPAD (layar sentuh)", font=("", 15, "bold")).pack(pady=(8, 2))
        self.lbl_keypad = ctk.CTkLabel(f, text="ketuk kolom input dulu",
                                       font=("", 10), text_color=COLOR_IDLE)
        self.lbl_keypad.pack(pady=(0, 6))

        grid = ctk.CTkFrame(f, fg_color="transparent")
        grid.pack(pady=(0, 6))
        keys = [["7", "8", "9"], ["4", "5", "6"], ["1", "2", "3"], ["0", ".", "back"]]
        for r, rowk in enumerate(keys):
            for cc, k in enumerate(rowk):
                txt = "⌫" if k == "back" else k
                ctk.CTkButton(grid, text=txt, width=70, height=46,
                              font=("", 18, "bold"),
                              command=lambda ch=k: self._keypad_press(ch)
                              ).grid(row=r, column=cc, padx=4, pady=4)
        ctk.CTkButton(f, text="Hapus (C)", fg_color=COLOR_IDLE, hover_color="#616a6b",
                      command=lambda: self._keypad_press("clear")).pack(
            fill="x", padx=10, pady=(0, 10))

    # ---- panel preview jalur (kanvas + daftar segmen) ----------------

    def _build_plan_panel(self, parent):
        f = ctk.CTkFrame(parent)
        f.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(f, text="PREVIEW JALUR (klik peta = titik awal)",
                     font=("", 15, "bold")).pack(pady=(8, 2))

        self.canvas = tk.Canvas(f, width=320, height=210, highlightthickness=0,
                                bg="#0e1b24", bd=0)
        self.canvas.pack(padx=10, pady=(2, 4))
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Configure>", lambda ev: self._draw_pond())

        self.lbl_plan_info = ctk.CTkLabel(f, text="—", font=("", 11),
                                          text_color=COLOR_OK, justify="left")
        self.lbl_plan_info.pack(pady=(0, 4))

        ctk.CTkLabel(f, text="Langkah (path -> maju/belok):",
                     font=("", 11), text_color=COLOR_IDLE).pack(anchor="w", padx=12)
        self.seg_box = ctk.CTkTextbox(f, height=120, font=("Consolas", 12))
        self.seg_box.pack(fill="x", padx=10, pady=(2, 10))
        self.seg_box.configure(state="disabled")

    # ---- panel komponen ---------------------------------------------

    def _build_component_panel(self, parent):
        f = ctk.CTkFrame(parent)
        f.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(f, text="KONTROL KOMPONEN", font=("", 15, "bold")).pack(pady=(8, 2))
        ctk.CTkLabel(f, text="hijau=aktif · merah=mati · abu=monitor",
                     font=("", 10), text_color=COLOR_IDLE).pack(pady=(0, 6))

        self.comp_leds: dict[str, ctk.CTkLabel] = {}

        # Komponen yg BISA dikontrol 1 arah (REAL effect):
        self.sw_nrf = self._add_component(
            f, "nrf", "NRF24 (radio)", real=True,
            command=self._on_toggle_nrf, default=True)
        self.sw_heartbeat = self._add_component(
            f, "hb", "Heartbeat PING", real=True,
            command=self._on_toggle_heartbeat, default=True)
        self.sw_motor = self._add_component(
            f, "motor", "Motor (kedua ESC)", real=True,
            command=self._on_toggle_motor, default=True)

        # Komponen MONITOR-only (butuh firmware 2 arah utk kontrol individual):
        self._add_component(f, "mleft", "Motor Kiri", real=False)
        self._add_component(f, "mright", "Motor Kanan", real=False)
        self._add_component(f, "mpu", "MPU6050 (heading)", real=False)

    def _add_component(self, parent, key, label, real, command=None, default=True):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=3)

        led = ctk.CTkLabel(row, text="●", width=18,
                           text_color=COLOR_IDLE, font=("", 16))
        led.pack(side="left")
        self.comp_leds[key] = led

        ctk.CTkLabel(row, text=label, anchor="w").pack(side="left", padx=(4, 0))

        if real:
            sw = ctk.CTkSwitch(row, text="", command=command, width=44)
            sw.pack(side="right")
            if default:
                sw.select()
            return sw
        else:
            ctk.CTkLabel(row, text="monitor", font=("", 10),
                         text_color=COLOR_IDLE).pack(side="right")
            return None

    # ---- panel simulasi ---------------------------------------------

    def _build_sim_panel(self, parent):
        f = ctk.CTkFrame(parent)
        f.pack(fill="x")
        ctk.CTkLabel(f, text="MODE SIMULASI (demo tanpa HW)",
                     font=("", 13, "bold")).pack(pady=(8, 4))
        self.sw_sim_online = ctk.CTkSwitch(
            f, text="Robot online (ACK)", command=self._on_sim_toggle)
        self.sw_sim_online.pack(pady=(0, 6))
        self.sw_sim_online.select()
        self.lbl_sim_note = ctk.CTkLabel(
            f, text="(hanya berfungsi saat mode simulasi)",
            font=("", 10), text_color=COLOR_IDLE)
        self.lbl_sim_note.pack(pady=(0, 8))

    # ---- panel status -----------------------------------------------

    def _build_status_panel(self, parent):
        f = ctk.CTkFrame(parent)
        f.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        f.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(f, text="STATUS KONEKSI", font=("", 15, "bold")).grid(
            row=0, column=0, columnspan=3, pady=(8, 6))

        self.badge_mode = self._status_tile(f, 0, "MODE", "—")
        self.badge_module = self._status_tile(f, 1, "MODUL NRF", "—")
        self.badge_robot = self._status_tile(f, 2, "ROBOT", "—")

    def _status_tile(self, parent, col, title, value):
        cell = ctk.CTkFrame(parent)
        cell.grid(row=1, column=col, sticky="ew", padx=6, pady=(0, 10))
        ctk.CTkLabel(cell, text=title, font=("", 11),
                     text_color=COLOR_IDLE).pack(pady=(8, 0))
        val = ctk.CTkLabel(cell, text=value, font=("", 16, "bold"))
        val.pack(pady=(0, 8))
        return val

    # ---- panel telemetri --------------------------------------------

    def _build_telemetry_panel(self, parent):
        f = ctk.CTkFrame(parent)
        f.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        f.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(f, text="TELEMETRI  (ESTIMASI dari throttle PWM)",
                     font=("", 15, "bold")).grid(row=0, column=0, columnspan=2,
                                                 pady=(8, 2))
        ctk.CTkLabel(f, text=f"KV={MOTOR_KV:.0f}  ·  V={BATTERY_V}  ·  "
                             "bukan hasil ukur sensor",
                     font=("", 10), text_color=COLOR_WARN).grid(
            row=1, column=0, columnspan=2, pady=(0, 6))

        # fase + progress
        self.lbl_phase = ctk.CTkLabel(f, text="Fase: IDLE", font=("", 14, "bold"))
        self.lbl_phase.grid(row=2, column=0, columnspan=2, pady=2)
        self.progress = ctk.CTkProgressBar(f)
        self.progress.set(0)
        self.progress.grid(row=3, column=0, columnspan=2, sticky="ew",
                           padx=14, pady=(2, 4))
        self.lbl_progress = ctk.CTkLabel(f, text="0%  ·  0.0 / 0.0 s",
                                         font=("", 11), text_color=COLOR_IDLE)
        self.lbl_progress.grid(row=4, column=0, columnspan=2, pady=(0, 8))

        # gauge motor kiri & kanan
        self.gauge_left = self._motor_gauge(f, 0, "BALING-BALING KIRI")
        self.gauge_right = self._motor_gauge(f, 1, "BALING-BALING KANAN")

    def _motor_gauge(self, parent, col, title):
        cell = ctk.CTkFrame(parent)
        cell.grid(row=5, column=col, sticky="ew", padx=8, pady=(0, 10))
        cell.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cell, text=title, font=("", 12, "bold")).grid(
            row=0, column=0, pady=(8, 4))

        rpm_val = ctk.CTkLabel(cell, text="0 RPM", font=("", 22, "bold"),
                               text_color=COLOR_OK)
        rpm_val.grid(row=1, column=0)
        bar = ctk.CTkProgressBar(cell)
        bar.set(0)
        bar.grid(row=2, column=0, sticky="ew", padx=16, pady=6)
        detail = ctk.CTkLabel(cell, text="Throttle 0%  ·  0.00 m/s  ·  PWM 1000µs",
                              font=("", 11), text_color=COLOR_IDLE)
        detail.grid(row=3, column=0, pady=(0, 8))
        return {"rpm": rpm_val, "bar": bar, "detail": detail}

    # ---- panel MPU ---------------------------------------------------

    def _build_mpu_panel(self, parent):
        f = ctk.CTkFrame(parent)
        f.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        f.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(f, text="SENSOR MPU6050  (data REAL via Serial USB)",
                     font=("", 15, "bold")).grid(row=0, column=0, columnspan=3,
                                                 pady=(8, 2))
        ctk.CTkLabel(f, text="dari ESP32 (mpu.ino) — jalur terpisah dari NRF",
                     font=("", 10), text_color=COLOR_IDLE).grid(
            row=1, column=0, columnspan=3, pady=(0, 4))

        # baris kontrol koneksi
        ctrl = ctk.CTkFrame(f, fg_color="transparent")
        ctrl.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 6))
        ctk.CTkLabel(ctrl, text="Port:").pack(side="left")
        self.entry_mpu_port = ctk.CTkEntry(ctrl, width=120)
        self.entry_mpu_port.insert(0, self._default_port)
        self.entry_mpu_port.pack(side="left", padx=(4, 8))
        ctk.CTkButton(ctrl, text="Hubungkan", width=90,
                      command=self._on_mpu_connect).pack(side="left", padx=2)
        ctk.CTkButton(ctrl, text="Simulasi", width=80, fg_color=COLOR_WARN,
                      hover_color="#d68910",
                      command=self._on_mpu_sim).pack(side="left", padx=2)
        ctk.CTkButton(ctrl, text="Putus", width=60, fg_color=COLOR_IDLE,
                      command=self._on_mpu_disconnect).pack(side="left", padx=2)
        self.sw_mpu_record = ctk.CTkSwitch(ctrl, text="Rekam ke log",
                                           command=self._on_mpu_record)
        self.sw_mpu_record.pack(side="right")

        # tiga tile sudut
        self.mpu_tiles = {
            "roll": self._mpu_tile(f, 0, "ROLL (X)"),
            "pitch": self._mpu_tile(f, 1, "PITCH (Y)"),
            "yaw": self._mpu_tile(f, 2, "YAW / HEADING (Z)"),
        }
        self.lbl_mpu_gyro = ctk.CTkLabel(
            f, text="Gyro X/Y/Z: —   ·   status: TERPUTUS",
            font=("", 11), text_color=COLOR_IDLE)
        self.lbl_mpu_gyro.grid(row=4, column=0, columnspan=3, pady=(2, 8))

    def _mpu_tile(self, parent, col, title):
        cell = ctk.CTkFrame(parent)
        cell.grid(row=3, column=col, sticky="ew", padx=8, pady=2)
        cell.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cell, text=title, font=("", 11),
                     text_color=COLOR_IDLE).grid(row=0, column=0, pady=(6, 0))
        val = ctk.CTkLabel(cell, text="0.0°", font=("", 22, "bold"))
        val.grid(row=1, column=0, pady=(0, 6))
        return val

    # ---- panel log ---------------------------------------------------

    def _build_log_panel(self, parent):
        f = ctk.CTkFrame(parent)
        f.grid(row=3, column=0, sticky="nsew")
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(f, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(head, text="LOG AKTIVITAS", font=("", 15, "bold")).pack(side="left")
        ctk.CTkButton(head, text="Export CSV", width=90,
                      command=self._export_csv).pack(side="right", padx=3)
        ctk.CTkButton(head, text="Export TXT", width=90,
                      command=self._export_txt).pack(side="right", padx=3)
        ctk.CTkButton(head, text="Clear", width=60, fg_color=COLOR_IDLE,
                      command=self._clear_log).pack(side="right", padx=3)

        self.log_box = ctk.CTkTextbox(f, font=("Consolas", 12))
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.log_box.configure(state="disabled")

    # ==================================================================
    # EVENT HANDLER
    # ==================================================================

    def _on_send_mission(self):
        self._refresh_plan()
        plan = self.plan
        if plan is None or plan.n_lanes <= 0:
            messagebox.showerror(
                "Input salah",
                "Dimensi tambak belum valid — Panjang & Lebar harus angka > 0.")
            return
        if not self.motor_armed:
            messagebox.showwarning("Motor mati",
                                   "Nyalakan komponen Motor dulu sebelum kirim misi.")
            return

        payload = encode_mission(plan)
        ok = self.link.send_retry(payload)

        self.estimator = MissionEstimator(plan.panjang_m, plan.lebar_m,
                                          plan.speed_mps, plan.lane_width_m)
        self.mission_start = time.monotonic()
        self.mission_running = True
        self.heartbeat_enabled = True
        self.sw_heartbeat.select()

        self.logger.log(
            "MISI",
            f"Kirim [{payload.decode()}] -> {'ACK OK' if ok else 'TANPA ACK'} | "
            f"{plan.n_lanes} jalur, mulai {CORNER_LABEL[plan.start_corner]}, "
            f"belok pertama {'kanan' if plan.first_turn == 'R' else 'kiri'}, "
            f"~{plan.est_time_s:.0f}s")
        if not ok:
            self.logger.log("PERINGATAN", "Misi tak ter-ACK — cek koneksi NRF/robot")

    # ==================================================================
    # PERENCANAAN JALUR: keypad, titik awal, kanvas, daftar segmen
    # ==================================================================

    @staticmethod
    def _read_float(entry, default=None):
        s = entry.get().strip().replace(",", ".")
        if not s:
            return default
        try:
            return float(s)
        except ValueError:
            return None

    def _set_active_entry(self, entry, name):
        """Dipanggil saat sebuah kolom input mendapat fokus (untuk keypad)."""
        self._active_entry = entry
        self.lbl_keypad.configure(text=f"input aktif: {name}", text_color=COLOR_OK)

    def _keypad_press(self, ch):
        en = self._active_entry
        if en is None:
            self.lbl_keypad.configure(text="ketuk kolom input dulu",
                                      text_color=COLOR_WARN)
            return
        if ch == "clear":
            en.delete(0, "end")
        elif ch == "back":
            s = en.get()
            en.delete(0, "end")
            en.insert(0, s[:-1])
        elif ch == ".":
            if "." not in en.get():
                en.insert("end", ".")
        else:
            en.insert("end", ch)
        self._refresh_plan()

    def _on_corner_select(self, label):
        self.start_corner = LABEL_TO_CORNER.get(label, "BL")
        self._refresh_plan()

    def _refresh_plan(self):
        P = self._read_float(self.entry_panjang)
        L = self._read_float(self.entry_lebar)
        lw = self._read_float(self.entry_lanew, LANE_WIDTH_M) or LANE_WIDTH_M
        spd = self._read_float(self.entry_speed, ROBOT_SPEED_MPS) or ROBOT_SPEED_MPS
        if P is None or L is None or P <= 0 or L <= 0:
            self.plan = None
        else:
            self.plan = plan_coverage(P, L, lw, spd, self.start_corner)
        self._draw_pond()
        self._render_segments()
        self._update_plan_info()

    def _update_plan_info(self):
        if not self.plan or self.plan.n_lanes <= 0:
            self.lbl_plan_info.configure(text="Isi Panjang & Lebar lalu Preview",
                                         text_color=COLOR_IDLE)
            return
        p = self.plan
        self.lbl_plan_info.configure(
            text=(f"{p.n_lanes} jalur  ·  {p.total_distance_m:.1f} m  ·  ~{p.est_time_s:.0f} s\n"
                  f"mulai {CORNER_LABEL[p.start_corner]}  ·  belok pertama "
                  f"{'kanan' if p.first_turn == 'R' else 'kiri'}"),
            text_color=COLOR_OK)

    def _render_segments(self):
        self.seg_box.configure(state="normal")
        self.seg_box.delete("1.0", "end")
        if self.plan and self.plan.steps:
            for i, st in enumerate(self.plan.steps, 1):
                self.seg_box.insert("end", f"{i:2d}. {st.human()}\n")
        else:
            self.seg_box.insert("end", "(belum ada jalur — isi dimensi)\n")
        self.seg_box.configure(state="disabled")

    def _pond_geometry(self):
        """Return (ox, oy, scale, pond_w, pond_h) atau None."""
        if not self.plan or self.plan.panjang_m <= 0 or self.plan.lebar_m <= 0:
            return None
        c = self.canvas
        W = c.winfo_width() or 320
        H = c.winfo_height() or 210
        if W < 10:
            W = 320
        if H < 10:
            H = 210
        margin = 22
        pond_w = self.plan.lebar_m
        pond_h = self.plan.panjang_m
        scale = min((W - 2 * margin) / pond_w, (H - 2 * margin) / pond_h)
        ox = (W - pond_w * scale) / 2
        oy = (H - pond_h * scale) / 2
        return ox, oy, scale, pond_w, pond_h

    def _on_canvas_click(self, ev):
        geo = self._pond_geometry()
        if not geo:
            return
        ox, oy, scale, pond_w, pond_h = geo
        x = (ev.x - ox) / scale
        y = pond_h - (ev.y - oy) / scale
        if not (-0.2 * pond_w <= x <= 1.2 * pond_w and
                -0.2 * pond_h <= y <= 1.2 * pond_h):
            return
        left = x < pond_w / 2
        bottom = y < pond_h / 2
        code = ("BL" if left else "BR") if bottom else ("TL" if left else "TR")
        self.start_corner = code
        self.opt_corner.set(CORNER_LABEL[code])
        self._refresh_plan()

    def _draw_pond(self):
        c = self.canvas
        c.delete("all")
        geo = self._pond_geometry()
        if not geo:
            W = c.winfo_width() or 320
            H = c.winfo_height() or 210
            c.create_text(max(W, 320) // 2, max(H, 210) // 2,
                          text="Isi dimensi lalu Preview",
                          fill="#7f8c8d", font=("", 11))
            return
        ox, oy, scale, pond_w, pond_h = geo
        plan = self.plan
        if plan is None:
            return

        def tx(x, y):
            return ox + x * scale, oy + (pond_h - y) * scale

        x0, y0 = tx(0, 0)
        x1, y1 = tx(pond_w, pond_h)
        c.create_rectangle(x0, y1, x1, y0, outline="#2c6da3", width=2, fill="#12232e")

        # garis bantu antar-lintasan
        lw = plan.lane_width_m
        n = 1
        while n * lw < pond_w - 1e-9:
            gx, _ = tx(n * lw, 0)
            c.create_line(gx, y1, gx, y0, fill="#1c3a4d")
            n += 1

        # jalur (polyline berpanah)
        pts = [tx(px, py) for (px, py) in plan.waypoints]
        for i in range(len(pts) - 1):
            c.create_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                          fill="#2ecc71", width=2, arrow="last", arrowshape=(8, 9, 3))

        # penanda titik awal
        if pts:
            sx, sy = pts[0]
            c.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill="#f39c12", outline="")
            c.create_text(sx, sy - 11, text="START", fill="#f39c12", font=("", 8, "bold"))

        c.create_text((x0 + x1) / 2, y0 + 11, text=f"lebar {pond_w:g} m",
                      fill="#7f8c8d", font=("", 8))

    def _on_stop_mission(self):
        # STOP: sama seperti CLI — hentikan heartbeat lalu spam STOP
        self.mission_running = False
        self.heartbeat_enabled = False
        time.sleep(HEARTBEAT_INTERVAL_S)
        ok = self.link.send_retry(b"STOP")
        self.logger.log("STOP", "Misi dibatalkan — STOP "
                        f"{'terkirim' if ok else 'GAGAL (cek NRF)'}")

    def _on_toggle_nrf(self):
        on = bool(self.sw_nrf.get())
        self.link.tx_enabled = on
        self.logger.log("KOMPONEN", f"NRF TX di-{'AKTIFKAN' if on else 'MATIKAN'}")

    def _on_toggle_heartbeat(self):
        self.heartbeat_enabled = bool(self.sw_heartbeat.get())
        self.logger.log("KOMPONEN",
                        f"Heartbeat PING di-{'AKTIFKAN' if self.heartbeat_enabled else 'MATIKAN'}"
                        + ("" if self.heartbeat_enabled else " (robot failsafe stop ~3s)"))

    def _on_toggle_motor(self):
        on = bool(self.sw_motor.get())
        self.motor_armed = on
        if not on:
            # matikan motor secara REAL lewat perintah STOP
            self.link.send_retry(b"STOP")
            self.mission_running = False
            self.logger.log("KOMPONEN", "Motor DIMATIKAN (STOP terkirim ke robot)")
        else:
            self.logger.log("KOMPONEN", "Motor DIAKTIFKAN (siap misi)")

    def _on_sim_toggle(self):
        online = bool(self.sw_sim_online.get())
        self.link.set_sim_robot_reachable(online)
        self.logger.log("SIMULASI", f"Robot virtual di-set {'ONLINE' if online else 'OFFLINE'}")

    # ---- MPU ---------------------------------------------------------

    def _on_mpu_connect(self):
        port = self.entry_mpu_port.get().strip()
        ok, msg = self.mpu.start_real(port)
        self.logger.log("MPU", msg)
        if not ok:
            self.logger.log("MPU", "Fallback ke simulasi (klik Simulasi bila perlu)")

    def _on_mpu_sim(self):
        ok, msg = self.mpu.start_sim()
        self.logger.log("MPU", msg)

    def _on_mpu_disconnect(self):
        self.mpu.stop()
        self.logger.log("MPU", "MPU diputus")

    def _on_mpu_record(self):
        self.mpu_record = bool(self.sw_mpu_record.get())
        self.logger.log("MPU", f"Rekam MPU ke log {'AKTIF' if self.mpu_record else 'nonaktif'}")

    # ---- export ------------------------------------------------------

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=f"log_feeder_{datetime.now():%Y%m%d_%H%M%S}.csv")
        if path:
            self.logger.export_csv(path)
            messagebox.showinfo("Export", f"Log CSV disimpan:\n{path}")

    def _export_txt(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Teks", "*.txt")],
            initialfile=f"log_feeder_{datetime.now():%Y%m%d_%H%M%S}.txt")
        if path:
            self.logger.export_txt(path)
            messagebox.showinfo("Export", f"Log TXT disimpan:\n{path}")

    def _clear_log(self):
        self.logger.clear()
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ==================================================================
    # BACKGROUND: heartbeat + UI tick
    # ==================================================================

    def _heartbeat_loop(self):
        """Kirim PING selama misi aktif (meniru receiverArduino.py)."""
        while True:
            if self.mission_running and self.heartbeat_enabled:
                self.link.send(b"PING")
            time.sleep(HEARTBEAT_INTERVAL_S)

    def _ui_tick(self):
        self._refresh_conn_badge()
        self._refresh_components()
        self._refresh_telemetry()
        self._refresh_mpu()
        self.after(self.UI_TICK_MS, self._ui_tick)

    def _refresh_mpu(self):
        r: MPUReading = self.mpu.latest
        if self.mpu.connected:
            self.mpu_tiles["roll"].configure(text=f"{r.angle_x:.1f}°",
                                             text_color=COLOR_OK)
            self.mpu_tiles["pitch"].configure(text=f"{r.angle_y:.1f}°",
                                              text_color=COLOR_OK)
            self.mpu_tiles["yaw"].configure(text=f"{r.angle_z:.1f}°",
                                            text_color=COLOR_OK)
            src = "SIMULASI" if self.mpu.simulation else self.mpu.port
            self.lbl_mpu_gyro.configure(
                text=f"Gyro X={r.gyro_x:.1f} Y={r.gyro_y:.1f} Z={r.gyro_z:.1f}"
                     f"   ·   sumber: {src}",
                text_color=COLOR_OK)

            # rekam ke log @1 Hz saat diaktifkan
            if self.mpu_record and (time.monotonic() - self._last_mpu_log) >= 1.0:
                self._last_mpu_log = time.monotonic()
                self.logger.log("MPU-DATA",
                                f"Roll={r.angle_x:.1f} Pitch={r.angle_y:.1f} "
                                f"Yaw={r.angle_z:.1f} | GyroZ={r.gyro_z:.1f}")
        else:
            for t in self.mpu_tiles.values():
                t.configure(text_color=COLOR_IDLE)
            self.lbl_mpu_gyro.configure(text="Gyro X/Y/Z: —   ·   status: TERPUTUS",
                                        text_color=COLOR_IDLE)

    def _refresh_conn_badge(self):
        mode = "SIMULASI" if self.link.simulation else "REAL"
        self.badge_mode.configure(
            text=mode, text_color=COLOR_WARN if self.link.simulation else COLOR_OK)
        self.badge_module.configure(
            text="TERDETEKSI" if self.link.module_present else "TIDAK ADA",
            text_color=COLOR_OK if self.link.module_present else COLOR_BAD)
        reachable = self.link.robot_reachable()
        self.badge_robot.configure(
            text="TERHUBUNG" if reachable else "TERPUTUS",
            text_color=COLOR_OK if reachable else COLOR_BAD)

    def _refresh_components(self):
        self.comp_leds["nrf"].configure(
            text_color=COLOR_OK if self.link.tx_enabled else COLOR_BAD)
        self.comp_leds["hb"].configure(
            text_color=COLOR_OK if (self.heartbeat_enabled and self.mission_running)
            else (COLOR_WARN if self.heartbeat_enabled else COLOR_BAD))
        self.comp_leds["motor"].configure(
            text_color=COLOR_OK if self.motor_armed else COLOR_BAD)

        # LED monitor: warnai sesuai fase estimasi
        snap = self._current_snapshot()
        left_on = snap and snap.left_pwm > STOP_PWM
        right_on = snap and snap.right_pwm > STOP_PWM
        self.comp_leds["mleft"].configure(
            text_color=COLOR_OK if left_on else COLOR_IDLE)
        self.comp_leds["mright"].configure(
            text_color=COLOR_OK if right_on else COLOR_IDLE)
        self.comp_leds["mpu"].configure(
            text_color=COLOR_OK if self.mission_running else COLOR_IDLE)

    def _current_snapshot(self):
        if not (self.mission_running and self.estimator and self.mission_start):
            return None
        elapsed = (time.monotonic() - self.mission_start) * 1000.0
        return self.estimator.snapshot_at(elapsed)

    def _refresh_telemetry(self):
        snap = self._current_snapshot()

        if snap is None:
            self.lbl_phase.configure(text="Fase: IDLE")
            self.progress.set(0)
            self.lbl_progress.configure(text="0%  ·  0.0 / 0.0 s")
            self._set_gauge(self.gauge_left, STOP_PWM)
            self._set_gauge(self.gauge_right, STOP_PWM)
            return

        # misi selesai -> auto stop
        if snap.phase == Phase.DONE and self.mission_running:
            self.mission_running = False
            self.heartbeat_enabled = False
            self.sw_heartbeat.deselect()
            self.logger.log("MISI", "MISI SELESAI (estimasi timeline habis)")

        self.lbl_phase.configure(
            text=f"Fase: {snap.phase.value}   |   Jalur {snap.lane}/{snap.total_lanes}")
        self.progress.set(snap.progress)
        self.lbl_progress.configure(
            text=f"{snap.progress*100:.0f}%  ·  "
                 f"{snap.elapsed_ms/1000:.1f} / {snap.total_ms/1000:.1f} s")
        self._set_gauge(self.gauge_left, snap.left_pwm)
        self._set_gauge(self.gauge_right, snap.right_pwm)

    def _set_gauge(self, gauge, pwm):
        from feeder_core import throttle_fraction, estimate_speed_mps
        rpm = estimate_rpm(pwm)
        frac = rpm / RPM_MAX if RPM_MAX else 0
        gauge["rpm"].configure(text=f"{rpm:,.0f} RPM",
                               text_color=COLOR_OK if pwm > STOP_PWM else COLOR_IDLE)
        gauge["bar"].set(frac)
        gauge["detail"].configure(
            text=f"Throttle {throttle_fraction(pwm)*100:.0f}%  ·  "
                 f"{estimate_speed_mps(pwm):.2f} m/s  ·  PWM {pwm}µs")

    # ==================================================================
    # LOG VIEW
    # ==================================================================

    def _on_log_event(self, ev: LogEvent):
        # dipanggil dari thread mana pun -> jadwalkan ke main thread
        self.after(0, self._append_log, ev)

    def _append_log(self, ev: LogEvent):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{ev.ts}] ({ev.category}) {ev.message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _on_close(self):
        try:
            if self.mission_running:
                self.link.send_retry(b"STOP")
            self.mpu.stop()
        finally:
            self.destroy()


if __name__ == "__main__":
    FeederGUI().mainloop()
