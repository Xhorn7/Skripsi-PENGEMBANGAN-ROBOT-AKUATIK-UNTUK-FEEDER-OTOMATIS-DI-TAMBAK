"""
Panduan lapangan uji C1 (kotak 1 x 2 m) yang diukur dari titik belok ke titik
belok: alat, cara membuat dudukan penanda (botol isi pasir + pipa pendek + sok),
titik acuan robot, alur kerja di kolam, pemasangan benang, pembacaan busur,
pengambilan yaw MPU dari log, dan pengolahan data.

    pip install -r requirements.txt
    python buat_panduan_c1.py      # gambar/*.png + Panduan_Pengujian_C1.docx (+ .pdf)

Gambar ilustrasi juga dipakai terpisah: fig_c1_pasang_benang.png (gabungan tiga
tahap) cocok dikirim lewat chat.
"""
import math
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Cm, Pt
from matplotlib.patches import Arc, Circle, FancyBboxPatch, Polygon, Rectangle

from buat_grafik_c1 import C_RENCANA, RENCANA
from build_skenario import CENTER, GAMBAR, HERE, INK, NAVY, RED, ROBOT, WATER, Doc, export_pdf

OUT = HERE / "Panduan_Pengujian_C1.docx"

# ukuran ilustrasi (cm), tampak samping: lantai kolam di y = 0
DALAM = 75                      # contoh kedalaman air; di lapangan diukur dulu
JARAK_ATAS = 15                 # ujung atas sok minimal segini di bawah permukaan air
BOTOL_W, BOTOL_BADAN, BOTOL_BAHU, BOTOL_LEHER, LEHER_W = 7, 20, 4, 5, 2.6
KARET = 1                       # alas karet anti-selip di dasar botol
PIPA_D, SOK_D, SOK_H = 2.6, 3.4, 6
SOK_ATAS = DALAM - JARAK_ATAS
PIPA_PANJANG, MASUK_SOK, TANDA = 60, 4, 38   # tanda lakban: cm dari ujung bawah pipa panjang
Y_TANDA = SOK_ATAS - MASUK_SOK + TANDA

C_AIR = "#38bdf8"
C_PASIR = "#d6b98c"
C_PIPA = "#f1f5f9"
C_SOK = "#94a3b8"
C_LAKBAN = "#f59e0b"
C_KARET = "#334155"
PANAH = dict(arrowstyle="->", color=INK, lw=0.8)


# ---------------------------------------------------------------- unsur gambar
def _kolam(ax, x0, x1, label=True, kiri=False):
    ax.add_patch(Rectangle((x0, 0), x1 - x0, DALAM, fc=WATER, ec="none", zorder=0))
    ax.plot([x0, x1], [DALAM, DALAM], color=C_AIR, lw=1.5, zorder=1)
    ax.plot([x0, x1], [0, 0], color=INK, lw=2, zorder=1)
    if label:
        xl, ha = (x0 + 1, "left") if kiri else (x1, "right")
        ax.text(xl, DALAM + 1.5, "permukaan air", fontsize=7.5, color="#0369a1", ha=ha,
                va="bottom")
        ax.text(xl, -2, "dasar kolam", fontsize=7.5, color=INK, ha=ha, va="top")


def _dudukan(ax, x, panjang=False):
    """Dudukan penanda dengan as pipa di x: botol isi pasir di kiri, pipa pendek + sok."""
    bx1 = x - PIPA_D / 2
    bx0 = bx1 - BOTOL_W
    cx = (bx0 + bx1) / 2
    y_badan = KARET + BOTOL_BADAN
    y_atas = y_badan + BOTOL_BAHU + BOTOL_LEHER

    def bentuk(inset, atas):
        return [(bx0 + inset, KARET + inset), (bx1 - inset, KARET + inset),
                (bx1 - inset, y_badan), (cx + LEHER_W / 2 - inset, y_badan + BOTOL_BAHU),
                (cx + LEHER_W / 2 - inset, atas), (cx - LEHER_W / 2 + inset, atas),
                (cx - LEHER_W / 2 + inset, y_badan + BOTOL_BAHU), (bx0 + inset, y_badan)]

    ax.add_patch(Rectangle((bx0 - 0.4, 0), BOTOL_W + 0.8, KARET, fc=C_KARET, ec="none", zorder=3))
    ax.add_patch(Polygon(bentuk(0, y_atas), fc="white", ec=INK, lw=0.8, zorder=3))
    ax.add_patch(Polygon(bentuk(0.6, y_atas - 1.5), fc=C_PASIR, ec="none", zorder=3))
    ax.add_patch(Rectangle((cx - LEHER_W / 2 - 0.4, y_atas - 0.6), LEHER_W + 0.8, 1.6, fc=INK,
                           ec="none", zorder=4))
    ax.add_patch(Rectangle((x - PIPA_D / 2, 0), PIPA_D, SOK_ATAS - SOK_H / 2, fc=C_PIPA, ec=INK,
                           lw=0.8, zorder=3))
    if panjang:
        ax.add_patch(Rectangle((x - PIPA_D / 2, SOK_ATAS - MASUK_SOK), PIPA_D, PIPA_PANJANG,
                               fc=C_PIPA, ec=INK, lw=0.8, zorder=3))
        ax.add_patch(Rectangle((x - PIPA_D / 2 - 0.8, Y_TANDA - 1.2), PIPA_D + 1.6, 2.4,
                               fc=C_LAKBAN, ec="none", zorder=5))
    ax.add_patch(Rectangle((x - SOK_D / 2, SOK_ATAS - SOK_H), SOK_D, SOK_H, fc=C_SOK, ec=INK,
                           lw=0.8, zorder=4))
    for y in (KARET + 4, KARET + 15):                                   # kabel ties + isolasi
        ax.add_patch(Rectangle((bx0 - 0.3, y), x + PIPA_D / 2 + 0.3 - (bx0 - 0.3), 1.4, fc=INK,
                               ec="none", zorder=5))


