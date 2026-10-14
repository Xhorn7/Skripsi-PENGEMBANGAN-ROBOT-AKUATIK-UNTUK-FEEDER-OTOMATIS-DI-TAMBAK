"""
C1 (kotak 1 x 2 m) diukur dari titik belok ke titik belok, lalu digambar seperti
Fig. 4 dan Tabel I pada paper rujukan [1]: rute rencana vs lintasan aktual, dan
lintasan menurut robot (jarak perintah + yaw MPU) disandingkan dengan aktual.

    pip install -r requirements.txt
    python buat_grafik_c1.py --lembar-xy  # sekali: buat Lembar_Data_C1_Koordinat.xlsx
    python buat_grafik_c1.py --lembar     # (cara benang) Lembar_Data_C1_Titik_Belok.xlsx
    python buat_grafik_c1.py --log <log>  # yaw MPU di tiap FIN dari log GUI (kolom Yaw)
    python buat_grafik_c1.py              # setelah lembar diisi & disimpan: buat grafik

Ada dua cara ukur; grafik dan tabelnya sama:

CARA KOORDINAT (dipakai di lapangan, cukup 3 orang). Pipa panjang tidak bisa
berdiri di kolam, jadi botol hanya menandai titik di lantai. Sebelum start
sebuah koin ditaruh tepat di bawah stiker robot (titik S); tiap FIN FW satu
orang menaruh botol di bawah stiker (T1..T4). Setelah robot diangkat, tiap
titik diukur dengan meteran: X dari dinding kiri dan Y dari dinding belakang
(dinding di belakang robot saat start). Jarak, sudut belok, dan galat posisi
dihitung dari koordinat itu. Bila Lembar_Data_C1_Koordinat.xlsx ada, lembar
inilah yang dibaca.

CARA BENANG (rancangan awal, butuh pipa panjang yang dipegang tegak):

Prosedur lengkap di lapangan (alat, dudukan penanda, benang, busur) ada di
Panduan_Pengujian_C1.pdf (buat_panduan_c1.py).

Robot dibiarkan menjalankan kotak tanpa
berhenti untuk diukur. Setiap kali robot selesai maju (FIN FW), satu orang
menaruh DUDUKAN PENANDA (botol isi pasir + pipa pendek + sok) di dasar kolam,
as pipanya tepat di bawah titik acuan robot. Setelah robot selesai, pipa panjang
dicolok ke tiap sok dan pipa yang berurutan dihubungkan dengan BENANG di atas
air, lalu:
    jarak  = meteran sepanjang benang dari penanda ke penanda berikutnya (cm)
    sudut  = busur di tiap penanda, sudut DALAM antara benang ke penanda
             sebelumnya dan benang ke penanda berikutnya (ideal 90°)
    yaw    = yaw MPU dari log GUI saat FIN tiap FW (arah robot di segmen itu)

Posisi tiap titik dihitung dari jarak + sudut tersebut (seperti poligon pada
pengukuran tanah), dimulai dari S dengan segmen pertama searah rencana. Posisi
"menurut robot" memakai jarak perintah (FW berbasis waktu) dan arah dari yaw
MPU, jadi selisihnya dengan posisi aktual adalah galat perhitungan robot.

[1] J. Putra dan D. E. Saputra, "Autonomous Drone Indoor Navigation Based on
    Virtual 3D Map Reference," IEEE, 2022.
"""
import argparse
import math
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from build_skenario import GAMBAR, HERE, INK, ROBOT
from buat_lembar_data import BOX, CENTER, HEAD, ISI, NAVY, RUMUS

XLSX = HERE / "Lembar_Data_C1_Titik_Belok.xlsx"
SHEET = "C1 Titik Belok"
N = 3                                    # pengulangan
BELOK = 90                               # tiap belokan C1 = CW:90

# (segmen, titik ujung, perintah, jarak perintah cm)
SEGMEN = [
    ("S → T1", "T1", "FW:200, lalu CW:90 di T1", 200),
    ("T1 → T2", "T2", "FW:100, lalu CW:90 di T2", 100),
    ("T2 → T3", "T3", "FW:200, lalu CW:90 di T3", 200),
    ("T3 → T4", "T4", "FW:100, lalu CW:90 terakhir di T4", 100),
]
RENCANA = [(0, 0), (0, 200), (100, 200), (100, 0), (0, 0)]   # S, T1..T4 (cm)
BARIS_PER_PERC = len(SEGMEN) + 1                              # + baris "Akhir"

C_RENCANA = "#64748b"                    # rute rencana: abu tua, putus-putus
C_MPU = "#d97706"                        # menurut robot (MPU): oranye

# kolom lembar
K_JARAK, K_SUDUT, K_YAW = 4, 5, 6
K_GJARAK, K_BELOK, K_BELOK_MPU, K_GSUDUT, K_SELISIH, K_KET = 7, 8, 9, 10, 11, 12

