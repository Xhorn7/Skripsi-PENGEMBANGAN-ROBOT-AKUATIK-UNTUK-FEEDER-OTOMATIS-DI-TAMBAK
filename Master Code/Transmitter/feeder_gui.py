"""
feeder_gui.py  —  GUI Kontrol Robot Feeder Akuatik  (CustomTkinter)
====================================================================

Antarmuka PENGENDALI UTAMA. Dijalankan di Raspberry Pi dengan layar sentuh
7 inci. Aplikasi SELALU MULAI DI MODE SIMULASI (aman untuk demo & latihan);
tombol MODE pada bilah status atas memindahkannya ke NRF sungguhan kapan saja.

RANCANGAN TAMPILAN (revisi: gaya mesin ATM)
-------------------------------------------
Jendela mengikuti UKURAN LAYAR PERANGKAT (fullscreen, tanpa bilah judul) dan
seluruh ukuran huruf/tombol diskalakan dari acuan 800x480 piksel — resolusi
layar sentuh 7 inci. Alih-alih menumpuk semua panel dalam satu layar padat,
antarmuka dipecah menjadi HALAMAN dengan navigasi tombol besar di bawah,
persis pola mesin ATM: satu layar = satu tugas, target sentuh lebar,
tombol berhenti darurat selalu terlihat.

    +--------------------------------------------------+
    |  judul       [MODE*][NRF][ROBOT]      [ STOP ]   |  bilah status
    +--------------------------------------------------+     * bisa disentuh:
                                                           REAL <-> SIMULASI
    |                                                  |
    |                  ISI HALAMAN                     |
    |                                                  |
    +--------------------------------------------------+
    | BERANDA | MISI | MANUAL | SENSOR | LOG | SISTEM  |  navigasi
    +--------------------------------------------------+

Halaman:
    BERANDA -> ringkasan status + perintah yang sedang berjalan
    MISI    -> dimensi tambak, preview jalur, kirim antrean perintah
    MANUAL  -> maju dalam METER + putar kiri/kanan (+ STOP di bilah atas)
    SENSOR  -> telemetri baling-baling (estimasi) & sudut MPU dari NRF (real),
               plus tombol nyala/mati pencatatan MPU
    LOG     -> catatan aktivitas, auto-simpan TXT, ekspor CSV/TXT
    SISTEM  -> kontrol komponen, pilih mode REAL/SIMULASI, keluar aplikasi

Papan angka muncul sebagai LAPISAN PENUH saat sebuah kolom disentuh, supaya
halaman tetap lega tanpa kehilangan kemampuan input tanpa keyboard.

Cara jalan:
    pip install customtkinter
    python feeder_gui.py                 # fullscreen, mulai mode SIMULASI
    python feeder_gui.py --windowed      # jendela 800x480 untuk uji di PC
    python feeder_gui.py --real          # langsung mencoba NRF sungguhan

Arsitektur: GUI ini hanya presentasi; semua logika ada di feeder_core.py.
"""

from __future__ import annotations

import os
import sys
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
    CommandRunner,
    CoveragePlan,
    CORNER_LABEL,
    LogEvent,
    MPUMonitor,
    MOVE_CCW,
    MOVE_CW,
    MOVE_FW,
    MOVE_RANGE,
    RadioLink,
    RobotCommand,
    RunStatus,
    HEARTBEAT_INTERVAL_S,
    LANE_WIDTH_M,
    LOG_DIR_NAME,
    MANUAL_FW_MAX_M,
    MANUAL_FW_MIN_M,
    MANUAL_FW_STEP_M,
    MPU_LOG_INTERVAL_S,
    ROBOT_SPEED_MPS,
    MOTOR_KV,
    BATTERY_V,
    default_log_path,
    estimate_rpm,
    estimate_speed_mps,
    plan_command_queue,
    plan_coverage,
    queue_duration_s,
    split_forward,
    throttle_fraction,
    FULL_PWM,
    STOP_PWM,
)

# label sudut (GUI) -> kode titik awal (BL/BR/TL/TR)
LABEL_TO_CORNER = {v: k for k, v in CORNER_LABEL.items()}

# ---- warna ------------------------------------------------------------
COLOR_OK    = "#2ecc71"   # hijau
COLOR_WARN  = "#f39c12"   # oranye
COLOR_BAD   = "#e74c3c"   # merah
COLOR_IDLE  = "#7f8c8d"   # abu
COLOR_NAV   = "#1f2b36"   # dasar bilah navigasi
COLOR_NAVON = "#2c6da3"   # halaman aktif
COLOR_CANVAS = "#0e1b24"

RPM_MAX = estimate_rpm(FULL_PWM)   # skala penuh utk normalisasi gauge

# Acuan rancangan: layar sentuh 7 inci Raspberry Pi (800 x 480 piksel).
BASE_W, BASE_H = 800, 480