def _rapikan(ax):
    ax.set_aspect("equal")
    ax.axis("off")


def _simpan(fig, nama):
    GAMBAR.mkdir(exist_ok=True)
    path = GAMBAR / nama
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return path


def _dimensi(ax, x, y0, y1, teks, kiri=True):
    ax.annotate("", (x, y1), xytext=(x, y0), arrowprops=dict(arrowstyle="<->", color=RED, lw=1))
    ax.text(x - 2 if kiri else x + 2, (y0 + y1) / 2, teks, fontsize=7.5, color=RED,
            ha="right" if kiri else "left", va="center")


# ---------------------------------------------------------------- panel
def panel_rakitan(ax):
    """Dudukan penanda dari dekat, dengan nama tiap bagian."""
    ax.set_xlim(-34, 52)
    ax.set_ylim(-10, 66)
    ax.plot([-20, 20], [0, 0], color=INK, lw=2)
    _dudukan(ax, 0)
    lbl = dict(fontsize=8, color=INK, va="center", arrowprops=PANAH)
    ax.annotate("sok PVC ¾\" (dilem ke pipa pendek)", (SOK_D / 2, SOK_ATAS - 2), xytext=(8, 61), **lbl)
    ax.annotate("pipa pendek PVC ¾\"\n= AS PENANDA", (PIPA_D / 2, 38), xytext=(8, 40), **lbl)
    ax.annotate("tutup: plastik + karet\ngelang + lakban", (-5.3, 30), xytext=(8, 27), **lbl)
    ax.annotate("botol penuh pasir\n(bukan air)", (-4.3, 12), xytext=(8, 13.5), **lbl)
    ax.annotate("kabel ties + isolasi\n(2 ikatan di badan botol)", (1.6, 5.7), xytext=(8, 4.5), **lbl)
    ax.annotate("alas karet anti-selip", (-7, 0.5), xytext=(-33, -3.5), fontsize=8, color=INK,
                va="center", arrowprops=PANAH)
    ax.annotate("ujung bawah pipa rata\ndengan dasar botol", (PIPA_D / 2, 0.3), xytext=(8, -5.5),
                fontsize=8, color=INK, va="center", arrowprops=PANAH)
    _dimensi(ax, -13, 0, SOK_ATAS, "tinggi s.d.\natas sok =\nkedalaman\n− 15 cm")
    _rapikan(ax)


def panel_tiang(ax):
    """Satu tiang lengkap di kolam: dudukan + pipa panjang + tanda lakban."""
    ax.set_xlim(-40, 62)
    ax.set_ylim(-5, 128)
    _kolam(ax, -40, 62, label=False)
    _dudukan(ax, 0, panjang=True)
    ax.plot([0, 30], [Y_TANDA, Y_TANDA], color=INK, lw=1.2, zorder=4)
    ax.text(31, Y_TANDA, "benang", fontsize=7.5, color=INK, va="center")
    lbl = dict(fontsize=8, color=INK, va="center", arrowprops=PANAH)
    ax.annotate("pipa panjang ± 60 cm,\ndicolok ke sok\n(tanpa lem)", (PIPA_D / 2, 112),
                xytext=(8, 121), **lbl)
    ax.annotate(f"tanda lakban {TANDA} cm dari\nujung bawah pipa panjang\n(sama di semua pipa)",
                (PIPA_D / 2 + 0.8, Y_TANDA + 1), xytext=(8, 104), **lbl)
    _dimensi(ax, 14, SOK_ATAS, DALAM, "≥ 15 cm", kiri=False)
    ax.text(61, DALAM + 1.5, "permukaan air", fontsize=7.5, color="#0369a1", ha="right",
            va="bottom")
    ax.text(61, -2, "dasar kolam", fontsize=7.5, color=INK, ha="right", va="top")
    _rapikan(ax)


def panel_saat_fin(ax):
    """Saat FIN FW: robot diam di atas, dudukan ditaruh dengan as pipa di bawah stiker."""
    ax.set_xlim(-10, 160)
    ax.set_ylim(-6, 112)
    _kolam(ax, -10, 160, kiri=True)
    ax.add_patch(FancyBboxPatch((60, DALAM - 4), 60, 9, boxstyle="round,pad=0,rounding_size=3",
                                fc=ROBOT, ec="none", alpha=0.35, zorder=2))
    ax.add_patch(Rectangle((74, DALAM + 5), 24, 13, fc=ROBOT, ec="none", alpha=0.55, zorder=2))
    ax.text(86, DALAM + 11.5, "robot", fontsize=7.5, color="white", ha="center", va="center",
            zorder=3)
    xs = 102                                                    # stiker titik acuan
    ax.plot(xs, DALAM + 8, "v", color=RED, ms=8, zorder=5)
    ax.plot([xs, xs], [SOK_ATAS, DALAM + 6], ls=(0, (3, 2)), color=RED, lw=1, zorder=4)
    _dudukan(ax, xs)
    ax.annotate("stiker titik acuan robot", (xs, DALAM + 10), xytext=(40, 102), fontsize=8,
                color=INK, va="center", arrowprops=PANAH)
    ax.annotate("as pipa tepat di bawah stiker", (xs - 1.5, 45), xytext=(-8, 50), fontsize=8,
                color=INK, va="center", arrowprops=PANAH)
    ax.annotate("dudukan penanda di dasar", (xs - 10, 12), xytext=(-8, 18), fontsize=8,
                color=INK, va="center", arrowprops=PANAH)
    _dimensi(ax, 116, SOK_ATAS, DALAM, "≥ 15 cm", kiri=False)
    _rapikan(ax)


