"""
Buat Lembar_Data_Pengujian.xlsx — lembar isian dengan perhitungan otomatis.

    pip install -r requirements.txt
    python buat_lembar_data.py

Isi hanya sel berlatar KUNING (hasil baca grid keramik di kolam). Kolom abu-abu
berisi rumus: jarak, galat, %, lateral, jarak luncur, sudut, MAE, MAPE, dan
simpangan baku terhitung sendiri.
"""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = Path(__file__).resolve().parent
OUT = HERE / "Lembar_Data_Pengujian.xlsx"

N = 3                      # pengulangan per skenario
KERAMIK = 25               # cm
BARIS_START, KOLOM_START = 2, 4      # start skenario A

NAVY = "1E3A5F"
ISI = "FFF7CC"             # kuning: diisi manual
RUMUS = "EDF2F7"           # abu: otomatis
HEAD = Font(bold=True, color="FFFFFF", size=10)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
THIN = Side(style="thin", color="B0BEC5")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def sheet(wb, nama, judul, headers, widths, n_isi, rows_extra=()):
    ws = wb.create_sheet(nama)
    ws.freeze_panes = "A3"
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    t = ws.cell(row=1, column=1, value=judul)
    t.font = Font(bold=True, size=12, color=NAVY)
    for c, (h, w) in enumerate(zip(headers, widths), start=1):
        cell = ws.cell(row=2, column=c, value=h)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.font = HEAD
        cell.alignment = CENTER
        cell.border = BOX
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.row_dimensions[2].height = 34
    for r in range(3, 3 + N):
        ws.cell(row=r, column=1, value=r - 2).alignment = CENTER
        ws.cell(row=r, column=1).border = BOX
        for c in range(2, len(headers) + 1):
            cell = ws.cell(row=r, column=c)
            cell.fill = PatternFill("solid", fgColor=ISI if c <= n_isi else RUMUS)
            cell.alignment = CENTER
            cell.border = BOX
    for label, func in (("Rata-rata", "AVERAGE"), ("Simpangan baku", "STDEV")):
        r = ws.max_row + 1
        c1 = ws.cell(row=r, column=1, value=label)
        c1.font = Font(bold=True, size=10)
        c1.border = BOX
        for c in range(2, len(headers) + 1):
            col = get_column_letter(c)
            cell = ws.cell(row=r, column=c)
            if headers[c - 1] not in ("Keterangan", "Kirim ulang? (Y/T)"):
                cell.value = f'=IFERROR({func}({col}3:{col}{2 + N}),"")'
            cell.fill = PatternFill("solid", fgColor=RUMUS)
            cell.font = Font(bold=True, size=10)
            cell.alignment = CENTER
            cell.border = BOX
    for label, formula in rows_extra:
        r = ws.max_row + 1
        c1 = ws.cell(row=r, column=1, value=label)
        c1.font = Font(bold=True, size=10, color="B45309")
        c1.border = BOX
        cell = ws.cell(row=r, column=2, value=formula)
        cell.font = Font(bold=True, size=10, color="B45309")
        cell.alignment = Alignment(horizontal="left")
    r = ws.max_row + 2
    ws.cell(row=r, column=1, value="Kuning = diisi manual (hasil baca grid keramik). "
            "Abu-abu = otomatis, jangan diketik.").font = Font(italic=True, size=9)
    return ws


def mae(col):
    """Rata-rata nilai mutlak, aman terhadap baris yang belum diisi."""
    parts = ",".join(f'IF(ISNUMBER({col}{r}),ABS({col}{r}),0)' for r in range(3, 3 + N))
    return f'=IF(COUNT({col}3:{col}{2 + N})=0,"",SUM({parts})/COUNT({col}3:{col}{2 + N}))'


def isi(ws, row, col, value):
    ws.cell(row=row, column=col, value=value)


def sheet_a(wb, kode, perintah, target_cm):
    headers = ["Perc.", "Baris saat FIN (opsional)", "Kolom akhir", "Baris akhir",
               "Jarak aktual (cm)", "Galat (cm)", "Galat (%)", "Lateral (cm)",
               "Jarak luncur (cm)", "Kirim ulang? (Y/T)", "Keterangan"]
    ws = sheet(wb, kode, f"{kode} — {perintah}   (target {target_cm} cm, "
               f"start kolom {KOLOM_START} ; baris {BARIS_START})", headers,
               [6, 13, 10, 10, 12, 10, 10, 11, 12, 11, 26],
               n_isi=4,
               rows_extra=[("MAE (cm)", mae("F")), ("MAPE (%)", mae("G"))])
    for r in range(3, 3 + N):
        isi(ws, r, 5, f'=IF(D{r}="","",(D{r}-{BARIS_START})*{KERAMIK})')
        isi(ws, r, 6, f'=IF(E{r}="","",E{r}-{target_cm})')
        isi(ws, r, 7, f'=IF(E{r}="","",E{r}/{target_cm}*100-100)')
        isi(ws, r, 8, f'=IF(C{r}="","",(C{r}-{KOLOM_START})*{KERAMIK})')
        isi(ws, r, 9, f'=IF(OR(B{r}="",D{r}=""),"",(D{r}-B{r})*{KERAMIK})')
    return ws


