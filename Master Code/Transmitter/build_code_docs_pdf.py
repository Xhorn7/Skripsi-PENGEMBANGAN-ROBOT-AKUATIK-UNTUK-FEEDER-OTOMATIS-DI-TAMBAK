"""
build_code_docs_pdf.py — Render dokumentasi kode (Markdown) menjadi PDF
=======================================================================

Mengubah berkas .md dokumentasi kode menjadi PDF bergaya sama dengan
Dokumentasi_GUI_Feeder_SDLC.pdf, sehingga seluruh dokumen skripsi tampil
konsisten.

Sebelumnya PDF ini dibuat dengan skrip sekali-pakai sehingga tidak bisa
diperbarui saat kodenya berubah. Skrip ini menggantikannya agar dokumentasi
dapat di-regenerate kapan saja:

    python build_code_docs_pdf.py

Butuh: reportlab   (pip install reportlab)

Subset Markdown yang didukung — cukup untuk dokumentasi kode di repo ini:
    # / ## / ###      judul
    ```blok kode```   blok kode (spasi dipertahankan)
    | tabel | pipa |   tabel GFM
    - butir            daftar tak berurut
    1. butir           daftar berurut
    > kutipan          blok catatan
    ---                garis pemisah
    **tebal**  *miring*  `kode`  [teks](tautan)
"""

import html
import os
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle, XPreformatted,
)

# (berkas markdown, berkas PDF keluaran) — relatif terhadap folder skrip ini
DOCS = [
    ("Dokumentasi_Kode_receiverArduino.md",
     "Dokumentasi_Kode_receiverArduino.pdf"),
    ("../Robot/New/Finalnew/Dokumentasi_Kode_Finalnew.md",
     "../Robot/New/Finalnew/Dokumentasi_Kode_Finalnew.pdf"),
    ("../Robot/New/Finalnew/Dokumentasi_Troubleshooting_NRF.md",
     "../Robot/New/Finalnew/Dokumentasi_Troubleshooting_NRF.pdf"),
]

PAGE_W = A4[0]
MARGIN = 2 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

NAVY = colors.HexColor("#1a3c5e")
BLUE = colors.HexColor("#2c6da3")
LIGHT = colors.HexColor("#eaf2f8")
GREY = colors.HexColor("#7f8c8d")
CODEBG = colors.HexColor("#f4f6f7")
QUOTEBG = colors.HexColor("#fdf6e3")

# --------------------------------------------------------------------- styles
styles = getSampleStyleSheet()
S = {
    "TitleBig": ParagraphStyle("TitleBig", parent=styles["Title"], fontSize=19,
                               textColor=NAVY, spaceAfter=4, leading=23),
    "H1": ParagraphStyle("H1x", parent=styles["Heading1"], fontSize=14,
                         textColor=NAVY, spaceBefore=14, spaceAfter=6),
    "H2": ParagraphStyle("H2x", parent=styles["Heading2"], fontSize=11.5,
                         textColor=BLUE, spaceBefore=10, spaceAfter=4),
    "Body": ParagraphStyle("Bodyx", parent=styles["Normal"], fontSize=10,
                           leading=14.5, alignment=TA_JUSTIFY, spaceAfter=6),
    "Bullet": ParagraphStyle("Bulletx", parent=styles["Normal"], fontSize=10,
                             leading=14, spaceAfter=2),
    "Cell": ParagraphStyle("Cellx", parent=styles["Normal"], fontSize=8.5,
                           leading=11),
    "CellHead": ParagraphStyle("CellHeadx", parent=styles["Normal"], fontSize=8.5,
                               leading=11, textColor=colors.white,
                               fontName="Helvetica-Bold"),
    "Code": ParagraphStyle("Codex", parent=styles["Normal"], fontName="Courier",
                           fontSize=7.8, leading=10.2, backColor=CODEBG,
                           borderPadding=6, spaceBefore=2, spaceAfter=8,
                           leftIndent=2, rightIndent=2),
    "Quote": ParagraphStyle("Quotex", parent=styles["Normal"], fontSize=9.2,
                            leading=13, alignment=TA_JUSTIFY,
                            backColor=QUOTEBG, borderPadding=6,
                            leftIndent=6, rightIndent=6, spaceAfter=8),
    "Foot": ParagraphStyle("Footx", parent=styles["Normal"], fontSize=8,
                           textColor=GREY, alignment=TA_CENTER),
}


# ------------------------------------------------------------------- inline md

def inline(text: str) -> str:
    """Markdown sebaris -> markup mini reportlab. Kode dilindungi lebih dulu."""
    text = html.escape(text, quote=False)

    # `kode` disimpan sementara agar ** / * di dalamnya tidak ikut diproses
    spans: list[str] = []

    def stash(m):
        spans.append(m.group(1))
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)

    # tebal diproses lebih dulu dan non-greedy, supaya *miring* yang BERSARANG
    # di dalamnya (mis. "**teks *miring* lagi**") tetap ikut terbaca
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", text)
    # Tautan: bagian URL sengaja TIDAK boleh memuat spasi, tanda kutip, atau
    # penanda kode. Tanpa batasan ini, tanda kurung biasa di dalam kalimat bisa
    # tertangkap sebagai URL dan menghasilkan atribut href yang tidak sah.
    text = re.sub(r"\[([^\]\n]+)\]\(([^)\s\"'\x00]+)\)",
                  r'<link href="\2"><font color="#2c6da3">\1</font></link>', text)

    def unstash(m):
        code = spans[int(m.group(1))]
        return (f'<font face="Courier" size="8.6" backColor="#eef2f4">'
                f'{code}</font>')

    return re.sub(r"\x00(\d+)\x00", unstash, text)