def panel_benang(ax):
    """Setelah robot selesai: pipa panjang dicolok, benang diikat di tanda lakban."""
    ax.set_xlim(-45, 262)
    ax.set_ylim(-6, 132)
    _kolam(ax, -45, 262)
    xs = [0, 100, 200]
    for x, nm in zip(xs, ["T1", "T2", "T3"]):
        _dudukan(ax, x, panjang=True)
        ax.text(x, SOK_ATAS - MASUK_SOK + PIPA_PANJANG + 3, nm, fontsize=9, weight="bold",
                color=RED, ha="center", va="bottom")
    ax.plot([xs[0], xs[-1]], [Y_TANDA, Y_TANDA], color=INK, lw=1.2, zorder=6)
    ax.annotate("", (xs[1] - 2, Y_TANDA + 8), xytext=(xs[0] + 2, Y_TANDA + 8),
                arrowprops=dict(arrowstyle="<->", color=ROBOT, lw=1.4))
    ax.text(50, Y_TANDA + 11, "meteran (as ke as)", fontsize=8, color=INK, ha="center",
            va="bottom")
    ax.annotate("benang ditarik\nkencang, diikat di\ntanda lakban", (150, Y_TANDA),
                xytext=(110, 56), fontsize=8, color=INK, va="center", arrowprops=PANAH)
    ax.annotate("pipa panjang dicolok\nke sok tiap dudukan", (1.3, 70), xytext=(14, 40),
                fontsize=8, color=INK, va="center", arrowprops=PANAH)
    ax.annotate("dudukan tetap di\ntempatnya (jangan\ndigeser)", (195, 14), xytext=(112, 22),
                fontsize=8, color=INK, va="center", arrowprops=PANAH)
    _rapikan(ax)


def panel_busur(ax):
    """Tampak atas di pojok T1: busur datar di atas benang, pusatnya di as pipa."""
    ax.set_xlim(-80, 100)
    ax.set_ylim(-100, 72)
    t1, t0, t2 = (0, 0), (0, -110), (110, 8)
    ax.plot(*zip(t0, t1, t2), color=INK, lw=1.2, zorder=2)
    r = 42
    ax.add_patch(Arc(t1, 2 * r, 2 * r, theta1=-90, theta2=90, color=ROBOT, lw=2, zorder=3))
    ax.plot([0, 0], [-r, r], color=ROBOT, lw=2, zorder=3)
    for d in range(0, 181, 10):                              # skala busur, 0° di benang masuk
        a = math.radians(-90 + d)
        k = 6 if d % 30 == 0 else 3
        ax.plot([r * math.cos(a), (r - k) * math.cos(a)], [r * math.sin(a), (r - k) * math.sin(a)],
                color=ROBOT, lw=1, zorder=3)
        if d % 90 == 0:
            ax.text((r + 9) * math.cos(a), (r + 9) * math.sin(a), f"{d}°", fontsize=7.5,
                    color=ROBOT, ha="center", va="center")
    ax.add_patch(Circle(t1, 2.5, fc=C_SOK, ec=INK, lw=0.8, zorder=4))
    ax.text(-8, 4, "T1", fontsize=9, weight="bold", color=RED, ha="right", va="bottom")
    ax.text(4, -100, "ke S (titik sebelumnya)", fontsize=8, weight="bold", color=RED, ha="left",
            va="bottom")
    ax.text(100, 12, "ke T2", fontsize=8, weight="bold", color=RED, ha="right", va="bottom")
    ax.annotate("baca angka di benang\nke titik berikutnya\n= SUDUT DALAM", (r * 0.99, 3),
                xytext=(22, 50), fontsize=8, color=INK, arrowprops=PANAH)
    ax.annotate("garis 0° busur\nsejajar benang ke\ntitik sebelumnya", (0, -30),
                xytext=(-80, -75), fontsize=8, color=INK, arrowprops=PANAH)
    ax.annotate("pusat busur\ndi as pipa", (-2, -1), xytext=(-78, 30), fontsize=8, color=INK,
                arrowprops=PANAH)
    _rapikan(ax)


# ---------------------------------------------------------------- gambar
def fig_cara_ukur():
    """Tampak atas: penanda di titik belok, benang, jarak, dan sudut yang diukur."""
    fig, ax = plt.subplots(figsize=(7.4, 5.8))
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
    ax.add_patch(FancyBboxPatch((T[1][0] - 21, T[1][1] - 30), 42, 60,
                                boxstyle="round,pad=0,rounding_size=6", fc=ROBOT, ec="none",
                                alpha=0.18, zorder=3))
    ax.annotate("Robot sampai di titik belok (FIN FW)\n→ taruh dudukan penanda di\nbawah titik "
                "acuan robot", T[1], xytext=(-145, 240), fontsize=8.5, color=INK, va="center",
                arrowprops=PANAH)
    ax.annotate("JARAK S–T1\nmeteran sepanjang benang\n(perintah 200 cm)", (-3, 98),
                xytext=(-145, 110), fontsize=8.5, color=INK, va="center", arrowprops=PANAH)
    a1 = math.degrees(math.atan2(T[1][1] - T[2][1], T[1][0] - T[2][0])) % 360
    a2 = math.degrees(math.atan2(T[3][1] - T[2][1], T[3][0] - T[2][0])) % 360
    ax.add_patch(Arc(T[2], 46, 46, theta1=min(a1, a2), theta2=max(a1, a2), color=ROBOT, lw=2,
                     zorder=3))
    ax.annotate("SUDUT DALAM di T2\nbusur antara benang T2–T1\ndan benang T2–T3 (ideal 90°)",
                (T[2][0] - 14, T[2][1] - 14), xytext=(150, 240), fontsize=8.5, color=INK,
                va="center", arrowprops=PANAH)
    ax.annotate("Sudut di T4 tidak bisa diukur\ndengan benang (tidak ada segmen\n"
                "sesudahnya) → hanya yaw MPU", T[4], xytext=(150, -45), fontsize=8.5,
                color=INK, va="center", arrowprops=PANAH)
    ax.plot([], [], "o", color=RED, ms=8, label="Dudukan penanda di titik belok")
    ax.plot([], [], color=INK, lw=1.4, label="Benang antar pipa")
    ax.plot([], [], ls=(0, (5, 3)), color=C_RENCANA, lw=1.2, label="Rute rencana 1 × 2 m")
    ax.legend(loc="lower left", frameon=False, fontsize=8.5)
    _rapikan(ax)
    return _simpan(fig, "fig_c1_cara_ukur.png")


