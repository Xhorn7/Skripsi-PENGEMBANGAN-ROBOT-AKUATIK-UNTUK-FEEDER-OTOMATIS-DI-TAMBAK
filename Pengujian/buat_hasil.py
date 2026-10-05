"""
Laporan hasil pengujian gerak robot (DOCX + PDF) dari data di Lembar_Data_Pengujian.xlsx.

    pip install -r requirements.txt
    python buat_hasil.py

Angka diambil langsung dari sheet A1–A3, B1–B4, dan C1 (nilai hasil rumus Excel),
jadi jalankan ulang setelah Excel diubah dan disimpan dari Excel.
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from docx.shared import Pt
from openpyxl import load_workbook

from build_skenario import CENTER, GAMBAR, HERE, INK, Doc, export_pdf

OUT = HERE / "Hasil_Pengujian_Gerak.docx"
XLSX = HERE / "Lembar_Data_Pengujian.xlsx"

SEBELUM = [0, 0, 54.2]          # uji awal 29 Sep (FW:50, FW:100) & 1 Okt (FW:200, 3x), 0,5 m/s


def baca_data():
    wb = load_workbook(XLSX, data_only=True)
    kol = lambda ws, c: [ws.cell(row=r, column=c).value for r in (3, 4, 5)]
    a = {k: kol(wb[k], 5) for k in ("A1", "A2", "A3")}                 # jarak aktual
    lat = {k: kol(wb[k], 8) for k in ("A1", "A2", "A3")}
    b = {k: dict(aktual=kol(wb[k], 7), mpu=kol(wb[k], 6), panjang=kol(wb[k], 10),
                 ket=kol(wb[k], 11)) for k in ("B1", "B2", "B3", "B4")}
    ws = wb["C1"]
    c = dict(posisi=kol(ws, 8), arah=kol(ws, 10), fin=kol(ws, 6), waktu=kol(ws, 7))
    return a, lat, b, c


def f(x, n=1):
    return f"{x:.{n}f}".replace(".", ",")


def mae(xs, target=0):
    return float(np.mean([abs(x - target) for x in xs]))


def fig_kalibrasi(a):
    perintah = [50, 100, 200]
    sesudah = [float(np.mean(a[k])) for k in ("A1", "A2", "A3")]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    x = np.arange(3)
    w = 0.26
    for dx, vals, lab, col in ((-w, perintah, "Target (perintah)", "#cbd5e1"),
                               (0, SEBELUM, "Sebelum kalibrasi", "#f87171"),
                               (w, sesudah, "Sesudah kalibrasi", "#2563eb")):
        ax.bar(x + dx, vals, w, label=lab, color=col)
        for i, v in enumerate(vals):
            ax.text(i + dx, v + 3, f"{v:.1f}".rstrip("0").rstrip(".").replace(".", ","),
                    ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels([f"FW:{p}" for p in perintah])
    ax.set_ylabel("Jarak tempuh (cm)")
    ax.set_ylim(0, 225)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.set_title("A · Jarak tempuh nyata sebelum dan sesudah kalibrasi", fontsize=11,
                 weight="bold", color=INK, loc="left")
    return _simpan(fig, "fig_hasil_lurus.png")


def fig_belok(b):
    kode = ["B1", "B2", "B3", "B4"]
    target = [45, 90, 45, 90]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    x = np.arange(4)
    w = 0.26
    akt = [b[k]["aktual"] for k in kode]
    mpu = [b[k]["mpu"] for k in kode]
    ax.bar(x - w, target, w, label="Target", color="#cbd5e1")
    ax.bar(x, [np.mean(v) for v in akt], w, yerr=[np.std(v, ddof=1) for v in akt], capsize=3,
           label="Aktual (foto, rata-rata ± s)", color="#2563eb")
    ax.bar(x + w, [np.mean(v) for v in mpu], w, yerr=[np.std(v, ddof=1) for v in mpu],
           capsize=3, label="MPU (log, rata-rata ± s)", color="#f59e0b")
    for i in x:
        for dx, v in ((0, np.mean(akt[i])), (w, np.mean(mpu[i]))):
            ax.text(i + dx, 3, f(v), ha="center", fontsize=7.5, color="white", weight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(["B1 · CW:45", "B2 · CW:90", "B3 · CCW:45", "B4 · CCW:90"])
    ax.set_ylabel("Sudut belok (°)")
    ax.set_ylim(0, 125)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=3)
    ax.set_title("B · Sudut belok aktual dan menurut MPU", fontsize=11, weight="bold",
                 color=INK, loc="left")
    return _simpan(fig, "fig_hasil_belok.png")


def _simpan(fig, nama):
    fig.tight_layout()
    GAMBAR.mkdir(exist_ok=True)
    path = GAMBAR / nama
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def build():
    a, lat, b, c = baca_data()
    D = Doc()
    d = D.d
    d.sections[0].header.paragraphs[0].runs[0].text = "Hasil Pengujian Gerak Robot Akuatik"
    t = d.add_paragraph()
    t.alignment = CENTER
    r = t.add_run("HASIL PENGUJIAN GERAK ROBOT")
    r.bold = True
    r.font.size = Pt(14)
    t = d.add_paragraph()
    t.alignment = CENTER
    r = t.add_run("Kolam uji 5 × 2 m  •  29 September – 5 Oktober 2026")
    r.italic = True
    r.font.size = Pt(11)

    perintah = {"A1": 50, "A2": 100, "A3": 200}
    mape = {k: mae(v, perintah[k]) / perintah[k] * 100 for k, v in a.items()}
    tgt_b = {"B1": 45, "B2": 90, "B3": 45, "B4": 90}
    mae_b = {k: mae(b[k]["aktual"], tgt_b[k]) for k in b}
    mae_mpu = {k: mae([m - s for m, s in zip(b[k]["mpu"], b[k]["aktual"])]) for k in b}
    mae_pos, mae_arah = mae(c["posisi"]), mae(c["arah"])
    fin = sum(c["fin"])
    ok = lambda cond: "Memenuhi" if cond else "Belum"

    D.h1("1. Ringkasan")
    D.p("Seluruh 24 percobaan (A1–A3, B1–B4, C1; masing-masing 3×) sudah dilaksanakan. "
        "Perbandingan dengan kriteria usulan pada dokumen rancangan:")
    D.table(["Skenario", "Hasil", "Kriteria", "Status"], [
        ["A1 · FW:50", f"rata-rata {f(np.mean(a['A1']))} cm, MAPE {f(mape['A1'])}%", "MAPE ≤ 10%",
         ok(mape["A1"] <= 10)],
        ["A2 · FW:100", f"rata-rata {f(np.mean(a['A2']))} cm, MAPE {f(mape['A2'])}%", "MAPE ≤ 10%",
         ok(mape["A2"] <= 10)],
        ["A3 · FW:200", f"rata-rata {f(np.mean(a['A3']))} cm, MAPE {f(mape['A3'])}%", "MAPE ≤ 10%",
         ok(mape["A3"] <= 10)],
        ["A · lateral", f"{f(max(abs(x) for v in lat.values() for x in v), 0)} cm di semua percobaan",
         "≤ 10% jarak", "Memenuhi"],
        *[[f"{k} · {cmd}", f"rata-rata {f(np.mean(b[k]['aktual']))}°, MAE {f(mae_b[k])}°", "MAE ≤ 5°",
           ok(mae_b[k] <= 5)]
          for k, cmd in (("B1", "CW:45"), ("B2", "CW:90"), ("B3", "CCW:45"), ("B4", "CCW:90"))],
        ["B · MPU vs aktual", "MAE " + " / ".join(f(mae_mpu[k]) for k in b) + "°", "MAE ≤ 5°",
         "Belum"],
        ["C1 · posisi", f"MAE {f(mae_pos)} cm", "≤ 30 cm", ok(mae_pos <= 30)],
        ["C1 · arah", f"MAE {f(mae_arah)}°", "≤ 10°", ok(mae_arah <= 10)],
        ["C1 · eksekusi", f"FIN {fin}/24", "100%", ok(fin == 24)],
    ], [3.4, 6.6, 3.0, 3.4], size=9.5, center=(2, 3))

    D.h1("2. Gerak lurus (A) dan kalibrasi kecepatan")
    D.p("Dengan asumsi awal 0,5 m/s, FW:50 dan FW:100 hampir tidak bergerak dan FW:200 hanya "
        "menempuh rata-rata 54 cm. Kalibrasi satu titik (0,135 m/s) membuat FW:100 kebablasan "
        "menjadi 150 cm. Dari dua titik data tersebut (motor 4,0 s → 54 cm; 7,4 s → 150 cm), "
        "durasi maju dimodelkan sebagai awalan 2,1 s + jarak ÷ 0,28 m/s.")
    D.figure(fig_kalibrasi(a), "Gambar 1. Jarak tempuh nyata (dibaca dari grid keramik)", 15.0)
    D.table(["Perintah", "Hasil 3× (cm)", "Rata-rata", "Simp. baku", "MAPE", "Lateral"], [
        [f"FW:{perintah[k]}", " / ".join(f(x, 1).replace(",0", "") for x in a[k]),
         f"{f(np.mean(a[k]))} cm", f"{f(np.std(a[k], ddof=1))} cm", f"{f(mape[k])}%", "0 cm"]
        for k in ("A1", "A2", "A3")
    ], [2.4, 4.0, 2.6, 2.6, 2.2, 2.2], size=10, center=(0, 1, 2, 3, 4, 5))
    D.p("FW:100 dan FW:200 memenuhi kriteria. FW:50 masih kurang jauh karena fase awalan "
        "mendominasi pada jarak pendek. Robot berjalan lurus (penyimpangan lateral 0 cm), "
        "menunjukkan heading-hold MPU bekerja.")

    D.h1("3. Belok (B)")
    D.p("Sebelum data B diambil, dua masalah firmware ditemukan dan diperbaiki: (1) kabel ESC "
        "tersilang sehingga CW berbelok ke kiri — isi fungsi spinCW dan spinCCW ditukar; (2) robot "
        "masih berputar ± 15° setelah motor mati sehingga CW:45 berhenti di 55–59° — motor kini "
        "dimatikan 15° sebelum target.")
    D.figure(fig_belok(b), "Gambar 2. Sudut belok aktual (kotak mozaik pada foto) dan menurut "
             "MPU (log GUI)", 15.0)
    D.table(["Skenario", "Aktual 3× (°)", "Rata-rata", "MAE", "MPU 3× (°)", "MAE MPU vs aktual"], [
        [f"{k} · {cmd}", " / ".join(f(x) for x in b[k]["aktual"]), f"{f(np.mean(b[k]['aktual']))}°",
         f"{f(mae_b[k])}°", " / ".join(f(x) for x in b[k]["mpu"]), f"{f(mae_mpu[k])}°"]
        for k, cmd in (("B1", "CW:45"), ("B2", "CW:90"), ("B3", "CCW:45"), ("B4", "CCW:90"))
    ], [2.6, 3.6, 2.0, 1.6, 3.6, 3.0], size=9.5, center=(0, 2, 3, 5))
    D.bullet(" B1 dan B4 memenuhi kriteria. B3 (CCW:45) konsisten kelebihan ± 16° dengan simpangan "
             "baku kecil, sehingga kompensasi 15° tampaknya kurang untuk putaran ke kiri (motor "
             "berbeda). B2 (CW:90) tersebar lebar (62–99°).", "Sudut aktual —")
    D.bullet(" pada 10 dari 12 percobaan B, gyro belum selesai terkalibrasi saat uji sehingga yaw "
             "merayap. Karena itu selisih MPU dengan sudut aktual besar dan belum dapat dipakai "
             "untuk menilai ketelitian sensor.", "Sensor MPU —")

    D.h1("4. Kombinasi kotak 1 × 2 m (C1)")
    D.table(["Percobaan", "FIN", "Waktu total", "Galat posisi", "Galat arah", "Catatan"], [
        ["C1.1", f"{c['fin'][0]}/8", f"{c['waktu'][0]} s", f"{f(c['posisi'][0])} cm",
         f"{f(c['arah'][0])}°", "belok ke-2/3/4 perlu kirim ulang"],
        ["C1.2", f"{c['fin'][1]}/8", f"{c['waktu'][1]} s", f"{f(c['posisi'][1])} cm",
         f"{f(c['arah'][1])}°", "tanpa kirim ulang"],
        ["C1.3", f"{c['fin'][2]}/8", f"{c['waktu'][2]} s", f"{f(c['posisi'][2])} cm",
         f"{f(c['arah'][2])}°", "tanpa kirim ulang"],
        ["MAE", "", "", f"{f(mae_pos)} cm", f"{f(mae_arah)}°", ""],
    ], [2.2, 1.6, 2.4, 2.6, 2.4, 5.2], size=9.5, center=(0, 1, 2, 3, 4))
    D.p("Robot kembali ke titik start dengan galat posisi rata-rata di bawah 1 kotak keramik dan "
        "galat arah rata-rata di bawah 5°. Waktu total termasuk jeda karena kedelapan perintah "
        "dikirim satu per satu dari halaman MANUAL; waktu gerak murni (ON → FIN) 47–54 s. Di sela "
        "perintah robot sempat hanyut berputar oleh riak air tanpa dikoreksi, yang kemungkinan "
        "menjadi penyebab galat arah 9,3° pada C1.1.")

    D.h1("5. Keterbatasan")
    D.bullet(" baris keramik dibaca sampai 0,5 keramik (12,5 cm), sehingga hasil A bertingkat "
             "12,5–25 cm.", "Resolusi A —")
    D.bullet(" pada 5 dari 12 foto B, panjang pelampung terbaca menyimpang lebih dari 10 cm dari "
             "60 cm (paralaks foto miring), dan sudut dihitung dengan anggapan robot start sejajar "
             "garis keramik. Satu kotak mozaik ≈ 3–4°.", "Foto B —")
    D.bullet(" gyro belum terkalibrasi pada sebagian besar percobaan B; pada sesi kedua C1 (C1.2 "
             "dan C1.3) yaw juga merayap ± 1,5°/s sehingga yaw MPU tidak dipakai.", "MPU —")
    D.bullet(" posisi HP berbeda antar foto, sehingga posisi dicocokkan lewat keramik tepi kolam "
             "dengan ketelitian ± 1 mozaik (± 4 cm). Foto akhir C1.2 sekaligus menjadi foto awal "
             "C1.3 (robot tidak dipindah).", "Foto C1 —")
    D.bullet(" skenario zigzag mini (C2) tidak dilaksanakan; kombinasi diwakili C1.",
             "Cakupan —")

    D.h1("6. Tindak lanjut")
    D.steps([
        "Olah data ke Bab 4 (tabel dan grafik di dokumen ini dapat langsung dipakai).",
        "Bila waktu memungkinkan: pisahkan kompensasi putar CW dan CCW, lalu ulangi B3 dan B2 "
        "dengan gyro dikalibrasi saat robot diam.",
        "Kirim perintah C1 berikutnya segera setelah FIN (atau tambahkan antrian perintah di "
        "halaman MANUAL) untuk memperkecil jeda dan efek hanyut di sela perintah.",
    ])
    return d


def main():
    d = build()
    try:
        d.save(OUT)
    except PermissionError:
        sys.exit(f"Tidak bisa menulis {OUT.name} — tutup dulu file itu di Word.")
    print(f"DOCX : {OUT}")
    pdf = export_pdf(OUT)
    print(f"PDF  : {pdf}" if pdf else "PDF  : dilewati (Word/LibreOffice tidak ditemukan).")


if __name__ == "__main__":
    main()