# lembar cara koordinat: baris S, T1..T4, Akhir per percobaan
XLSX_XY = HERE / "Lembar_Data_C1_Koordinat.xlsx"
SHEET_XY = "C1 Koordinat"
TITIK_XY = [
    ("S", "Koin di lantai, tepat di bawah stiker robot sebelum perintah pertama"),
    ("T1", "Botol, ditaruh saat FIN FW:200 pertama"),
    ("T2", "Botol, ditaruh saat FIN FW:100 pertama"),
    ("T3", "Botol, ditaruh saat FIN FW:200 kedua"),
    ("T4", "Botol, ditaruh saat FIN FW:100 kedua"),
]
BARIS_XY = len(TITIK_XY) + 1                                  # + baris "Akhir"
X_X, X_Y, X_YAW, X_KET = 4, 5, 6, 16                          # kolom isian


def baris_xy(p, i):
    """Baris Excel lembar koordinat: percobaan p (1..N), titik ke-i (0 = S .. 4 = T4, 5 = Akhir)."""
    return 3 + (p - 1) * BARIS_XY + i


def baris(p, i):
    """Baris Excel untuk percobaan p (1..N), segmen ke-i (0..3) atau 4 = Akhir."""
    return 3 + (p - 1) * BARIS_PER_PERC + i


def maju(p, arah, jarak):
    """Titik baru dari p sejauh `jarak` ke arah `arah` (° searah jarum jam dari depan)."""
    a = math.radians(arah)
    return p[0] + jarak * math.sin(a), p[1] + jarak * math.cos(a)


def selisih_sudut(a, b):
    """|b − a| dalam derajat, dibungkus ke 0..180."""
    return abs((b - a + 180) % 360 - 180)


# ---------------------------------------------------------------- lembar isian
def _kepala(ws, row, headers):
    for c, h in enumerate(headers, start=1):
        if h is None:
            continue
        cell = ws.cell(row=row, column=c, value=h)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.font = HEAD
        cell.alignment = CENTER
        cell.border = BOX


def _sel(ws, r, c, value=None, isi=False, fmt=None, warna=True):
    cell = ws.cell(row=r, column=c, value=value)
    cell.border = BOX
    cell.alignment = CENTER
    if warna:
        cell.fill = PatternFill("solid", fgColor=ISI if isi else RUMUS)
    if fmt:
        cell.number_format = fmt
    return cell


def _teks(ws, r, c, value):
    cell = _sel(ws, r, c, value, warna=False)
    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    return cell