def fig_dudukan():
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.6, 5.0), gridspec_kw=dict(width_ratios=[1, 0.95]))
    panel_rakitan(a)
    a.set_title("(a) Rakitan dudukan penanda", fontsize=9.5, weight="bold", color=INK, loc="left")
    panel_tiang(b)
    b.set_title("(b) Tiang lengkap setelah robot selesai", fontsize=9.5, weight="bold", color=INK,
                loc="left")
    fig.tight_layout()
    return _simpan(fig, "fig_c1_dudukan.png")


def fig_titik_acuan():
    """Sketsa tampak atas robot: posisi stiker titik acuan dan zona baling-baling."""
    fig, ax = plt.subplots(figsize=(6.6, 4.9))
    ax.set_xlim(-95, 95)
    ax.set_ylim(-45, 52)
    for x0 in (-21, 9):                                             # pelampung kiri & kanan
        ax.add_patch(FancyBboxPatch((x0, -30), 12, 60, boxstyle="round,pad=0,rounding_size=5",
                                    fc="white", ec=INK, lw=1, zorder=2))
    for y in (16, -7):                                              # palang penghubung
        ax.add_patch(Rectangle((-9, y - 1.5), 18, 3, fc="#e2e8f0", ec=INK, lw=0.6, zorder=2))
    ax.add_patch(Rectangle((-8, 1), 16, 22, fc="#e2e8f0", ec=INK, lw=0.8, zorder=3))
    ax.text(0, 12, "kotak\nelek-\ntronik", fontsize=7, color=INK, ha="center", va="center", zorder=4)
    for s in (-1, 1):                                               # lengan + baling-baling
        ax.plot([0, s * 40], [0, -6], color=INK, lw=2.2, zorder=2)
        ax.add_patch(Circle((s * 40, -6), 13, fc=RED, ec=RED, alpha=0.15, lw=1, ls="--", zorder=1))
        ax.plot([s * 40 - 10, s * 40 + 10], [-8, -4], color=INK, lw=2, zorder=3)
    ax.plot(0, 0, "x", color=INK, ms=7, mew=1.5, zorder=5)
    ax.plot(0, -3.5, "o", ms=9, color=RED, mec="white", mew=1.5, zorder=6)
    ax.annotate("", (0, 50), xytext=(0, 34), arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.4))
    ax.text(3, 46, "DEPAN", fontsize=8, weight="bold", color=INK, va="center")
    ax.annotate("STIKER TITIK ACUAN\ngaris tengah, tepat di\nbelakang kotak; dasar\n"
                "kolam masih terlihat\nlewat celah", (-1, -4.5), xytext=(-93, 36), fontsize=8,
                color=INK, va="center", arrowprops=PANAH)
    ax.annotate("titik tengah badan robot", (0.5, 0.5), xytext=(28, 36), fontsize=8, color=INK,
                va="center", arrowprops=PANAH)
    ax.annotate("zona baling-baling: tangan\nmenjauh selama motor menyala", (48, -15),
                xytext=(30, -38), fontsize=8, color=RED, va="center", arrowprops=dict(
                    arrowstyle="->", color=RED, lw=0.8))
    ax.annotate("pelampung", (-15, -22), xytext=(-70, -36), fontsize=8, color=INK, va="center",
                arrowprops=PANAH)
    _rapikan(ax)
    return _simpan(fig, "fig_c1_titik_acuan.png")


def fig_alur():
    """Urutan kerja di satu titik belok, diulang untuk T1–T4."""
    fig, ax = plt.subplots(figsize=(7.8, 2.9))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 37)
    ax.axis("off")
    langkah = [
        ("OPERATOR", "Kirim maju\n(FW:200 / FW:100)\ndari halaman\nMANUAL", ROBOT),
        ("ROBOT", "Maju lalu berhenti\n→ FIN FW di GUI,\nbaling-baling\nberhenti", C_RENCANA),
        ("PENANDA", "Taruh dudukan:\nas pipa di bawah\nstiker, menjauh,\nbilang \"OKE\"", RED),
        ("OPERATOR", "Baru setelah \"OKE\":\nkirim CW:90", ROBOT),
        ("ROBOT", "Berputar\n→ FIN CW,\nlangsung lanjut\nke maju berikutnya", C_RENCANA),
    ]
    w, gap, y0, h = 17.6, 2.9, 12, 22
    for i, (peran, isi, warna) in enumerate(langkah):
        x = i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0,rounding_size=1.5",
                                    fc="white", ec=warna, lw=1.6))
        ax.add_patch(FancyBboxPatch((x, y0 + h - 5), w, 5, boxstyle="round,pad=0,rounding_size=1.5",
                                    fc=warna, ec=warna, lw=1.6))
        ax.text(x + w / 2, y0 + h - 2.5, f"{i + 1} · {peran}", fontsize=7.5, weight="bold",
                color="white", ha="center", va="center")
        ax.text(x + w / 2, y0 + (h - 5) / 2, isi, fontsize=7.3, color=INK, ha="center",
                va="center", linespacing=1.25)
        if i < len(langkah) - 1:
            ax.annotate("", (x + w + gap - 0.3, y0 + h / 2), xytext=(x + w + 0.3, y0 + h / 2),
                        arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.2))
    xa, xb = 4 * (w + gap) + w / 2, w / 2
    ax.annotate("", (xb, y0 - 0.3), xytext=(xa, y0 - 0.3),
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.2,
                                connectionstyle="bar,fraction=-0.1"))
    ax.text(50, 3.2, "ulangi untuk T1 → T2 → T3 → T4 (4 kali); setelah CW:90 terakhir tunggu "
            "3 detik, lalu angkat robot", fontsize=7.5, color=INK, ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none"))
    return _simpan(fig, "fig_c1_alur.png")


def _satu(panel, size, nama):
    fig, ax = plt.subplots(figsize=size)
    panel(ax)
    return _simpan(fig, nama)


def fig_pasang():
    """Tiga tahap dalam satu gambar (untuk dibagikan lewat chat)."""
    fig = plt.figure(figsize=(13.5, 4.8))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.75, 1.0], wspace=0.06)
    for k, (panel, judul) in enumerate((
            (panel_saat_fin, "1 · Saat FIN FW (baling-baling mati):\n     taruh dudukan penanda"),
            (panel_benang, "2 · Setelah robot selesai: colok pipa\n     panjang, tarik benang"),
            (panel_busur, "3 · Tampak atas: busur datar di atas\n     benang, pusatnya di as pipa"))):
        ax = fig.add_subplot(gs[k])
        panel(ax)
        ax.set_title(judul, fontsize=10, weight="bold", color=INK, loc="left")
    return _simpan(fig, "fig_c1_pasang_benang.png")