def sheet_b(wb, kode, perintah, target_deg):
    headers = ["Perc.", "Yaw MPU awal (°)", "Yaw MPU akhir (°)", "Haluan kolom", "Haluan baris",
               "Buritan kolom", "Buritan baris", "Sudut MPU (°)", "Sudut aktual (°)",
               "Galat aktual (°)", "Galat MPU vs aktual (°)", "Keterangan"]
    ws = sheet(wb, kode, f"{kode} — {perintah}   (target {target_deg}°, arah awal 0° "
               "sejajar garis baris)", headers,
               [6, 11, 11, 10, 10, 10, 10, 11, 12, 11, 13, 22], n_isi=7,
               rows_extra=[("MAE sudut (°)", mae("J")), ("MAE MPU (°)", mae("K"))])
    for r in range(3, 3 + N):
        isi(ws, r, 8, f'=IF(OR(B{r}="",C{r}=""),"",ABS(C{r}-B{r}))')
        isi(ws, r, 9, f'=IF(OR(D{r}="",F{r}=""),"",ABS(DEGREES(ATAN2(E{r}-G{r},D{r}-F{r}))))')
        isi(ws, r, 10, f'=IF(I{r}="","",ABS(I{r}-{target_deg}))')
        isi(ws, r, 11, f'=IF(OR(H{r}="",I{r}=""),"",ABS(H{r}-I{r}))')
    return ws


def sheet_c(wb, kode, judul, kolom_target, baris_target, n_fin):
    headers = ["Perc.", "Kolom akhir", "Baris akhir", "Haluan kolom", "Haluan baris",
               "Buritan kolom", "Buritan baris", "Δ kolom", "Δ baris", "Galat posisi (cm)",
               "Arah akhir (°)", f"FIN (…/{n_fin})", "Waktu total (s)", "Keterangan"]
    ws = sheet(wb, kode, f"{kode} — {judul}   (target kolom {kolom_target} ; "
               f"baris {baris_target})", headers,
               [6, 10, 10, 10, 10, 10, 10, 9, 9, 12, 11, 10, 12, 20], n_isi=7,
               rows_extra=[("MAE posisi (cm)", mae("J"))])
    for r in range(3, 3 + N):
        isi(ws, r, 8, f'=IF(B{r}="","",B{r}-{kolom_target})')
        isi(ws, r, 9, f'=IF(C{r}="","",C{r}-{baris_target})')
        isi(ws, r, 10, f'=IF(OR(H{r}="",I{r}=""),"",SQRT(H{r}^2+I{r}^2)*{KERAMIK})')
        isi(ws, r, 11, f'=IF(OR(D{r}="",F{r}=""),"",ABS(DEGREES(ATAN2(E{r}-G{r},D{r}-F{r}))))')
    return ws


def sheet_sesi(wb):
    ws = wb.create_sheet("Data Sesi", 0)
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 30
    ws.cell(row=1, column=1, value="Data Sesi Pengujian").font = Font(bold=True, size=13,
                                                                     color=NAVY)
    items = ["Tanggal / jam mulai", "Ukuran 1 keramik (cm)", "Ukuran 1 mozaik (cm)",
             "Pojok acuan (0 ; 0)", "Baterai penuh saat mulai (Y/T)", "Status MPU (S)",
             "ROBOT_SPEED_MPS", "KP_HEADING", "Ukuran melintang C1/C2 (hasil uji coba ruang)",
             "Cuaca / angin / riak air", "Pencatat"]
    for i, k in enumerate(items, start=3):
        c = ws.cell(row=i, column=1, value=k)
        c.font = Font(bold=True, size=10)
        c.border = BOX
        v = ws.cell(row=i, column=2)
        v.fill = PatternFill("solid", fgColor=ISI)
        v.border = BOX
    r = ws.max_row + 2
    ws.cell(row=r, column=1, value="Cara pakai").font = Font(bold=True, size=11, color=NAVY)
    for i, t in enumerate((
            "1. Tiap skenario punya satu sheet. Isi hanya sel kuning.",
            "2. Skenario A: isi baris saat FIN (kalau sempat), lalu kolom & baris posisi akhir.",
            "3. Skenario B & C: isi posisi haluan dan buritan setelah robot diam.",
            "4. Jarak, galat, sudut, rata-rata, MAE, MAPE, dan simpangan baku terhitung sendiri.",
            "5. Satu baris = satu percobaan nyata. Jangan menyalin hasil percobaan lain."),
            start=r + 1):
        ws.cell(row=i, column=1, value=t).font = Font(size=10)
    return ws


def main():
    wb = Workbook()
    wb.remove(wb.active)
    sheet_sesi(wb)
    for kode, perintah, target in (("A1", "FW:50", 50), ("A2", "FW:100", 100),
                                   ("A3", "FW:200", 200)):
        sheet_a(wb, kode, perintah, target)
    for kode, perintah, target in (("B1", "CW:45", 45), ("B2", "CW:90", 90),
                                   ("B3", "CCW:45", 45), ("B4", "CCW:90", 90)):
        sheet_b(wb, kode, perintah, target)
    sheet_c(wb, "C1", "Kotak 1 x 2 m", 2, 4, 8)
    sheet_c(wb, "C2", "Zigzag mini", 2, 4, 13)
    wb.save(OUT)
    print(f"XLSX : {OUT}")


if __name__ == "__main__":
    main()