def buat_lembar():
    if XLSX.exists():
        sys.exit(f"{XLSX.name} sudah ada — tidak ditimpa. Pindahkan/ganti nama dulu "
                 "bila memang ingin lembar kosong.")
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    headers = ["Perc.", "Segmen", "Perintah",
               "Jarak aktual (cm) — meteran sepanjang benang antar penanda",
               "Sudut DALAM di titik ujung (°) — busur antara 2 benang",
               "Yaw MPU (°) — rata-rata selama FW (--log)",
               "Galat jarak (cm)", "Sudut belok aktual (°) = 180 − sudut dalam",
               "Sudut belok menurut MPU (°)", "Galat sudut aktual (°)",
               "Selisih MPU vs aktual (°)", "Keterangan"]
    widths = [6, 9, 27, 17, 17, 14, 9, 13, 12, 10, 11, 26]
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws.cell(row=1, column=1, value="C1 — Kotak 1 x 2 m, diukur dari titik belok ke titik belok "
            "(penanda + benang + meteran + busur)").font = Font(bold=True, size=12, color=NAVY)
    ws.freeze_panes = "D3"
    _kepala(ws, 2, headers)
    for c, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.row_dimensions[2].height = 62

    for p in range(1, N + 1):
        s = baris(p, 0)
        ws.merge_cells(start_row=s, start_column=1, end_row=s + BARIS_PER_PERC - 1, end_column=1)
        _sel(ws, s, 1, p, warna=False).font = Font(bold=True)
        for i, (seg, _ujung, perintah, L) in enumerate(SEGMEN):
            r = baris(p, i)
            _sel(ws, r, 2, seg, warna=False)
            _teks(ws, r, 3, perintah)
            for c in (K_JARAK, K_YAW, K_KET):
                _sel(ws, r, c, isi=True)
            _sel(ws, r, K_GJARAK, f'=IF(D{r}="","",D{r}-{L})', fmt="0.0")
            yaw_next = f"F{r + 1}"           # segmen berikutnya, atau baris Akhir
            _sel(ws, r, K_BELOK_MPU, f'=IF(OR(F{r}="",{yaw_next}=""),"",'
                 f'ABS(MOD({yaw_next}-F{r}+180,360)-180))', fmt="0.0")
            if i < len(SEGMEN) - 1:
                _sel(ws, r, K_SUDUT, isi=True)
                _sel(ws, r, K_BELOK, f'=IF(E{r}="","",180-E{r})', fmt="0.0")
                _sel(ws, r, K_GSUDUT, f'=IF(H{r}="","",ABS(H{r}-{BELOK}))', fmt="0.0")
                _sel(ws, r, K_SELISIH, f'=IF(OR(H{r}="",I{r}=""),"",ABS(I{r}-H{r}))', fmt="0.0")
            else:                                # belokan terakhir tak punya benang keluar
                for c in (K_SUDUT, K_BELOK, K_GSUDUT, K_SELISIH):
                    _sel(ws, r, c, "—")
        r = baris(p, len(SEGMEN))
        _sel(ws, r, 2, "Akhir", warna=False)
        _teks(ws, r, 3, "Setelah CW:90 terakhir, robot diam. Kolom D: jarak penanda T4 ke S "
              "(opsional, cek ukuran)")
        ws.row_dimensions[r].height = 30
        for c in (K_JARAK, K_YAW, K_KET):
            _sel(ws, r, c, isi=True)
        for c in (K_SUDUT, K_GJARAK, K_BELOK, K_BELOK_MPU, K_GSUDUT, K_SELISIH):
            _sel(ws, r, c, "—")

    # Ringkasan per segmen (rata-rata percobaan yang sudah diisi)
    r0 = baris(N, BARIS_PER_PERC) + 1
    ws.cell(row=r0, column=2, value="Ringkasan per segmen (rata-rata percobaan yang sudah "
            "diisi). Posisi tiap titik dihitung oleh buat_grafik_c1.py.").font = Font(
        bold=True, size=11, color=NAVY)
    _kepala(ws, r0 + 1, [None, "Segmen", None, "MAE jarak (cm)", "MAPE jarak (%)",
                         None, None, "MAE sudut belok (°)", None, None,
                         "MAE MPU vs aktual (°)"])
    for i, (seg, _ujung, _perintah, L) in enumerate(SEGMEN):
        r = r0 + 2 + i
        rows = [baris(p, i) for p in range(1, N + 1)]
        g = ",".join(f"G{x}" for x in rows)
        abs_g = ",".join(f'IF(ISNUMBER(G{x}),ABS(G{x}),0)' for x in rows)
        _sel(ws, r, 2, seg, warna=False)
        _sel(ws, r, 4, f'=IF(COUNT({g})=0,"",SUM({abs_g})/COUNT({g}))', fmt="0.0")
        _sel(ws, r, 5, f'=IF(D{r}="","",D{r}/{L}*100)', fmt="0.0")
        if i < len(SEGMEN) - 1:
            _sel(ws, r, 8, f'=IFERROR(AVERAGE({",".join(f"J{x}" for x in rows)}),"")', fmt="0.0")
            _sel(ws, r, 11, f'=IFERROR(AVERAGE({",".join(f"K{x}" for x in rows)}),"")', fmt="0.0")
        else:
            _sel(ws, r, 8, "—")
            _sel(ws, r, 11, "—")

    catatan = (
        "Kuning = diisi manual. Abu-abu = otomatis, jangan diketik.",
        "1. Robot dibiarkan menjalankan kotak; tiap perintah dikirim segera setelah FIN "
        "sebelumnya. Robot tidak dihentikan untuk diukur.",
        "2. Saat FIN tiap FW muncul (robot sampai di titik belok), satu orang menaruh penanda "
        "di dasar kolam tepat di bawah titik acuan robot (stiker, sedekat mungkin ke tengah).",
        "3. Setelah robot selesai, hubungkan penanda berurutan (S–T1–T2–T3–T4) dengan benang "
        "di atas air.",
        "4. Kolom D: meteran sepanjang benang. Kolom E: busur di penanda, sudut DALAM antara "
        "benang ke penanda sebelumnya dan berikutnya (ideal 90°).",
        "5. Kolom F: rata-rata yaw selama tiap FW dari log GUI (--log, kolom Rata2 FW); baris "
        "Akhir = yaw 3 s setelah CW:90 terakhir dan robot diam. Gyro wajib terkalibrasi (robot diam saat dinyalakan).",
        "6. Sudut di T4 tidak bisa diukur dengan benang (tidak ada segmen sesudahnya), jadi "
        "hanya sudut MPU-nya yang ada. Setelah disimpan, jalankan python buat_grafik_c1.py.",
    )
    r1 = r0 + 3 + len(SEGMEN)
    for k, t in enumerate(catatan, start=r1):
        ws.cell(row=k, column=1, value=t).font = Font(italic=k == r1, size=9 if k == r1 else 10)
    wb.save(XLSX)
    print(f"XLSX : {XLSX}")