def split_row(line: str) -> list[str]:
    """Pecah satu baris tabel GFM, hormati pipa yang di-escape (\\|)."""
    line = line.strip().strip("|")
    parts, buf, esc = [], "", False
    for ch in line:
        if esc:
            buf += ch if ch == "|" else "\\" + ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == "|":
            parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    parts.append(buf.strip())
    return parts


def make_table(rows: list[list[str]]):
    """Bangun Table dengan lebar kolom proporsional terhadap panjang isi."""
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]

    # bobot kolom = panjang teks terpanjang, dijepit agar tidak ekstrem
    weights = []
    for c in range(ncol):
        longest = max(len(r[c]) for r in rows)
        weights.append(min(max(longest, 8), 60))
    total = sum(weights)
    widths = [CONTENT_W * w / total for w in weights]

    data = [[Paragraph(inline(c), S["CellHead"]) for c in rows[0]]]
    data += [[Paragraph(inline(c), S["Cell"]) for c in r] for r in rows[1:]]

    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b0bec5")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    return t


# ------------------------------------------------------------------- md -> pdf

def markdown_to_story(md: str) -> list:
    lines = md.split("\n")
    story: list = []
    i = 0
    first_heading = True

    def flush_list(items, ordered):
        if not items:
            return
        story.append(ListFlowable(
            [ListItem(Paragraph(inline(t), S["Bullet"]), leftIndent=14)
             for t in items],
            bulletType="1" if ordered else "bullet",
            bulletFontSize=8, leftIndent=16, spaceAfter=6))

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # --- blok kode ---
        if stripped.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            story.append(XPreformatted(
                html.escape("\n".join(block), quote=False), S["Code"]))
            continue

        # --- garis pemisah ---
        if stripped in ("---", "***", "___"):
            story.append(Spacer(1, 2))
            story.append(HRFlowable(width="100%", thickness=0.5, color=GREY,
                                    spaceBefore=2, spaceAfter=8))
            i += 1
            continue

        # --- judul ---
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level, text = len(m.group(1)), m.group(2)
            if level == 1 and first_heading:
                story.append(Paragraph(inline(text), S["TitleBig"]))
                story.append(HRFlowable(width="100%", thickness=1.2, color=BLUE,
                                        spaceBefore=6, spaceAfter=10))
                first_heading = False
            else:
                story.append(Paragraph(inline(text),
                                       S["H1"] if level <= 2 else S["H2"]))
            i += 1
            continue

        # --- tabel ---
        if stripped.startswith("|") and i + 1 < len(lines) and \
                re.match(r"^\|[\s:|-]+\|?$", lines[i + 1].strip()):
            rows = [split_row(stripped)]
            i += 2                                   # lewati baris pemisah
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            story.append(make_table(rows))
            story.append(Spacer(1, 8))
            continue

        # --- kutipan / catatan ---
        if stripped.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            story.append(Paragraph(inline(" ".join(b for b in buf if b)),
                                   S["Quote"]))
            continue

        # --- daftar ---
        if re.match(r"^[-*]\s+", stripped) or re.match(r"^\d+\.\s+", stripped):
            ordered = bool(re.match(r"^\d+\.\s+", stripped))
            marker = r"^\d+\.\s+" if ordered else r"^[-*]\s+"
            items: list[str] = []
            while i < len(lines):
                s = lines[i].strip()
                if re.match(marker, s):
                    items.append(re.sub(marker, "", s))
                elif items and s and not re.match(
                        r"^(#{1,6}\s|>|\||```|---|[-*]\s|\d+\.\s)", s):
                    # baris lanjutan butir sebelumnya (lazy continuation) —
                    # tanpa ini, penanda **tebal** yang terpotong antar-baris
                    # akan bocor mentah ke PDF
                    items[-1] += " " + s
                else:
                    break
                i += 1
            flush_list(items, ordered)
            continue

        # --- paragraf ---
        if stripped:
            buf = []
            while i < len(lines) and lines[i].strip() and \
                    not re.match(r"^(#{1,6}\s|>|\||```|---|[-*]\s|\d+\.\s)",
                                 lines[i].strip()):
                buf.append(lines[i].strip())
                i += 1
            story.append(Paragraph(inline(" ".join(buf)), S["Body"]))
            continue

        i += 1

    return story


def build(md_path: str, pdf_path: str) -> None:
    with open(md_path, encoding="utf-8") as f:
        md = f.read()

    title = next((l.lstrip("# ").strip() for l in md.split("\n")
                  if l.startswith("# ")), os.path.basename(md_path))
    story = markdown_to_story(md)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GREY)
        canvas.drawString(MARGIN, 1.2 * cm, "Robot Akuatik Feeder — Dokumentasi Kode")
        canvas.drawRightString(PAGE_W - MARGIN, 1.2 * cm, f"Hal. {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            topMargin=2 * cm, bottomMargin=2 * cm,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            title=title)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"OK -> {pdf_path}")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    for md_rel, pdf_rel in DOCS:
        build(os.path.join(here, md_rel), os.path.join(here, pdf_rel))
