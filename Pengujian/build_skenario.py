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
EDGE = "#8b6b3d"
ROBOT = "#2563eb"
GHOST = "#94a3b8"
RED = "#dc2626"
GREEN = "#15803d"
WATER = "#e0f2fe"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})


def _robot(ax, x, y, heading_deg, color, filled=True, ls="-"):
    L, W = 36, 22
    t = np.radians(heading_deg)
    fwd = np.array([np.cos(t), np.sin(t)])
    side = np.array([-np.sin(t), np.cos(t)])
    c = np.array([x, y])
    pts = [c + fwd * L * 0.3 + side * W / 2, c + fwd * L / 2,
           c + fwd * L * 0.3 - side * W / 2, c - fwd * L / 2 - side * W / 2,
           c - fwd * L / 2 + side * W / 2]
    ax.add_patch(Polygon(pts, closed=True, fc=color if filled else "none", ec=color,
                         lw=1.6, ls=ls, alpha=0.9 if filled else 1))
    ax.add_patch(Circle(c, 2.6, fc="white", ec=INK, lw=0.8, zorder=6))


def _edge_h(ax, x0, x1, y, below=True, label="tepi kolam (garis acuan 0°)"):
    h = 14
    ax.add_patch(Rectangle((x0, y - h if below else y), x1 - x0, h, fc="#d6c7a1",
                           ec="none", hatch="///", alpha=0.9))
    ax.plot([x0, x1], [y, y], color=EDGE, lw=2.4)
    ax.text(x0 + 3, y - h / 2 if below else y + h / 2, label, fontsize=8.8, color="#5b4523",
            va="center", weight="bold")


def _mark(ax, x, y, text, color):
    ax.plot([x], [y], marker="X", ms=10, color=color, mec="black", mew=0.6, zorder=7)
    ax.text(x, y - 18, text, ha="center", va="top", fontsize=8.5, color=color, weight="bold")


def _save(fig, name):
    GAMBAR.mkdir(exist_ok=True)
    path = GAMBAR / name
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return path


def fig_lurus():
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.add_patch(Rectangle((-45, 0), 340, 105, fc=WATER, ec="none"))
    _edge_h(ax, -45, 295, 0, below=True, label="tepi kolam")
    y0 = 30
    ax.plot([0, 245], [y0, y0], color=GHOST, lw=1.2, ls=(0, (5, 4)))
    ax.text(110, y0 - 4, "garis lurus rencana", fontsize=8.5, color="#64748b",
            ha="center", va="top")
    _robot(ax, 0, y0, 0, GHOST, filled=False, ls="--")
    ax.text(0, y0 + 20, "START", ha="center", fontsize=9, color="#475569", weight="bold")
    xe, ye = 188, y0 + 17
    _robot(ax, xe, ye, 5, ROBOT)
    ax.text(xe - 40, ye + 14, "posisi akhir\n(setelah diam)", ha="center", fontsize=9,
            color=ROBOT, weight="bold")
    xs = np.linspace(0, xe, 60)
    ax.plot(xs, y0 + (ye - y0) * (xs / xe) ** 1.8, color=ROBOT, lw=1.4, alpha=0.6)

    ax.plot([0, 0], [y0 - 3, 0], color=GREEN, lw=1, ls=":")
    ax.plot([xe, xe], [ye - 3, 0], color=GREEN, lw=1, ls=":")
    _mark(ax, 0, 0, "tanda start", GREEN)
    _mark(ax, xe, 0, "tanda akhir", GREEN)
    ax.add_patch(FancyArrowPatch((0, -36), (xe, -36), arrowstyle="<|-|>",
                                 mutation_scale=10, color=GREEN, lw=1.4))
    ax.text(xe / 2, -40, "d aktual = jarak dua tanda, diukur meteran di sepanjang tepi",
            ha="center", va="top", fontsize=9.5, color=GREEN, weight="bold")

    ax.add_patch(FancyArrowPatch((xe + 34, 0), (xe + 34, ye), arrowstyle="<|-|>",
                                 mutation_scale=9, color=RED, lw=1.3))
    ax.plot([xe, xe + 38], [ye, ye], color=RED, lw=0.8, ls=":")
    ax.text(xe + 40, ye / 2 + 2, "jarak robot ke tepi\n(meteran)\ne lateral = jarak − 30 cm",
            fontsize=8.8, color=RED, va="center", weight="bold")
    ax.add_patch(FancyArrowPatch((-32, 0), (-32, y0), arrowstyle="<|-|>",
                                 mutation_scale=8, color="#475569", lw=1))
    ax.text(-35, y0 / 2, "30 cm", fontsize=8.5, color="#475569", ha="right", va="center")
    ax.text(-40, 98, "Cukup meteran. Tepi kolam = garis lurus acuan; batu/sandal/kapur = tanda.",
            fontsize=9, color=INK, va="top")

    ax.set_xlim(-48, 298)
    ax.set_ylim(-58, 106)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Pengukuran gerak lurus (tampak atas)", fontsize=12, weight="bold",
                 color=INK, loc="left")
    return _save(fig, "fig_setup_lurus.png")


