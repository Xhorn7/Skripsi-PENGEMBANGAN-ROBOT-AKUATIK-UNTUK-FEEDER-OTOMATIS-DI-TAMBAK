"""
C1 (kotak 1 x 2 m) diukur di tiap titik belok dengan meteran dan busur, lalu
digambar seperti Fig. 4 dan Tabel I pada paper rujukan [1]: rute rencana vs
posisi aktual robot di tiap waypoint, dan MAE posisi per waypoint.

    pip install -r requirements.txt
    python buat_grafik_c1.py --lembar     # sekali: buat Lembar_Data_C1_Titik_Belok.xlsx
    python buat_grafik_c1.py              # setelah lembar diisi & disimpan: buat grafik

Yang diukur di setiap titik: titik tengah robot (ditandai di dek).
    X = meteran dari dinding KIRI kolam, tegak lurus dinding (cm)
    Y = meteran dari dinding BELAKANG kolam (ujung dekat tangga) (cm)
    Arah = busur, simpangan haluan dari arah rencana (°, + bila lebih ke kanan)

Titik: S (start), T1–T4 (setelah tiap FW, sebelum CW:90 berikutnya) dan Akhir
(setelah CW:90 terakhir). Rute rencana ditarik dari posisi S yang terukur,
jadi posisi start tidak harus persis sama antar percobaan.

[1] J. Putra dan D. E. Saputra, "Autonomous Drone Indoor Navigation Based on
    Virtual 3D Map Reference," IEEE, 2022.
"""
import argparse
import sys
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
LEBAR_KOLAM, PANJANG_KOLAM = 200, 500    # cm
KERAMIK = 25                             # cm

# (kode, kapan diukur, dX, dY dari start dalam cm) — urutan perintah C1:
# FW:200 → CW:90 → FW:100 → CW:90 → FW:200 → CW:90 → FW:100 → CW:90
TITIK = [
    ("S", "Start, sebelum FW:200 pertama — menghadap depan", 0, 0),
    ("T1", "Setelah FW:200 ke-1, sebelum CW:90 — menghadap depan", 0, 200),
    ("T2", "Setelah FW:100 ke-1, sebelum CW:90 — menghadap kanan", 100, 200),
    ("T3", "Setelah FW:200 ke-2, sebelum CW:90 — menghadap belakang", 100, 0),
    ("T4", "Setelah FW:100 ke-2, sebelum CW:90 — menghadap kiri", 0, 0),
    ("Akhir", "Setelah CW:90 terakhir — menghadap depan", 0, 0),
]
BARIS_PER_PERC = len(TITIK)
RENCANA = "#64748b"                      # rute rencana: abu tua, garis putus-putus
PERC = "#94a3b8"                         # garis tiap percobaan (latar)


def baris(p, i):
    """Baris Excel untuk percobaan p (1..N) dan titik ke-i."""
    return 3 + (p - 1) * BARIS_PER_PERC + i