def semua_gambar():
    return dict(
        cara=fig_cara_ukur(),
        dudukan=fig_dudukan(),
        acuan=fig_titik_acuan(),
        alur=fig_alur(),
        fin=_satu(panel_saat_fin, (6.4, 4.4), "fig_c1_saat_fin.png"),
        benang=_satu(panel_benang, (7.6, 3.6), "fig_c1_benang.png"),
        busur=_satu(panel_busur, (5.2, 4.8), "fig_c1_busur.png"),
        pasang=fig_pasang(),
    )


# ---------------------------------------------------------------- dokumen
def _siku(c, a=60, b=80):
    """Sudut dalam (°) dari cek siku: tanda a dan b cm dari pojok, jarak antar tanda c cm."""
    return math.degrees(math.acos((a * a + b * b - c * c) / (2 * a * b)))


def _f(x, n=1):
    return f"{x:.{n}f}".replace(".", ",")


def build(g):
    D = Doc()
    d = D.d
    d.sections[0].header.paragraphs[0].runs[0].text = "Panduan Pengujian C1 — Titik Belok"

    t = d.add_paragraph()
    t.alignment = CENTER
    t.paragraph_format.space_after = Pt(2)
    r = t.add_run("PANDUAN PENGUJIAN C1")
    r.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = NAVY
    t = d.add_paragraph()
    t.alignment = CENTER
    r = t.add_run("Kotak 1 × 2 m — diukur dari titik belok ke titik belok")
    r.italic = True
    r.font.size = Pt(12)
    info = d.add_table(rows=4, cols=2)
    info.autofit = False
    info.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (k, v) in enumerate((
            ("Disusun oleh", "Samuel Alfonsus"),
            ("Dosen Pembimbing", "Bapak Dany Eka Saputra"),
            ("Dasar", "Arahan dosen pembimbing (Oktober 2026) dan paper rujukan [1]"),
            ("Tanggal", "Oktober 2026"))):
        D.cell(info.rows[i].cells[0], k, bold=True, size=10.5)
        D.cell(info.rows[i].cells[1], ": " + v, size=10.5)
        info.rows[i].cells[0].width = Cm(3.8)
        info.rows[i].cells[1].width = Cm(11.8)
    d.add_paragraph()

    D.h1("Ringkasan")
    D.table(["Pertanyaan", "Jawaban singkat"], [
        ["Apa yang diuji?",
         "C1: FW:200 → CW:90 → FW:100 → CW:90 → FW:200 → CW:90 → FW:100 → CW:90, diulang 3 kali."],
        ["Apa yang diukur?",
         "Jarak antar titik belok (meteran), sudut di tiap titik belok (busur), dan yaw MPU dari "
         "log GUI sebagai pembanding."],
        ["Bagaimana menandai titik belok?",
         "Setiap FIN FW, dudukan penanda (botol isi pasir + pipa pendek + sok) ditaruh di dasar "
         "kolam dengan as pipanya tepat di bawah titik acuan robot."],
        ["Bagaimana mengukur di atas air?",
         "Setelah robot selesai, pipa panjang dicolok ke sok tiap dudukan, benang ditarik antar "
         "pipa, lalu jarak diukur dengan meteran dan sudut dengan busur di atas benang."],
        ["Apa hasilnya?",
         "Lintasan aktual vs rute rencana vs lintasan menurut robot (seperti Fig. 4 pada [1]) dan "
         "galat posisi per titik belok (seperti Tabel I pada [1])."],
    ], [4.6, 11.8], size=10)

    # 1
    D.h1("1. Latar Belakang")
    D.p("Pada uji C1 sebelumnya posisi robot hanya diambil dari foto awal dan foto akhir, sehingga "
        "galat di setiap titik belok tidak diketahui. Dosen pembimbing meminta C1 diulang dengan "
        "pengukuran di setiap titik belok memakai meteran dan busur, agar hasilnya dapat "
        "digambarkan seperti Fig. 4 dan Tabel I pada [1]. Arahan tersebut:")
    D.bullet("Robot dibiarkan berjalan menyelesaikan kotak. Pengukuran tidak dihitung dari titik "
             "awal, melainkan dari titik belok ke titik belok berikutnya.")
    D.bullet("Setiap titik belok diberi penanda di kolam; jarak antar penanda diukur dengan meteran "
             "di atas air.")
    D.bullet("Sudut di titik belok diukur dengan busur memakai benang yang menghubungkan dua titik "
             "belok, mirip benang acuan tukang keramik.")
    D.bullet("Posisi menurut MPU adalah hasil perhitungan sehingga dapat berbeda dari posisi "
             "sebenarnya; karena itu data MPU disandingkan dengan hasil ukur.")

    # 2
    D.h1("2. Apa yang Diukur")
    D.figure(g["cara"], "Gambar 1. Penanda di titik belok, benang antar penanda, serta jarak dan "
             "sudut yang diukur (contoh lintasan yang sedikit melenceng)", 14.5)
    D.table(["Besaran", "Alat / sumber", "Nilai ideal", "Kolom lembar data"], [
        ["Jarak S–T1, T1–T2, T2–T3, T3–T4", "Meteran sepanjang benang", "200 / 100 / 200 / 100 cm",
         "D"],
        ["Sudut dalam di T1, T2, T3", "Busur di atas benang", "90°", "E"],
        ["Yaw MPU saat FIN tiap FW, dan setelah CW:90 terakhir", "Log GUI",
         "berubah ± 90° tiap belokan", "F"],
        ["Jarak T4–S (opsional, cek)", "Meteran", "0 cm bila kotak tertutup", "D, baris Akhir"],
    ], [5.2, 3.8, 4.0, 3.4], size=9.5, center=(3,))
    D.p("Posisi tiap titik belok dihitung dari jarak dan sudut tersebut, seperti poligon pada "
        "pengukuran tanah, lalu dibandingkan dengan rute rencana. Posisi menurut robot dihitung "
        "dari jarak perintah (FW berbasis waktu) dan arah dari yaw MPU. Sudut di T4 tidak dapat "
        "diukur dengan benang karena tidak ada segmen sesudahnya, sehingga hanya yaw MPU-nya yang "
        "tercatat.")

    # 3
    D.h1("3. Alat dan Bahan")
    D.table(["No", "Alat / bahan", "Jumlah", "Keterangan"], [
        ["1", "Botol (plastik tebal disarankan; botol bir kaca boleh dengan hati-hati)", "5",
         "Badan dudukan S, T1, T2, T3, T4"],
        ["2", "Pasir atau kerikil", "secukupnya", "Pengisi botol. Bukan air: air di dalam air tidak "
         "menambah berat"],
        ["3", "Plastik kresek, karet gelang, lakban", "secukupnya", "Penutup mulut botol"],
        ["4", "Pipa PVC ¾\"", "5 pendek + 3 panjang", "Pendek: tinggi sampai atas sok = kedalaman − "
         "15 cm. Panjang: ± 60 cm (5 batang lebih leluasa)"],
        ["5", "Sok (sambungan lurus) PVC ¾\"", "5", "Dilem ke ujung atas pipa pendek"],
        ["6", "Lem PVC", "1", "Hanya untuk sok ke pipa pendek"],
        ["7", "Kabel ties panjang ≥ 30 cm", "10–15", "Mengikat pipa pendek ke badan botol"],
        ["8", "Isolasi listrik hitam / lakban kain", "1 rol", "Dililit di atas kabel ties agar "
         "tidak melorot. Jangan lakban coklat/bening"],
        ["9", "Potongan karet (ban dalam / sandal bekas)", "5", "Alas anti-selip di dasar botol"],
        ["10", "Lakban warna (mis. oranye)", "1", "Tanda tinggi benang di pipa panjang dan label "
         "dudukan"],
        ["11", "Benang tukang (nilon bangunan)", "1 gulung", "Benang antar pipa"],
        ["12", "Meteran ≥ 3 m", "1", "Mengukur jarak"],
        ["13", "Busur derajat (yang besar lebih mudah dibaca)", "1", "Mengukur sudut"],
        ["14", "Stiker / lakban warna kecil", "1", "Titik acuan di robot"],
        ["15", "HP (aplikasi waterpass), lembar data, pulpen", "—", "Cek tegak pipa; mencatat"],
    ], [1.0, 6.4, 2.6, 6.4], size=9.3, center=(0, 2))

    # 4
    D.h1("4. Membuat Dudukan Penanda")
    D.figure(g["dudukan"], "Gambar 2. (a) Rakitan dudukan penanda; (b) tiang lengkap di kolam "
             "setelah pipa panjang dicolok (contoh kedalaman 75 cm)", 16.0)
    D.steps([
        ("Ukur kedalaman air ", "dari dasar sampai permukaan di beberapa titik area C1; pakai yang "
         "paling dangkal. Tinggi dudukan sampai atas sok = kedalaman − 15 cm, supaya robot lewat "
         "di atasnya tanpa menyenggol."),
        ("Isi botol dengan pasir kering ", "memakai corong atau kertas digulung. Ketuk-ketuk agar "
         "padat lalu tambah sampai hampir penuh. Tutup mulut botol dengan plastik, ikat karet "
         "gelang, lalu lilit lakban. Tutup tidak harus kedap air; tugasnya hanya menahan pasir."),
        ("Tempel alas karet ", "di dasar botol selagi kering (lem atau double tape)."),
        ("Lem sok ke ujung atas pipa pendek ", "dengan lem PVC."),
        ("Ikat pipa pendek ke botol. ", "Berdirikan botol dan pipa di lantai yang rata sehingga "
         "ujung bawah pipa rata dengan dasar botol. Ikat dengan 2–3 kabel ties di badan botol yang "
         "lurus (bukan di leher), kencangkan, lalu lilit isolasi di atasnya."),
        ("Cek tegak ", "dengan aplikasi waterpass di HP atau dibandingkan dengan kusen pintu."),
        ("Beri label ", "S, T1, T2, T3, T4 dengan lakban warna di tiap dudukan."),
        ("Siapkan pipa panjang ± 60 cm. ", f"Beri tanda lakban pada jarak yang sama dari ujung "
         f"bawah di semua pipa panjang (mis. {TANDA} cm). Pipa panjang tidak dilem."),
    ])
    D.note("Titik penanda adalah AS PIPA, bukan tengah botol. Saat dudukan ditaruh, yang "
           "dipaskan di bawah titik acuan robot adalah pipanya.", lead="Penting: ")

    # 5
    D.h1("5. Titik Acuan Robot")
    D.figure(g["acuan"], "Gambar 3. Sketsa tampak atas robot (bukan ukuran persis): letak stiker "
             "titik acuan dan zona baling-baling", 12.5)
    D.p("Bagian tengah robot tertutup kotak elektronik, sehingga dipilih satu titik acuan di garis "
        "tengah robot, sedekat mungkin ke titik tengah badan, yang dasar kolam di bawahnya masih "
        "terlihat lewat celah antara dua pelampung (misalnya tepat di belakang kotak). Tempel "
        "stiker di titik itu dan pakai titik yang sama di semua percobaan. Baling-baling menonjol "
        "di samping badan robot, jadi tangan harus menjauh selama motor menyala.")

    # 6
    D.h1("6. Pembagian Tugas")
    D.table(["Peran", "Saat robot berjalan", "Saat mengukur"], [
        ["Operator GUI", "Mengirim perintah dari halaman MANUAL. Perintah berikutnya dikirim segera "
         "setelah FIN; khusus setelah FIN FW, tunggu penanda bilang \"OKE\".",
         "Mencatat angka ke lembar data."],
        ["Penanda (di dalam kolam)", "Menaruh dudukan di bawah stiker setiap FIN FW, lalu menjauh "
         "dari robot.", "Memegang pipa tegak; membaca busur."],
        ["Pengukur", "Diam dan menjauh dari jalur robot agar tidak membuat riak; mencatat jam mulai "
         "tiap percobaan.", "Mencolok pipa panjang, menarik benang, membaca meteran."],
    ], [3.4, 7.0, 6.0], size=9.5)
    D.p("Minimal 3 orang. Bila hanya bertiga, operator ikut memegang pipa saat mengukur.",
        italic=True, size=10)

    # 7
    D.h1("7. Prosedur Saat Robot Berjalan")
    D.h2("7.1 Persiapan sesi")
    D.steps([
        "Isi penuh baterai robot. Nyalakan robot dalam keadaan diam sampai peringatan \"Gyro belum "
        "terkalibrasi\" di GUI hilang. Bila robot bergerak saat kalibrasi, yaw MPU merayap dan "
        "data MPU tidak dapat dipakai.",
        "Pilih mode REAL di GUI. Pastikan saklar Log MPU menyala (default menyala sejak aplikasi "
        "dibuka) dan catat nama berkas log yang sedang ditulis.",
        "Letakkan robot di posisi start C1 seperti pada rancangan (± 1 panjang robot dari dinding "
        "ujung, ± 20 cm dari dinding kiri), menghadap sepanjang kolam.",
    ])
    D.h2("7.2 Satu percobaan")
    D.figure(g["alur"], "Gambar 4. Urutan kerja di setiap titik belok", 16.4)
    D.figure(g["fin"], "Gambar 5. Saat FIN FW: dudukan ditaruh dengan as pipa tepat di bawah "
             "stiker; atas sok ≥ 15 cm di bawah permukaan air", 12.0)
    D.steps([
        ("Dudukan S: ", "taruh di dasar dengan as pipa tepat di bawah stiker (robot masih diam). "
         "Catat jam mulai."),
        ("Kirim FW:200 ", "(halaman MANUAL: maju 2 m). Semua orang diam dan menjauh dari jalur."),
        ("Saat FIN FW:200 muncul dan baling-baling berhenti, ", "penanda mendekat pelan-pelan, "
         "menaruh dudukan T1 dengan as pipa tepat di bawah stiker (lihat tegak lurus dari atas), "
         "menjauh, lalu bilang \"OKE\"."),
        ("Kirim CW:90. ", "Setelah FIN CW:90, langsung kirim FW:100 (maju 1 m)."),
        ("Ulangi langkah 3–4 ", "untuk T2 (setelah FW:100), T3 (setelah FW:200), dan T4 (setelah "
         "FW:100 kedua)."),
        ("Kirim CW:90 terakhir. ", "Setelah FIN, tunggu robot diam ± 3 detik, lalu angkat robot "
         "dari kolam tanpa menyenggol dudukan."),
    ])
    D.note("Robot memang diam beberapa detik saat dudukan ditaruh. Itu bukan pengukuran dari "
           "titik awal: robot tidak dipegang atau dipindahkan, dan tetap menjalankan seluruh "
           "kotak.", lead="Catatan: ")

    # 8
    D.h1("8. Memasang Benang dan Mengukur")
    D.figure(g["benang"], "Gambar 6. Pipa panjang dicolok ke sok tiap dudukan, benang diikat di "
             "tanda lakban yang tingginya sama", 16.0)
    D.steps([
        ("Colok pipa panjang ", "ke sok dudukan sampai mentok, dipegang tegak."),
        ("Ikat benang ", "di tanda lakban, dari pipa ke pipa, lalu tarik kencang sampai lurus "
         "(tidak melengkung). Tarik pelan agar dudukan tidak terguling."),
        ("Jarak: ", "bentangkan meteran sepanjang benang dari as pipa ke as pipa. Tulis di kolom "
         "D."),
        ("Sudut: ", "lihat Gambar 7. Tulis sudut dalam yang terbaca di kolom E."),
    ])
    D.figure(g["busur"], "Gambar 7. Membaca sudut dalam di pojok T1: busur datar di atas benang, "
             "pusatnya di as pipa, garis 0° sejajar benang ke titik sebelumnya", 9.5)
    D.p("Cukup 3 pipa panjang yang dipindah-pindah:")
    D.table(["Putaran", "Pipa panjang di", "Yang diukur", "Baris lembar data"], [
        ["1", "S, T1, T2", "Jarak S–T1; sudut dalam di T1", "S → T1 (D, E)"],
        ["2", "T1, T2, T3", "Jarak T1–T2; sudut dalam di T2", "T1 → T2 (D, E)"],
        ["3", "T2, T3, T4", "Jarak T2–T3; sudut dalam di T3; jarak T3–T4",
         "T2 → T3 (D, E); T3 → T4 (D)"],
        ["4 (opsional)", "T4, S", "Jarak T4–S", "Akhir (D)"],
    ], [2.4, 3.0, 6.2, 4.8], size=9.5, center=(0,))
    contoh = ", ".join(f"{c} cm → {_f(_siku(c))}°" for c in (90, 95, 100, 105, 110))
    D.note("dari pojok, tandai 60 cm di benang ke titik sebelumnya dan 80 cm di benang ke titik "
           "berikutnya, lalu ukur jarak antar tanda (c). Bila c = 100 cm, sudutnya tepat 90° "
           "(seperti cara tukang mengecek siku 3-4-5). Sudut dalam = arccos((60² + 80² − c²) ÷ "
           f"(2 × 60 × 80)); contoh: {contoh}. Pakai untuk memeriksa bacaan busur yang "
           "meragukan.", lead="Cek silang (opsional): ")

    # 9
    D.h1("9. Mengambil Yaw MPU dari Log")
    D.p("GUI mencatat yaw MPU setiap 1 detik dan setiap FIN ke berkas logs/log_feeder_*.txt di "
        "samping program GUI. Salin berkas log sesi tersebut ke laptop, lalu jalankan:")
    D.code("python Pengujian/buat_grafik_c1.py --log <berkas log>")
    D.p("Keluarannya berupa daftar setiap FIN beserta jam, perintah, yaw saat FIN, dan yaw 3 "
        "detik sesudahnya. Pilih FIN yang jamnya masuk dalam percobaan yang dimaksud (lihat jam "
        "mulai yang dicatat), lalu salin ke kolom F:")
    D.table(["FIN pada log", "Nilai yang disalin", "Baris lembar data (kolom F)"], [
        ["FW:200 ke-1", "Yaw FIN", "S → T1"],
        ["FW:100 ke-1", "Yaw FIN", "T1 → T2"],
        ["FW:200 ke-2", "Yaw FIN", "T2 → T3"],
        ["FW:100 ke-2", "Yaw FIN", "T3 → T4"],
        ["CW:90 terakhir", "Yaw +3 s", "Akhir"],
    ], [4.6, 4.2, 7.6], size=9.5, center=(1,))

    # 10
    D.h1("10. Mengisi Lembar Data dan Membuat Grafik")
    D.steps([
        "Buka Pengujian/Lembar_Data_C1_Titik_Belok.xlsx. Isi hanya sel kuning: kolom D (jarak), "
        "E (sudut dalam), F (yaw MPU), dan Keterangan. Kolom abu-abu terhitung sendiri: galat "
        "jarak, sudut belok aktual (180° − sudut dalam), sudut belok MPU, dan MAE per segmen.",
        "Simpan, lalu jalankan:",
    ])
    D.code("python Pengujian/buat_grafik_c1.py")
    D.p("Hasilnya:")
    D.bullet(" rute rencana, lintasan aktual, dan lintasan menurut robot untuk tiap percobaan "
             "(setara Fig. 4 pada [1]).", "gambar/fig_c1_rute_aktual.png —")
    D.bullet(" galat posisi rata-rata di T1–T4, aktual vs rencana dan menurut robot vs aktual.",
             "gambar/fig_c1_galat_titik.png —")
    D.bullet(" tabel galat per titik dan per segmen di terminal (setara Tabel I pada [1]), "
             "ditambah cek jarak T4–S bila diisi.", "Terminal —")

    # 11
    D.h1("11. Keselamatan dan Tips")
    D.bullet(" tangan menjauh selama motor menyala. Operator hanya mengirim perintah setelah "
             "penanda bilang \"OKE\".", "Baling-baling:")
    D.bullet(" bila memakai botol kaca, taruh pelan-pelan. Bila pecah, hentikan uji dan bersihkan "
             "kolam. Botol plastik lebih aman.", "Botol kaca:")
    D.bullet(" Raspberry Pi, laptop, dan charger jauh dari air.", "Listrik:")
    D.bullet(" bergerak pelan dan jangan berdiri di jalur robot; riak air mendorong robot.",
             "Riak:")
    D.bullet(" bila dudukan tersenggol setelah ditaruh, catat di Keterangan dan ulangi percobaan. "
             "Percobaan gagal (FIN tidak muncul, robot menabrak dinding) tetap dicatat lalu "
             "diganti sampai ada 3 data valid.", "Percobaan gagal:")
    D.bullet(" pasir tetap di dalam botol tertutup; angkat semua dudukan dan benang setelah "
             "selesai.", "Kebersihan kolam:")

    # 12
    D.h1("12. Daftar Periksa Sebelum ke Kolam")
    for item in (
            "5 dudukan penanda (S, T1–T4) sudah berlabel dan tegak",
            "3–5 pipa panjang bertanda lakban di jarak yang sama",
            "Benang, meteran, busur, stiker, gunting",
            "Kedalaman kolam sudah diukur; atas sok ≥ 15 cm di bawah permukaan air",
            "Stiker titik acuan terpasang di robot",
            "Baterai robot penuh",
            "GUI mode REAL, Log MPU menyala, nama berkas log dicatat",
            "Lembar data (cetak atau di HP) dan pulpen",
            "Minimal 3 orang dengan peran yang sudah dibagi"):
        D.p("☐  " + item, after=2)

    D.h1("Referensi")
    D.p("[1] J. Putra dan D. E. Saputra, “Autonomous Drone Indoor Navigation Based on Virtual 3D "
        "Map Reference,” IEEE, 2022.", size=10)
    return d


def main():
    g = semua_gambar()
    for v in g.values():
        print(f"PNG  : {v}")
    d = build(g)
    try:
        d.save(OUT)
    except PermissionError:
        sys.exit(f"Tidak bisa menulis {OUT.name} — tutup dulu file itu di Word.")
    print(f"DOCX : {OUT}")
    pdf = export_pdf(OUT)
    print(f"PDF  : {pdf}" if pdf else "PDF  : dilewati (Word/LibreOffice tidak ditemukan).")


if __name__ == "__main__":
    main()