def buat_lembar_xy():
    if XLSX_XY.exists():
        sys.exit(f"{XLSX_XY.name} sudah ada — tidak ditimpa. Pindahkan/ganti nama dulu "
                 "bila memang ingin lembar kosong.")
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_XY
    headers = ["Perc.", "Titik", "Penanda / kapan diukur",
               "X (cm) — meteran dari dinding KIRI", "Y (cm) — meteran dari dinding BELAKANG",
               "Yaw MPU (°) — rata-rata selama FW (--log)",
               "x thd S (cm)", "y thd S (cm)", "Jarak dari titik sebelumnya (cm)",
               "Galat jarak (cm)", "Sudut belok aktual (°)", "Galat sudut (°)",
               "Sudut belok menurut MPU (°)", "Selisih MPU vs aktual (°)",
               "Galat posisi vs rencana (cm)", "Keterangan"]
    widths = [6, 6, 30, 12, 13, 12, 8, 8, 11, 8, 9, 8, 10, 10, 10, 24]
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws.cell(row=1, column=1, value="C1 — Kotak 1 x 2 m, posisi tiap titik diukur dengan meteran "
            "dari dinding kiri (X) dan dinding belakang (Y)").font = Font(
        bold=True, size=12, color=NAVY)
    ws.freeze_panes = "A3"
    _kepala(ws, 2, headers)
    for c, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.row_dimensions[2].height = 62

    for p in range(1, N + 1):
        s = baris_xy(p, 0)
        ws.merge_cells(start_row=s, start_column=1, end_row=s + BARIS_XY - 1, end_column=1)
        _sel(ws, s, 1, p, warna=False).font = Font(bold=True)
        for i, (kode, ket) in enumerate(TITIK_XY):
            r = baris_xy(p, i)
            _sel(ws, r, 2, kode, warna=False).font = Font(bold=True)
            _teks(ws, r, 3, ket)
            for c in (X_X, X_Y, X_KET):
                _sel(ws, r, c, isi=True)
            _sel(ws, r, 7, f'=IF(OR(D{r}="",D{s}=""),"",D{r}-D{s})', fmt="0.0")
            _sel(ws, r, 8, f'=IF(OR(E{r}="",E{s}=""),"",E{r}-E{s})', fmt="0.0")
            if i == 0:                       # S hanya titik acuan
                for c in [X_YAW] + list(range(9, 16)):
                    _sel(ws, r, c, "—")
                continue
            q = r - 1
            L = SEGMEN[i - 1][3]
            xr, yr = RENCANA[i]
            _sel(ws, r, X_YAW, isi=True)
            _sel(ws, r, 9, f'=IF(OR(D{r}="",E{r}="",D{q}="",E{q}=""),"",'
                 f'SQRT((D{r}-D{q})^2+(E{r}-E{q})^2))', fmt="0.0")
            _sel(ws, r, 10, f'=IF(I{r}="","",I{r}-{L})', fmt="0.0")
            _sel(ws, r, 13, f'=IF(OR(F{r}="",F{r + 1}=""),"",'
                 f'ABS(MOD(F{r + 1}-F{r}+180,360)-180))', fmt="0.0")
            _sel(ws, r, 15, f'=IF(OR(G{r}="",H{r}=""),"",SQRT((G{r}-{xr})^2+(H{r}-{yr})^2))',
                 fmt="0.0")
            if i < len(TITIK_XY) - 1:
                n = r + 1
                # arah segmen = ATAN2(dy, dx) → derajat searah jarum jam dari arah maju (Y)
                _sel(ws, r, 11, f'=IF(OR(D{q}="",E{q}="",D{r}="",E{r}="",D{n}="",E{n}=""),"",'
                     f'IFERROR(MOD(DEGREES(ATAN2(E{n}-E{r},D{n}-D{r}))'
                     f'-DEGREES(ATAN2(E{r}-E{q},D{r}-D{q}))+180,360)-180,""))', fmt="0.0")
                _sel(ws, r, 12, f'=IF(K{r}="","",ABS(K{r}-{BELOK}))', fmt="0.0")
                _sel(ws, r, 14, f'=IF(OR(K{r}="",M{r}=""),"",ABS(M{r}-ABS(K{r})))', fmt="0.0")
            else:                            # belokan terakhir tak punya segmen sesudahnya
                for c in (11, 12, 14):
                    _sel(ws, r, c, "—")
        r = baris_xy(p, len(TITIK_XY))
        _sel(ws, r, 2, "Akhir", warna=False).font = Font(bold=True)
        _teks(ws, r, 3, "Yaw 3 detik setelah FIN CW:90 terakhir (robot sudah diam)")
        for c in (X_YAW, X_KET):
            _sel(ws, r, c, isi=True)
        for c in [X_X, X_Y] + list(range(7, 16)):
            _sel(ws, r, c, "—")

    # Ringkasan per titik (rata-rata percobaan yang sudah diisi)
    r0 = baris_xy(N, BARIS_XY) + 1
    ws.cell(row=r0, column=2, value="Ringkasan per titik (rata-rata percobaan yang sudah "
            "diisi). Grafik dibuat oleh buat_grafik_c1.py.").font = Font(
        bold=True, size=11, color=NAVY)
    _kepala(ws, r0 + 1, [None, "Titik", None, None, None, None, None, None,
                         "MAE jarak (cm)", "MAPE jarak (%)", None, "MAE sudut (°)", None,
                         "MAE MPU vs aktual (°)", "MAE posisi (cm)"])
    for i, (kode, _ket) in enumerate(TITIK_XY[1:], start=1):
        r = r0 + 1 + i
        rows = [baris_xy(p, i) for p in range(1, N + 1)]
        j = ",".join(f"J{x}" for x in rows)
        abs_j = ",".join(f'IF(ISNUMBER(J{x}),ABS(J{x}),0)' for x in rows)
        _sel(ws, r, 2, kode, warna=False)
        _sel(ws, r, 9, f'=IF(COUNT({j})=0,"",SUM({abs_j})/COUNT({j}))', fmt="0.0")
        _sel(ws, r, 10, f'=IF(I{r}="","",I{r}/{SEGMEN[i - 1][3]}*100)', fmt="0.0")
        if i < len(TITIK_XY) - 1:
            _sel(ws, r, 12, f'=IFERROR(AVERAGE({",".join(f"L{x}" for x in rows)}),"")', fmt="0.0")
            _sel(ws, r, 14, f'=IFERROR(AVERAGE({",".join(f"N{x}" for x in rows)}),"")', fmt="0.0")
        else:
            _sel(ws, r, 12, "—")
            _sel(ws, r, 14, "—")
        _sel(ws, r, 15, f'=IFERROR(AVERAGE({",".join(f"O{x}" for x in rows)}),"")', fmt="0.0")

    catatan = (
        "Kuning = diisi manual. Abu-abu = otomatis, jangan diketik.",
        "1. Sebelum start: taruh koin di lantai tepat di bawah stiker robot (S). Robot menghadap "
        "memanjang kolam, sejajar dinding samping.",
        "2. Tiap FIN FW: orang di air menaruh botol dengan as pipa tepat di bawah stiker "
        "(T1, T2, T3, T4). Robot tidak dipegang.",
        "3. Setelah robot diangkat: ukur tiap titik dengan meteran. X = dari dinding KIRI, "
        "Y = dari dinding BELAKANG (di belakang robot saat start). Meteran sejajar garis nat, "
        "baca tepat di atas as pipa / koin.",
        "4. Kolom Yaw: rata-rata yaw selama tiap FW dari log GUI (python buat_grafik_c1.py "
        "--log <log>, kolom Rata2 FW); baris Akhir = yaw 3 s setelah CW:90 terakhir. Gyro wajib "
        "terkalibrasi.",
        "5. Isi angka hasil ukur apa adanya. Bila belum diukur, kosongkan — jangan diisi "
        "angka perintah (200/100/90).",
    )
    r1 = r0 + 2 + len(TITIK_XY)
    for k, t in enumerate(catatan, start=r1):
        ws.cell(row=k, column=1, value=t).font = Font(italic=k == r1, size=9 if k == r1 else 10)
    wb.save(XLSX_XY)
    print(f"XLSX : {XLSX_XY}")


