"""
build_panduan_pdf.py — Ubah PANDUAN_OPERASIONAL_RASPBERRY.md menjadi PDF
=======================================================================

Menghasilkan: PANDUAN_OPERASIONAL_RASPBERRY.pdf

Panduan operator dipegang di lapangan, sering dicetak, dan dibaca orang yang
belum tentu punya akses ke repositori — jadi bentuk PDF-nya ikut dipelihara,
bukan hanya berkas Markdown-nya.

Gaya warna & tata letaknya sengaja disamakan dengan build_docs_pdf.py supaya
seluruh dokumen proyek terlihat sebagai satu kesatuan.

Butuh: reportlab   (pip install reportlab)
Jalankan:  python build_panduan_pdf.py
"""

import os
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable, KeepTogether, ListFlowable, ListItem, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

SRC = "PANDUAN_OPERASIONAL_RASPBERRY.md"
OUT = "PANDUAN_OPERASIONAL_RASPBERRY.pdf"

# --------------------------------------------------------------------- warna
NAVY = colors.HexColor("#1a3c5e")
BLUE = colors.HexColor("#2c6da3")
LIGHT = colors.HexColor("#eaf2f8")
GREY = colors.HexColor("#7f8c8d")
CODEBG = colors.HexColor("#f4f6f8")
WARNBG = colors.HexColor("#fff8e1")
WARNLINE = colors.HexColor("#e6a817")
RULE = colors.HexColor("#d5dde5")

styles = getSampleStyleSheet()

styles.add(ParagraphStyle("TitleBig", parent=styles["Title"], fontSize=21,
                          textColor=NAVY, spaceAfter=4, leading=25))
styles.add(ParagraphStyle("Sub", parent=styles["Normal"], fontSize=11,
                          textColor=GREY, alignment=TA_CENTER, spaceAfter=2))
styles.add(ParagraphStyle("H1", parent=styles["Heading1"], fontSize=15,
                          textColor=NAVY, spaceBefore=15, spaceAfter=7))
styles.add(ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12.5,
                          textColor=BLUE, spaceBefore=11, spaceAfter=5))
styles.add(ParagraphStyle("H3", parent=styles["Heading3"], fontSize=11,
                          textColor=BLUE, spaceBefore=9, spaceAfter=4))
# Rata kiri, bukan rata kanan-kiri: panduan langkah lebih mudah dipindai mata
# kalau jarak antar katanya seragam.
styles.add(ParagraphStyle("Body", parent=styles["Normal"], fontSize=10.5,
                          leading=15, spaceAfter=6))
styles.add(ParagraphStyle("CodeBlk", parent=styles["Normal"], fontName="Courier",
                          fontSize=9, leading=12.5, textColor=colors.HexColor("#14304a")))
styles.add(ParagraphStyle("Quote", parent=styles["Normal"], fontSize=10,
                          leading=14.5, textColor=colors.HexColor("#5d4a12")))