# ---------------------------------------------------------------- lembar isian
def buat_lembar():
    if XLSX.exists():
        sys.exit(f"{XLSX.name} sudah ada — tidak ditimpa. Pindahkan/ganti nama dulu "
                 "bila memang ingin lembar kosong.")
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    headers = ["Perc.", "Titik", "Kapan diukur / arah rencana",
               "X aktual (cm) — meteran dari dinding KIRI",
               "Y aktual (cm) — meteran dari dinding BELAKANG",
               "Simpangan arah (°) — busur, + bila ke kanan",
               "X rencana (cm)", "Y rencana (cm)", "Galat posisi (cm)", "Keterangan"]
    widths = [6, 7, 44, 15, 15, 15, 10, 10, 11, 28]
    n_isi = (4, 5, 6, 10)

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws.cell(row=1, column=1, value="C1 — Kotak 1 x 2 m, diukur di tiap titik belok "
            "(meteran + busur)").font = Font(bold=True, size=12, color=NAVY)
    ws.freeze_panes = "D3"
    for c, (h, w) in enumerate(zip(headers, widths), start=1):
        cell = ws.cell(row=2, column=c, value=h)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.font = HEAD
        cell.alignment = CENTER
        cell.border = BOX
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.row_dimensions[2].height = 46

    for p in range(1, N + 1):
        s = baris(p, 0)
        ws.merge_cells(start_row=s, start_column=1, end_row=s + BARIS_PER_PERC - 1, end_column=1)
        ws.cell(row=s, column=1, value=p).font = Font(bold=True)
        for i, (kode, kapan, dx, dy) in enumerate(TITIK):
            r = baris(p, i)
            ws.cell(row=r, column=2, value=kode)
            ws.cell(row=r, column=3, value=kapan)
            ws.cell(row=r, column=7, value=f'=IF($D${s}="","",$D${s}+{dx})')
            ws.cell(row=r, column=8, value=f'=IF($E${s}="","",$E${s}+{dy})')
            ws.cell(row=r, column=9, value="acuan" if i == 0 else
                    f'=IF(OR(D{r}="",E{r}="",G{r}=""),"",'
                    f'ROUND(SQRT((D{r}-G{r})^2+(E{r}-H{r})^2),1))')
            for c in range(1, len(headers) + 1):
                cell = ws.cell(row=r, column=c)
                cell.border = BOX
                cell.alignment = Alignment(horizontal="left", vertical="center",
                                           wrap_text=True) if c == 3 else CENTER
                if c >= 4:
                    cell.fill = PatternFill("solid", fgColor=ISI if c in n_isi else RUMUS)

    # Ringkasan per titik, setara Tabel I pada paper
    r0 = baris(N, BARIS_PER_PERC) + 1
    ws.cell(row=r0, column=2, value="Ringkasan per titik (rata-rata percobaan yang "
            "sudah diisi)").font = Font(bold=True, size=11, color=NAVY)
    for c, h in enumerate(["Titik", "", "MAE posisi (cm)", "MAE arah (°)"], start=2):
        if h:
            cell = ws.cell(row=r0 + 1, column=c, value=h)
            cell.fill = PatternFill("solid", fgColor=NAVY)
            cell.font = HEAD
            cell.alignment = CENTER
            cell.border = BOX
    semua_galat = []
    for i, (kode, *_rest) in enumerate(TITIK[1:], start=1):
        r = r0 + 1 + i
        rows = [baris(p, i) for p in range(1, N + 1)]
        semua_galat += [f"I{x}" for x in rows]
        ws.cell(row=r, column=2, value=kode).border = BOX
        ws.cell(row=r, column=4, value=f'=IFERROR(AVERAGE({",".join(f"I{x}" for x in rows)}),"")')
        abs_f = ",".join(f'IF(ISNUMBER(F{x}),ABS(F{x}),0)' for x in rows)
        cnt_f = ",".join(f"F{x}" for x in rows)
        ws.cell(row=r, column=5, value=f'=IF(COUNT({cnt_f})=0,"",SUM({abs_f})/COUNT({cnt_f}))')
        for c in (2, 4, 5):
            ws.cell(row=r, column=c).alignment = CENTER
            ws.cell(row=r, column=c).border = BOX
        for c in (4, 5):
            ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=RUMUS)
            ws.cell(row=r, column=c).number_format = "0.0"
    r = r0 + 2 + len(TITIK) - 1
    ws.cell(row=r, column=2, value="Semua").font = Font(bold=True)
    ws.cell(row=r, column=4, value=f'=IFERROR(AVERAGE({",".join(semua_galat)}),"")').font = Font(bold=True)
    for c in (2, 4):
        ws.cell(row=r, column=c).alignment = CENTER
        ws.cell(row=r, column=c).border = BOX
    ws.cell(row=r, column=4).fill = PatternFill("solid", fgColor=RUMUS)
    ws.cell(row=r, column=4).number_format = "0.0"

    catatan = (
        "Kuning = diisi manual. Abu-abu = otomatis, jangan diketik.",
        "1. Tandai titik tengah robot di dek (selotip/stiker). Titik inilah yang diukur di semua baris.",
        "2. X: meteran dari dinding KIRI ke tanda, tegak lurus dinding. Y: meteran dari dinding "
        "BELAKANG (ujung dekat tangga).",
        "3. Arah: busur, simpangan haluan dari arah rencana pada kolom C (0 bila tepat; + bila "
        "lebih ke kanan / searah jarum jam).",
        "4. Kirim satu perintah, tunggu FIN dan robot diam, ukur, baru kirim perintah berikutnya. "
        "Robot tidak dipegang/didorong.",
        "5. Ukur secepatnya (dua orang: satu X, satu Y) karena robot bisa hanyut oleh riak air.",
        "6. Rute rencana dihitung dari posisi S yang terukur. Setelah disimpan, jalankan "
        "python buat_grafik_c1.py.",
    )
    for k, t in enumerate(catatan, start=r + 2):
        ws.cell(row=k, column=1, value=t).font = Font(italic=k == r + 2, size=9 if k == r + 2 else 10)
    wb.save(XLSX)
    print(f"XLSX : {XLSX}")