# ---------------------------------------------------------------- baca & hitung
def angka(v):
    if v is None or v == "" or v == "—":
        return None
    if isinstance(v, str):
        try:
            return float(v.strip().replace(",", "."))
        except ValueError:
            return None
    return float(v)


def lintasan(jarak, belok):
    """Titik S, T1.. dari jarak tiap segmen dan sudut belok di ujungnya (searah jarum jam)."""
    pts, arah = [(0.0, 0.0)], 0.0
    for i, L in enumerate(jarak):
        if L is None:
            break
        pts.append(maju(pts[-1], arah, L))
        if i < len(jarak) - 1:
            if belok[i] is None:
                break
            arah += belok[i]
    return pts


def baca(path):
    """Baca isian kuning saja (tidak bergantung pada nilai rumus tersimpan)."""
    ws = load_workbook(path)[SHEET]
    data = []
    for p in range(1, N + 1):
        def sel(i, c):
            return angka(ws.cell(row=baris(p, i), column=c).value)
        jarak = [sel(i, K_JARAK) for i in range(len(SEGMEN))]
        dalam = [sel(i, K_SUDUT) for i in range(len(SEGMEN) - 1)]
        yaw = [sel(i, K_YAW) for i in range(BARIS_PER_PERC)]
        tutup = sel(len(SEGMEN), K_JARAK)
        if all(x is None for x in jarak + dalam + yaw):
            continue
        belok = [None if d is None else 180 - d for d in dalam]
        belok_mpu = [None if a is None or b is None else selisih_sudut(a, b)
                     for a, b in zip(yaw, yaw[1:])]
        aktual = lintasan(jarak, belok)
        robot = lintasan([L for *_x, L in SEGMEN], belok_mpu)
        galat = [math.dist(a, r) for a, r in zip(aktual[1:], RENCANA[1:])]
        galat_mpu = [math.dist(m, a) for m, a in zip(robot[1:], aktual[1:])]
        data.append(dict(perc=p, jarak=jarak, belok=belok, belok_mpu=belok_mpu, tutup=tutup,
                         aktual=aktual, robot=robot, galat=galat, galat_mpu=galat_mpu,
                         sumber="meteran + busur"))
    return data