styles.add(ParagraphStyle("TblHead", parent=styles["Normal"], fontSize=9.5,
                          leading=12.5, textColor=colors.white, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle("TblCell", parent=styles["Normal"], fontSize=9.5,
                          leading=12.5))
styles.add(ParagraphStyle("Foot", parent=styles["Normal"], fontSize=8,
                          textColor=GREY, alignment=TA_CENTER))

# Font bawaan reportlab memakai WinAnsi (cp1252). Karakter di luar itu tercetak
# sebagai kotak kosong, jadi diganti padanan ASCII-nya lebih dulu.
SUBST = {
    "→": "->", "←": "<-", "↑": "^", "↓": "v",
    "⇒": "=>", "⚡": "(petir)", "✓": "v", "✔": "v",
    "✗": "x", "✘": "x", "•": "-", "·": "-",
    "─": "-", "│": "|", "┌": "+", "┐": "+",
    "└": "+", "┘": "+", "┼": "+",
}


def sanitize(text):
    for bad, good in SUBST.items():
        text = text.replace(bad, good)
    # Sisa karakter yang tetap tidak bisa dicetak dibuang, bukan dibiarkan
    # menjadi kotak kosong yang membingungkan pembaca.
    return text.encode("cp1252", "ignore").decode("cp1252")


def inline(text):
    """Ubah penanda Markdown sebaris menjadi markup mini reportlab."""
    text = sanitize(text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # `kode` -> monospace berlatar; dikerjakan sebelum bold agar isinya utuh
    text = re.sub(r"`([^`]+)`",
                  r'<font face="Courier" size="9" color="#14304a">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    # [teks](tautan) -> cukup teksnya; tautan relatif tidak berguna di cetakan
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def code_block(lines):
    body = "<br/>".join(
        sanitize(l).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace(" ", "&nbsp;")
        for l in lines
    )
    tbl = Table([[Paragraph(body, styles["CodeBlk"])]], colWidths=[16.4 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODEBG),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return [tbl, Spacer(1, 7)]


def quote_block(lines):
    body = "<br/>".join(inline(l) for l in lines if l.strip())
    tbl = Table([[Paragraph(body, styles["Quote"])]], colWidths=[16.4 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WARNBG),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, WARNLINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return [tbl, Spacer(1, 7)]


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def table_block(rows):
    head, body = rows[0], rows[1:]
    ncol = len(head)

    # Lebar kolom mengikuti panjang isi terpanjang tiap kolom, dibatasi agar
    # satu kolom tidak menelan seluruh halaman.
    weights = []
    for i in range(ncol):
        longest = max([len(head[i])] + [len(r[i]) for r in body if i < len(r)])
        weights.append(max(6, min(longest, 46)))
    total = float(sum(weights))
    widths = [16.4 * cm * w / total for w in weights]

    data = [[Paragraph(inline(c), styles["TblHead"]) for c in head]]
    for r in body:
        r = (r + [""] * ncol)[:ncol]
        data.append([Paragraph(inline(c), styles["TblCell"]) for c in r])

    tbl = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    tbl.setStyle(TableStyle(style))
    return [tbl, Spacer(1, 9)]


def list_block(items, ordered):
    flow = ListFlowable(
        [ListItem(Paragraph(inline(t), styles["Body"]), leftIndent=14) for t in items],
        bulletType="1" if ordered else "bullet",
        bulletFontSize=9, leftIndent=16, bulletOffsetY=-1,
    )
    return [flow, Spacer(1, 5)]


def build_story(md):
    story = []
    lines = md.split("\n")
    i = 0
    first_h1 = True
    buf_list, list_ordered = [], False

    def flush_list():
        nonlocal buf_list
        if buf_list:
            story.extend(list_block(buf_list, list_ordered))
            buf_list = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # ---- blok kode berpagar
        if stripped.startswith("```"):
            flush_list()
            i += 1
            block = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            story.extend(code_block(block))
            continue

        # ---- kutipan / kotak peringatan
        if stripped.startswith(">"):
            flush_list()
            block = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                block.append(lines[i].strip().lstrip(">").strip())
                i += 1
            story.extend(quote_block(block))
            continue

        # ---- tabel
        if stripped.startswith("|") and i + 1 < len(lines) and \
                set(lines[i + 1].strip()) <= set("|-: "):
            flush_list()
            rows = [split_row(lines[i])]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            story.extend(table_block(rows))
            continue

        # ---- judul
        m = re.match(r"^(#{1,4})\s+(.*)", stripped)
        if m:
            flush_list()
            level, text = len(m.group(1)), m.group(2)
            if level == 1 and first_h1:
                first_h1 = False
                story.append(Paragraph(inline(text), styles["TitleBig"]))
                story.append(HRFlowable(width="100%", thickness=1.2, color=NAVY,
                                        spaceBefore=4, spaceAfter=10))
            else:
                story.append(Paragraph(inline(text),
                                       styles["H1" if level <= 2 else
                                              ("H2" if level == 3 else "H3")]))
            i += 1
            continue

        # ---- garis pemisah
        if stripped in ("---", "***", "___"):
            flush_list()
            story.append(HRFlowable(width="100%", thickness=0.6, color=RULE,
                                    spaceBefore=8, spaceAfter=8))
            i += 1
            continue

        # ---- daftar
        m = re.match(r"^\s*(\d+)\.\s+(.*)", line)
        if m:
            if buf_list and not list_ordered:
                flush_list()
            list_ordered = True
            buf_list.append(m.group(2))
            i += 1
            continue
        m = re.match(r"^\s*[-*]\s+(.*)", line)
        if m:
            if buf_list and list_ordered:
                flush_list()
            list_ordered = False
            buf_list.append(m.group(1))
            i += 1
            continue

        # ---- baris kosong / paragraf biasa
        if not stripped:
            flush_list()
            i += 1
            continue

        flush_list()
        para = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and \
                not re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]) and \
                not lines[i].strip().startswith(("#", ">", "|", "```")):
            para.append(lines[i].strip())
            i += 1
        story.append(Paragraph(inline(" ".join(para)), styles["Body"]))

    flush_list()
    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(2 * cm, 1.05 * cm,
                      "Panduan Operasional Pengendali Utama - Robot Akuatik Feeder Tambak")
    canvas.drawRightString(A4[0] - 2 * cm, 1.05 * cm, "Hal. %d" % doc.page)
    canvas.restoreState()


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)

    with open(SRC, encoding="utf-8") as fh:
        md = fh.read()

    doc = SimpleDocTemplate(
        OUT, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.8 * cm, bottomMargin=2 * cm,
        title="Panduan Operasional Pengendali Utama (Raspberry Pi 4)",
        author="Samuel Alfonsus",
    )
    doc.build(build_story(md), onFirstPage=footer, onLaterPages=footer)
    print("OK -> %s (%.0f KB)" % (OUT, os.path.getsize(OUT) / 1024.0))


if __name__ == "__main__":
    main()