class FeederGUI(ctk.CTk):
    UI_TICK_MS = 120   # frekuensi refresh gauge/status (ms)

    # ==================================================================
    # SIKLUS HIDUP
    # ==================================================================

    def __init__(self, fullscreen: bool = True, simulation: bool = True):
        """
        simulation=True (default) -> aplikasi mulai dengan robot virtual.
        Operator memindahkannya ke NRF sungguhan lewat tombol MODE.
        """
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Pengendali Utama — Robot Akuatik Feeder")
        self._setup_screen(fullscreen)

        # ---- state ----
        # CATATAN THREAD: RadioLink & CommandRunner bekerja di thread latar,
        # sedangkan Tkinter hanya boleh disentuh dari thread utama. Karena itu
        # keduanya TIDAK diberi callback ke GUI — tampilan justru MENARIK
        # (polling) status & log pada _ui_tick. Memanggil after() dari thread
        # lain sempat membuat thread runner terblokir menunggu Tcl.
        self.link = RadioLink()
        self.logger = ActivityLogger()
        self.runner = CommandRunner(self.link, logger=self.logger)
        self._log_shown = 0              # jumlah baris log yang sudah ditampilkan
        self.heartbeat_enabled = True
        self.motor_armed = True          # False = motor dimatikan (STOP terkirim)
        self.want_simulation = simulation  # mode yang DIMINTA operator
        self._closing = False            # penanda jendela sedang ditutup

        # perencanaan jalur (path planning)
        self.plan: CoveragePlan | None = None
        self.queue: list[RobotCommand] = []
        self.start_corner = "BL"         # titik awal robot (sudut tambak)

        # Nilai perintah manual. MAJU dipegang dalam METER (satuan yang dipakai
        # operator di lapangan); pemecahan ke paket FW 10-200 cm dikerjakan
        # split_forward() saat tombol KIRIM ditekan.
        self.manual_val: dict[str, float] = {MOVE_FW: 1.0, MOVE_CW: 90,
                                             MOVE_CCW: 90}

        # MPU: tidak lagi lewat port serial — sudutnya ikut telemetri NRF dan
        # ditarik di latar belakang oleh MPUMonitor.
        self.mpu = MPUMonitor(self.link, logger=self.logger)

        self._pages: dict[str, ctk.CTkFrame] = {}
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._active_page = ""

        self._build_ui()

        # init radio + heartbeat thread. Default SIMULASI: robot sungguhan baru
        # tersentuh setelah operator sendiri menekan tombol MODE.
        self.link.begin(force_sim=self.want_simulation)
        self._sync_mode_widgets()
        self._refresh_status_chips()
        self.logger.log("SISTEM", "GUI start — mode " +
                        ("SIMULASI (robot virtual)" if self.link.simulation
                         else "REAL (NRF aktif)") +
                        "; ganti lewat tombol MODE di bilah atas")
        self.logger.log("SISTEM",
                        f"Layar {self.screen_w}x{self.screen_h} px "
                        f"(skala tampilan {self.S:.2f}x dari acuan 800x480)")

        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        self.after(300, self._refresh_plan)
        self.after(self.UI_TICK_MS, self._ui_tick)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_screen(self, fullscreen: bool):
        """
        Samakan jendela dengan ukuran layar perangkat, lalu hitung faktor skala
        terhadap acuan 800x480 supaya tata letak tetap proporsional baik di
        layar 7 inci maupun monitor yang lebih besar.
        """
        self.screen_w = self.winfo_screenwidth()
        self.screen_h = self.winfo_screenheight()

        if fullscreen:
            self.geometry(f"{self.screen_w}x{self.screen_h}+0+0")
            try:
                self.attributes("-fullscreen", True)
            except Exception:
                pass
            w, h = self.screen_w, self.screen_h
        else:
            w, h = BASE_W, BASE_H
            self.geometry(f"{w}x{h}")
        self.minsize(BASE_W, BASE_H)

        # skala dijepit agar huruf tidak jadi mikro di layar kecil atau
        # raksasa di monitor besar
        self.S = max(0.85, min(2.0, min(w / BASE_W, h / BASE_H)))

        # Escape / F11: keluar-masuk fullscreen (berguna saat uji di PC)
        self.bind("<Escape>", lambda e: self._toggle_fullscreen())
        self.bind("<F11>", lambda e: self._toggle_fullscreen())

    def _toggle_fullscreen(self):
        try:
            self.attributes("-fullscreen", not self.attributes("-fullscreen"))
        except Exception:
            pass

    # ---- pembantu skala ---------------------------------------------

    def px(self, v: float) -> int:
        """Ukuran piksel yang sudah diskalakan."""
        return max(1, int(round(v * self.S)))

    def F(self, size: float, bold: bool = False):
        """Font berskala."""
        return ("", max(8, int(round(size * self.S))), "bold" if bold else "normal")

    # ==================================================================
    # KERANGKA: bilah status + area halaman + navigasi
    # ==================================================================

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()

        self.page_area = ctk.CTkFrame(self, fg_color="transparent")
        self.page_area.grid(row=1, column=0, sticky="nsew",
                            padx=self.px(8), pady=self.px(6))
        self.page_area.grid_columnconfigure(0, weight=1)
        self.page_area.grid_rowconfigure(0, weight=1)

        self._build_navbar()

        # halaman
        self._pages["BERANDA"] = self._build_page_home()
        self._pages["MISI"]    = self._build_page_mission()
        self._pages["MANUAL"]  = self._build_page_manual()
        self._pages["SENSOR"]  = self._build_page_sensor()
        self._pages["LOG"]     = self._build_page_log()
        self._pages["SISTEM"]  = self._build_page_system()
        for pg in self._pages.values():
            pg.grid(row=0, column=0, sticky="nsew")

        self._build_keypad_overlay()
        self.show_page("BERANDA")

    # ---- bilah status atas -------------------------------------------

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, height=self.px(50), corner_radius=0,
                           fg_color=COLOR_NAV)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)

        ctk.CTkLabel(bar, text="ROBOT AKUATIK  ·  PENGENDALI UTAMA",
                     font=self.F(13, True)).pack(side="left", padx=self.px(12))

        # tombol berhenti darurat — selalu terlihat di setiap halaman
        self.btn_stop = ctk.CTkButton(
            bar, text="■  STOP", width=self.px(110), height=self.px(36),
            font=self.F(15, True), fg_color=COLOR_BAD, hover_color="#c0392b",
            command=self._on_stop)
        self.btn_stop.pack(side="right", padx=self.px(10))

        self.chip_robot  = self._chip(bar, "ROBOT")
        self.chip_module = self._chip(bar, "NRF")
        # MODE bukan sekadar penanda: disentuh = pindah REAL <-> SIMULASI.
        self.chip_mode   = self._chip(bar, "MODE  ⇄  sentuh",
                                      command=self._on_toggle_mode)

    def _chip(self, parent, title, command=None):
        """
        Kotak status kecil di bilah atas. Bila diberi command, nilainya menjadi
        TOMBOL (dipakai chip MODE untuk berpindah REAL/SIMULASI).
        """
        cell = ctk.CTkFrame(parent, corner_radius=self.px(6))
        cell.pack(side="right", padx=self.px(4), pady=self.px(7))
        ctk.CTkLabel(cell, text=title, font=self.F(8),
                     text_color=COLOR_IDLE).pack(padx=self.px(9), pady=(self.px(3), 0))
        if command is not None:
            val = ctk.CTkButton(cell, text="—", font=self.F(11, True),
                                width=self.px(96), height=self.px(22),
                                corner_radius=self.px(5), fg_color="#243442",
                                hover_color="#2f4557", command=command)
        else:
            val = ctk.CTkLabel(cell, text="—", font=self.F(10, True))
        val.pack(padx=self.px(9), pady=(0, self.px(3)))
        return val

    # ---- navigasi bawah ----------------------------------------------

    def _build_navbar(self):
        nav = ctk.CTkFrame(self, height=self.px(62), corner_radius=0,
                           fg_color=COLOR_NAV)
        nav.grid(row=2, column=0, sticky="ew")
        nav.grid_propagate(False)

        pages = [("BERANDA", "⌂  BERANDA"), ("MISI", "▦  MISI"),
                 ("MANUAL", "⇄  MANUAL"), ("SENSOR", "◎  SENSOR"),
                 ("LOG", "≡  LOG"), ("SISTEM", "⚙  SISTEM")]
        for i, (key, label) in enumerate(pages):
            nav.grid_columnconfigure(i, weight=1)
            b = ctk.CTkButton(nav, text=label, font=self.F(11, True),
                              height=self.px(46), corner_radius=self.px(8),
                              fg_color="transparent", hover_color="#2b3a48",
                              command=lambda k=key: self.show_page(k))
            b.grid(row=0, column=i, sticky="ew",
                   padx=self.px(4), pady=self.px(8))
            self._nav_buttons[key] = b

    def show_page(self, key: str):
        if key not in self._pages:
            return
        self._active_page = key
        self._pages[key].tkraise()
        for k, b in self._nav_buttons.items():
            b.configure(fg_color=COLOR_NAVON if k == key else "transparent")
        if key == "MISI":
            self.after(60, self._draw_pond)

    # ==================================================================
    # HALAMAN 1 — BERANDA
    # ==================================================================

    def _build_page_home(self):
        pg = ctk.CTkFrame(self.page_area, fg_color="transparent")
        pg.grid_columnconfigure(0, weight=1)
        pg.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(pg, corner_radius=self.px(12))
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="STATUS ROBOT", font=self.F(11),
                     text_color=COLOR_IDLE).pack(pady=(self.px(14), 0))
        self.home_status = ctk.CTkLabel(card, text="SIAP", font=self.F(30, True),
                                        text_color=COLOR_OK)
        self.home_status.pack(pady=(self.px(2), self.px(2)))

        self.home_cmd = ctk.CTkLabel(card, text="Belum ada perintah berjalan",
                                     font=self.F(14, True))
        self.home_cmd.pack()

        self.home_progress = ctk.CTkProgressBar(card, height=self.px(16))
        self.home_progress.set(0)
        self.home_progress.pack(fill="x", padx=self.px(30), pady=self.px(10))

        self.home_detail = ctk.CTkLabel(card, text="—", font=self.F(11),
                                        text_color=COLOR_IDLE)
        self.home_detail.pack()

        # tiga ubin ringkas
        tiles = ctk.CTkFrame(card, fg_color="transparent")
        tiles.pack(fill="x", padx=self.px(20), pady=self.px(12))
        for i in range(3):
            tiles.grid_columnconfigure(i, weight=1)
        self.tile_queue = self._tile(tiles, 0, "ANTREAN PERINTAH")
        self.tile_eta   = self._tile(tiles, 1, "PERKIRAAN WAKTU")
        self.tile_yaw   = self._tile(tiles, 2, "ARAH HADAP (YAW)")

        # dua tombol besar
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=self.px(20), pady=(0, self.px(16)))
        row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(row, text="▶   MULAI MISI", height=self.px(52),
                      font=self.F(15, True), fg_color=COLOR_OK,
                      hover_color="#27ae60",
                      command=lambda: self.show_page("MISI")).grid(
            row=0, column=0, sticky="ew", padx=self.px(6))
        ctk.CTkButton(row, text="⇄   KENDALI MANUAL", height=self.px(52),
                      font=self.F(15, True),
                      command=lambda: self.show_page("MANUAL")).grid(
            row=0, column=1, sticky="ew", padx=self.px(6))
        return pg

    def _tile(self, parent, col, title):
        cell = ctk.CTkFrame(parent, corner_radius=self.px(8))
        cell.grid(row=0, column=col, sticky="ew", padx=self.px(6))
        ctk.CTkLabel(cell, text=title, font=self.F(9),
                     text_color=COLOR_IDLE).pack(pady=(self.px(7), 0))
        val = ctk.CTkLabel(cell, text="—", font=self.F(17, True))
        val.pack(pady=(0, self.px(7)))
        return val

    # ==================================================================
    # HALAMAN 2 — MISI (dimensi tambak -> antrean perintah)
    # ==================================================================

    def _build_page_mission(self):
        pg = ctk.CTkFrame(self.page_area, fg_color="transparent")
        pg.grid_columnconfigure(0, weight=0, minsize=self.px(300))
        pg.grid_columnconfigure(1, weight=1)
        pg.grid_rowconfigure(0, weight=1)

        # ---- kiri: input dimensi ----
        left = ctk.CTkFrame(pg, corner_radius=self.px(12))
        left.grid(row=0, column=0, sticky="nsew", padx=(0, self.px(6)))

        # Tombol aksi dijangkar ke DASAR kartu lebih dulu supaya tidak pernah
        # terpotong walau daftar kolom input bertambah panjang.
        ctk.CTkButton(left, text="▶   KIRIM MISI KE ROBOT", height=self.px(44),
                      font=self.F(13, True), fg_color=COLOR_OK,
                      hover_color="#27ae60", command=self._on_send_mission).pack(
            side="bottom", fill="x", padx=self.px(12), pady=(0, self.px(8)))
        ctk.CTkButton(left, text="⟳   HITUNG ULANG JALUR", height=self.px(36),
                      font=self.F(11, True), fg_color=COLOR_WARN,
                      hover_color="#d68910", command=self._refresh_plan).pack(
            side="bottom", fill="x", padx=self.px(12), pady=(0, self.px(4)))

        ctk.CTkLabel(left, text="UKURAN TAMBAK   ·   sentuh kolom untuk "
                                "papan angka", font=self.F(11, True)).pack(
            pady=(self.px(7), self.px(3)))

        self.entry_panjang = self._field(left, "Panjang", "m", "10")
        self.entry_lebar   = self._field(left, "Lebar", "m", "4")
        self.entry_lanew   = self._field(left, "Lebar lintasan", "m", "1")
        self.entry_speed   = self._field(left, "Kecepatan", "m/s", "0.5")

        row_c = ctk.CTkFrame(left, fg_color="transparent")
        row_c.pack(fill="x", padx=self.px(12), pady=self.px(2))
        ctk.CTkLabel(row_c, text="Titik awal", width=self.px(102), anchor="w",
                     font=self.F(11)).pack(side="left")
        self.opt_corner = ctk.CTkOptionMenu(
            row_c, values=list(CORNER_LABEL.values()), font=self.F(11),
            dropdown_font=self.F(11), height=self.px(32),
            command=self._on_corner_select)
        self.opt_corner.set(CORNER_LABEL[self.start_corner])
        self.opt_corner.pack(side="left", fill="x", expand=True)

        # ---- kanan: preview jalur + daftar perintah ----
        right = ctk.CTkFrame(pg, corner_radius=self.px(12))
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=3)
        right.grid_rowconfigure(3, weight=2)

        ctk.CTkLabel(right, text="PREVIEW JALUR  (sentuh peta = titik awal)",
                     font=self.F(11, True)).grid(row=0, column=0,
                                                 pady=(self.px(8), self.px(2)))
        self.canvas = tk.Canvas(right, highlightthickness=0, bg=COLOR_CANVAS, bd=0)
        self.canvas.grid(row=1, column=0, sticky="nsew",
                         padx=self.px(10), pady=self.px(2))
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Configure>", lambda ev: self._draw_pond())

        self.lbl_plan_info = ctk.CTkLabel(right, text="—", font=self.F(10),
                                          text_color=COLOR_OK, justify="center")
        self.lbl_plan_info.grid(row=2, column=0, pady=self.px(2))

        self.seg_box = ctk.CTkTextbox(right, font=("Consolas", self.px(10)))
        self.seg_box.grid(row=3, column=0, sticky="nsew",
                          padx=self.px(10), pady=(self.px(2), self.px(10)))
        self.seg_box.configure(state="disabled")
        return pg

    def _field(self, parent, label, unit, default=""):
        """Kolom angka: sentuh -> papan angka terbuka."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=self.px(12), pady=self.px(2))
        ctk.CTkLabel(row, text=label, width=self.px(102), anchor="w",
                     font=self.F(11)).pack(side="left")
        e = ctk.CTkEntry(row, font=self.F(13, True), height=self.px(32),
                         justify="right")
        e.pack(side="left", fill="x", expand=True)
        if default:
            e.insert(0, default)
        ctk.CTkLabel(row, text=unit, width=self.px(34), anchor="w",
                     font=self.F(10), text_color=COLOR_IDLE).pack(
            side="left", padx=(self.px(5), 0))
        e.bind("<Button-1>", lambda ev, en=e, nm=f"{label} ({unit})":
               self._open_keypad(en, nm))
        e.bind("<KeyRelease>", lambda ev: self._refresh_plan())
        return e

    # ==================================================================
    # HALAMAN 3 — MANUAL (input FW / CW / CCW)
    # ==================================================================

    def _build_page_manual(self):
        pg = ctk.CTkFrame(self.page_area, fg_color="transparent")
        pg.grid_columnconfigure(0, weight=1)
        pg.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(pg, corner_radius=self.px(10))
        head.grid(row=0, column=0, sticky="ew", pady=(0, self.px(5)))
        ctk.CTkLabel(
            head,
            text="KENDALI MANUAL   ·   MAJU diisi dalam METER, otomatis dipecah "
                 "jadi paket FW 10–200 cm   ·   robot membalas ON lalu FIN",
            font=self.F(11, True)).pack(pady=self.px(7))

        body = ctk.CTkFrame(pg, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        for i in range(3):
            body.grid_columnconfigure(i, weight=1)

        self.manual_cards = {
            MOVE_FW:  self._manual_card(body, 0, MOVE_FW, "MAJU", "▲",
                                        COLOR_OK, "#27ae60"),
            MOVE_CCW: self._manual_card(body, 1, MOVE_CCW, "PUTAR KIRI", "↺",
                                        "#3498db", "#2c81ba"),
            MOVE_CW:  self._manual_card(body, 2, MOVE_CW, "PUTAR KANAN", "↻",
                                        "#3498db", "#2c81ba"),
        }
        self._update_manual_card(MOVE_FW)
        return pg

    # ---- satuan antarmuka kartu MANUAL -------------------------------
    #
    # MAJU memakai METER (yang dipikirkan operator saat berdiri di tepi
    # tambak), sedangkan PUTAR tetap derajat sesuai protokol. Konversi meter ->
    # paket FW dilakukan saat pengiriman, bukan disimpan.

    def _manual_range(self, move) -> tuple[float, float, str]:
        if move == MOVE_FW:
            return MANUAL_FW_MIN_M, MANUAL_FW_MAX_M, "meter"
        lo, hi, unit = MOVE_RANGE[move]
        return float(lo), float(hi), unit

    def _manual_text(self, move) -> str:
        v = self.manual_val[move]
        return f"{v:.1f}" if move == MOVE_FW else f"{int(v)}"

    def _update_manual_card(self, move):
        """Segarkan angka besar + keterangan pemecahan paket pada satu kartu."""
        card = self.manual_cards[move]
        card["val"].configure(text=self._manual_text(move))
        hint = card.get("hint")
        if hint is None:
            return
        cmds = split_forward(self.manual_val[move])
        if not cmds:
            hint.configure(text=f"minimal {MANUAL_FW_MIN_M:g} m", text_color=COLOR_BAD)
        else:
            hint.configure(
                text=(f"→ {len(cmds)} paket  ·  "
                      f"{cmds[0].encode().decode()}"
                      + (f" ×{len(cmds)}" if len(cmds) > 1 else "")),
                text_color=COLOR_IDLE)

    def _manual_card(self, parent, col, move, title, icon, color, hover):
        lo, hi, unit = self._manual_range(move)
        card = ctk.CTkFrame(parent, corner_radius=self.px(12))
        card.grid(row=0, column=col, sticky="nsew", padx=self.px(5))
        card.grid_columnconfigure(0, weight=1)

        # Tombol dijangkar ke DASAR kartu lebih dulu supaya selalu terjangkau
        # walau tinggi layar mepet (7 inci = 480 piksel).
        ctk.CTkButton(card, text="KIRIM  ▶", height=self.px(46),
                      font=self.F(14, True), fg_color=color, hover_color=hover,
                      command=lambda m=move: self._on_send_manual(m)).pack(
            side="bottom", fill="x", padx=self.px(12), pady=(0, self.px(10)))
        ctk.CTkButton(card, text="⌨  ISI ANGKA", height=self.px(32),
                      font=self.F(10, True), fg_color="#34495e",
                      hover_color="#3f5c78",
                      command=lambda m=move, t=title: self._open_keypad_manual(m, t)
                      ).pack(side="bottom", fill="x", padx=self.px(12),
                             pady=(0, self.px(5)))

        ctk.CTkLabel(card, text=f"{icon}  {title}", font=self.F(13, True)).pack(
            pady=(self.px(8), 0))
        ctk.CTkLabel(card, text=f"{move}  ·  {lo:g}–{hi:g} {unit}", font=self.F(9),
                     text_color=COLOR_IDLE).pack(pady=(0, self.px(2)))

        val = ctk.CTkLabel(card, text=self._manual_text(move),
                           font=self.F(32, True), text_color=color)
        val.pack()
        ctk.CTkLabel(card, text=unit, font=self.F(9),
                     text_color=COLOR_IDLE).pack(pady=(0, self.px(2)))

        # Khusus MAJU: perlihatkan jadi berapa paket FW jarak itu dipecah,
        # supaya operator tahu persis apa yang dikirim ke robot.
        hint = None
        if move == MOVE_FW:
            hint = ctk.CTkLabel(card, text="—", font=self.F(9),
                                text_color=COLOR_IDLE)
            hint.pack(pady=(0, self.px(2)))

        # pengatur cepat -/+
        step_row = ctk.CTkFrame(card, fg_color="transparent")
        step_row.pack(pady=(0, self.px(4)))
        step = MANUAL_FW_STEP_M if move == MOVE_FW else 15
        for txt, delta in (("−", -step), ("+", step)):
            ctk.CTkButton(step_row, text=txt, width=self.px(50),
                          height=self.px(36), font=self.F(17, True),
                          fg_color="#34495e", hover_color="#3f5c78",
                          command=lambda m=move, d=delta: self._manual_step(m, d)
                          ).pack(side="left", padx=self.px(5))
        return {"val": val, "hint": hint}

    # ==================================================================
    # HALAMAN 4 — SENSOR (telemetri baling-baling + MPU)
    # ==================================================================

    def _build_page_sensor(self):
        pg = ctk.CTkFrame(self.page_area, fg_color="transparent")
        pg.grid_columnconfigure(0, weight=1)
        pg.grid_rowconfigure((0, 1), weight=1)

        # --- baling-baling (estimasi) ---
        top = ctk.CTkFrame(pg, corner_radius=self.px(10))
        top.grid(row=0, column=0, sticky="nsew", pady=(0, self.px(5)))
        top.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(top, text="BALING-BALING  ·  estimasi dari throttle PWM  "
                               f"(KV={MOTOR_KV:.0f}, V={BATTERY_V}) — bukan "
                               "hasil ukur sensor RPM",
                     font=self.F(10, True), text_color=COLOR_WARN).grid(
            row=0, column=0, columnspan=2, pady=(self.px(6), self.px(2)))
        self.gauge_left  = self._gauge(top, 0, "KIRI")
        self.gauge_right = self._gauge(top, 1, "KANAN")

        # --- MPU (real, lewat telemetri NRF — tanpa port serial) ---
        bot = ctk.CTkFrame(pg, corner_radius=self.px(10))
        bot.grid(row=1, column=0, sticky="nsew")
        bot.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(bot, text="SENSOR MPU  ·  data REAL dari robot  —  "
                               "dikirim sendiri lewat NRF, tanpa kabel/port",
                     font=self.F(10, True)).grid(row=0, column=0, columnspan=3,
                                                 pady=(self.px(6), self.px(2)))

        ctrl = ctk.CTkFrame(bot, fg_color="transparent")
        ctrl.grid(row=1, column=0, columnspan=3, sticky="ew",
                  padx=self.px(12), pady=self.px(3))
        ctk.CTkLabel(ctrl, text="Sudut mengalir di latar belakang selama "
                                "heartbeat hidup.", font=self.F(10),
                     text_color=COLOR_IDLE).pack(side="left")
        self.sw_mpu_record = ctk.CTkSwitch(
            ctrl, text=f"Log MPU (tiap {MPU_LOG_INTERVAL_S:g} s)",
            font=self.F(10), command=self._on_mpu_record)
        self.sw_mpu_record.pack(side="right")

        self.mpu_tiles = {
            "roll":  self._mpu_tile(bot, 0, "ROLL (X)"),
            "pitch": self._mpu_tile(bot, 1, "PITCH (Y)"),
            "yaw":   self._mpu_tile(bot, 2, "YAW / HEADING (Z)"),
        }
        self.lbl_mpu_src = ctk.CTkLabel(bot, text="status: TERPUTUS",
                                        font=self.F(9), text_color=COLOR_IDLE)
        self.lbl_mpu_src.grid(row=3, column=0, columnspan=3,
                              pady=(self.px(1), self.px(6)))
        return pg

    def _gauge(self, parent, col, title):
        cell = ctk.CTkFrame(parent, corner_radius=self.px(8))
        cell.grid(row=1, column=col, sticky="nsew",
                  padx=self.px(8), pady=(0, self.px(7)))
        cell.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cell, text=title, font=self.F(10, True)).grid(
            row=0, column=0, pady=(self.px(4), 0))
        rpm = ctk.CTkLabel(cell, text="0 RPM", font=self.F(20, True),
                           text_color=COLOR_IDLE)
        rpm.grid(row=1, column=0)
        bar = ctk.CTkProgressBar(cell, height=self.px(10))
        bar.set(0)
        bar.grid(row=2, column=0, sticky="ew", padx=self.px(16), pady=self.px(3))
        detail = ctk.CTkLabel(cell, text="Throttle 0% · 0.00 m/s · PWM 1000µs",
                              font=self.F(9), text_color=COLOR_IDLE)
        detail.grid(row=3, column=0, pady=(0, self.px(5)))
        return {"rpm": rpm, "bar": bar, "detail": detail}

    def _mpu_tile(self, parent, col, title):
        cell = ctk.CTkFrame(parent, corner_radius=self.px(8))
        cell.grid(row=2, column=col, sticky="nsew", padx=self.px(8),
                  pady=self.px(3))
        cell.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cell, text=title, font=self.F(9),
                     text_color=COLOR_IDLE).grid(row=0, column=0,
                                                 pady=(self.px(4), 0))
        val = ctk.CTkLabel(cell, text="0.0°", font=self.F(19, True))
        val.grid(row=1, column=0, pady=(0, self.px(4)))
        return val

    # ==================================================================
    # HALAMAN 5 — LOG
    # ==================================================================

    def _build_page_log(self):
        pg = ctk.CTkFrame(self.page_area, corner_radius=self.px(12))
        pg.grid_rowconfigure(2, weight=1)
        pg.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(pg, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=self.px(10),
                  pady=(self.px(8), self.px(2)))
        ctk.CTkLabel(head, text="LOG AKTIVITAS", font=self.F(13, True)).pack(
            side="left")
        for txt, cmd, col in (("Clear", self._clear_log, COLOR_IDLE),
                              ("Export TXT", self._export_txt, None),
                              ("Export CSV", self._export_csv, None)):
            ctk.CTkButton(head, text=txt, width=self.px(95), height=self.px(34),
                          font=self.F(11), fg_color=col, command=cmd).pack(
                side="right", padx=self.px(4))

        # --- auto-simpan: tiap baris langsung ditulis ke berkas TXT ---
        auto = ctk.CTkFrame(pg, fg_color="transparent")
        auto.grid(row=1, column=0, sticky="ew", padx=self.px(10),
                  pady=(0, self.px(4)))
        self.sw_autosave = ctk.CTkSwitch(auto, text="Auto-simpan TXT",
                                         font=self.F(11),
                                         command=self._on_toggle_autosave)
        self.sw_autosave.pack(side="left")
        self.lbl_autosave = ctk.CTkLabel(
            auto, text="nonaktif — catatan hanya tersimpan di memori",
            font=self.F(9), text_color=COLOR_IDLE, anchor="w")
        self.lbl_autosave.pack(side="left", padx=self.px(10), fill="x",
                               expand=True)

        self.log_box = ctk.CTkTextbox(pg, font=("Consolas", self.px(10)))
        self.log_box.grid(row=2, column=0, sticky="nsew",
                          padx=self.px(10), pady=(0, self.px(10)))
        self.log_box.configure(state="disabled")
        return pg

    # ==================================================================
    # HALAMAN 6 — SISTEM (komponen, simulasi, keluar)
    # ==================================================================

    def _build_page_system(self):
        pg = ctk.CTkFrame(self.page_area, fg_color="transparent")
        pg.grid_columnconfigure((0, 1), weight=1)
        pg.grid_rowconfigure(0, weight=1)

        # --- komponen ---
        comp = ctk.CTkFrame(pg, corner_radius=self.px(12))
        comp.grid(row=0, column=0, sticky="nsew", padx=(0, self.px(5)))
        ctk.CTkLabel(comp, text="KONTROL KOMPONEN", font=self.F(13, True)).pack(
            pady=(self.px(10), 0))
        ctk.CTkLabel(comp, text="hijau = aktif · merah = mati · abu = monitor",
                     font=self.F(9), text_color=COLOR_IDLE).pack(
            pady=(0, self.px(6)))

        self.comp_leds: dict[str, ctk.CTkLabel] = {}
        self.sw_nrf = self._component(comp, "nrf", "NRF24 (radio)", True,
                                      self._on_toggle_nrf)
        self.sw_heartbeat = self._component(comp, "hb", "Heartbeat PING", True,
                                            self._on_toggle_heartbeat)
        self.sw_motor = self._component(comp, "motor", "Motor (kedua ESC)", True,
                                        self._on_toggle_motor)
        self._component(comp, "mleft", "Motor Kiri", False)
        self._component(comp, "mright", "Motor Kanan", False)
        self._component(comp, "mpu", "MPU (heading)", False)

        # --- mode kerja + keluar ---
        side = ctk.CTkFrame(pg, corner_radius=self.px(12))
        side.grid(row=0, column=1, sticky="nsew", padx=(self.px(5), 0))
        ctk.CTkLabel(side, text="MODE KERJA", font=self.F(13, True)).pack(
            pady=(self.px(10), 0))
        ctk.CTkLabel(side, text="SIMULASI = robot virtual (default, aman) · "
                                "REAL = kirim ke NRF24",
                     font=self.F(9), text_color=COLOR_IDLE).pack(
            pady=(0, self.px(6)))
        self.seg_mode = ctk.CTkSegmentedButton(
            side, values=["SIMULASI", "REAL"], font=self.F(11, True),
            height=self.px(36), command=self._on_mode_segment)
        self.seg_mode.set("SIMULASI")
        self.seg_mode.pack(fill="x", padx=self.px(14), pady=(0, self.px(6)))

        self.sw_sim_online = ctk.CTkSwitch(side, text="Robot virtual online (ACK)",
                                           font=self.F(11),
                                           command=self._on_sim_toggle)
        self.sw_sim_online.select()
        self.sw_sim_online.pack(pady=self.px(4))

        self.lbl_sys_info = ctk.CTkLabel(side, text="—", font=self.F(10),
                                         text_color=COLOR_IDLE, justify="left")
        self.lbl_sys_info.pack(pady=self.px(12))

        ctk.CTkButton(side, text="⛶  JENDELA / LAYAR PENUH", height=self.px(42),
                      font=self.F(11, True), fg_color="#34495e",
                      hover_color="#3f5c78",
                      command=self._toggle_fullscreen).pack(
            fill="x", padx=self.px(14), pady=(self.px(10), self.px(4)))
        ctk.CTkButton(side, text="✕  TUTUP APLIKASI", height=self.px(42),
                      font=self.F(11, True), fg_color=COLOR_BAD,
                      hover_color="#c0392b", command=self._on_close).pack(
            fill="x", padx=self.px(14), pady=(0, self.px(12)))
        return pg

    def _component(self, parent, key, label, real, command=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=self.px(14), pady=self.px(4))
        led = ctk.CTkLabel(row, text="●", width=self.px(18),
                           text_color=COLOR_IDLE, font=self.F(15))
        led.pack(side="left")
        self.comp_leds[key] = led
        ctk.CTkLabel(row, text=label, anchor="w", font=self.F(11)).pack(
            side="left", padx=(self.px(4), 0))
        if real:
            sw = ctk.CTkSwitch(row, text="", command=command, width=self.px(44))
            sw.select()
            sw.pack(side="right")
            return sw
        ctk.CTkLabel(row, text="monitor", font=self.F(9),
                     text_color=COLOR_IDLE).pack(side="right")
        return None

    # ==================================================================
    # PAPAN ANGKA (lapisan penuh — pengganti keyboard di layar sentuh)
    # ==================================================================

    def _build_keypad_overlay(self):
        self.keypad = ctk.CTkFrame(self, corner_radius=0, fg_color="#0b1218")
        self._keypad_target: ctk.CTkEntry | None = None
        self._keypad_move: str | None = None
        self._keypad_buf = ""
        self._keypad_fresh = True       # True = ketikan berikutnya mengganti nilai
        self._keypad_hint = ""

        self.keypad.grid_columnconfigure(0, weight=1)
        self.keypad.grid_rowconfigure(3, weight=1)

        self.kp_title = ctk.CTkLabel(self.keypad, text="", font=self.F(13, True))
        self.kp_title.grid(row=0, column=0, pady=(self.px(10), 0))
        self.kp_value = ctk.CTkLabel(self.keypad, text="0", font=self.F(30, True),
                                     text_color=COLOR_OK)
        self.kp_value.grid(row=1, column=0)
        self.kp_hint = ctk.CTkLabel(self.keypad, text="", font=self.F(10),
                                    text_color=COLOR_IDLE)
        self.kp_hint.grid(row=2, column=0, pady=(0, self.px(4)))

        grid = ctk.CTkFrame(self.keypad, fg_color="transparent")
        grid.grid(row=3, column=0, pady=self.px(2))
        keys = [["7", "8", "9"], ["4", "5", "6"], ["1", "2", "3"], ["0", ".", "⌫"]]
        for r, rowk in enumerate(keys):
            for c, k in enumerate(rowk):
                ctk.CTkButton(grid, text=k, width=self.px(86), height=self.px(50),
                              font=self.F(20, True), corner_radius=self.px(8),
                              fg_color="#243442", hover_color="#2f4557",
                              command=lambda ch=k: self._keypad_press(ch)
                              ).grid(row=r, column=c, padx=self.px(5),
                                     pady=self.px(4))

        act = ctk.CTkFrame(self.keypad, fg_color="transparent")
        act.grid(row=4, column=0, sticky="ew", padx=self.px(30),
                 pady=(self.px(4), self.px(12)))
        act.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkButton(act, text="BATAL", height=self.px(46), font=self.F(13, True),
                      fg_color=COLOR_IDLE, hover_color="#616a6b",
                      command=self._close_keypad).grid(row=0, column=0,
                                                       sticky="ew", padx=self.px(5))
        ctk.CTkButton(act, text="HAPUS", height=self.px(46), font=self.F(13, True),
                      fg_color="#34495e", hover_color="#3f5c78",
                      command=lambda: self._keypad_press("C")).grid(
            row=0, column=1, sticky="ew", padx=self.px(5))
        ctk.CTkButton(act, text="OK", height=self.px(46), font=self.F(13, True),
                      fg_color=COLOR_OK, hover_color="#27ae60",
                      command=self._keypad_ok).grid(row=0, column=2,
                                                    sticky="ew", padx=self.px(5))

    def _show_keypad(self, title, hint, value):
        self._keypad_buf = value
        # Nilai lama ditampilkan sebagai acuan, tapi angka PERTAMA yang ditekan
        # menggantinya — perilaku yang diharapkan saat mengetik ulang nilai.
        self._keypad_fresh = True
        self._keypad_hint = hint
        self.kp_title.configure(text=title)
        self.kp_hint.configure(text=hint, text_color=COLOR_IDLE)
        self.kp_value.configure(text=value or "0")
        self.keypad.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.keypad.tkraise()

    def _open_keypad(self, entry, name):
        """Papan angka untuk kolom input misi."""
        self._keypad_target = entry
        self._keypad_move = None
        self._show_keypad(name, "isi nilai lalu tekan OK", entry.get().strip())
        return "break"

    def _open_keypad_manual(self, move, title):
        """Papan angka untuk nilai perintah manual: meter (FW) / derajat."""
        self._keypad_target = None
        self._keypad_move = move
        lo, hi, unit = self._manual_range(move)
        self._show_keypad(f"{title}  ({move})",
                          f"rentang sah {lo:g}–{hi:g} {unit}",
                          self._manual_text(move))

    def _close_keypad(self):
        self.keypad.place_forget()
        self._keypad_target = None
        self._keypad_move = None

    def _keypad_press(self, ch):
        if ch in ("C", "⌫"):
            self._keypad_buf = "" if ch == "C" else self._keypad_buf[:-1]
            self._keypad_fresh = False
        else:
            if self._keypad_fresh:
                self._keypad_buf = ""        # ketikan pertama mengganti nilai lama
                self._keypad_fresh = False
            if ch == ".":
                # MAJU dalam meter boleh pecahan (mis. 2.5 m); PUTAR selalu
                # bilangan bulat derajat sesuai protokol.
                allow_dot = self._keypad_move in (None, MOVE_FW)
                if allow_dot and "." not in self._keypad_buf:
                    self._keypad_buf += "."
            else:
                self._keypad_buf += ch
        self.kp_value.configure(text=self._keypad_buf or "0")
        self.kp_hint.configure(text=self._keypad_hint, text_color=COLOR_IDLE)

    def _keypad_ok(self):
        text = self._keypad_buf.strip()
        if self._keypad_move is not None:
            move = self._keypad_move
            lo, hi, unit = self._manual_range(move)
            try:
                num = float(text or 0)
            except ValueError:
                num = float(self.manual_val[move])
            val = round(num, 1) if move == MOVE_FW else int(num)
            if not (lo <= val <= hi):
                self.kp_hint.configure(
                    text=f"nilai harus {lo:g}–{hi:g} {unit}", text_color=COLOR_BAD)
                return
            self.manual_val[move] = val
            self._update_manual_card(move)
        elif self._keypad_target is not None:
            self._keypad_target.delete(0, "end")
            self._keypad_target.insert(0, text)
            self._refresh_plan()
        self._close_keypad()

    # ==================================================================
    # AKSI: MISI
    # ==================================================================

    def _on_send_mission(self):
        self._refresh_plan()
        if self.plan is None or not self.queue:
            messagebox.showerror(
                "Input belum sah",
                "Panjang & Lebar tambak harus berupa angka lebih dari 0.")
            return
        if not self._ready_to_move():
            return

        started, msg = self.runner.run(self.queue, label="MISI")
        if not started:
            messagebox.showwarning("Belum bisa dikirim", msg)
            return

        p = self.plan
        self.logger.log(
            "MISI",
            f"Misi {p.panjang_m:g}x{p.lebar_m:g} m dimulai — {len(self.queue)} "
            f"perintah, {p.n_lanes} jalur, mulai {CORNER_LABEL[p.start_corner]}, "
            f"~{queue_duration_s(self.queue, p.speed_mps):.0f} s")
        self.show_page("BERANDA")

    def _ready_to_move(self) -> bool:
        """Prasyarat sebelum perintah gerak apa pun dikirim."""
        if not self.motor_armed:
            messagebox.showwarning(
                "Motor dimatikan",
                "Nyalakan komponen Motor di halaman SISTEM terlebih dahulu.")
            return False
        if not self.link.tx_enabled:
            messagebox.showwarning(
                "NRF dimatikan",
                "Aktifkan NRF24 di halaman SISTEM terlebih dahulu.")
            return False
        return True

    # ==================================================================
    # AKSI: MANUAL & STOP
    # ==================================================================

    def _manual_step(self, move, delta):
        lo, hi, _ = self._manual_range(move)
        val = max(lo, min(hi, self.manual_val[move] + delta))
        self.manual_val[move] = round(val, 1) if move == MOVE_FW else int(val)
        self._update_manual_card(move)

    def _on_send_manual(self, move):
        """
        MAJU: jarak METER dipecah jadi antrean paket FW 10-200 cm.
        PUTAR: satu paket CW/CCW sesuai derajat.
        """
        if move == MOVE_FW:
            meters = float(self.manual_val[move])
            cmds = split_forward(meters)
            if not cmds:
                messagebox.showerror(
                    "Jarak terlalu pendek",
                    f"Jarak maju minimal {MANUAL_FW_MIN_M:g} m "
                    f"(paket FW terkecil 10 cm).")
                return
            human = (f"Maju {meters:g} m — {len(cmds)} paket "
                     f"{cmds[0].encode().decode()}"
                     + (f" ×{len(cmds)}" if len(cmds) > 1 else ""))
        else:
            cmd = RobotCommand(move, int(self.manual_val[move]))
            ok, msg = cmd.validate()
            if not ok:
                messagebox.showerror("Nilai di luar rentang", msg)
                return
            cmds, human = [cmd], f"[{cmd.encode().decode()}] — {cmd.human()}"

        if not self._ready_to_move():
            return
        started, msg = self.runner.run(cmds, label="MANUAL")
        if not started:
            messagebox.showwarning("Belum bisa dikirim", msg)
            return
        self.logger.log("MANUAL", f"Perintah manual {human}")
        self.show_page("BERANDA")

    def _on_stop(self):
        """Berhenti darurat — dapat ditekan dari halaman mana pun."""
        ok = self.runner.abort()
        self.logger.log("STOP", "Berhenti darurat — STOP:0 " +
                        ("terkirim" if ok else "GAGAL (cek NRF)"))

    # ==================================================================
    # PERENCANAAN JALUR
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

    def _on_corner_select(self, label):
        self.start_corner = LABEL_TO_CORNER.get(label, "BL")
        self._refresh_plan()

    def _refresh_plan(self):
        P = self._read_float(self.entry_panjang)
        L = self._read_float(self.entry_lebar)
        lw = self._read_float(self.entry_lanew, LANE_WIDTH_M) or LANE_WIDTH_M
        spd = self._read_float(self.entry_speed, ROBOT_SPEED_MPS) or ROBOT_SPEED_MPS
        if P is None or L is None or P <= 0 or L <= 0:
            self.plan, self.queue = None, []
        else:
            self.plan = plan_coverage(P, L, lw, spd, self.start_corner)
            self.queue = plan_command_queue(self.plan)
        self._draw_pond()
        self._render_queue()

    def _render_queue(self):
        """Daftar perintah yang BENAR-BENAR akan dikirim ke robot."""
        self.seg_box.configure(state="normal")
        self.seg_box.delete("1.0", "end")
        if self.queue:
            for i, c in enumerate(self.queue, 1):
                self.seg_box.insert(
                    "end", f"{i:3d}. {c.encode().decode():<9} {c.human()}\n")
        else:
            self.seg_box.insert("end", "(belum ada perintah — isi dimensi tambak)\n")
        self.seg_box.configure(state="disabled")

        if not self.plan or not self.queue:
            self.lbl_plan_info.configure(text="Isi Panjang & Lebar tambak",
                                         text_color=COLOR_IDLE)
            return
        p = self.plan
        self.lbl_plan_info.configure(
            text=(f"{p.n_lanes} jalur · {p.total_distance_m:.1f} m · "
                  f"{len(self.queue)} perintah · ~{p.est_time_s:.0f} s   |   "
                  f"mulai {CORNER_LABEL[p.start_corner]}"),
            text_color=COLOR_OK)

    def _pond_geometry(self):
        """Return (ox, oy, scale, pond_w, pond_h) atau None."""
        if not self.plan or self.plan.panjang_m <= 0 or self.plan.lebar_m <= 0:
            return None
        c = self.canvas
        W, H = c.winfo_width(), c.winfo_height()
        if W < 20 or H < 20:
            return None
        margin = self.px(20)
        pond_w, pond_h = self.plan.lebar_m, self.plan.panjang_m
        scale = min((W - 2 * margin) / pond_w, (H - 2 * margin) / pond_h)
        return ((W - pond_w * scale) / 2, (H - pond_h * scale) / 2,
                scale, pond_w, pond_h)

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
        left, bottom = x < pond_w / 2, y < pond_h / 2
        code = ("BL" if left else "BR") if bottom else ("TL" if left else "TR")
        self.start_corner = code
        self.opt_corner.set(CORNER_LABEL[code])
        self._refresh_plan()

    def _draw_pond(self):
        c = self.canvas
        c.delete("all")
        geo = self._pond_geometry()
        if not geo:
            W = max(c.winfo_width(), 120)
            H = max(c.winfo_height(), 80)
            c.create_text(W // 2, H // 2, text="Isi dimensi tambak",
                          fill=COLOR_IDLE, font=self.F(10))
            return
        ox, oy, scale, pond_w, pond_h = geo
        plan = self.plan
        if plan is None:
            return

        def tx(x, y):
            return ox + x * scale, oy + (pond_h - y) * scale

        x0, y0 = tx(0, 0)
        x1, y1 = tx(pond_w, pond_h)
        c.create_rectangle(x0, y1, x1, y0, outline="#2c6da3",
                           width=self.px(2), fill="#12232e")

        # garis bantu antar-lintasan
        n = 1
        while n * plan.lane_width_m < pond_w - 1e-9:
            gx, _ = tx(n * plan.lane_width_m, 0)
            c.create_line(gx, y1, gx, y0, fill="#1c3a4d")
            n += 1

        # jalur (polyline berpanah)
        pts = [tx(px_, py_) for (px_, py_) in plan.waypoints]
        for i in range(len(pts) - 1):
            c.create_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                          fill=COLOR_OK, width=self.px(2), arrow="last",
                          arrowshape=(self.px(8), self.px(9), self.px(3)))

        if pts:
            sx, sy = pts[0]
            r = self.px(5)
            c.create_oval(sx - r, sy - r, sx + r, sy + r, fill=COLOR_WARN,
                          outline="")
            c.create_text(sx, sy - self.px(12), text="START", fill=COLOR_WARN,
                          font=self.F(7, True))

        c.create_text((x0 + x1) / 2, y0 + self.px(10),
                      text=f"lebar {pond_w:g} m", fill=COLOR_IDLE,
                      font=self.F(7))

    # ==================================================================
    # KOMPONEN / SIMULASI / MPU
    # ==================================================================

    def _on_toggle_nrf(self):
        on = bool(self.sw_nrf.get())            # type: ignore
        self.link.tx_enabled = on
        self.logger.log("KOMPONEN", f"NRF TX di-{'AKTIFKAN' if on else 'MATIKAN'}")

    def _on_toggle_heartbeat(self):
        self.heartbeat_enabled = bool(self.sw_heartbeat.get())   # type: ignore
        self.logger.log(
            "KOMPONEN",
            f"Heartbeat PING di-{'AKTIFKAN' if self.heartbeat_enabled else 'MATIKAN'}"
            + ("" if self.heartbeat_enabled else " (robot failsafe stop ~3 s)"))

    def _on_toggle_motor(self):
        on = bool(self.sw_motor.get())          # type: ignore
        self.motor_armed = on
        if not on:
            self.runner.abort()                 # matikan motor secara REAL
            self.logger.log("KOMPONEN", "Motor DIMATIKAN (STOP:0 terkirim)")
        else:
            self.logger.log("KOMPONEN", "Motor DIAKTIFKAN (siap menerima perintah)")

    def _on_sim_toggle(self):
        online = bool(self.sw_sim_online.get())
        self.link.set_sim_robot_reachable(online)
        self.logger.log("SIMULASI",
                        f"Robot virtual di-set {'ONLINE' if online else 'OFFLINE'}")

    # ---- pindah mode REAL / SIMULASI --------------------------------

    def _on_toggle_mode(self):
        """Tombol MODE di bilah atas: balik ke mode seberangnya."""
        self._set_mode(simulation=not self.link.simulation)

    def _on_mode_segment(self, value):
        """Pemilih MODE KERJA di halaman SISTEM."""
        self._set_mode(simulation=(value == "SIMULASI"))

    def _set_mode(self, simulation: bool):
        """
        Pindah lawan bicara radio. Ditolak selagi ada perintah berjalan supaya
        robot tidak ditinggalkan bergerak tanpa pengendali.
        """
        if simulation == self.link.simulation:
            self._sync_mode_widgets()
            return
        if self.runner.is_busy():
            messagebox.showwarning(
                "Perintah sedang berjalan",
                "Tekan STOP dulu sebelum berpindah mode REAL/SIMULASI.")
            self._sync_mode_widgets()
            return

        ok, msg = self.link.set_mode(simulation)
        self.want_simulation = self.link.simulation
        self.logger.log("MODE", msg)
        # sinkronkan lagi keadaan yang dipegang GUI ke radio yang baru
        self.link.tx_enabled = bool(self.sw_nrf.get())          # type: ignore
        self.link.set_sim_robot_reachable(bool(self.sw_sim_online.get()))
        self._sync_mode_widgets()
        if not ok:
            messagebox.showwarning("Mode REAL tidak tersedia", msg)

    def _sync_mode_widgets(self):
        """Samakan tampilan tombol MODE (bilah atas) & pemilih di SISTEM."""
        sim = self.link.simulation
        text = "SIMULASI" if sim else "REAL"
        color = COLOR_WARN if sim else COLOR_OK
        self.chip_mode.configure(text=text, text_color=color)
        if self.seg_mode.get() != text:
            self.seg_mode.set(text)

    # ---- MPU (telemetri NRF, tanpa port) ----------------------------

    def _on_mpu_record(self):
        msg = self.mpu.set_logging(bool(self.sw_mpu_record.get()))
        self.logger.log("MPU", msg)

    # ---- auto-simpan log --------------------------------------------

    def _on_toggle_autosave(self):
        """
        Nyalakan/matikan penulisan tiap baris log ke berkas TXT. Berkas dibuat
        otomatis di folder logs/ (tanpa dialog — layar sentuh tanpa keyboard).
        """
        if not self.sw_autosave.get():
            _, msg = self.logger.set_autosave(None)
            self.logger.log("LOG", msg)
            self.lbl_autosave.configure(
                text="nonaktif — catatan hanya tersimpan di memori",
                text_color=COLOR_IDLE)
            return

        ok, msg = self.logger.set_autosave(default_log_path())
        self.logger.log("LOG", msg)
        if not ok:
            self.sw_autosave.deselect()
            self.lbl_autosave.configure(text=msg, text_color=COLOR_BAD)
            messagebox.showerror("Auto-simpan gagal", msg)
            return
        # Tampilkan nama berkasnya saja — path lengkap terlalu panjang untuk
        # layar 7 inci (dan sudah tercatat utuh di baris log di bawahnya).
        path = self.logger.autosave_path or ""
        self.lbl_autosave.configure(
            text=f"menulis ke {os.path.join(LOG_DIR_NAME, os.path.basename(path))}",
            text_color=COLOR_OK)

    # ==================================================================
    # EKSPOR LOG
    # ==================================================================

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
        self._log_shown = 0
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ==================================================================
    # LATAR: heartbeat + penyegaran tampilan
    # ==================================================================

    def _heartbeat_loop(self):
        """
        PING berkala saat tidak ada perintah berjalan: menjaga failsafe robot
        dan memancing telemetri MPU balik. Saat CommandRunner aktif, ia sudah
        menyelipkan PING sendiri — jangan ditambah supaya tidak rebutan radio.
        """
        while True:
            if self.heartbeat_enabled and not self.runner.is_busy():
                self.link.ping()
            time.sleep(HEARTBEAT_INTERVAL_S)

    def _ui_tick(self):
        """Satu-satunya tempat tampilan diperbarui — selalu di thread utama."""
        if self._closing:
            return
        self._refresh_status_chips()
        self._refresh_runner_view()
        self._refresh_components()
        self._refresh_gauges()
        self._refresh_mpu()
        self._refresh_autosave()
        self._drain_log()
        self.after(self.UI_TICK_MS, self._ui_tick)

    def _refresh_autosave(self):
        """
        Auto-simpan bisa mati sendiri bila berkas gagal ditulis (mis. kartu SD
        penuh / dicabut). Tarik keadaan sebenarnya dari logger supaya tombol
        tidak menampilkan 'aktif' padahal tidak ada yang tersimpan.
        """
        if self.sw_autosave.get() and self.logger.autosave_path is None:
            self.sw_autosave.deselect()
            self.lbl_autosave.configure(
                text=f"auto-simpan BERHENTI: {self.logger.autosave_error}",
                text_color=COLOR_BAD)

    def _refresh_status_chips(self):
        self._sync_mode_widgets()
        self.chip_module.configure(
            text="ADA" if self.link.module_present else "TIDAK ADA",
            text_color=COLOR_OK if self.link.module_present else COLOR_BAD)
        reachable = self.link.robot_reachable()
        self.chip_robot.configure(
            text="TERHUBUNG" if reachable else "TERPUTUS",
            text_color=COLOR_OK if reachable else COLOR_BAD)

    def _refresh_runner_view(self):
        st = self.runner.state
        color = {RunStatus.IDLE: COLOR_IDLE, RunStatus.DONE: COLOR_OK,
                 RunStatus.RUNNING: COLOR_OK, RunStatus.SENDING: COLOR_WARN,
                 RunStatus.RETRYING: COLOR_WARN, RunStatus.ABORTED: COLOR_BAD,
                 RunStatus.FAILED: COLOR_BAD}.get(st.status, COLOR_IDLE)
        self.home_status.configure(text=st.status.value, text_color=color)

        if st.command is not None:
            self.home_cmd.configure(
                text=f"{st.command.encode().decode()}   —   {st.command.human()}")
            extra = f"percobaan ke-{st.attempt}" if st.attempt > 1 else ""
            self.home_detail.configure(
                text=f"perintah {st.index} dari {st.total}  ·  {st.label}  {extra}")
        else:
            self.home_cmd.configure(text=st.message or "Belum ada perintah berjalan")
            self.home_detail.configure(
                text=f"{st.total} perintah terkirim" if st.total else "—")
        self.home_progress.set(st.queue_progress)

        if st.running:
            self.tile_queue.configure(text=f"{st.index} / {st.total}")
            sisa = max(0.0, queue_duration_s(self.queue[st.index:], ROBOT_SPEED_MPS)
                       if st.label == "MISI" else st.cmd_expected_s)
            self.tile_eta.configure(text=f"{sisa:.0f} s")
        else:
            self.tile_queue.configure(
                text=f"{len(self.queue)} siap" if self.queue else "—")
            self.tile_eta.configure(
                text=f"{self.plan.est_time_s:.0f} s" if self.plan else "—")

        tel = self.link.get_telemetry()
        self.tile_yaw.configure(text=f"{tel[2]:.0f}°" if tel else "—")

    def _refresh_components(self):
        self.comp_leds["nrf"].configure(
            text_color=COLOR_OK if self.link.tx_enabled else COLOR_BAD)
        self.comp_leds["hb"].configure(
            text_color=COLOR_OK if self.heartbeat_enabled else COLOR_BAD)
        self.comp_leds["motor"].configure(
            text_color=COLOR_OK if self.motor_armed else COLOR_BAD)

        # LED monitor mengikuti perintah yang sedang berjalan
        lp, rp = self.runner.state.pwm()
        self.comp_leds["mleft"].configure(
            text_color=COLOR_OK if lp > STOP_PWM else COLOR_IDLE)
        self.comp_leds["mright"].configure(
            text_color=COLOR_OK if rp > STOP_PWM else COLOR_IDLE)
        self.comp_leds["mpu"].configure(
            text_color=COLOR_OK if self.mpu.latest else COLOR_IDLE)

        auto = self.logger.autosave_path
        self.lbl_sys_info.configure(
            text=(f"Layar   : {self.screen_w} x {self.screen_h} px\n"
                  f"Skala   : {self.S:.2f}x (acuan 800x480)\n"
                  f"Radio   : {'SIMULASI' if self.link.simulation else 'NRF24 nyata'}\n"
                  f"Log MPU : {'AKTIF' if self.mpu.log_enabled else 'nonaktif'}\n"
                  f"Auto-TXT: {'AKTIF' if auto else 'nonaktif'}\n"
                  f"Protokol: FW / CW / CCW / STOP  +  ON & FIN"))

    def _refresh_gauges(self):
        lp, rp = self.runner.state.pwm()
        self._set_gauge(self.gauge_left, lp)
        self._set_gauge(self.gauge_right, rp)

    def _set_gauge(self, gauge, pwm):
        rpm = estimate_rpm(pwm)
        gauge["rpm"].configure(text=f"{rpm:,.0f} RPM",
                               text_color=COLOR_OK if pwm > STOP_PWM else COLOR_IDLE)
        gauge["bar"].set(rpm / RPM_MAX if RPM_MAX else 0)
        gauge["detail"].configure(
            text=f"Throttle {throttle_fraction(pwm)*100:.0f}% · "
                 f"{estimate_speed_mps(pwm):.2f} m/s · PWM {pwm}µs")

    def _refresh_mpu(self):
        """
        Tarik cuplikan MPU terbaru (dan catat bila log MPU menyala). Dipanggil
        tiap tick di HALAMAN MANA PUN, jadi pencatatan tetap jalan walau
        operator sedang membuka halaman lain.
        """
        sample = self.mpu.poll()
        if sample is None:
            for t in self.mpu_tiles.values():
                t.configure(text_color=COLOR_IDLE)
            self.lbl_mpu_src.configure(
                text="menunggu telemetri robot — pastikan heartbeat & robot hidup",
                text_color=COLOR_IDLE)
            return

        for key, v in zip(("roll", "pitch", "yaw"),
                          (sample.roll, sample.pitch, sample.yaw)):
            self.mpu_tiles[key].configure(text=f"{v:.1f}°", text_color=COLOR_OK)

        catat = (f"log AKTIF · {self.mpu.logged} baris tercatat"
                 if self.mpu.log_enabled else "log MPU nonaktif")
        self.lbl_mpu_src.configure(
            text=f"sumber: NRF ({sample.source}) · {self.mpu.samples} cuplikan "
                 f"· {catat}",
            text_color=COLOR_OK)

    # ==================================================================
    # LOG VIEW
    # ==================================================================

    def _drain_log(self):
        """
        Salin catatan baru dari ActivityLogger ke kotak log. Ditarik dari thread
        utama supaya thread radio tidak pernah menyentuh widget Tk.
        """
        events: list[LogEvent] = self.logger.events[self._log_shown:]
        if not events:
            return
        self._log_shown += len(events)
        self.log_box.configure(state="normal")
        for ev in events:
            self.log_box.insert("end", f"[{ev.ts}] ({ev.category}) {ev.message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _on_close(self):
        self._closing = True
        try:
            if self.runner.is_busy():
                self.runner.abort()
            self.mpu.set_logging(False)
            if self.logger.autosave_path:
                self.logger.log("SISTEM", "Aplikasi ditutup — log tersimpan di "
                                          f"{self.logger.autosave_path}")
        finally:
            self.destroy()


if __name__ == "__main__":
    FeederGUI(fullscreen="--windowed" not in sys.argv,
              simulation="--real" not in sys.argv).mainloop()