def arah(a, b):
    """Arah segmen a→b dalam derajat, searah jarum jam dari arah maju (+y)."""
    return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))


def baca_xy(path):
    """Baca lembar cara koordinat: titik aktual langsung dari X/Y, relatif terhadap S."""
    ws = load_workbook(path)[SHEET_XY]
    data = []
    for p in range(1, N + 1):
        def sel(i, c):
            return angka(ws.cell(row=baris_xy(p, i), column=c).value)
        xy = [(sel(i, X_X), sel(i, X_Y)) for i in range(len(TITIK_XY))]
        yaw = [sel(i, X_YAW) for i in range(1, BARIS_XY)]           # T1..T4 + Akhir
        if all(v is None for v in [c for t in xy for c in t] + yaw):
            continue
        if None in xy[0]:
            print(f"Perc. {p}: X/Y titik S kosong — percobaan dilewati.")
            continue
        aktual = []
        for x, y in xy:
            if x is None or y is None:
                break
            aktual.append((x - xy[0][0], y - xy[0][1]))
        jarak = [math.dist(a, b) for a, b in zip(aktual, aktual[1:])]
        jarak += [None] * (len(SEGMEN) - len(jarak))
        belok = [(arah(b, c) - arah(a, b) + 180) % 360 - 180
                 for a, b, c in zip(aktual, aktual[1:], aktual[2:])][:len(SEGMEN) - 1]
        belok_mpu = [None if a is None or b is None else selisih_sudut(a, b)
                     for a, b in zip(yaw, yaw[1:])]
        robot = lintasan([L for *_x, L in SEGMEN], belok_mpu)
        galat = [math.dist(a, r) for a, r in zip(aktual[1:], RENCANA[1:])]
        galat_mpu = [math.dist(m, a) for m, a in zip(robot[1:], aktual[1:])]
        data.append(dict(perc=p, jarak=jarak, belok=belok, belok_mpu=belok_mpu, tutup=None,
                         aktual=aktual, robot=robot, galat=galat, galat_mpu=galat_mpu,
                         sumber="meteran dari dinding"))
    return data


def rata(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def kolom(rows, i):
    return [r[i] if i < len(r) else None for r in rows]


def f(x, n=1):
    return "—" if x is None else f"{x:.{n}f}".replace(".", ",")


# ---------------------------------------------------------------- grafik
def _batas(data):
    """Batas peta (kelipatan 50 cm) yang memuat semua titik, minimal −50..150 × −50..250."""
    pts = RENCANA + [p for d in data for p in d["aktual"] + d["robot"]]
    lo = lambda v, m: min(m, 50 * math.floor((v - 10) / 50))
    hi = lambda v, m: max(m, 50 * math.ceil((v + 10) / 50))
    return (lo(min(x for x, _ in pts), -50), hi(max(x for x, _ in pts), 150),
            lo(min(y for _, y in pts), -50), hi(max(y for _, y in pts), 250))


def _gaya_peta(ax, batas):
    x0, x1, y0, y1 = batas
    ax.set_aspect("equal")
    ax.set_xlim(x0, x1 + 10)
    ax.set_ylim(y0, y1 + 10)
    ax.set_xticks(range(x0, x1 + 1, 50))
    ax.set_yticks(range(y0, y1 + 1, 50))
    ax.set_xticks(range(x0, x1 + 1, 25), minor=True)
    ax.set_yticks(range(y0, y1 + 1, 25), minor=True)
    ax.grid(which="both", color="#e2e8f0", lw=0.6)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=INK, labelsize=9.5, length=0)