# ---------------------------------------------------------------- baca & hitung
def angka(v):
    if v is None or v == "":
        return None
    if isinstance(v, str):
        v = v.strip().replace(",", ".")
        try:
            return float(v)
        except ValueError:
            return None
    return float(v)


def baca(path):
    """Baca isian kuning saja (tidak bergantung pada nilai rumus tersimpan)."""
    ws = load_workbook(path)[SHEET]
    data = []
    for p in range(1, N + 1):
        pts = [(angka(ws.cell(row=baris(p, i), column=4).value),
                angka(ws.cell(row=baris(p, i), column=5).value),
                angka(ws.cell(row=baris(p, i), column=6).value)) for i in range(len(TITIK))]
        x0, y0, _ = pts[0]
        if x0 is None or y0 is None:
            continue
        rencana = [(x0 + dx, y0 + dy) for _k, _w, dx, dy in TITIK]
        galat = [None if x is None or y is None else
                 ((x - rx) ** 2 + (y - ry) ** 2) ** 0.5
                 for (x, y, _a), (rx, ry) in zip(pts, rencana)]
        data.append(dict(perc=p, aktual=pts, rencana=rencana, galat=galat))
    return data


def rata(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def f(x, n=1):
    return "—" if x is None else f"{x:.{n}f}".replace(".", ",")


# ---------------------------------------------------------------- grafik
def fig_rute(data, out):
    """Satu panel per percobaan: rute rencana vs posisi aktual (seperti Fig. 4 [1])."""
    n = len(data)
    ys = [y for d in data for y in [ry for _rx, ry in d["rencana"]] +
          [y for _x, y, _a in d["aktual"] if y is not None]]
    y_top = min(PANJANG_KOLAM, (max(ys) // KERAMIK + 3) * KERAMIK)
    panel_w = 2.1                                           # inci, skala sama di x dan y
    panel_h = panel_w * (y_top + 8) / (LEBAR_KOLAM + 16)
    fig, axes = plt.subplots(1, n, figsize=(n * (panel_w + 0.45) + 0.5, panel_h + 1.6),
                             sharey=True, squeeze=False)
    for ax, d in zip(axes[0], data):
        ax.set_xlim(-8, LEBAR_KOLAM + 8)
        ax.set_ylim(-8, y_top)
        ax.set_aspect("equal")
        ax.set_xticks(range(0, LEBAR_KOLAM + 1, 50))
        ax.set_xticks(range(0, LEBAR_KOLAM + 1, KERAMIK), minor=True)
        ax.set_yticks(range(0, int(y_top) + 1, 50))
        ax.set_yticks(range(0, int(y_top) + 1, KERAMIK), minor=True)
        ax.grid(which="both", color="#e2e8f0", lw=0.6)
        ax.set_axisbelow(True)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(colors=INK, labelsize=8, length=0)
        # dinding kolam: kiri, kanan, belakang
        ax.plot([0, 0, LEBAR_KOLAM, LEBAR_KOLAM], [y_top, 0, 0, y_top], color=INK, lw=2.2,
                solid_capstyle="butt")

        rx, ry = zip(*d["rencana"][:-1])          # Akhir = T4 secara posisi
        ax.plot(rx, ry, ls=(0, (5, 3)), color=RENCANA, lw=1.6, marker="o", ms=6,
                mfc="white", mec=RENCANA, mew=1.4, label="Rute rencana", zorder=2)
        ok = [(x, y) for x, y, _a in d["aktual"] if x is not None and y is not None]
        if ok:
            ax.plot(*zip(*ok), color=ROBOT, lw=2, marker="o", ms=5, mfc=ROBOT,
                    mec="white", mew=1, label="Posisi aktual", zorder=3)
        xa, ya, _a = d["aktual"][-1]
        if xa is not None and ya is not None:
            ax.annotate("akhir", (xa, ya), xytext=(5, -9), textcoords="offset points",
                        fontsize=7, color=INK, style="italic")
        # label titik di posisi rencana, digeser ke luar kotak
        geser = {"S": (-9, -2), "T1": (-9, 2), "T2": (9, 2), "T3": (9, -2)}
        for (kode, *_r), (x, y) in zip(TITIK, d["rencana"]):
            if kode in geser:
                dx, dy = geser[kode]
                ax.annotate("S/T4" if kode == "S" else kode, (x, y), xytext=(dx, dy),
                            textcoords="offset points", fontsize=7.5, color=INK,
                            ha="right" if dx < 0 else "left", va="center")
        mae = rata(d["galat"][1:])
        ax.set_title(f"Percobaan {d['perc']}\nMAE posisi {f(mae)} cm", fontsize=9,
                     color=INK, loc="left")
        ax.set_xlabel("X dari dinding kiri (cm)", fontsize=8, color=INK)
    axes[0][0].set_ylabel("Y dari dinding belakang (cm)", fontsize=8, color=INK)
    h, lab = axes[0][0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper right", ncol=2, frameon=False, fontsize=8.5)
    fig.suptitle("C1 · Rute rencana vs posisi aktual di tiap titik belok", x=0.02, ha="left",
                 fontsize=11, weight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    return out


def fig_galat(data, out):
    """Galat posisi per titik: tiap percobaan (abu) dan rata-ratanya (biru)."""
    kode = [k for k, *_r in TITIK[1:]]
    x = range(len(kode))
    fig, ax = plt.subplots(figsize=(7, 3.4))
    for d in data:
        ys = d["galat"][1:]
        pts = [(i, y) for i, y in zip(x, ys) if y is not None]
        if pts:
            ax.plot(*zip(*pts), color=PERC, lw=1, marker="o", ms=4,
                    label="Tiap percobaan" if d is data[0] else None)
    mae = [rata([d["galat"][i] for d in data]) for i in range(1, len(TITIK))]
    pts = [(i, m) for i, m in zip(x, mae) if m is not None]
    if pts:
        ax.plot(*zip(*pts), color=ROBOT, lw=2, marker="o", ms=7, mec="white", mew=1.2,
                label="MAE (rata-rata)")
        for i, m in pts:
            ax.annotate(f(m), (i, m), xytext=(0, 9), textcoords="offset points",
                        ha="center", fontsize=8.5, color=INK,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    ax.set_xticks(list(x))
    ax.set_xticklabels(kode)
    ax.set_xlabel("Titik", fontsize=9, color=INK)
    ax.set_ylabel("Galat posisi (cm)", fontsize=9, color=INK)
    ax.set_ylim(0, max([m for _i, m in pts] + [y for d in data for y in d["galat"][1:]
                                               if y is not None] + [10]) * 1.25)
    ax.grid(axis="y", color="#e2e8f0", lw=0.6)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=INK, labelsize=8.5)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("C1 · Galat posisi di tiap titik belok", fontsize=11, weight="bold",
                 color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def cetak_tabel(data):
    """Setara Tabel I [1]: galat posisi tiap percobaan dan MAE per titik."""
    kepala = ["Titik"] + [f"Perc. {d['perc']} (cm)" for d in data] + ["MAE (cm)", "MAE arah (°)"]
    print("  ".join(f"{h:>13}" for h in kepala))
    for i, (kode, *_r) in enumerate(TITIK[1:], start=1):
        g = [d["galat"][i] for d in data]
        arah = [abs(d["aktual"][i][2]) if d["aktual"][i][2] is not None else None for d in data]
        print("  ".join(f"{v:>13}" for v in [kode] + [f(x) for x in g] + [f(rata(g)), f(rata(arah))]))
    semua = [d["galat"][i] for d in data for i in range(1, len(TITIK))]
    print(f"{'Semua':>13}  " + "  ".join(" " * 13 for _ in data) + f"{f(rata(semua)):>13}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--lembar", action="store_true", help="buat lembar isian kosong")
    ap.add_argument("--xlsx", type=Path, default=XLSX, help="lembar data yang dibaca")
    ap.add_argument("--out-dir", type=Path, default=GAMBAR, help="folder keluaran gambar")
    a = ap.parse_args()
    if a.lembar:
        return buat_lembar()
    if not a.xlsx.exists():
        sys.exit(f"{a.xlsx.name} belum ada. Buat dulu: python buat_grafik_c1.py --lembar")
    data = baca(a.xlsx)
    if not data:
        sys.exit("Belum ada percobaan dengan posisi S (start) terisi — grafik tidak dibuat.")
    a.out_dir.mkdir(exist_ok=True)
    print(f"PNG  : {fig_rute(data, a.out_dir / 'fig_c1_rute_aktual.png')}")
    print(f"PNG  : {fig_galat(data, a.out_dir / 'fig_c1_galat_titik.png')}")
    cetak_tabel(data)


if __name__ == "__main__":
    main()
