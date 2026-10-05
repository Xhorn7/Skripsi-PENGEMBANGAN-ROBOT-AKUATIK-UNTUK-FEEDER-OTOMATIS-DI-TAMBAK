"""
Generator dokumen Rancangan Skenario Pengujian Gerak Robot (DOCX + PDF).

    pip install -r requirements.txt
    python build_skenario.py

Bisa dijalankan dari folder mana pun, di PC maupun laptop. Gambar ditulis ke
gambar/, dokumen ke folder ini. PDF dibuat lewat Microsoft Word (Windows) atau
LibreOffice bila tersedia; kalau keduanya tidak ada, PDF dilewati.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
GAMBAR = HERE / "gambar"
OUT_DOCX = HERE / "Rancangan_Skenario_Pengujian_Gerak.docx"

# =====================================================================
# Gambar
# =====================================================================
INK = "#1f2933"
ROBOT = "#2563eb"
GHOST = "#94a3b8"
RED = "#dc2626"
GREEN = "#15803d"
WATER = "#e0f2fe"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})


def _save(fig, name, rect=None):
    GAMBAR.mkdir(exist_ok=True)
    path = GAMBAR / name
    fig.tight_layout(rect=rect)
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return path


KERAMIK_CM = 25
MOZAIK_CM = 4.1
KOLAM_KOLOM, KOLAM_BARIS = 8, 20
ROBOT_P_CM, ROBOT_L_CM = 60, 42


def _kolam(ax, title):
    ax.add_patch(Rectangle((0, 0), KOLAM_KOLOM, KOLAM_BARIS, fc=WATER, ec="#1e3a8a", lw=2.2))
    for i in range(1, KOLAM_KOLOM):
        ax.plot([i, i], [0, KOLAM_BARIS], color="#93c5fd", lw=0.7)
    for j in range(1, KOLAM_BARIS):
        ax.plot([0, KOLAM_KOLOM], [j, j], color="#93c5fd", lw=0.7)
    ax.set_xticks(range(0, KOLAM_KOLOM + 1))
    ax.set_yticks(range(0, KOLAM_BARIS + 1, 2))
    ax.tick_params(labelsize=7, length=2)
    ax.set_xlim(-0.3, KOLAM_KOLOM + 0.3)
    ax.set_ylim(-0.6, KOLAM_BARIS + 0.3)
    ax.set_aspect("equal")
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(title, fontsize=9.5, weight="bold", color=INK, loc="left")


def _jalur(ax, pts, color=ROBOT):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=color, lw=2.2, marker="o", ms=3.5, zorder=4)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        ax.add_patch(FancyArrowPatch((x1, y1), ((x1 + x2) / 2 + (x2 - x1) * 0.08,
                                                (y1 + y2) / 2 + (y2 - y1) * 0.08),
                                     arrowstyle="-|>", mutation_scale=11, color=color, lw=0,
                                     zorder=5))
    ax.plot(*pts[0], marker="*", ms=13, color=GREEN, mec="black", mew=0.5, zorder=6)


def _lbl(ax, x, y, t, color=INK, ha="left", size=7.2, weight="normal"):
    ax.text(x, y, t, fontsize=size, color=color, ha=ha, va="center", weight=weight,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85), zorder=7)


def fig_sumbu():
    fig, ax = plt.subplots(figsize=(8, 9.5))
    ax.add_patch(Rectangle((0, 0), KOLAM_KOLOM, KOLAM_BARIS, fc=WATER, ec="#1e3a8a", lw=2.5))
    for i in range(1, KOLAM_KOLOM):
        ax.plot([i, i], [0, KOLAM_BARIS], color="#93c5fd", lw=0.8)
    for j in range(1, KOLAM_BARIS):
        ax.plot([0, KOLAM_KOLOM], [j, j], color="#93c5fd", lw=0.8)
    for i in range(KOLAM_KOLOM + 1):
        ax.text(i, -0.45, str(i), ha="center", va="top", fontsize=10, color="#b91c1c",
                weight="bold")
    for j in range(KOLAM_BARIS + 1):
        ax.text(-0.3, j, str(j), ha="right", va="center", fontsize=9, color=GREEN, weight="bold")
    ax.add_patch(FancyArrowPatch((0, -1.6), (KOLAM_KOLOM, -1.6), arrowstyle="-|>",
                                 mutation_scale=18, color="#b91c1c", lw=2.5))
    ax.text(4, -2.1, "KOLOM → hitung ke SAMPING (kiri → kanan)\n"
            "0 sampai 8  •  sisi PENDEK kolam (2 m)", ha="center", va="top", fontsize=10.5,
            color="#b91c1c", weight="bold")
    ax.add_patch(FancyArrowPatch((-1.6, 0), (-1.6, KOLAM_BARIS), arrowstyle="-|>",
                                 mutation_scale=18, color=GREEN, lw=2.5))
    ax.text(-2.7, 10, "BARIS ↑ hitung ke DEPAN (menjauh dari tangga)\n"
            "0 sampai 20  •  sisi PANJANG kolam (5 m)", ha="center", va="center", rotation=90,
            fontsize=10.5, color=GREEN, weight="bold")
    ax.plot(0, 0, marker="*", ms=22, color="#f59e0b", mec="black", zorder=6)
    ax.text(0.25, 0.35, "pojok (0 ; 0)\ntitik nol", fontsize=9.5, weight="bold", color=INK,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#f59e0b"))
    rp, rl = ROBOT_P_CM / KERAMIK_CM, ROBOT_L_CM / KERAMIK_CM
    _robot_k(ax, 4, 2, 90, ROBOT, length=rp, width=rl)
    ax.plot([4, 4], [0, 2], color="#b91c1c", lw=1.6, ls="--", zorder=6)
    ax.plot([0, 4], [2, 2], color=GREEN, lw=1.6, ls="--", zorder=6)
    ax.text(5.05, 2.1, "robot di (4 ; 2)\n= 4 keramik dari dinding KIRI\n"
            "= 2 keramik dari dinding BELAKANG", fontsize=9.5, va="center", color=INK,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#cbd5e1"))
    ax.plot(6, 12, "o", ms=10, color="#7c3aed", mec="black", zorder=6)
    ax.plot([6, 6], [0, 12], color="#7c3aed", lw=1, ls=":")
    ax.plot([0, 6], [12, 12], color="#7c3aed", lw=1, ls=":")
    ax.text(5.9, 12.7, "(6 ; 12)\nkolom 6, baris 12", fontsize=9.5, ha="right",
            color="#7c3aed", weight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
    ax.text(4, 20.6, "ujung jauh kolam", ha="center", fontsize=10, color="#475569")
    ax.text(4, -4.4, "▲ OPERATOR BERDIRI DI SINI (ujung pendek dekat tangga), "
            "menghadap ke arah panjang kolam", ha="center", fontsize=10, weight="bold", color=INK)
    ax.text(4, -5.4, "Cara tulis: (kolom ; baris)  →  angka SAMPING dulu, baru angka DEPAN",
            ha="center", fontsize=11, weight="bold", color="#1e3a8a",
            bbox=dict(boxstyle="round,pad=0.35", fc="#fef9c3", ec="#eab308"))
    ax.set_xlim(-3.8, 10.8)
    ax.set_ylim(-6.2, 21.3)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Kolam dilihat dari atas (1 kotak = 1 keramik = 25 cm)", fontsize=12.5,
                 weight="bold", color=INK)
    return _save(fig, "fig_sumbu_kolam.png")


def fig_kolam():
    fig, axs = plt.subplots(1, 3, figsize=(9.4, 7.6))
    a, b, c = axs

    _kolam(a, "A · Lurus")
    for y_end, cmd, col in ((4, "FW:50", "#16a34a"), (6, "FW:100", "#ea580c"),
                            (10, "FW:200", RED)):
        a.plot([3.85, 4.15], [y_end, y_end], color=col, lw=2.2, zorder=5)
        _lbl(a, 4.4, y_end, f"{cmd} → baris {y_end}", col)
    _jalur(a, [(4, 2), (4, 10)])
    _lbl(a, 4.4, 2, "start: kolom 4, baris 2", GREEN, weight="bold")
    _lbl(a, 0.2, 15.5, "maju di tengah kolam\n(kolom 4)\n\n50 cm = 2 keramik\n"
         "100 cm = 4 keramik\n200 cm = 8 keramik", INK, size=7)

    _kolam(b, "B · Belok")
    th = np.radians(np.linspace(180, 90, 30))
    b.plot(1.5, 5, marker="*", ms=13, color=GREEN, mec="black", mew=0.5, zorder=6)
    b.plot([1.5, 1.5], [5, 6.5], color=ROBOT, lw=2.2)
    b.plot(2.5 + np.cos(th), 6.5 + np.sin(th), color=ROBOT, lw=2.2)
    b.add_patch(FancyArrowPatch((2.5, 7.5), (3.9, 7.5), arrowstyle="-|>", mutation_scale=11,
                                color=ROBOT, lw=2.2))
    _lbl(b, 0.2, 3.9, "CW:45 / CW:90\nstart kolom 1,5\nbelok ke kanan", ROBOT)
    th2 = np.radians(np.linspace(0, 90, 30))
    b.plot(6.5, 12, marker="*", ms=13, color=GREEN, mec="black", mew=0.5, zorder=6)
    b.plot([6.5, 6.5], [12, 13.5], color="#7c3aed", lw=2.2)
    b.plot(5.5 + np.cos(th2), 13.5 + np.sin(th2), color="#7c3aed", lw=2.2)
    b.add_patch(FancyArrowPatch((5.5, 14.5), (4.1, 14.5), arrowstyle="-|>", mutation_scale=11,
                                color="#7c3aed", lw=2.2))
    _lbl(b, 7.8, 10.9, "CCW:45 / CCW:90\nstart kolom 6,5\nbelok ke kiri", "#7c3aed", ha="right")
    _lbl(b, 0.2, 18.2, "belok selalu ke arah\nsisi kolam yang lega", INK, size=7)

    _kolam(c, "C1 · Kotak 1 × 2 m")
    kotak = [(2, 4), (2, 12), (6, 12), (6, 4), (2, 4)]
    _jalur(c, kotak)
    _lbl(c, 2.2, 6.5, "1. FW:200", INK)
    _lbl(c, 4, 12.6, "2. CW:90  3. FW:100", INK, ha="center")
    _lbl(c, 5.8, 9.5, "4. CW:90\n5. FW:200", INK, ha="right")
    _lbl(c, 4, 3.4, "6. CW:90  7. FW:100", INK, ha="center")
    _lbl(c, 2.2, 2.3, "8. CW:90 → kembali ke start", GREEN)
    _lbl(c, 0.2, 16.5, "start ± 1 panjang robot dari\ndinding ujung, ± 20 cm dari\n"
         "dinding kiri; 2 m = 8 baris,\n1 m = 4 kolom", INK, size=7)

    rp, rl = ROBOT_P_CM / KERAMIK_CM, ROBOT_L_CM / KERAMIK_CM
    for ax, x, y, h in ((a, 4, 2, 90), (b, 1.5, 5, 90), (b, 6.5, 12, 90), (c, 6, 12, 0)):
        _robot_k(ax, x, y, h, "#f97316", filled=False, length=rp, width=rl)
    c.annotate("", xy=(8, 13.3), xytext=(6 + rp / 2, 13.3),
               arrowprops=dict(arrowstyle="<->", color="#c2410c", lw=1.2))
    _lbl(c, 7.9, 14.0, "sisa ± 20 cm", "#c2410c", ha="right", size=6.8, weight="bold")
    fig.suptitle("Tata letak skenario di kolam uji 5 × 2 m\n"
                 "(1 kotak = 25 cm; garis oranye = badan robot 60 × 42 cm sesuai skala)",
                 fontsize=10.5, weight="bold", color=INK, x=0.01, ha="left")
    return _save(fig, "fig_kolam_skenario.png", rect=[0, 0, 1, 0.93])


def fig_hitung():
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.6))
    a.add_patch(Rectangle((0, 0), 6, 5, fc=WATER, ec="none"))
    for i in range(7):
        a.plot([i, i], [0, 5], color="#60a5fa", lw=0.9)
    for j in range(6):
        a.plot([0, 6], [j, j], color="#60a5fa", lw=0.9)
    a.set_xlim(-0.2, 6.2)
    a.set_ylim(-0.9, 5.2)
    m = MOZAIK_CM / KERAMIK_CM          # satu mozaik dalam satuan keramik
    b.add_patch(Rectangle((0, 0), 6, 5, fc=WATER, ec="none"))
    for i in np.arange(0, 6 + 1e-9, m):
        b.plot([i, i], [0, 5], color="#bfdbfe", lw=0.5)
    for j in np.arange(0, 5 + 1e-9, m):
        b.plot([0, 6], [j, j], color="#bfdbfe", lw=0.5)
    b.set_xlim(-0.2, 6.2)
    b.set_ylim(-0.9, 5.2)
    for ax in (a, b):
        ax.set_aspect("equal")
        ax.axis("off")
    rp, rl = ROBOT_P_CM / KERAMIK_CM, ROBOT_L_CM / KERAMIK_CM

    a.set_title("Hitung JARAK: baca baris titik tengah robot", fontsize=10, weight="bold",
                color=INK, loc="left")
    _robot_k(a, 2.5, 1.3, 90, GHOST, filled=False, length=rp, width=rl)
    _robot_k(a, 2.5, 3.7, 90, ROBOT, length=rp, width=rl)
    a.plot([2.5, 2.5], [1.3, 3.7], color=GREEN, lw=1.3, ls=":")
    for y, t in ((1.3, "awal: baris 1,3"), (3.7, "akhir: baris 3,7")):
        a.plot([2.5, 3.9], [y, y], color=GREEN, lw=0.8, ls=":")
        _lbl(a, 4.0, y, t, GREEN, weight="bold", size=8.5)
    _lbl(a, 0.05, -0.5, "jarak = (3,7 − 1,3) × 25 cm = 2,4 × 25 = 60 cm   (perintah FW:50 → galat 10 cm)",
         INK, size=8.5)

    b.set_title("Hitung SUDUT: mozaik sepanjang pelampung kiri (foto tegak)", fontsize=10,
                weight="bold", color=INK, loc="left")
    sx, sy, n = 1.2, 0.9, 10                         # ujung belakang; 10 mozaik ke samping & depan
    ex, ey = sx + n * m, sy + n * m
    pw = 2.4 * m                                     # lebar pelampung ± 10 cm
    u = np.array([ex - sx, ey - sy]) / np.hypot(ex - sx, ey - sy)
    v = np.array([-u[1], u[0]]) * pw / 2
    p0, p1 = np.array([sx, sy]), np.array([ex, ey])
    b.add_patch(Polygon([p0 + v, p1 + v, p1 - v, p0 - v], closed=True, fc=ROBOT, ec=ROBOT,
                        alpha=0.8, zorder=5))
    b.plot([sx, ex], [sy, ey], "o", color="#facc15", mec="black", ms=7, zorder=8)
    b.plot([sx, ex], [sy, sy], color=RED, lw=1.4, ls="--", zorder=7)
    b.plot([ex, ex], [sy, ey], color=RED, lw=1.4, ls="--", zorder=7)
    _lbl(b, 0.05, sy + 0.55, "ujung belakang", INK, size=8)
    _lbl(b, ex - 1.6, ey + 0.35, "ujung depan", INK, size=8)
    _lbl(b, (sx + ex) / 2, sy - 0.45, "SAMPING = 10 mozaik", RED, ha="center", size=8)
    _lbl(b, ex + 0.12, (sy + ey) / 2, "DEPAN\n= 10 mozaik", RED, size=8)
    _lbl(b, 0.05, 4.65, "start menghadap sepanjang kolam (DEPAN). Setelah belok, hitung\n"
         "kotak mozaik dari ujung belakang ke ujung depan satu pelampung:", INK, size=8)
    _lbl(b, 0.05, -0.5, "sudut = atan(10 ÷ 10) = 45°;  cek panjang = √(10² + 10²) × 4,1 = 58 cm ≈ 60 cm",
         INK, size=8.5)
    fig.tight_layout()
    return _save(fig, "fig_hitung_keramik.png")


def _robot_k(ax, x, y, heading_deg, color, filled=True, length=1.6, width=0.9):
    t = np.radians(heading_deg)
    fwd = np.array([np.cos(t), np.sin(t)])
    side = np.array([-np.sin(t), np.cos(t)])
    c = np.array([x, y])
    L, W = length, width
    pts = [c + fwd * L * 0.3 + side * W / 2, c + fwd * L / 2, c + fwd * L * 0.3 - side * W / 2,
           c - fwd * L / 2 - side * W / 2, c - fwd * L / 2 + side * W / 2]
    ax.add_patch(Polygon(pts, closed=True, fc=color if filled else "none", ec=color, lw=1.6,
                         ls="-" if filled else "--", alpha=0.85 if filled else 1, zorder=5))
    ax.add_patch(Circle(c, 0.07, fc="white", ec=INK, lw=0.8, zorder=6))


# =====================================================================
# Dokumen
# =====================================================================
FONT = "Times New Roman"
NAVY = RGBColor(0x1E, 0x3A, 0x5F)
HEAD_BG = "1E3A5F"
ZEBRA = "F1F5F9"
NOTE_BG = "FFF7E6"
CENTER = WD_ALIGN_PARAGRAPH.CENTER


class Doc:
    def __init__(self):
        self.d = Document()
        self._styles()
        sec = self.d.sections[0]
        sec.page_width, sec.page_height = Cm(21), Cm(29.7)
        sec.left_margin = sec.right_margin = Cm(2.3)
        sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.0)
        hp = sec.header.paragraphs[0]
        hr = hp.add_run("Rancangan Skenario Pengujian Gerak Robot Akuatik")
        hr.font.size = Pt(8.5)
        hr.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        fp = sec.footer.paragraphs[0]
        fp.alignment = CENTER
        self._page_field(fp)

    @staticmethod
    def _set_fonts(el, name):
        rpr = el.get_or_add_rPr()
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts")
            rpr.insert(0, rf)
        for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if rf.get(qn(a)) is not None:
                del rf.attrib[qn(a)]
        for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rf.set(qn(a), name)

    def _styles(self):
        st = self.d.styles
        st["Normal"].font.size = Pt(11)
        self._set_fonts(st["Normal"].element, FONT)
        st["Normal"].paragraph_format.space_after = Pt(4)
        st["Normal"].paragraph_format.line_spacing = 1.15
        for lvl, size in ((1, 13.5), (2, 11.5)):
            h = st[f"Heading {lvl}"]
            self._set_fonts(h.element, FONT)
            h.font.size = Pt(size)
            h.font.bold = True
            h.font.italic = False
            h.font.color.rgb = NAVY
            h.paragraph_format.space_before = Pt(14 if lvl == 1 else 9)
            h.paragraph_format.space_after = Pt(5)
            h.paragraph_format.keep_with_next = True
        lb = st["List Bullet"]
        self._set_fonts(lb.element, FONT)
        lb.font.size = Pt(11)
        lb.paragraph_format.space_after = Pt(2)

    @staticmethod
    def _page_field(par):
        run = par.add_run()
        for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
            if tag:
                el = OxmlElement("w:fldChar")
                el.set(qn("w:fldCharType"), tag)
            else:
                el = OxmlElement("w:instrText")
                el.set(qn("xml:space"), "preserve")
                el.text = text
            run._r.append(el)
        run.font.size = Pt(9)

    # ---- sel & tabel ----
    @staticmethod
    def shade(cell, color):
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), color)
        cell._tc.get_or_add_tcPr().append(shd)

    @staticmethod
    def _margins(t, top=50, bottom=50, left=80, right=80):
        mar = OxmlElement("w:tblCellMar")
        for side, v in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
            el = OxmlElement(f"w:{side}")
            el.set(qn("w:w"), str(v))
            el.set(qn("w:type"), "dxa")
            mar.append(el)
        t._tbl.tblPr.append(mar)

    @staticmethod
    def cell(cell, text, bold=False, size=9.5, color=None, align=None):
        cell.text = ""
        lines = text if isinstance(text, list) else [text]
        for i, line in enumerate(lines):
            p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            if align:
                p.alignment = align
            segs = line if isinstance(line, tuple) else ((line, bold),)
            for seg, b in segs:
                r = p.add_run(seg)
                r.bold = b
                r.font.size = Pt(size)
                if color:
                    r.font.color.rgb = color
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    def table(self, headers, rows, widths, size=9.5, zebra=True, center=(), header_size=None,
              row_height=None):
        t = self.d.add_table(rows=1, cols=len(headers))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        self._margins(t)
        hdr = t.rows[0]
        el = OxmlElement("w:tblHeader")
        el.set(qn("w:val"), "true")
        hdr._tr.get_or_add_trPr().append(el)
        for i, h in enumerate(headers):
            self.cell(hdr.cells[i], h, bold=True, size=header_size or size,
                      color=RGBColor(0xFF, 0xFF, 0xFF), align=CENTER)
            self.shade(hdr.cells[i], HEAD_BG)
        for ri, row in enumerate(rows):
            cells = t.add_row().cells
            t.rows[-1]._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
            if row_height:
                t.rows[-1].height = Cm(row_height)
            for ci, val in enumerate(row):
                self.cell(cells[ci], val, size=size, align=CENTER if ci in center else None)
                if zebra and ri % 2 == 1:
                    self.shade(cells[ci], ZEBRA)
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
        for i, gc in enumerate(t._tbl.tblGrid.findall(qn("w:gridCol"))):
            gc.set(qn("w:w"), str(int(widths[i] * 567)))
        self.d.add_paragraph().paragraph_format.space_after = Pt(2)
        return t

    # ---- teks ----
    def h1(self, text):
        self.d.add_heading(text, level=1)

    def h2(self, text):
        self.d.add_heading(text, level=2)

    def p(self, text, lead=None, size=None, italic=False, after=None, bold=False):
        par = self.d.add_paragraph()
        if lead:
            r = par.add_run(lead)
            r.bold = True
            if size:
                r.font.size = Pt(size)
        r = par.add_run(text)
        r.italic = italic
        r.bold = bold
        if size:
            r.font.size = Pt(size)
        if after is not None:
            par.paragraph_format.space_after = Pt(after)
        return par

    def bullet(self, text, lead=None):
        par = self.d.add_paragraph(style="List Bullet")
        if lead:
            par.add_run(lead).bold = True
        par.add_run(text)

    def steps(self, items):
        for i, it in enumerate(items, 1):
            par = self.d.add_paragraph()
            par.paragraph_format.left_indent = Cm(0.9)
            par.paragraph_format.first_line_indent = Cm(-0.6)
            par.paragraph_format.space_after = Pt(2)
            par.add_run(f"{i}.  ")
            if isinstance(it, tuple):
                par.add_run(it[0]).bold = True
                par.add_run(it[1])
            else:
                par.add_run(it)

    def code(self, text):
        par = self.d.add_paragraph()
        par.paragraph_format.left_indent = Cm(0.9)
        r = par.add_run(text)
        r.font.name = "Consolas"
        r.font.size = Pt(10)

    def note(self, text, lead="Catatan: "):
        t = self.d.add_table(rows=1, cols=1)
        t.autofit = False
        self._margins(t, 90, 90, 140, 140)
        c = t.rows[0].cells[0]
        c.width = Cm(16.4)
        self.cell(c, [((lead, True), (text, False))], size=10)
        self.shade(c, NOTE_BG)
        borders = OxmlElement("w:tblBorders")
        for side in ("top", "left", "bottom", "right"):
            el = OxmlElement(f"w:{side}")
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), "4")
            el.set(qn("w:color"), "E8C07A")
            borders.append(el)
        t._tbl.tblPr.append(borders)
        self.d.add_paragraph().paragraph_format.space_after = Pt(2)

    def figure(self, path, caption, width=16.0):
        par = self.d.add_paragraph()
        par.alignment = CENTER
        par.paragraph_format.keep_with_next = True
        par.paragraph_format.space_after = Pt(0)
        par.add_run().add_picture(str(path), width=Cm(width))
        c = self.d.add_paragraph()
        c.alignment = CENTER
        r = c.add_run(caption)
        r.italic = True
        r.font.size = Pt(9.5)


def build(fig):
    D = Doc()
    d = D.d

    # ---------------- judul ----------------
    t = d.add_paragraph()
    t.alignment = CENTER
    t.paragraph_format.space_after = Pt(2)
    r = t.add_run("RANCANGAN SKENARIO PENGUJIAN GERAK ROBOT")
    r.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = NAVY
    t = d.add_paragraph()
    t.alignment = CENTER
    r = t.add_run("Pengembangan Robot Akuatik untuk Feeder Otomatis di Tambak")
    r.italic = True
    r.font.size = Pt(12)
    info = d.add_table(rows=4, cols=2)
    info.autofit = False
    info.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (k, v) in enumerate((
            ("Disusun oleh", "Samuel Alfonsus"),
            ("Dosen Pembimbing", "Bapak Dany Eka Saputra"),
            ("Status", "Revisi akhir — disesuaikan dengan pelaksanaan uji (perubahan: bagian 11)"),
            ("Tanggal", "Oktober 2026"))):
        D.cell(info.rows[i].cells[0], k, bold=True, size=10.5)
        D.cell(info.rows[i].cells[1], ": " + v, size=10.5)
        info.rows[i].cells[0].width = Cm(3.8)
        info.rows[i].cells[1].width = Cm(11.8)
    d.add_paragraph()

    # ---------------- ringkasan ----------------
    D.h1("Ringkasan")
    D.table(["Pertanyaan", "Jawaban singkat"], [
        ["Gerakan apa yang diuji?",
         "Tiga kelompok: (A) maju lurus, (B) belok kanan dan kiri 45° dan 90°, (C1) kombinasi — "
         "lintasan kotak 1 × 2 m. Total 8 skenario."],
        ["Jaraknya berapa?",
         "Lurus 50, 100, dan 200 cm; belok 45° dan 90°; kotak 1 × 2 m (keliling 6 m). Semua muat "
         "di kolam uji 5 × 2 m dan masih di dalam batas perintah robot (FW 10–200 cm, "
         "CW/CCW 1–180°)."],
        ["Berapa kali pengulangan?",
         "Setiap skenario diulang 3 kali, total 24 percobaan."],
        ["Bagaimana cara mengukurnya?",
         "Dengan grid lantai kolam sebagai alat ukur: keramik 25 × 25 cm dan kotak mozaik 4,1 cm "
         "di dalamnya, seperti area uji bergrid pada [1]. A dibaca langsung dalam baris/kolom "
         "keramik; B dihitung dari kotak mozaik sepanjang satu pelampung pada foto tegak; C1 "
         "dari foto awal dan akhir. Hasilnya dibandingkan dengan perintah dan dengan yaw MPU dari "
         "log GUI memakai MAE dan MAPE seperti pada [1], [2]. Tidak perlu membeli alat."],
    ], [4.2, 12.2], size=10)

    # ---------------- 1 ----------------
    D.h1("1. Latar Belakang dan Tujuan Pengujian")
    D.p("Pengujian sebelumnya menunjukkan bahwa GUI pada Pengendali Utama dapat mengirim perintah "
        "dan robot membalas dengan sinyal ON dan FIN. Namun sinyal FIN hanya berarti robot sudah "
        "menyelesaikan perintah menurut perhitungannya sendiri; FIN belum membuktikan bahwa robot "
        "benar-benar bergerak sejauh atau berbelok sebesar yang diperintahkan. Hal ini penting "
        "terutama untuk perintah maju (FW), karena jaraknya diturunkan dari waktu tempuh dan tidak "
        "diukur oleh sensor, sehingga jarak nyata dapat berbeda akibat hambatan air, inersia, dan "
        "kondisi baterai.")
    D.p("Tujuan pengujian:")
    D.bullet("mengukur kesesuaian jarak tempuh aktual dengan perintah maju (FW);")
    D.bullet("mengukur kesesuaian sudut belok aktual dengan perintah belok (CW/CCW);")
    D.bullet("mengukur kemampuan robot menjalankan rangkaian gerakan (kombinasi) hingga sampai di "
             "titik yang direncanakan;")
    D.bullet("mengukur keterulangan (presisi) gerak robot melalui pengulangan;")
    D.bullet("membandingkan pembacaan sensor MPU dengan sudut aktual, untuk mengetahui seberapa "
             "dapat dipercaya sensor tersebut.")

    # ---------------- 2 ----------------
    D.h1("2. Karakteristik Robot yang Memengaruhi Rancangan Uji")
    D.table(["Aspek", "Kondisi pada robot", "Akibat pada pengujian"], [
        ["Ukuran badan", "Panjang 60 cm (2,4 keramik), lebar 42 cm (1,7 keramik).",
         "Posisi start diatur agar badan robot tidak menyentuh dinding kolam 2 m."],
        ["Perintah maju FW:<10–200 cm>",
         "Durasi = awalan 2,1 s + jarak ÷ 0,28 m/s (hasil kalibrasi, bagian 10.1); arah dijaga "
         "heading-hold MPU.",
         "Jarak tidak diukur sensor, jadi wajib diverifikasi dengan pengukuran dari luar robot."],
        ["Perintah belok CW/CCW:<1–180°>",
         "Motor dimatikan 15° sebelum yaw MPU mencapai target (TURN_COAST_DEG), karena robot "
         "masih berputar setelah motor mati.",
         "Sudut aktual dibandingkan dengan perintah dan dengan nilai MPU."],
        ["Mekanisme belok",
         "Differential thrust: satu motor dimatikan (CW = motor kiri jalan, CCW = motor kanan "
         "jalan).",
         "Robot berbelok melingkar, bukan di tempat; posisinya ikut bergeser. Belok kanan dan "
         "kiri diuji terpisah."],
        ["Inersia (Hukum I Newton)",
         "ESC hanya satu arah, sehingga robot tidak bisa mengerem; setelah baling-baling berhenti "
         "robot masih meluncur atau berputar sedikit.",
         "Posisi akhir diukur setelah robot diam. Posisi saat FIN dapat dicatat untuk menghitung "
         "jarak luncur (bagian 7.6)."],
    ], [3.4, 6.5, 6.5])

    # ---------------- 3 ----------------
    D.h1("3. Lokasi dan Sistem Koordinat")
    D.p("Pengujian dilakukan di kolam berukuran 5 × 2 m dengan lantai keramik 25 × 25 cm, yaitu "
        "8 keramik melintang dan 20 keramik memanjang. Grid keramik ini dipakai sebagai sistem "
        "koordinat sekaligus alat ukur posisi, serupa dengan area uji bergrid dan titik waypoint "
        "yang posisinya sudah pasti pada [1].")
    D.table(["Sumbu", "Arah", "Rentang", "Satuan"], [
        ["Kolom", "ke samping, kiri → kanan (sisi pendek, 2 m)", "0 – 8", "1 kolom = 25 cm"],
        ["Baris", "ke depan, menjauh dari tangga (sisi panjang, 5 m)", "0 – 20", "1 baris = 25 cm"],
    ], [3.0, 5.4, 3.0, 5.0], size=10)
    D.p("Operator berdiri di ujung pendek kolam yang dekat tangga, menghadap ke arah panjang "
        "kolam. Titik (0 ; 0) adalah pojok kiri di ujung tersebut dan dipakai tetap selama "
        "seluruh pengujian. Posisi ditulis sebagai (kolom ; baris) — angka samping dulu, baru "
        "angka depan — dan dibaca sampai 0,1 keramik (2,5 cm) dengan bantuan kotak mozaik kecil "
        "di dalam tiap keramik. Contoh: (4 ; 2) berarti 4 keramik dari dinding kiri dan 2 keramik "
        "dari dinding belakang.")
    D.figure(fig["sumbu"], "Gambar 1. Sistem koordinat kolam: kolom dihitung ke samping, baris "
             "dihitung ke depan dari pojok (0 ; 0).", 7.6)
    D.figure(fig["kolam"], "Gambar 2. Tata letak skenario di kolam uji. Garis oranye menunjukkan "
             "badan robot 60 × 42 cm sesuai skala.", 16.4)

    # ---------------- 4 ----------------
    D.h1("4. Variabel Pengujian")
    D.table(["Jenis variabel", "Isi"], [
        ["Variabel bebas (yang diubah)",
         "Jenis gerakan dan besar perintah (jarak dalam cm, sudut dalam derajat)."],
        ["Variabel terikat (yang diukur)",
         "Jarak aktual, penyimpangan lateral, jarak luncur, sudut aktual, galat posisi akhir, dan "
         "keberhasilan eksekusi perintah."],
        ["Variabel kontrol (dijaga tetap)",
         "Kolam dan titik start yang sama; CRUISE_PWM 1300 µs; konstanta firmware tidak diubah "
         "selama pengujian resmi; baterai terisi penuh di awal sesi; gyro dikalibrasi saat robot "
         "diam (peringatan MPU di GUI sudah hilang); GUI pada mode REAL."],
        ["Kondisi yang dicatat", "Angin, riak air, dan jam mulai (lama pemakaian baterai)."],
    ], [4.6, 11.8], size=10)

    # ---------------- 5 ----------------
    D.h1("5. Skenario Pengujian")
    D.p("Semua perintah dikirim dari GUI Pengendali Utama pada mode REAL. Posisi start dan target "
        "ditulis dalam koordinat keramik (kolom ; baris); lihat Gambar 2.")
    t = D.table(["Kode", "Gerakan", "Perintah dari GUI", "Start", "Target", "Ulang"], [
        ["A1", "Maju lurus 50 cm", "FW:50", "(4 ; 2), menghadap sepanjang baris", "baris 4", "3×"],
        ["A2", "Maju lurus 100 cm", "FW:100", "(4 ; 2)", "baris 6", "3×"],
        ["A3", "Maju lurus 200 cm", "FW:200", "(4 ; 2)", "baris 10", "3×"],
        ["B1", "Belok kanan 45°", "CW:45", "(1,5 ; 5), menghadap sepanjang baris", "arah 45° kanan", "3×"],
        ["B2", "Belok kanan 90°", "CW:90", "(1,5 ; 5)", "arah 90° kanan", "3×"],
        ["B3", "Belok kiri 45°", "CCW:45", "(6,5 ; 12), menghadap sepanjang baris", "arah 45° kiri", "3×"],
        ["B4", "Belok kiri 90°", "CCW:90", "(6,5 ; 12)", "arah 90° kiri", "3×"],
        ["C1", "Lintasan kotak 1 × 2 m (4 × belok kanan)",
         "FW:200 → CW:90 → FW:100 → CW:90 → FW:200 → CW:90 → FW:100 → CW:90",
         "± 1 panjang robot dari dinding ujung, ± 20 cm dari dinding kiri, menghadap "
         "sepanjang kolam", "kembali ke posisi dan arah start", "3×"],
        ["", "", "", "", "", ""],
    ], [1.1, 3.2, 4.6, 3.6, 2.8, 1.1], size=9, center=(0, 5))
    last = t.rows[-1]
    merged = last.cells[0].merge(last.cells[5])
    D.cell(merged, "Total: 8 skenario × 3 pengulangan = 24 percobaan", bold=True,
           size=9.5, align=CENTER)
    D.shade(merged, "DCE6F0")

    D.h2("Alasan pemilihan skenario")
    D.bullet(" mewakili jarak pendek, sedang, dan maksimum satu perintah FW. Lintasan panjang pada "
             "misi selalu dipecah aplikasi menjadi potongan ≤ 200 cm. Robot maju di tengah lebar "
             "kolam (kolom 4) agar jauh dari kedua dinding.", "Lurus 50/100/200 cm —")
    D.bullet(" 90° dipakai pada setiap belokan misi, 45° menguji sudut kecil. Kanan dan kiri diuji "
             "terpisah karena memakai motor berbeda; posisi start dipilih agar robot berbelok ke "
             "sisi kolam yang lega.", "Belok 45° dan 90°, kanan dan kiri —")
    D.bullet(" sesuai contoh dosen pembimbing. Lintasan tertutup: bila semua gerakan tepat, robot "
             "kembali ke titik start dengan arah semula, sehingga kesalahan yang menumpuk terlihat "
             "di satu titik.", "Kotak 1 × 2 m —")
    D.bullet(" jumlah minimum agar rata-rata dan simpangan baku tetap bermakna sambil menjaga "
             "waktu pelaksanaan.", "Pengulangan 3 kali —")
    D.note("dengan robot 60 cm, ujung depan robot hanya berjarak sekitar 20 cm dari dinding saat "
           "menghadap melintang di C1. Uji coba ruang (bagian 10.1) menunjukkan ukuran melintang "
           "1 m tetap muat, sehingga ukuran kotak tidak diperkecil.", lead="Catatan ruang: ")

    # ---------------- 6 ----------------
    D.h1("6. Alat")
    D.p("Tidak ada alat yang perlu dibeli. Acuan ukurnya adalah grid fisik lantai kolam (keramik "
        "25 cm dan mozaik 4,1 cm) serta ukuran robot sendiri; foto HP hanya merekam posisi robot "
        "terhadap grid tersebut agar bisa dihitung ulang.")
    D.table(["No", "Alat", "Fungsi"], [
        ["1", "Lantai kolam: keramik 25 × 25 cm berisi mozaik 4,1 cm",
         "Alat ukur posisi utama (kolom ; baris keramik) dan sudut (kotak mozaik)"],
        ["2", "Meteran", "Memverifikasi ukuran keramik dan mozaik sekali di awal"],
        ["3", "HP", "Foto tegak dari atas: B dihitung dari kotak mozaik pada foto, C1 dari foto "
                    "awal dan akhir (ukur_foto_c1.py)"],
        ["4", "Raspberry Pi + GUI (bagian dari sistem)",
         "Mengirim perintah; mencatat waktu ON/FIN dan yaw MPU tiap 1 detik ke file log"],
        ["5", "Lembar data Excel (Lampiran)", "Pencatatan dan perhitungan hasil tiap percobaan"],
    ], [1.0, 5.8, 9.6], size=10, center=(0,))
    D.note("sinyal FIN dan sensor MPU berasal dari robot sendiri, sehingga tidak dapat membuktikan "
           "bahwa robot benar-benar bergerak sesuai perintah. Nilai aktual harus diambil dari "
           "acuan fisik di luar robot, sebagaimana posisi nyata pada [1] dan jarak nyata pada [2].",
           lead="Mengapa acuan fisik: ")

    # ---------------- 7 ----------------
    D.h1("7. Metode Pengukuran")
    D.h2("7.1 Prinsip: tiga nilai untuk setiap percobaan")
    D.table(["Nilai", "Sumber", "Fungsi"], [
        ["Perintah (target)", "Yang dikirim dari GUI, mis. FW:100", "Acuan pembanding"],
        ["Menurut sistem robot", "Sinyal FIN dan yaw MPU di log GUI",
         "Menunjukkan apa yang “dikira” robot"],
        ["Aktual", "Posisi robot terhadap grid keramik/mozaik (langsung atau dari foto)",
         "Kebenaran lapangan, dasar penilaian"],
    ], [4.0, 6.4, 6.0], size=10)

    D.h2("7.2 Cara membaca posisi")
    D.bullet(" titik tengah badan robot, dibaca dalam baris dan kolom keramik.", "Jarak (A) —")
    D.bullet(" pelampung kiri (panjang 60 cm ≈ 14,6 mozaik). Kotak mozaik dihitung dari ujung "
             "belakang ke ujung depan pelampung: berapa kotak ke SAMPING dan berapa ke DEPAN.",
             "Sudut (B) —")
    D.bullet(" ambil foto HP tegak dari atas. Melihat miring melalui air membuat posisi tampak "
             "bergeser (paralaks dan pembiasan). Sebagai pemeriksaan, √(samping² + depan²) × 4,1 cm "
             "harus mendekati 60 cm.", "Cara melihat —")
    D.figure(fig["hitung"], "Gambar 3. Contoh membaca jarak (keramik) dan sudut (mozaik pelampung)",
             16.0)

    D.h2("7.3 Gerak lurus (A1–A3)")
    D.steps([
        "Letakkan titik tengah robot di (4 ; 2), menghadap sepanjang baris (sejajar garis keramik).",
        "Kirim perintah. Bila memungkinkan, catat baris titik tengah robot saat FIN muncul di GUI.",
        "Tunggu hingga robot benar-benar diam (± 3 detik), lalu baca posisi titik tengah (kolom ; baris).",
        ("Jarak aktual ", "= (baris akhir − 2) × 25 cm."),
        ("Penyimpangan lateral ", "= (kolom akhir − 4) × 25 cm; positif bila ke kanan."),
    ])

    D.h2("7.4 Belok (B1–B4)")
    D.steps([
        "Letakkan robot di posisi start (B1–B2 di (1,5 ; 5), B3–B4 di (6,5 ; 12)), menghadap "
        "sepanjang kolam (pelampung sejajar garis keramik).",
        "Kirim perintah. Setelah FIN diterima, tunggu hingga robot berhenti berputar, lalu foto "
        "tegak dari atas.",
        "Pada foto, hitung kotak mozaik pelampung kiri dari ujung belakang ke ujung depan: "
        "SAMPING (melintang kolam) dan DEPAN (sepanjang kolam; minus bila ke belakang).",
        ("Sudut aktual ", "= atan(|samping| ÷ depan); bila depan negatif (lewat 90°), sudut = "
         "180° − atan(|samping| ÷ |depan|). Galat = |sudut aktual − sudut perintah|."),
        ("Sudut MPU ", "= |yaw akhir − yaw awal|, diambil dari log GUI pada jam perintah dikirim "
         "dan setelah FIN."),
    ])
    D.note("salah hitung satu kotak mozaik pada pelampung 14,6 mozaik menggeser sudut sekitar "
           "3–4°. Bila cek panjang pelampung menyimpang lebih dari 10 cm dari 60 cm, hitungan "
           "diulang dari foto.", lead="Ketelitian: ")

    D.h2("7.5 Kombinasi (C1)")
    D.steps([
        "Letakkan robot ± 1 panjang robot dari dinding ujung dan ± 20 cm dari dinding kiri, "
        "menghadap sepanjang kolam. Operator berdiri di belakang robot.",
        "Foto dari belakang robot sebelum perintah pertama (foto awal).",
        "Kirim delapan perintah berurutan dari halaman MANUAL sesuai tabel skenario; perintah "
        "berikutnya dikirim setelah FIN perintah sebelumnya diterima.",
        "Setelah robot diam, foto lagi dari tempat yang sama (foto akhir).",
        ("Galat arah ", "= selisih sudut garis ujung belakang kedua pelampung terhadap baris "
         "mozaik, foto akhir dikurangi foto awal (ideal 0°, karena total belokan 360°)."),
        ("Galat posisi ", "= pergeseran ujung belakang pelampung kiri dari foto awal ke foto "
         "akhir. Karena posisi HP tidak persis sama, foto akhir dipetakan ke foto awal lewat pola "
         "keramik tepi kolam (ukur_foto_c1.py); skala dari lebar robot 42 cm, hasil dalam kotak "
         "mozaik: e = √(geser samping² + geser depan²) × 4,1 cm."),
        "Dari log GUI, catat jumlah FIN (…/8), kirim ulang, dan waktu total.",
    ])

    D.h2("7.6 Jarak luncur (inersia)")
    D.p("Setelah baling-baling berhenti, robot masih meluncur karena inersia dan tidak dapat "
        "mengerem karena ESC hanya satu arah. Posisi resmi selalu diambil setelah robot diam, "
        "karena itulah posisi nyata robot di tambak. Pada skenario A, baris saat FIN juga dicatat "
        "bila memungkinkan, sehingga:")
    D.bullet(" = (baris akhir − baris saat FIN) × 25 cm.", "Jarak luncur")
    D.p("Data ini memisahkan dua sumber galat: kalibrasi kecepatan (robot bergerak terlalu jauh "
        "atau kurang selama motor menyala) dan efek meluncur. Bila jarak luncur rata-rata "
        "konsisten, firmware dapat mematikan motor lebih awal sejauh nilai tersebut, lalu "
        "diuji ulang.")

    # ---------------- 8 ----------------
    D.h1("8. Pengolahan Data")
    D.p("Metrik mengikuti [1] dan [2]: Mean Absolute Error (MAE) dan Mean Absolute Percentage "
        "Error (MAPE), ditambah simpangan baku untuk keterulangan.")
    D.table(["Besaran", "Rumus", "Keterangan"], [
        ["MAE", "MAE = Σ | x aktual − x perintah | ÷ n", "Dalam cm atau derajat; n = 3"],
        ["MAPE", "MAPE = Σ ( | x aktual − x perintah | ÷ x perintah ) ÷ n × 100%", "Dalam persen"],
        ["Akurasi", "A = 100% − MAPE", "Semakin tinggi semakin tepat"],
        ["Simpangan baku", "s = √[ Σ (xi − x̄)² ÷ (n − 1) ]",
         "Keterulangan (presisi): semakin kecil semakin konsisten"],
        ["Galat posisi (C1)", "e = √(geser samping² + geser depan²) × 4,1 cm",
         "Jarak posisi akhir ke posisi start (mozaik)"],
        ["Galat sensor MPU", "e MPU = | θ MPU − θ aktual |", "Ketelitian sensor MPU"],
        ["Keberhasilan eksekusi", "(percobaan dengan semua FIN ÷ jumlah percobaan) × 100%",
         "Keandalan komunikasi dan eksekusi"],
    ], [3.6, 7.6, 5.2])
    D.p("Contoh: FW:50 dengan baris awal 1,3 dan baris akhir 3,7 → jarak aktual 60 cm, galat 10 cm, "
        "galat relatif 20%.", italic=True)

    # ---------------- 9 ----------------
    D.h1("9. Kriteria Keberhasilan (Usulan)")
    D.table(["Skenario", "Parameter", "Batas usulan"], [
        ["A1–A3", "MAPE jarak", "≤ 10%"],
        ["A1–A3", "Penyimpangan lateral rata-rata", "≤ 10% dari jarak perintah"],
        ["B1–B4", "MAE sudut", "≤ 5°"],
        ["B1–B4", "MAE sensor MPU terhadap sudut aktual", "≤ 5°"],
        ["C1", "Galat penutupan rata-rata", "≤ 30 cm (± 5% dari keliling 6 m)"],
        ["C1", "Galat arah akhir rata-rata", "≤ 10°"],
        ["C1", "Keberhasilan eksekusi", "100% perintah selesai (FIN)"],
    ], [2.6, 7.2, 6.6], size=10, center=(0,))
    D.note("batas di atas masih usulan. Bila suatu kriteria tidak tercapai, penyebabnya dianalisis "
           "(mis. jarak luncur, kalibrasi kecepatan, gain heading, angin) dan dilaporkan sebagai "
           "temuan pengujian.")

    # ---------------- 10 ----------------
    D.h1("10. Prosedur Pelaksanaan")
    D.h2("10.1 Tahap pendahuluan (tidak dihitung sebagai data resmi)")
    D.p("Tahap ini sudah dilaksanakan; hasilnya dipakai untuk mengunci konstanta firmware.")
    D.table(["Langkah", "Hasil"], [
        ["Verifikasi ukuran grid dengan meteran", "1 keramik = 25 cm; 1 mozaik = 4,1 cm."],
        ["Kalibrasi maju: FW:200 dan FW:100, masing-masing 3×",
         "Dengan asumsi awal 0,5 m/s, FW:200 hanya menempuh rata-rata 54 cm. Data dua titik "
         "(motor 4,0 s → 54 cm; 7,4 s → 150 cm) menghasilkan model durasi = awalan 2,1 s + "
         "jarak ÷ 0,28 m/s (FW_START_MS dan ROBOT_SPEED_MPS)."],
        ["Periksa arah putar: kirim CW:90",
         "Robot berbelok ke kiri karena kabel ESC tersilang (pin ESC kiri menggerakkan motor "
         "kanan). Diperbaiki di firmware dengan menukar isi fungsi spinCW dan spinCCW."],
        ["Periksa besar putaran: CW:45 3×",
         "Robot berhenti di ± 55–59° karena masih berputar setelah motor mati. Ditambahkan "
         "kompensasi: motor dimatikan 15° sebelum target (TURN_COAST_DEG)."],
        ["Uji coba ruang: CW:90 lalu FW:100 dari posisi C1",
         "Robot melebar kurang dari 1 keramik, sehingga ukuran melintang C1 tetap 1 m."],
    ], [5.6, 10.8], size=9.5)
    D.p("Setelah tahap ini selesai, seluruh konstanta firmware dan ukuran skenario dikunci.",
        size=10)

    D.h2("10.2 Persiapan setiap sesi")
    D.steps([
        "Isi penuh baterai dan catat jam mulai.",
        "Nyalakan robot di tepi kolam dalam keadaan benar-benar diam, lalu tunggu sampai "
        "peringatan “Gyro belum terkalibrasi” di GUI hilang. Bila robot bergerak atau dipegang "
        "saat kalibrasi, yaw akan terus merayap selama sesi.",
        "Pilih mode REAL di GUI dan periksa koneksi (telemetri MPU masuk).",
        "Catat tanggal, cuaca, dan kondisi angin/air pada lembar data sesi.",
    ])
    D.h2("10.3 Langkah setiap percobaan")
    D.steps([
        "Letakkan robot di posisi start sesuai skenario, sejajar garis keramik, dan tunggu sampai "
        "diam (tidak hanyut).",
        "Kirim perintah dari halaman MANUAL GUI. Yaw MPU, waktu kirim, ON, dan FIN tercatat "
        "otomatis di file log.",
        "Saat FIN muncul, catat baris robot bila memungkinkan (skenario A).",
        "Tunggu robot diam ± 3 detik, lalu baca posisi dari grid (A) atau foto tegak dari atas "
        "(B, C1), dan catat ke lembar data beserta ada/tidaknya kirim ulang.",
        "Kembalikan robot ke posisi start, lalu ulangi hingga 3 percobaan.",
    ])
    D.h2("10.4 Percobaan yang gagal")
    D.p("Percobaan yang gagal (sinyal hilang, robot menabrak dinding, terbawa arus, dan "
        "sebagainya) tetap dicatat beserta penyebabnya, lalu diganti dengan percobaan baru sampai "
        "terkumpul 3 data valid. Jumlah percobaan gagal ikut dilaporkan sebagai data keandalan.")
    D.h2("10.5 Estimasi waktu")
    D.table(["Kelompok", "Jumlah percobaan", "Perkiraan waktu"], [
        ["Tahap pendahuluan", "—", "± 30 menit"],
        ["A (lurus)", "9", "± 20 menit"],
        ["B (belok)", "12", "± 25 menit"],
        ["C1 (kotak)", "3", "± 20 menit"],
        ["Total", "24", "± 1,5 jam"],
    ], [4.5, 4.0, 7.9], size=10, center=(1,))

    # ---------------- 11 ----------------
    D.h1("11. Perubahan terhadap Rancangan Awal")
    D.p("Rancangan awal (September 2026) disesuaikan selama pelaksanaan. Perubahan dan alasannya:")
    D.table(["Bagian", "Rancangan awal", "Pelaksanaan", "Alasan"], [
        ["Kecepatan maju", "ROBOT_SPEED_MPS 0,5 m/s (asumsi)",
         "Awalan 2,1 s + jarak ÷ 0,28 m/s", "Uji awal: robot jauh lebih lambat dari asumsi"],
        ["Arah putar", "Cek YAW_SIGN", "Isi spinCW/spinCCW ditukar",
         "Kabel ESC tersilang; sensor sudah benar"],
        ["Berhenti putar", "Toleransi 3° dari target", "Motor mati 15° sebelum target",
         "Robot masih berputar ± 15° setelah motor mati"],
        ["Baca sudut (B)", "Haluan & buritan dalam keramik",
         "Kotak mozaik sepanjang pelampung kiri pada foto",
         "Bacaan haluan–buritan tidak konsisten (panjang terbaca 29 cm, seharusnya 60 cm)"],
        ["Yaw MPU", "Dicatat tangan dari layar GUI", "Diambil dari file log GUI",
         "Catatan tangan tidak cocok dengan log; log tercatat otomatis tiap 1 detik"],
        ["Posisi & arah (C1)", "Titik tengah, haluan, buritan dalam keramik",
         "Foto awal & akhir, dihitung dengan ukur_foto_c1.py",
         "Robot di tengah kolam sulit dibaca dari tepi tanpa alat tambahan"],
        ["Start C1", "(2 ; 4)", "± 1 panjang robot dari dinding ujung, ± 20 cm dari dinding kiri",
         "Diukur relatif terhadap posisi start sendiri, bukan koordinat kolam"],
        ["C2 zigzag mini", "3 percobaan", "Tidak dilaksanakan",
         "Kombinasi disederhanakan menjadi C1 saja; zigzag tersusun dari perintah FW dan CW/CCW "
         "yang sudah diuji di A, B, dan C1"],
    ], [2.6, 3.8, 4.4, 5.6], size=9)

    # ---------------- referensi ----------------
    D.h1("Referensi")
    for ref in (
            "[1]  J. Putra dan D. E. Saputra, “Autonomous Drone Indoor Navigation Based on "
            "Virtual 3D Map Reference,” IEEE, 2022.",
            "[2]  D. E. Saputra, “Experiment on Pinhole Model Distance Calculation for Drone "
            "Navigation.”"):
        par = D.p(ref, size=10.5)
        par.paragraph_format.left_indent = Cm(0.8)
        par.paragraph_format.first_line_indent = Cm(-0.8)

    # ---------------- lampiran ----------------
    sec = d.add_section(WD_SECTION.NEW_PAGE)
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Cm(29.7), Cm(21)
    sec.left_margin = sec.right_margin = Cm(1.8)
    sec.top_margin, sec.bottom_margin = Cm(1.8), Cm(1.6)

    D.h1("Lampiran — Lembar Pengambilan Data")
    D.p("A ditulis dalam keramik (kolom ; baris); B dan C1 dalam kotak mozaik. Versi Excel dengan "
        "perhitungan otomatis tersedia sebagai Lembar_Data_Pengujian.xlsx.", size=10)
    D.h2("Data sesi")
    D.table(["Keterangan", "Isi", "Keterangan", "Isi"], [
        ["Tanggal / jam mulai", "", "Baterai penuh saat mulai (Y/T)", ""],
        ["Ukuran 1 keramik / 1 mozaik (cm)", "", "Gyro terkalibrasi saat diam (Y/T)", ""],
        ["Cuaca / angin / riak air", "", "ROBOT_SPEED_MPS / KP_HEADING", ""],
        ["Ukuran melintang C1 (hasil 10.1)", "", "Pencatat", ""],
    ], [5.4, 7.65, 5.4, 7.65], size=10, zebra=False, row_height=0.75)

    blank = ["1", "2", "3", "Rata-rata", "Simp. baku"]

    def lembar(title, headers, widths):
        D.h2(title)
        t = D.table(headers, [[n] + [""] * (len(headers) - 1) for n in blank], widths, size=9,
                    zebra=False, center=(0,), header_size=8.5, row_height=0.62)
        for r in t.rows[-2:]:
            for c in r.cells:
                D.shade(c, ZEBRA)
            D.cell(r.cells[0], r.cells[0].text, bold=True, size=9, align=CENTER)

    a_h = ["Perc.", "Baris saat FIN (opsional)", "Posisi akhir (kolom ; baris)",
           "Jarak aktual (cm)", "Galat (cm)", "Galat (%)", "Lateral (cm)",
           "Jarak luncur (cm)", "Kirim ulang? (Y/T)", "Keterangan"]
    a_w = [1.8, 2.6, 3.0, 2.4, 2.1, 2.1, 2.2, 2.4, 2.2, 5.3]
    for code, cmd, tgt in (("A1", "FW:50", "baris 4"), ("A2", "FW:100", "baris 6"),
                           ("A3", "FW:200", "baris 10")):
        lembar(f"Skenario {code} — {cmd} (start (4 ; 2), target {tgt})", a_h, a_w)
    b_h = ["Perc.", "Yaw MPU awal (°)", "Yaw MPU akhir (°)", "Mozaik SAMPING (pelampung kiri)",
           "Mozaik DEPAN (minus bila ke belakang)", "Sudut MPU (°)", "Sudut aktual (°)",
           "Galat aktual (°)", "Galat MPU vs aktual (°)", "Cek panjang (cm) ≈ 60", "Keterangan"]
    b_w = [1.7, 2.0, 2.0, 2.4, 2.5, 1.9, 2.0, 1.9, 2.2, 2.1, 5.4]
    for code, cmd, st in (("B1", "CW:45", "(1,5 ; 5)"), ("B2", "CW:90", "(1,5 ; 5)"),
                          ("B3", "CCW:45", "(6,5 ; 12)"), ("B4", "CCW:90", "(6,5 ; 12)")):
        lembar(f"Skenario {code} — {cmd} (start {st})", b_h, b_w)
    c_h = ["Perc.", "Geser SAMPING (mozaik)", "Geser DEPAN (mozaik)", "Arah: mozaik SAMPING",
           "Arah: mozaik DEPAN", "FIN (…/8)", "Waktu total (s)", "Galat posisi (cm)",
           "Galat arah (°)", "Keterangan"]
    c_w = [1.7, 2.6, 2.6, 2.5, 2.3, 1.9, 2.2, 2.4, 2.2, 5.7]
    lembar("Skenario C1 — Kotak 1 × 2 m (target: kembali ke posisi & arah start)", c_h, c_w)
    return d


# =====================================================================
# Ekspor PDF (opsional)
# =====================================================================
def export_pdf(docx):
    pdf = docx.with_suffix(".pdf")
    before = pdf.stat().st_mtime if pdf.exists() else None

    def ok():
        return pdf.exists() and pdf.stat().st_mtime != before

    if sys.platform == "win32" and shutil.which("powershell"):
        q = lambda p: str(p).replace("'", "''")
        ps = ("$w = New-Object -ComObject Word.Application; $w.Visible = $false; "
              f"try {{ $d = $w.Documents.Open('{q(docx)}', $false, $true); "
              f"$d.ExportAsFixedFormat('{q(pdf)}', 17); $d.Close($false) }} "
              "finally { $w.Quit() }")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
        if ok():
            return pdf
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir",
                        str(pdf.parent), str(docx)], capture_output=True)
        if ok():
            return pdf
    return None


def main():
    fig = {"sumbu": fig_sumbu(), "kolam": fig_kolam(), "hitung": fig_hitung()}
    doc = build(fig)
    try:
        doc.save(OUT_DOCX)
    except PermissionError:
        sys.exit(f"Tidak bisa menulis {OUT_DOCX.name} — tutup dulu file itu di Word.")
    print(f"DOCX : {OUT_DOCX}")
    pdf = export_pdf(OUT_DOCX)
    if pdf:
        print(f"PDF  : {pdf}")
    else:
        print("PDF  : dilewati (Word/LibreOffice tidak ditemukan). Buka DOCX lalu Save As PDF.")


if __name__ == "__main__":
    main()