def fig_belok():
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.add_patch(Rectangle((-60, -60), 460, 120, fc=WATER, ec="none"))
    _edge_h(ax, -60, 400, 60, below=False)
    _robot(ax, 20, 30, 0, GHOST, filled=False, ls="--")
    ax.plot([-15, 70], [30, 30], color=GHOST, lw=1, ls=(0, (4, 3)))
    ax.text(20, 8, "SEBELUM\nsejajar tepi", ha="center", va="top", fontsize=9,
            color="#475569", weight="bold")
    xa, ya, ha = 150, 0, -42
    _robot(ax, xa, ya, ha, ROBOT)
    t = np.radians(ha)
    ax.plot([xa - 45 * np.cos(t), xa + 60 * np.cos(t)],
            [ya - 45 * np.sin(t), ya + 60 * np.sin(t)], color=ROBOT, lw=1, ls=(0, (4, 3)))
    ax.plot([xa - 20, xa + 70], [ya, ya], color=GHOST, lw=1, ls=(0, (4, 3)))
    arc = np.radians(np.linspace(0, ha, 30))
    ax.plot(xa + 45 * np.cos(arc), ya + 45 * np.sin(arc), color=RED, lw=1.8)
    ax.text(xa + 50, ya - 16, "sudut belok\naktual", color=RED, fontsize=9.5, weight="bold")
    ax.text(xa - 5, 34, "SESUDAH diam", ha="center", fontsize=9, color=ROBOT, weight="bold")
    p = np.linspace(0, 1, 40)
    ax.plot(20 + (xa - 20) * p, 30 + (ya - 30) * p ** 2, color=ROBOT, lw=1.2, alpha=0.5)
    ax.text(80, -32, "CW: tepi di kiri robot → robot\nberbelok menjauhi tepi",
            fontsize=8.5, color="#475569", ha="center")
    ax.text(222, 38, "1. Foto HP dari atas, sebelum & sesudah\n"
            "   (tepi kolam ikut masuk foto)\n"
            "2. Di laptop/PC:\n"
            "   python ukur_foto.py sebelum.jpg sesudah.jpg\n"
            "3. Skrip menampilkan sudut belok aktual",
            fontsize=8.4, va="top", color=INK, family="DejaVu Sans",
            bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="#cbd5e1"))
    ax.set_xlim(-60, 400)
    ax.set_ylim(-62, 76)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Pengukuran sudut belok dari foto HP tampak atas", fontsize=12,
                 weight="bold", color=INK, loc="left")
    return _save(fig, "fig_setup_belok.png")


def _path(ax, pts, labels, turns, title):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=ROBOT, lw=2.2, marker="o", ms=4)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        ax.add_patch(FancyArrowPatch((x1, y1), ((x1 + x2) / 2 + (x2 - x1) * 0.05,
                                                (y1 + y2) / 2 + (y2 - y1) * 0.05),
                                     arrowstyle="-|>", mutation_scale=14, color=ROBOT, lw=0))
    for x, y, txt, ha, va in labels:
        ax.text(x, y, txt, ha=ha, va=va, fontsize=8.6, color=INK,
                bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="#cbd5e1", lw=0.8))
    for x, y, txt, ha, va in turns:
        ax.text(x, y, txt, ha=ha, va=va, fontsize=8.2, color=RED, weight="bold")
    ax.plot(*pts[0], marker="*", ms=16, color=GREEN, zorder=5)
    ax.set_title(title, fontsize=10.5, weight="bold", color=INK, loc="left")
    ax.set_aspect("equal")
    ax.grid(True, color="#e2e8f0", lw=0.8)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")


