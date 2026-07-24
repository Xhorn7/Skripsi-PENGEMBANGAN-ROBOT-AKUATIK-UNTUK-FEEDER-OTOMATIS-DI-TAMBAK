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
    LogEvent,
    MissionEstimator,
    MPUReading,
    MPUSerialReader,
    Phase,
    RadioLink,
    HEARTBEAT_INTERVAL_S,
    MOTOR_KV,
    BATTERY_V,
    estimate_rpm,
    FULL_PWM,
    STOP_PWM,
)

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
        left = ctk.CTkScrollableFrame(self, width=340, label_text="KONTROL")
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        self._build_mission_panel(left)
        self._build_component_panel(left)
        self._build_sim_panel(left)

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

    def _build_mission_panel(self, parent):
        f = ctk.CTkFrame(parent)
        f.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(f, text="MISI TAMBAK", font=("", 15, "bold")).pack(pady=(8, 6))

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", padx=10)
        ctk.CTkLabel(row, text="Panjang (m)", width=90, anchor="w").pack(side="left")
        self.entry_panjang = ctk.CTkEntry(row, placeholder_text="mis. 10")
        self.entry_panjang.pack(side="left", fill="x", expand=True)

        row2 = ctk.CTkFrame(f, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(row2, text="Lebar (m)", width=90, anchor="w").pack(side="left")
        self.entry_lebar = ctk.CTkEntry(row2, placeholder_text="mis. 4")
        self.entry_lebar.pack(side="left", fill="x", expand=True)

        row3 = ctk.CTkFrame(f, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkLabel(row3, text="Mode", width=90, anchor="w").pack(side="left")
        ctk.CTkLabel(row3, text="AUTO (zigzag)", anchor="w",
                     text_color=COLOR_OK).pack(side="left")

        self.btn_send = ctk.CTkButton(f, text="▶  KIRIM MISI",
                                      fg_color=COLOR_OK, hover_color="#27ae60",
                                      command=self._on_send_mission)
        self.btn_send.pack(fill="x", padx=10, pady=(6, 4))

        self.btn_stop = ctk.CTkButton(f, text="■  STOP MISI",
                                      fg_color=COLOR_BAD, hover_color="#c0392b",
                                      command=self._on_stop_mission)
        self.btn_stop.pack(fill="x", padx=10, pady=(0, 10))

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
        try:
            panjang = float(self.entry_panjang.get().strip())
            lebar = float(self.entry_lebar.get().strip())
        except ValueError:
            messagebox.showerror("Input salah", "Panjang & Lebar harus angka (meter).")
            return
        if panjang <= 0 or lebar <= 0:
            messagebox.showerror("Input salah", "Panjang & Lebar harus > 0.")
            return
        if not self.motor_armed:
            messagebox.showwarning("Motor mati",
                                   "Nyalakan komponen Motor dulu sebelum kirim misi.")
            return

        payload = f"P={panjang:g};L={lebar:g};MODE=AUTO".encode()
        ok = self.link.send_retry(payload)

        self.estimator = MissionEstimator(panjang, lebar)
        s = self.estimator.summary()
        self.mission_start = time.monotonic()
        self.mission_running = True
        self.heartbeat_enabled = True
        self.sw_heartbeat.select()

        self.logger.log("MISI", f"Kirim P={panjang:g} L={lebar:g} -> "
                        f"{'ACK OK' if ok else 'TANPA ACK'} | "
                        f"{s['n_lanes']} jalur, est {s['total_s']}s")
        if not ok:
            self.logger.log("PERINGATAN", "Misi tak ter-ACK — cek koneksi NRF/robot")

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
