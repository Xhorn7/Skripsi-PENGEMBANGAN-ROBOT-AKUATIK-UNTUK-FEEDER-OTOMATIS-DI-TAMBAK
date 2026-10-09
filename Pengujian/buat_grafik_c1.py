"""
C1 (kotak 1 x 2 m) diukur dari titik belok ke titik belok, lalu digambar seperti
Fig. 4 dan Tabel I pada paper rujukan [1]: rute rencana vs lintasan aktual, dan
lintasan menurut robot (jarak perintah + yaw MPU) disandingkan dengan aktual.

    pip install -r requirements.txt
    python buat_grafik_c1.py --lembar     # sekali: buat Lembar_Data_C1_Titik_Belok.xlsx
    python buat_grafik_c1.py --cara       # gambar penjelasan cara ukur
    python buat_grafik_c1.py              # setelah lembar diisi & disimpan: buat grafik

Cara ukur (masukan dosen pembimbing): robot dibiarkan menjalankan kotak tanpa
berhenti untuk diukur. Setiap kali robot selesai maju (FIN FW), satu orang
menaruh PENANDA tepat di bawah titik tengah robot. Setelah robot selesai,
penanda yang berurutan dihubungkan dengan BENANG di atas air, lalu:
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
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, FancyBboxPatch
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from build_skenario import GAMBAR, HERE, INK, RED, ROBOT
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
               "Yaw MPU (°) — log GUI saat FIN FW",
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
        "tepat di bawah titik tengah robot.",
        "3. Setelah robot selesai, hubungkan penanda berurutan (S–T1–T2–T3–T4) dengan benang "
        "di atas air.",
        "4. Kolom D: meteran sepanjang benang. Kolom E: busur di penanda, sudut DALAM antara "
        "benang ke penanda sebelumnya dan berikutnya (ideal 90°).",
        "5. Kolom F: yaw MPU dari log GUI saat FIN tiap FW; baris Akhir = yaw setelah CW:90 "
        "terakhir dan robot diam. Gyro wajib terkalibrasi (robot diam saat dinyalakan).",
        "6. Sudut di T4 tidak bisa diukur dengan benang (tidak ada segmen sesudahnya), jadi "
        "hanya sudut MPU-nya yang ada. Setelah disimpan, jalankan python buat_grafik_c1.py.",
    )
    r1 = r0 + 3 + len(SEGMEN)
    for k, t in enumerate(catatan, start=r1):
        ws.cell(row=k, column=1, value=t).font = Font(italic=k == r1, size=9 if k == r1 else 10)
    wb.save(XLSX)
    print(f"XLSX : {XLSX}")


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
                         aktual=aktual, robot=robot, galat=galat, galat_mpu=galat_mpu))
    return data


def rata(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def kolom(rows, i):
    return [r[i] if i < len(r) else None for r in rows]


def f(x, n=1):
    return "—" if x is None else f"{x:.{n}f}".replace(".", ",")


# ---------------------------------------------------------------- grafik
def _gaya_peta(ax):
    ax.set_aspect("equal")
    ax.set_xlim(-50, 160)
    ax.set_ylim(-50, 260)
    ax.set_xticks(range(-50, 151, 50))
    ax.set_yticks(range(-50, 251, 50))
    ax.set_xticks(range(-50, 151, 25), minor=True)
    ax.set_yticks(range(-50, 251, 25), minor=True)
    ax.grid(which="both", color="#e2e8f0", lw=0.6)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=INK, labelsize=8, length=0)


def fig_rute(data, out):
    """Satu panel per percobaan: rencana vs aktual vs menurut robot (seperti Fig. 4 [1])."""
    n = len(data)
    fig, axes = plt.subplots(1, n, figsize=(n * 2.75 + 0.5, 5.2), sharey=True, squeeze=False)
    for ax, d in zip(axes[0], data):
        _gaya_peta(ax)
        ax.plot(*zip(*RENCANA), ls=(0, (5, 3)), color=C_RENCANA, lw=1.6, marker="o", ms=6,
                mfc="white", mec=C_RENCANA, mew=1.4, label="Rute rencana", zorder=2)
        if len(d["robot"]) > 1:
            ax.plot(*zip(*d["robot"]), color=C_MPU, lw=1.6, marker="s", ms=5, mfc=C_MPU,
                    mec="white", mew=1, label="Menurut robot (jarak perintah + yaw MPU)",
                    zorder=3)
        if len(d["aktual"]) > 1:
            ax.plot(*zip(*d["aktual"]), color=ROBOT, lw=2, marker="o", ms=5, mfc=ROBOT,
                    mec="white", mew=1, label="Aktual (meteran + busur)", zorder=4)
        geser = {"S/T4": (-9, -2), "T1": (-9, 2), "T2": (9, 2), "T3": (9, -2)}
        for kode, (x, y) in zip(("S/T4", "T1", "T2", "T3"), RENCANA):
            dx, dy = geser[kode]
            ax.annotate(kode, (x, y), xytext=(dx, dy), textcoords="offset points",
                        fontsize=7.5, color=INK, ha="right" if dx < 0 else "left", va="center")
        ax.set_title(f"Percobaan {d['perc']}\nMAE posisi aktual {f(rata(d['galat']))} cm",
                     fontsize=9, color=INK, loc="left")
        ax.set_xlabel("x (cm)", fontsize=8, color=INK)
    axes[0][0].set_ylabel("y (cm), S = (0, 0)", fontsize=8, color=INK)
    h, lab = axes[0][0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper left", bbox_to_anchor=(0.01, 0.94), ncol=3, frameon=False,
               fontsize=8)
    fig.suptitle("C1 · Rute rencana, lintasan aktual, dan lintasan menurut robot",
                 x=0.01, ha="left", fontsize=11, weight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    return out


def fig_galat(data, out):
    """MAE posisi per titik: aktual vs rencana, dan robot (MPU) vs aktual."""
    kode = [u for _s, u, *_r in SEGMEN]
    x = list(range(len(kode)))
    fig, ax = plt.subplots(figsize=(7, 3.4))
    semua = []
    # label biru di bawah titik, oranye di atas, supaya tidak bertumpuk
    for key, warna, label, mk, dy in (("galat", ROBOT, "Aktual vs rencana", "o", -15),
                                      ("galat_mpu", C_MPU, "Menurut robot vs aktual", "s", 9)):
        mae = [rata(kolom([d[key] for d in data], i)) for i in x]
        pts = [(i, m) for i, m in zip(x, mae) if m is not None]
        semua += [m for _i, m in pts]
        if not pts:
            continue
        ax.plot(*zip(*pts), color=warna, lw=2, marker=mk, ms=7, mec="white", mew=1.2,
                label=label)
        for i, m in pts:
            ax.annotate(f(m), (i, m), xytext=(0, dy), textcoords="offset points", ha="center",
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


def fig_cara(out):
    """Gambar penjelasan: penanda di titik belok, benang, meteran, dan busur."""
    fig, ax = plt.subplots(figsize=(8, 6.2))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-150, 300)
    ax.set_ylim(-75, 275)
    # contoh lintasan nyata yang sedikit melenceng dari rencana
    T = [(0, 0), (-6, 196), (98, 207), (112, 8), (14, -10)]
    nama = ["S", "T1", "T2", "T3", "T4"]
    offset = {"S": (-14, -4), "T1": (-32, 4), "T2": (12, 6), "T3": (12, -4), "T4": (10, -12)}
    ax.plot(*zip(*RENCANA), ls=(0, (5, 3)), color=C_RENCANA, lw=1.2, zorder=1)
    ax.plot(*zip(*T), color=INK, lw=1.4, zorder=2)                       # benang
    for (x0, y0), (x1, y1) in zip(T, T[1:]):                             # arah jalan robot
        xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
        ax.annotate("", (xm + (x1 - x0) * 0.06, ym + (y1 - y0) * 0.06), xytext=(xm, ym),
                    arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.4, mutation_scale=14),
                    zorder=2)
    for (x, y), nm in zip(T, nama):
        ax.plot(x, y, "o", ms=10, color=RED, mec="white", mew=1.5, zorder=4)
        dx, dy = offset[nm]
        ax.annotate(nm, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=11,
                    weight="bold", color=RED, ha="right" if dx < 0 else "left", va="center")
    # robot (60 x 42 cm) di T1, menghadap depan
    ax.add_patch(FancyBboxPatch((T[1][0] - 21, T[1][1] - 30), 42, 60,
                                boxstyle="round,pad=0,rounding_size=6", fc=ROBOT, ec="none",
                                alpha=0.18, zorder=3))
    panah = dict(arrowstyle="->", color=INK, lw=0.8)
    ax.annotate("Robot sampai di titik belok (FIN FW)\n→ taruh penanda di bawah\ntitik tengahnya",
                T[1], xytext=(-145, 240), fontsize=8.5, color=INK, va="center", arrowprops=panah)
    ax.annotate("JARAK S–T1\nmeteran sepanjang benang\n(perintah 200 cm)", (-3, 98),
                xytext=(-145, 110), fontsize=8.5, color=INK, va="center", arrowprops=panah)
    # busur di T2: sudut dalam antara benang T2→T1 dan T2→T3
    a1 = math.degrees(math.atan2(T[1][1] - T[2][1], T[1][0] - T[2][0])) % 360
    a2 = math.degrees(math.atan2(T[3][1] - T[2][1], T[3][0] - T[2][0])) % 360
    ax.add_patch(Arc(T[2], 46, 46, theta1=min(a1, a2), theta2=max(a1, a2), color=ROBOT, lw=2,
                     zorder=3))
    ax.annotate("SUDUT DALAM di T2\nbusur antara benang T2–T1\ndan benang T2–T3 (ideal 90°)",
                (T[2][0] - 14, T[2][1] - 14), xytext=(150, 240), fontsize=8.5, color=INK,
                va="center", arrowprops=panah)
    ax.annotate("Sudut di T4 tidak bisa diukur\ndengan benang (tidak ada segmen\n"
                "sesudahnya) → hanya yaw MPU", T[4], xytext=(150, -45), fontsize=8.5,
                color=INK, va="center", arrowprops=panah)
    ax.plot([], [], "o", color=RED, ms=8, label="Penanda titik belok")
    ax.plot([], [], color=INK, lw=1.4, label="Benang antar penanda")
    ax.plot([], [], ls=(0, (5, 3)), color=C_RENCANA, lw=1.2, label="Rute rencana 1 × 2 m")
    ax.legend(loc="lower left", frameon=False, fontsize=8.5)
    ax.set_title("C1 · Cara ukur dari titik belok ke titik belok", fontsize=12, weight="bold",
                 color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.1)
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


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--lembar", action="store_true", help="buat lembar isian kosong")
    ap.add_argument("--cara", action="store_true", help="gambar penjelasan cara ukur")
    ap.add_argument("--xlsx", type=Path, default=XLSX, help="lembar data yang dibaca")
    ap.add_argument("--out-dir", type=Path, default=GAMBAR, help="folder keluaran gambar")
    a = ap.parse_args()
    if a.lembar:
        return buat_lembar()
    a.out_dir.mkdir(exist_ok=True)
    if a.cara:
        return print(f"PNG  : {fig_cara(a.out_dir / 'fig_c1_cara_ukur.png')}")
    if not a.xlsx.exists():
        sys.exit(f"{a.xlsx.name} belum ada. Buat dulu: python buat_grafik_c1.py --lembar")
    data = baca(a.xlsx)
    if not data:
        sys.exit("Lembar C1 belum diisi — grafik tidak dibuat.")
    print(f"PNG  : {fig_rute(data, a.out_dir / 'fig_c1_rute_aktual.png')}")
    print(f"PNG  : {fig_galat(data, a.out_dir / 'fig_c1_galat_titik.png')}")
    cetak_tabel(data)


if __name__ == "__main__":
    main()