def fig_kombinasi():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 5), gridspec_kw={"width_ratios": [1, 1.3]})
    a1.axvspan(-1.2, -0.3, color="#d6c7a1", alpha=0.8, hatch="///", lw=0)
    a1.axvline(-0.3, color=EDGE, lw=2.4)
    a1.text(-0.75, 1.6, "tepi\nkolam", ha="center", fontsize=8.5, color="#5b4523", weight="bold")
    _path(a1, [(0, 0), (0, 1), (2, 1), (2, 0), (0, 0)],
          [(0.08, 0.5, "1. FW:100", "left", "center"), (1.0, 1.08, "3. FW:200", "center", "bottom"),
           (1.92, 0.5, "5. FW:100", "right", "center"), (1.0, -0.08, "7. FW:200", "center", "top")],
          [(0.05, 1.05, "2. CW:90", "left", "bottom"), (1.95, 1.05, "4. CW:90", "right", "bottom"),
           (2.05, -0.05, "6. CW:90", "left", "top"), (0.1, -0.28, "8. CW:90", "left", "top")],
          "C1 - Kotak 1 x 2 m (4x belok kanan 90°)")
    a1.text(0.0, -0.5, "START = FINISH", ha="left", va="top", fontsize=8.5, color=GREEN,
            weight="bold")
    a1.set_xlim(-1.2, 2.7)
    a1.set_ylim(-0.8, 1.9)

    a2.axhspan(-1.2, -0.5, color="#d6c7a1", alpha=0.8, hatch="///", lw=0)
    a2.axhline(-0.5, color=EDGE, lw=2.4)
    a2.text(1.5, -0.85, "tepi kolam", ha="center", fontsize=8.5, color="#5b4523", weight="bold")
    zz = [(0, 0), (0, 2), (1, 2), (1, 0), (2, 0), (2, 2), (3, 2), (3, 0)]
    _path(a2, zz,
          [(-0.08, 1.0, "FW:200", "right", "center"), (0.5, 2.08, "FW:100", "center", "bottom"),
           (0.92, 1.0, "FW:200", "right", "center"), (1.5, -0.08, "FW:100", "center", "top"),
           (1.92, 1.0, "FW:200", "right", "center"), (2.5, 2.08, "FW:100", "center", "bottom"),
           (3.08, 1.0, "FW:200", "left", "center")],
          [(0.0, 2.3, "CW:90", "center", "bottom"), (1.0, 2.3, "CW:90", "center", "bottom"),
           (1.0, -0.2, "CCW:90", "center", "top"), (2.0, -0.2, "CCW:90", "center", "top"),
           (2.0, 2.3, "CW:90", "center", "bottom"), (3.0, 2.3, "CW:90", "center", "bottom")],
          "C2 - Zigzag mini (tambak 2 x 3 m, lintasan 1 m)")
    a2.text(0.05, -0.2, "START", ha="left", va="top", fontsize=8.5, color=GREEN, weight="bold")
    a2.plot([3], [0], marker="X", ms=11, color=GREEN, mec="black", zorder=6)
    a2.text(3.12, 0.05, "FINISH\n(3 m, 0)", ha="left", va="bottom", fontsize=8.5,
            color=GREEN, weight="bold")
    a2.set_xlim(-0.8, 3.8)
    a2.set_ylim(-1.2, 2.7)
    return _save(fig, "fig_lintasan_kombinasi.png")


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
        hr = hp.add_run("Rancangan Skenario Pengujian Gerak Robot Akuatik  |  Draf untuk persetujuan")
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
            ("Diajukan kepada", "Bapak Dany Eka Saputra (Dosen Pembimbing)"),
            ("Status", "Draf — diajukan untuk persetujuan sebelum pengujian di kolam"),
            ("Tanggal", "September 2026"))):
        D.cell(info.rows[i].cells[0], k, bold=True, size=10.5)
        D.cell(info.rows[i].cells[1], ": " + v, size=10.5)
        info.rows[i].cells[0].width = Cm(3.6)
        info.rows[i].cells[1].width = Cm(11.5)
    d.add_paragraph()

    # ---------------- ringkasan ----------------
    D.h1("Ringkasan")
    D.p("Tabel berikut menjawab empat hal yang diminta untuk skenario uji. Rinciannya ada pada "
        "bagian-bagian selanjutnya.")
    D.table(["Pertanyaan", "Jawaban singkat"], [
        ["Gerakan apa yang diuji?",
         "Tiga kelompok: (A) maju lurus, (B) belok kanan dan kiri 45° dan 90°, "
         "(C) kombinasi — lintasan kotak 1 × 2 m dan misi zigzag mini 2 × 3 m. Total 9 skenario."],
        ["Jaraknya berapa?",
         "Lurus 50, 100, dan 200 cm; belok 45° dan 90°; kotak 1 × 2 m (keliling 6 m); zigzag "
         "tambak 2 × 3 m dengan lebar lintasan 1 m (4 lintasan, total 11 m). Semua masih di "
         "dalam batas perintah robot (FW 10–200 cm, CW/CCW 1–180°)."],
        ["Berapa kali pengulangan?",
         "Setiap skenario diulang 5 kali (5 data valid), sehingga total 45 percobaan."],
        ["Bagaimana cara mengukurnya?",
         "Cukup dengan HP dan meteran. Tepi kolam dipakai sebagai garis lurus acuan. Jarak "
         "diukur dengan meteran di sepanjang tepi kolam; sudut diukur dari foto HP tampak atas "
         "yang dihitung dengan skrip ukur_foto.py di laptop. Hasil ukur dibandingkan dengan "
         "perintah dan dengan pembacaan MPU di log GUI, lalu dihitung galat, akurasi, dan "
         "simpangan bakunya."],
    ], [4.2, 12.2], size=10)

    # ---------------- 1 ----------------
    D.h1("1. Latar Belakang dan Tujuan Pengujian")
    D.p("Pengujian sebelumnya menunjukkan bahwa GUI pada Pengendali Utama dapat mengirim perintah "
        "dan robot membalas dengan sinyal ON dan FIN. Namun sinyal FIN hanya berarti robot sudah "
        "menyelesaikan perintah menurut perhitungannya sendiri; FIN belum membuktikan bahwa robot "
        "benar-benar bergerak sejauh atau berbelok sebesar yang diperintahkan. Hal ini penting "
        "terutama untuk perintah maju (FW), karena jaraknya diturunkan dari waktu tempuh dan tidak "
        "diukur oleh sensor, sehingga jarak nyata dapat berbeda akibat hambatan air, angin, dan "
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
    D.table(["Aspek", "Cara kerja pada robot", "Akibat pada pengujian"], [
        ["Perintah maju FW:<10–200 cm>",
         "Durasi = jarak ÷ kecepatan jelajah (ROBOT_SPEED_MPS = 0,5 m/s); arah dijaga "
         "heading-hold MPU.",
         "Jarak tidak diukur sensor, jadi wajib diverifikasi dengan pengukuran dari luar robot."],
        ["Perintah belok CW/CCW:<1–180°>",
         "Putaran berhenti saat yaw MPU mencapai target (toleransi 3°).",
         "Sudut aktual dibandingkan dengan perintah dan dengan nilai MPU."],
        ["Mekanisme belok",
         "Differential thrust: satu motor dimatikan (CW = motor kiri jalan, CCW = motor kanan "
         "jalan).",
         "Robot berbelok melingkar, bukan di tempat. Robot diposisikan agar belok menjauhi tepi "
         "kolam; belok kanan dan kiri diuji terpisah."],
        ["Inersia di air",
         "Setelah motor berhenti, robot masih meluncur atau berputar sedikit.",
         "Pengukuran dilakukan setelah robot benar-benar diam, bukan saat FIN diterima."],
    ], [3.6, 6.4, 6.4])

    # ---------------- 3 ----------------
    D.h1("3. Variabel Pengujian")
    D.table(["Jenis variabel", "Isi"], [
        ["Variabel bebas (yang diubah)",
         "Jenis gerakan dan besar perintah (jarak dalam cm, sudut dalam derajat)."],
        ["Variabel terikat (yang diukur)",
         "Jarak aktual, penyimpangan lateral, sudut aktual, galat titik akhir/penutupan, dan "
         "keberhasilan eksekusi perintah."],
        ["Variabel kontrol (dijaga tetap)",
         "CRUISE_PWM 1300 µs; konstanta firmware tidak diubah selama pengujian resmi; baterai "
         "terisi penuh di awal sesi; lokasi dan titik start sama; status MPU sehat (S = 1); GUI "
         "pada mode REAL."],
        ["Kondisi yang dicatat",
         "Angin (tenang/sedang/kencang), riak atau arus air, jam mulai (lama pemakaian baterai)."],
    ], [4.6, 11.8], size=10)

    # ---------------- 4 ----------------
    D.h1("4. Skenario Pengujian")
    D.p("Sembilan skenario dibagi menjadi tiga kelompok. Semua perintah dikirim dari GUI "
        "Pengendali Utama pada mode REAL.")
    zig = ("Dari halaman MISI (antrean otomatis, 13 perintah): FW:200 → CW:90 → FW:100 → CW:90 → "
           "FW:200 → CCW:90 → FW:100 → CCW:90 → FW:200 → CW:90 → FW:100 → CW:90 → FW:200")
    t = D.table(["Kode", "Gerakan", "Perintah dari GUI", "Target", "Ulang", "Data yang diukur"], [
        ["A1", "Maju lurus 50 cm", "FW:50", "50 cm", "5×", "Jarak aktual, penyimpangan lateral"],
        ["A2", "Maju lurus 100 cm", "FW:100", "100 cm", "5×", "Jarak aktual, penyimpangan lateral"],
        ["A3", "Maju lurus 200 cm", "FW:200", "200 cm", "5×", "Jarak aktual, penyimpangan lateral"],
        ["B1", "Belok kanan 45°", "CW:45", "45°", "5×", "Sudut aktual, sudut MPU"],
        ["B2", "Belok kanan 90°", "CW:90", "90°", "5×", "Sudut aktual, sudut MPU"],
        ["B3", "Belok kiri 45°", "CCW:45", "45°", "5×", "Sudut aktual, sudut MPU"],
        ["B4", "Belok kiri 90°", "CCW:90", "90°", "5×", "Sudut aktual, sudut MPU"],
        ["C1", "Lintasan kotak 1 × 2 m (4 × belok kanan)",
         "FW:100 → CW:90 → FW:200 → CW:90 → FW:100 → CW:90 → FW:200 → CW:90",
         "Kembali ke titik start dengan arah semula", "5×",
         "Galat penutupan, galat arah akhir, jumlah FIN"],
        ["C2", "Misi zigzag mini: tambak 2 × 3 m, lebar lintasan 1 m", zig,
         "Titik akhir 3 m dari start di sepanjang tepi", "5×",
         "Galat titik akhir, jumlah FIN, waktu total"],
        ["", "", "", "", "", ""],
    ], [1.1, 3.1, 4.6, 2.8, 1.1, 3.7], size=9, center=(0, 3, 4))
    last = t.rows[-1]
    merged = last.cells[0].merge(last.cells[5])
    D.cell(merged, "Total: 9 skenario × 5 pengulangan = 45 percobaan valid", bold=True,
           size=9.5, align=CENTER)
    D.shade(merged, "DCE6F0")

    D.figure(fig["kombinasi"], "Gambar 1. Lintasan rencana skenario kombinasi C1 (kotak) dan "
             "C2 (zigzag mini) terhadap tepi kolam", 15.0)

    D.h2("Alasan pemilihan skenario")
    D.bullet(" mewakili jarak pendek, sedang, dan maksimum satu perintah FW. Lintasan panjang pada "
             "misi selalu dipecah aplikasi menjadi potongan ≤ 200 cm, jadi ketiga jarak ini "
             "mencakup semua potongan yang dipakai.", "Lurus 50/100/200 cm —")
    D.bullet(" 90° dipakai pada setiap belokan misi zigzag, sedangkan 45° menguji sudut kecil. "
             "Kanan dan kiri diuji terpisah karena memakai motor yang berbeda.",
             "Belok 45° dan 90°, kanan dan kiri —")
    D.bullet(" lintasan tertutup. Bila semua gerakan tepat, robot kembali ke titik start dengan "
             "arah semula, sehingga kesalahan yang menumpuk mudah terlihat dan cukup diukur di "
             "satu titik. Karena keempat belokannya sama, pergeseran akibat belok melingkar saling "
             "meniadakan; robot yang ideal tetap kembali ke start.", "Kotak 1 × 2 m —")
    D.bullet(" pola yang benar-benar dipakai robot untuk menebar pakan, diambil langsung dari "
             "perencana jalur aplikasi. Empat lintasan dipilih agar robot berakhir di sisi tepi "
             "yang sama dengan start, sehingga posisi akhirnya bisa diukur dengan meteran dari "
             "tepi.", "Zigzag mini 2 × 3 m —")
    D.bullet(" jumlah minimum agar rata-rata dan simpangan baku bermakna. Dapat ditambah menjadi "
             "10 kali bila waktu memungkinkan.", "Pengulangan 5 kali —")

    # ---------------- 5 ----------------
    D.h1("5. Alat")
    D.p("Pengujian cukup memakai alat yang sudah dimiliki:")
    D.table(["No", "Alat", "Fungsi"], [
        ["1", "HP", "Memotret robot dari atas (untuk sudut) dan stopwatch"],
        ["2", "Meteran gulung (≥ 3 m)", "Mengukur jarak di sepanjang tepi kolam dan jarak robot ke tepi"],
        ["3", "Laptop/PC berisi repositori skripsi",
         "Menjalankan ukur_foto.py untuk menghitung sudut dari foto"],
        ["4", "Raspberry Pi + GUI (bagian dari sistem)",
         "Mengirim perintah; mencatat waktu ON/FIN dan yaw MPU secara otomatis"],
    ], [1.0, 6.4, 9.0], size=10, center=(0,))
    D.p("Dari lokasi hanya dimanfaatkan tepi kolam yang lurus sebagai garis acuan 0°, dan benda "
        "apa saja (batu, sandal, kapur, selotip) sebagai tanda titik di tepi kolam. Hasil dicatat "
        "di lembar data (Lampiran) atau langsung di HP.")
    D.note("pengukuran minimal dengan HP dan meteran tetap diperlukan dan tidak bisa diganti "
           "data robot. Sinyal FIN dan sensor MPU berasal dari robot sendiri, sehingga tidak dapat "
           "membuktikan bahwa robot benar-benar bergerak sesuai perintah — itulah yang ingin "
           "dibuktikan oleh pengujian ini.", lead="Mengapa tetap perlu alat ukur: ")

    # ---------------- 6 ----------------
    D.h1("6. Metode Pengukuran")
    D.h2("6.1 Prinsip: tiga nilai untuk setiap percobaan")
    D.table(["Nilai", "Sumber", "Fungsi"], [
        ["Perintah (target)", "Yang dikirim dari GUI, mis. FW:100", "Acuan pembanding"],
        ["Menurut sistem robot", "Sinyal FIN dan yaw MPU di log GUI",
         "Menunjukkan apa yang “dikira” robot"],
        ["Aktual", "Diukur dari luar robot: meteran dan foto HP",
         "Kebenaran lapangan, dasar penilaian"],
    ], [4.0, 6.4, 6.0], size=10)
    D.p("Keberhasilan gerak dinilai dari selisih nilai aktual terhadap perintah. Nilai MPU tidak "
        "dipakai sebagai nilai aktual karena berasal dari sensor robot sendiri; nilai itu justru "
        "dibandingkan dengan nilai aktual untuk menilai ketelitian sensornya.")

    D.h2("6.2 Garis acuan dan titik acuan")
    D.p("Tepi kolam yang lurus dipakai sebagai garis acuan (arah 0°). Titik tengah robot dipakai "
        "sebagai titik acuan semua pengukuran jarak, dan arah hadap robot adalah garis tengah "
        "badan robot dari buritan ke haluan.")

    D.h2("6.3 Pengukuran gerak lurus (A1–A3)")
    D.figure(fig["lurus"], "Gambar 2. Pengukuran gerak lurus dengan meteran di sepanjang tepi kolam",
             15.5)
    D.steps([
        "Letakkan robot sejajar tepi kolam, ± 30 cm dari tepi. Beri tanda di tepi kolam yang "
        "segaris dengan titik tengah robot (tanda start).",
        "Kirim perintah. Setelah FIN diterima, tunggu hingga robot benar-benar diam (± 3 detik).",
        "Beri tanda kedua di tepi kolam yang segaris tegak lurus dengan titik tengah robot.",
        ("Jarak aktual (d aktual) ", "= jarak antara dua tanda, diukur dengan meteran di "
         "sepanjang tepi."),
        ("Penyimpangan lateral (e lateral) ", "= jarak titik tengah robot ke tepi (meteran) "
         "dikurangi 30 cm; positif bila menjauhi tepi."),
    ])
    D.note("tanda kedua dibidik dengan mata, sehingga ketelitian bacaan sekitar ± 3 cm. Nilai "
           "ini perlu diperhitungkan terutama pada A1 (50 cm).")

    D.h2("6.4 Pengukuran belok (B1–B4)")
    D.figure(fig["belok"], "Gambar 3. Pengukuran sudut belok dari foto HP tampak atas", 15.5)
    D.steps([
        "Letakkan robot sejajar tepi kolam. Untuk CW, tepi kolam berada di sisi kiri robot; untuk "
        "CCW, di sisi kanan, sehingga robot selalu berbelok menjauhi tepi.",
        "Catat yaw MPU awal dari GUI, lalu foto robot dari atas (foto “sebelum”). Tepi kolam harus "
        "ikut masuk ke foto.",
        "Kirim perintah. Setelah FIN diterima dan robot berhenti berputar, foto lagi (foto "
        "“sesudah”) dan catat yaw MPU akhir.",
        ("Sudut aktual ", "dihitung di laptop/PC dengan perintah di bawah. Pada tiap foto klik dua "
         "titik di tepi kolam, lalu buritan dan haluan robot; skrip menampilkan besar sudut belok "
         "dan menyimpan foto beranotasi sebagai bukti."),
        ("Sudut MPU ", "= yaw akhir − yaw awal dari log GUI."),
    ])
    D.code("python Pengujian/ukur_foto.py sebelum.jpg sesudah.jpg")
    D.note("foto diambil setegak mungkin tepat di atas robot (misalnya lengan diangkat di atas "
           "robot dari tepi kolam). Foto yang miring membuat sudut terbaca meleset.")

    D.h2("6.5 Pengukuran kombinasi (C1–C2)")
    D.p("C1 — Kotak 1 × 2 m", bold=True, after=2)
    D.steps([
        "Robot sejajar tepi kolam dengan tepi di sisi kiri robot, ± 30 cm dari tepi. Beri tanda "
        "start di tepi dan foto robot dari atas.",
        "Kirim delapan perintah berurutan dari halaman MANUAL sesuai tabel skenario; perintah "
        "berikutnya dikirim setelah FIN perintah sebelumnya diterima.",
        ("Galat penutupan ", "= jarak lurus titik tengah robot ke titik start setelah robot diam: "
         "ukur pergeseran di sepanjang tepi (Δx) dan selisih jarak ke tepi terhadap 30 cm (Δy)."),
        ("Galat arah akhir ", "= sudut dari foto sebelum dan sesudah dengan ukur_foto.py "
         "(ideal 0°, karena total belokan 360°)."),
    ])
    D.p("C2 — Misi zigzag mini", bold=True, after=2)
    D.steps([
        "Di halaman MISI masukkan panjang 2 m, lebar 3 m, lebar lintasan 1 m, titik awal "
        "kiri-bawah. Pastikan preview menghasilkan 13 perintah seperti pada tabel skenario.",
        "Robot menghadap tegak lurus menjauhi tepi, ± 50 cm dari tepi. Beri tanda start di tepi, "
        "lalu tanda titik akhir rencana 3 m dari tanda start di sepanjang tepi (arah belokan "
        "pertama).",
        "Jalankan misi. Setelah robot diam, ukur pergeseran di sepanjang tepi terhadap tanda "
        "titik akhir (Δx) dan selisih jarak robot ke tepi terhadap 50 cm (Δy).",
        "Dari log GUI, catat jumlah perintah yang selesai (FIN), kirim ulang, dan waktu total "
        "(estimasi aplikasi 31 detik).",
    ])
    D.note("karena robot berbelok melingkar, jarak antar-lintasan aktual berpotensi lebih lebar "
           "dari rencana. Hal ini akan terlihat sebagai titik akhir yang bergeser lebih jauh di "
           "sepanjang tepi (Δx positif), dan dapat dipakai untuk mengevaluasi perencana jalur.")

    # ---------------- 7 ----------------
    D.h1("7. Pengolahan Data")
    D.table(["Besaran", "Rumus", "Keterangan"], [
        ["Galat absolut", "e = | x aktual − x perintah |", "Dalam cm atau derajat"],
        ["Galat relatif", "e% = | x aktual − x perintah | ÷ x perintah × 100%", "Dalam persen"],
        ["Akurasi", "A = 100% − e%", "Semakin tinggi semakin tepat"],
        ["Rata-rata", "x̄ = (x1 + x2 + … + xn) ÷ n", "n = 5 percobaan"],
        ["Simpangan baku", "s = √[ Σ (xi − x̄)² ÷ (n − 1) ]",
         "Keterulangan (presisi): semakin kecil semakin konsisten"],
        ["Galat titik akhir / penutupan (C1, C2)", "e = √( Δx² + Δy² )",
         "Jarak posisi akhir robot ke titik rencana"],
        ["Galat sensor MPU", "e MPU = | θ MPU − θ aktual |", "Ketelitian sensor MPU"],
        ["Keberhasilan eksekusi",
         "(percobaan dengan semua perintah FIN ÷ jumlah percobaan) × 100%",
         "Keandalan komunikasi dan eksekusi"],
    ], [3.6, 7.6, 5.2])
    D.p("Contoh: perintah FW:100 dan jarak aktual 92 cm → e = 8 cm, e% = 8%, akurasi = 92%.",
        italic=True)
    D.p("Hasil setiap skenario disajikan dalam tabel 5 percobaan beserta rata-rata, simpangan "
        "baku, dan akurasi, lalu dirangkum dalam grafik perbandingan nilai perintah dan nilai "
        "aktual.")

    # ---------------- 8 ----------------
    D.h1("8. Kriteria Keberhasilan (Usulan)")
    D.table(["Skenario", "Parameter", "Batas usulan"], [
        ["A1–A3", "Galat jarak rata-rata", "≤ 10% dari jarak perintah"],
        ["A1–A3", "Penyimpangan lateral rata-rata", "≤ 10% dari jarak perintah"],
        ["B1–B4", "Galat sudut rata-rata", "≤ 5°"],
        ["B1–B4", "Galat sensor MPU terhadap sudut aktual", "≤ 5°"],
        ["C1", "Galat penutupan", "≤ 30 cm (± 5% dari keliling 6 m)"],
        ["C1", "Galat arah akhir", "≤ 10°"],
        ["C2", "Galat titik akhir", "≤ 55 cm (± 5% dari lintasan 11 m)"],
        ["C1, C2", "Keberhasilan eksekusi", "100% perintah selesai (FIN)"],
    ], [2.6, 7.2, 6.6], size=10, center=(0,))
    D.note("batas di atas masih usulan dan menunggu persetujuan Bapak. Bila suatu kriteria tidak "
           "tercapai, penyebabnya dianalisis (mis. angin, kalibrasi kecepatan, gain heading) dan "
           "dilaporkan sebagai temuan pengujian.")

    # ---------------- 9 ----------------
    D.h1("9. Prosedur Pelaksanaan")
    D.h2("9.1 Tahap pendahuluan (kalibrasi, tidak dihitung sebagai data resmi)")
    D.steps([
        "Periksa arah putar: kirim CW:90. Bila robot berputar ke kiri, ubah YAW_SIGN menjadi −1.",
        "Kirim FW:200 sebanyak 3 kali, ukur jarak nyata, lalu sesuaikan ROBOT_SPEED_MPS.",
        "Setelah kalibrasi selesai, seluruh konstanta firmware dikunci dan tidak diubah selama "
        "pengujian resmi.",
    ])
    D.h2("9.2 Persiapan setiap sesi")
    D.steps([
        "Isi penuh baterai dan catat jam mulai.",
        "Nyalakan robot dalam keadaan diam ± 10 detik agar giroskop terkalibrasi; pastikan GUI "
        "menunjukkan status MPU sehat (S = 1).",
        "Pilih bagian tepi kolam yang lurus dan cukup panjang (± 3,5 m) sebagai lokasi uji.",
        "Pilih mode REAL di GUI dan periksa koneksi (telemetri MPU masuk).",
        "Catat tanggal, lokasi, cuaca, dan kondisi angin/air pada lembar data sesi.",
    ])
    D.h2("9.3 Langkah setiap percobaan")
    D.steps([
        "Letakkan robot di titik start sesuai skenario dan tunggu sampai diam (tidak hanyut).",
        "Catat yaw MPU awal dari GUI; untuk skenario B dan C, foto robot dari atas.",
        "Kirim perintah dari GUI (halaman MANUAL untuk A, B, C1; halaman MISI untuk C2).",
        "Tunggu FIN, lalu tunggu robot diam ± 3 detik.",
        "Ukur dengan meteran dan/atau foto lagi, lalu catat ke lembar data, termasuk yaw MPU "
        "akhir dan ada/tidaknya kirim ulang.",
        "Kembalikan robot ke titik start, lalu ulangi hingga 5 percobaan valid.",
    ])
    D.p("Agar foto mudah dicocokkan, catat urutan foto di lembar data atau ganti nama filenya "
        "sesuai kode percobaan, mis. B2-3-sebelum.jpg dan B2-3-sesudah.jpg.")
    D.h2("9.4 Percobaan yang gagal")
    D.p("Percobaan yang gagal (sinyal hilang, robot menabrak tepi, terbawa angin, dan sebagainya) "
        "tetap dicatat beserta penyebabnya, lalu diganti dengan percobaan baru sampai terkumpul 5 "
        "data valid. Jumlah percobaan gagal ikut dilaporkan sebagai data keandalan.")
    D.h2("9.5 Urutan dan estimasi waktu")
    D.table(["Kelompok", "Jumlah percobaan", "Perkiraan waktu"], [
        ["Persiapan & kalibrasi", "—", "± 20 menit"],
        ["A (lurus)", "15", "± 40 menit"],
        ["B (belok)", "20", "± 50 menit"],
        ["C (kombinasi)", "10", "± 50 menit"],
        ["Total", "45", "± 2,5–3 jam (dapat dibagi dua sesi; isi baterai di antaranya)"],
    ], [4.5, 4.0, 7.9], size=10, center=(1,))

    # ---------------- lampiran ----------------
    sec = d.add_section(WD_SECTION.NEW_PAGE)
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Cm(29.7), Cm(21)
    sec.left_margin = sec.right_margin = Cm(1.8)
    sec.top_margin, sec.bottom_margin = Cm(1.8), Cm(1.6)

    D.h1("Lampiran — Lembar Pengambilan Data")
    D.p("Satu tabel untuk setiap skenario. Isi di lapangan; kolom galat dan statistik boleh "
        "dihitung setelahnya.", size=10)
    D.h2("Data sesi")
    D.table(["Keterangan", "Isi", "Keterangan", "Isi"], [
        ["Tanggal / jam mulai", "", "Baterai penuh saat mulai (Y/T)", ""],
        ["Lokasi kolam", "", "Status MPU (S)", ""],
        ["Cuaca / angin", "", "ROBOT_SPEED_MPS / KP_HEADING", ""],
        ["Kondisi air (riak/arus)", "", "Pencatat", ""],
    ], [5.0, 8.05, 5.0, 8.05], size=10, zebra=False, row_height=0.75)

    blank = ["1", "2", "3", "4", "5", "Rata-rata", "Simp. baku"]

    def lembar(title, headers, widths):
        D.h2(title)
        t = D.table(headers, [[n] + [""] * (len(headers) - 1) for n in blank], widths, size=9,
                    zebra=False, center=(0,), header_size=8.5, row_height=0.62)
        for r in t.rows[-2:]:
            for c in r.cells:
                D.shade(c, ZEBRA)
            D.cell(r.cells[0], r.cells[0].text, bold=True, size=9, align=CENTER)

    a_h = ["Perc.", "d aktual (cm)", "Galat (cm)", "Galat (%)", "Jarak ke tepi (cm)",
           "e lateral (cm)", "Waktu ON→FIN (s)", "Kirim ulang? (Y/T)", "Keterangan"]
    a_w = [2.0, 2.6, 2.3, 2.3, 2.7, 2.5, 2.8, 2.6, 6.3]
    for code, cmd in (("A1", "FW:50 (target 50 cm)"), ("A2", "FW:100 (target 100 cm)"),
                      ("A3", "FW:200 (target 200 cm)")):
        lembar(f"Skenario {code} — {cmd}", a_h, a_w)
    b_h = ["Perc.", "Yaw MPU awal (°)", "Yaw MPU akhir (°)", "Sudut MPU (°)",
           "Sudut aktual dari foto (°)", "Galat aktual (°)", "Galat MPU vs aktual (°)",
           "Kirim ulang? (Y/T)", "Keterangan / nama foto"]
    b_w = [2.0, 2.6, 2.6, 2.4, 2.8, 2.5, 3.0, 2.5, 5.7]
    for code, cmd in (("B1", "CW:45 (target 45°)"), ("B2", "CW:90 (target 90°)"),
                      ("B3", "CCW:45 (target 45°)"), ("B4", "CCW:90 (target 90°)")):
        lembar(f"Skenario {code} — {cmd}", b_h, b_w)
    lembar("Skenario C1 — Kotak 1 × 2 m (target: kembali ke start, arah semula)",
           ["Perc.", "Δx sepanjang tepi (cm)", "Jarak ke tepi (cm) [30]", "Δy (cm)",
            "Galat penutupan (cm)", "Galat arah akhir (°)", "FIN (…/8)", "Waktu total (s)",
            "Keterangan / nama foto"],
           [2.0, 2.8, 2.8, 2.2, 2.8, 2.7, 2.2, 2.6, 6.0])
    lembar("Skenario C2 — Zigzag mini 2 × 3 m (target: titik akhir 3 m dari start, 50 cm dari tepi)",
           ["Perc.", "Δx dari titik akhir (cm)", "Jarak ke tepi (cm) [50]", "Δy (cm)",
            "Galat titik akhir (cm)", "FIN (…/13)", "Kirim ulang (kali)", "Waktu total (s)",
            "Keterangan"],
           [2.0, 2.8, 2.8, 2.2, 2.8, 2.3, 2.6, 2.6, 6.0])
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
    fig = {"lurus": fig_lurus(), "belok": fig_belok(), "kombinasi": fig_kombinasi()}
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