def fig_rute(data, out):
    """Satu panel per percobaan: rencana vs aktual vs menurut robot (seperti Fig. 4 [1])."""
    n = len(data)
    batas = _batas(data)
    lebar = 2.9                                              # in per panel, skala sama
    tinggi = lebar * (batas[3] - batas[2] + 10) / (batas[1] - batas[0] + 10) + 1.7
    fig, axes = plt.subplots(1, n, figsize=(n * lebar + 0.4, tinggi), sharey=True,
                             squeeze=False)
    for ax, d in zip(axes[0], data):
        _gaya_peta(ax, batas)
        ax.plot(*zip(*RENCANA), ls=(0, (5, 3)), color=C_RENCANA, lw=1.6, marker="o", ms=6,
                mfc="white", mec=C_RENCANA, mew=1.4, label="Rute rencana", zorder=2)
        if len(d["robot"]) > 1:
            ax.plot(*zip(*d["robot"]), color=C_MPU, lw=1.6, marker="s", ms=5, mfc=C_MPU,
                    mec="white", mew=1, label="Menurut robot (jarak perintah + yaw MPU)",
                    zorder=3)
        if len(d["aktual"]) > 1:
            ax.plot(*zip(*d["aktual"]), color=ROBOT, lw=2, marker="o", ms=5, mfc=ROBOT,
                    mec="white", mew=1, label=f"Aktual ({d['sumber']})", zorder=4)
        geser = {"S/T4": (-9, -2), "T1": (-9, 2), "T2": (9, 2), "T3": (9, -2)}
        for kode, (x, y) in zip(("S/T4", "T1", "T2", "T3"), RENCANA):
            dx, dy = geser[kode]
            ax.annotate(kode, (x, y), xytext=(dx, dy), textcoords="offset points",
                        fontsize=9.5, color=INK, ha="right" if dx < 0 else "left", va="center")
        ax.set_title(f"Percobaan {d['perc']}\nMAE posisi aktual {f(rata(d['galat']))} cm",
                     fontsize=11, color=INK, loc="left")
        ax.set_xlabel("x (cm)", fontsize=10, color=INK)
    axes[0][0].set_ylabel("y (cm), S = (0, 0)", fontsize=10, color=INK)
    h, lab = axes[0][0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper left", bbox_to_anchor=(0.01, 0.93), ncol=3, frameon=False,
               fontsize=10)
    fig.suptitle("C1 · Rute rencana, lintasan aktual, dan lintasan menurut robot",
                 x=0.01, ha="left", fontsize=12.5, weight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    return out


def fig_galat(data, out):
    """MAE posisi per titik: aktual vs rencana, dan robot (MPU) vs aktual."""
    kode = [u for _s, u, *_r in SEGMEN]
    x = list(range(len(kode)))
    fig, ax = plt.subplots(figsize=(7, 3.4))
    semua = []
    # label biru di kanan titik, oranye di atas, supaya tidak bertumpuk / menutup sumbu
    for key, warna, label, mk, off in (("galat", ROBOT, "Aktual vs rencana", "o", (11, 0)),
                                       ("galat_mpu", C_MPU, "Menurut robot vs aktual", "s", (0, 9))):
        mae = [rata(kolom([d[key] for d in data], i)) for i in x]
        pts = [(i, m) for i, m in zip(x, mae) if m is not None]
        semua += [m for _i, m in pts]
        if not pts:
            continue
        ax.plot(*zip(*pts), color=warna, lw=2, marker=mk, ms=7, mec="white", mew=1.2,
                label=label)
        for i, m in pts:
            ax.annotate(f(m), (i, m), xytext=off, textcoords="offset points",
                        ha="left" if off[0] else "center", va="center" if off[0] else "bottom",
                        fontsize=8.5, color=INK,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    ax.set_xticks(x)
    ax.set_xticklabels(kode)
    ax.set_xlabel("Titik belok", fontsize=9, color=INK)
    ax.set_ylabel("MAE posisi (cm)", fontsize=9, color=INK)
    ax.set_ylim(0, max(semua + [10]) * 1.3)
    ax.grid(axis="y", color="#e2e8f0", lw=0.6)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=INK, labelsize=8.5)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("C1 · Galat posisi di tiap titik belok (rata-rata percobaan)", fontsize=11,
                 weight="bold", color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def cetak_tabel(data):
    """Setara Tabel I [1]: galat tiap percobaan dan MAE per titik / segmen."""
    w = 12
    print("\nPer titik — galat posisi aktual vs rencana (cm)")
    print("".join(f"{h:>{w}}" for h in ["Titik"] + [f"Perc. {d['perc']}" for d in data] +
                  ["MAE", "MPU vs akt."]))
    for i, (_s, ujung, *_r) in enumerate(SEGMEN):
        g = kolom([d["galat"] for d in data], i)
        m = kolom([d["galat_mpu"] for d in data], i)
        print("".join(f"{v:>{w}}" for v in [ujung] + [f(x) for x in g] + [f(rata(g)), f(rata(m))]))
    print("\nPer segmen — jarak (cm) dan sudut belok di ujungnya (°)")
    print("".join(f"{h:>{w}}" for h in ["Segmen", "Perintah", "Jarak akt.", "MAE jarak",
                                       "Belok akt.", "MAE belok", "Belok MPU", "MAE MPU-akt"]))
    for i, (seg, _u, _p, L) in enumerate(SEGMEN):
        jarak = [d["jarak"][i] for d in data]
        belok = kolom([d["belok"] for d in data], i)
        mpu = [d["belok_mpu"][i] for d in data]
        selisih = [None if a is None or b is None else abs(a - b) for a, b in zip(belok, mpu)]
        print("".join(f"{v:>{w}}" for v in [
            seg, L, f(rata(jarak)), f(rata([None if x is None else abs(x - L) for x in jarak])),
            f(rata(belok)), f(rata([None if b is None else abs(b - BELOK) for b in belok])),
            f(rata(mpu)), f(rata(selisih))]))
    for d in data:
        if d["tutup"] is not None and len(d["aktual"]) == len(RENCANA):
            hitung = math.dist(d["aktual"][-1], d["aktual"][0])
            print(f"Cek Perc. {d['perc']}: T4–S diukur {f(d['tutup'])} cm, dari jarak+sudut "
                  f"{f(hitung)} cm (beda besar = ada bacaan meteran/busur yang perlu dicek)")


def rata_sudut(xs):
    """Rata-rata sudut (°) yang aman terhadap lompatan ±180."""
    if not xs:
        return None
    sx = sum(math.sin(math.radians(x)) for x in xs)
    cx = sum(math.cos(math.radians(x)) for x in xs)
    return math.degrees(math.atan2(sx, cx))


def baca_log(path):
    """
    Yaw MPU per perintah dari berkas log GUI (logs/log_feeder_*.txt). Baris yang dipakai:
        [2026-10-05 21:49:35] (GERAK) ON FW diterima — Maju 200 cm
        [2026-10-05 21:49:44] (SELESAI) FIN FW:200 — ...
        [2026-10-05 21:49:45] (MPU-NRF) Roll=0.4 Pitch=-1.2 Yaw=44.1
    Untuk FW, nilai yang disalin ke lembar adalah RATA-RATA yaw selama robot maju
    (dari ON sampai FIN): itu arah segmen menurut MPU. Cuplikan tunggal saat FIN
    sering kena ayunan sesaat di ujung gerak. Yaw +3 s setelah CW terakhir (robot
    sudah berhenti berputar) dipakai di baris Akhir.
    """
    waktu = r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] "
    pola_on = re.compile(waktu + r"\(GERAK\) ON (\w+) diterima")
    pola_fin = re.compile(waktu + r"\(SELESAI\) FIN (\w+):(\d+)")
    pola_mpu = re.compile(waktu + r"\(MPU-\w+\) .*?Yaw=(-?[\d.]+)")
    fins, yaws, mulai = [], [], {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if m := pola_on.match(line):
                mulai[m[2]] = datetime.fromisoformat(m[1])
            elif m := pola_fin.match(line):
                fins.append((datetime.fromisoformat(m[1]), m[2], int(m[3]), mulai.get(m[2])))
            elif m := pola_mpu.match(line):
                yaws.append((datetime.fromisoformat(m[1]), float(m[2])))

    def yaw_pada(t, maks_s=3):
        for ty, y in yaws:
            if 0 <= (ty - t).total_seconds() <= maks_s:
                return y
        return None

    def yaw_selama(t0, t1):
        return rata_sudut([y for ty, y in yaws if t0 is not None and t0 <= ty <= t1])

    if not fins:
        sys.exit(f"Tidak ada baris FIN di {Path(path).name}.")
    print(f"{'No':>3}  {'Jam':8}  {'Perintah':9}  {'Yaw FIN':>8}  {'Rata2 FW':>8}  "
          f"{'Yaw +3 s':>8}  Isi ke lembar")
    for i, (t, move, dist, t0) in enumerate(fins, 1):
        fw = move == "FW"
        isi = ("Rata2 FW -> kolom Yaw titik ujung segmen ini" if fw else
               "Yaw +3 s -> kolom Yaw baris Akhir (bila ini CW terakhir)")
        print(f"{i:>3}  {t:%H:%M:%S}  {move + ':' + str(dist):9}  {f(yaw_pada(t)):>8}  "
              f"{f(yaw_selama(t0, t)) if fw else '':>8}  "
              f"{'' if fw else f(yaw_pada(t + timedelta(seconds=3))):>8}  {isi}")
    if not yaws:
        print("Tidak ada baris MPU — pastikan saklar Log MPU menyala saat uji.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--lembar-xy", action="store_true",
                    help="buat lembar isian kosong cara koordinat (X/Y dari dinding)")
    ap.add_argument("--lembar", action="store_true", help="buat lembar isian kosong cara benang")
    ap.add_argument("--log", type=Path, help="berkas log GUI: tampilkan yaw MPU di tiap FIN")
    ap.add_argument("--xlsx", type=Path, help="lembar data yang dibaca (bawaan: lembar "
                    "koordinat bila ada, selain itu lembar benang)")
    ap.add_argument("--out-dir", type=Path, default=GAMBAR, help="folder keluaran gambar")
    a = ap.parse_args()
    if a.lembar_xy:
        return buat_lembar_xy()
    if a.lembar:
        return buat_lembar()
    if a.log:
        return baca_log(a.log)
    a.out_dir.mkdir(exist_ok=True)
    # bawaan: lembar pertama yang sudah berisi data (koordinat dulu, lalu benang)
    data = None
    for path in [a.xlsx] if a.xlsx else [XLSX_XY, XLSX]:
        if not path.exists():
            continue
        data = baca_xy(path) if SHEET_XY in load_workbook(path).sheetnames else baca(path)
        if data:
            print(f"Baca : {path.name}")
            break
    if not data:
        sys.exit("Lembar C1 belum ada atau belum diisi — grafik tidak dibuat.")
    print(f"PNG  : {fig_rute(data, a.out_dir / 'fig_c1_rute_aktual.png')}")
    print(f"PNG  : {fig_galat(data, a.out_dir / 'fig_c1_galat_titik.png')}")
    cetak_tabel(data)


if __name__ == "__main__":
    main()
