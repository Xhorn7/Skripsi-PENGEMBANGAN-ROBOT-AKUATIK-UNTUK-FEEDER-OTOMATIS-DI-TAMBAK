"""
Ukur galat posisi dan arah skenario C1 (kotak 1 x 2 m) dari foto awal & akhir.

    pip install -r requirements.txt
    python ukur_foto_c1.py

Foto diambil dari belakang robot, sebelum perintah pertama dan setelah robot
berhenti. Posisi HP di kedua foto tidak persis sama, jadi:

- ARAH  : sudut garis yang menghubungkan ujung belakang kedua pelampung,
          diukur terhadap baris mozaik lantai di foto yang sama. Galat arah =
          selisih sudut foto akhir dan foto awal.
- POSISI: foto akhir dipetakan ke foto awal lewat pola keramik di tepi kolam
          (permukaannya hampir sejajar dengan permukaan air), dengan pencocokan
          titik SIFT + homografi RANSAC. Pergeseran ujung belakang pelampung
          kiri diukur dalam piksel, lalu diubah ke cm memakai lebar robot
          (42 cm) di foto awal, dan ke kotak mozaik (4,1 cm).

Hasilnya ditulis tangan ke sheet C1 di Lembar_Data_Pengujian.xlsx. Ketelitian
sekitar +/- 1 mozaik, karena posisi HP berbeda antar foto.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.feature import SIFT, match_descriptors
from skimage.measure import ransac
from skimage.transform import ProjectiveTransform

FOTO = Path(__file__).resolve().parent / "foto_c1"
LEBAR_ROBOT_CM = 42
MOZAIK_CM = 4.1
PANJANG_PELAMPUNG_MOZAIK = 60 / MOZAIK_CM

# Per foto (piksel, ukuran 1125 x 2000):
#   tepi  = dua titik pada tepi dalam bibir kolam (batas lantai tepi & dinding)
#   kiri / kanan = rentang x untuk mencari ujung belakang pelampung kiri / kanan
#   y     = rentang y tempat ujung belakang pelampung berada
FOTO_INFO = {
    "C1-1_awal": dict(tepi=((175, 250), (0, 575)), kiri=(200, 420), kanan=(780, 1010), y=(1000, 1220)),
    "C1-1_akhir": dict(tepi=((250, 450), (0, 790)), kiri=(150, 400), kanan=(760, 980), y=(1200, 1460)),
    "C1-2_awal": dict(tepi=((295, 265), (10, 640)), kiri=(220, 420), kanan=(780, 980), y=(1100, 1320)),
    "C1-2_akhir_C1-3_awal": dict(tepi=((350, 250), (100, 550)), kiri=(210, 420), kanan=(780, 980),
                                 y=(1050, 1290)),
    "C1-3_akhir": dict(tepi=((250, 305), (50, 700)), kiri=(240, 420), kanan=(680, 880), y=(1100, 1300)),
}
PERCOBAAN = [("C1.1", "C1-1_awal", "C1-1_akhir"),
             ("C1.2", "C1-2_awal", "C1-2_akhir_C1-3_awal"),
             ("C1.3", "C1-2_akhir_C1-3_awal", "C1-3_akhir")]


def baca(nama):
    return np.asarray(Image.open(FOTO / f"{nama}.webp").convert("RGB"), dtype=int)


def putih(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (r > 170) & (g > 150) & (b > 140) & (r - b < 90)


def ujung_belakang(nama):
    """Titik paling belakang (bawah di foto) kedua pelampung: [(x, y) kiri, (x, y) kanan]."""
    info = FOTO_INFO[nama]
    w = putih(baca(nama))
    y0, y1 = info["y"]
    hasil = []
    for x0, x1 in (info["kiri"], info["kanan"]):
        sub = w[y0:y1, x0:x1]
        yb = max(y for y in range(sub.shape[0]) if sub[y].sum() >= 6)
        _, xx = np.nonzero(sub[yb - 25:yb + 1])
        hasil.append((x0 + xx.mean(), y0 + yb))
    return hasil


def sudut_ujung(nama):
    (x1, y1), (x2, y2) = ujung_belakang(nama)
    return math.degrees(math.atan2(y2 - y1, x2 - x1))


def px_per_cm(nama):
    """Lebar luar robot (42 cm) di baris sedikit di depan ujung pelampung kiri."""
    (_, y), _ = ujung_belakang(nama)
    xs = np.where(putih(baca(nama))[int(y) - 66])[0]
    return (xs.max() - xs.min()) / LEBAR_ROBOT_CM


def fitur_tepi(nama, pita):
    (x1, y1), (x2, y2) = FOTO_INFO[nama]["tepi"]
    g = baca(nama).mean(axis=2) / 255
    s = SIFT()
    s.detect_and_extract(g)
    keep = [i for i, (r, c) in enumerate(s.keypoints)
            if r < 1000 and (x1 + (x2 - x1) * (r - y1) / (y2 - y1)) - pita < c
            < (x1 + (x2 - x1) * (r - y1) / (y2 - y1)) - 8]
    return s.keypoints[keep][:, ::-1], s.descriptors[keep]


def geser_px(awal, akhir):
    """Pergeseran ujung pelampung kiri (akhir dipetakan ke foto awal), rata-rata 3 lebar pita."""
    tip_awal = np.array(ujung_belakang(awal)[0])
    tip_akhir = np.array([ujung_belakang(akhir)[0]], dtype=float)
    hasil = []
    for pita in (120, 170, 230):
        pa, da = fitur_tepi(awal, pita)
        pb, db = fitur_tepi(akhir, pita)
        m = match_descriptors(db, da, cross_check=True, max_ratio=0.8)
        model, inl = ransac((pb[m[:, 0]], pa[m[:, 1]]), ProjectiveTransform, min_samples=4,
                            residual_threshold=3, max_trials=5000, rng=0)
        hasil.append(model(tip_akhir)[0] - tip_awal)
        print(f"    pita {pita:3d} px: {inl.sum():3d} titik cocok")
    return np.mean(hasil, axis=0)


def main():
    print(f"{'':6}{'samping':>9}{'depan':>8}{'posisi':>9}{'arah':>8}   (mozaik, mozaik, cm, °)")
    for kode, awal, akhir in PERCOBAAN:
        print(kode)
        dx, dy = geser_px(awal, akhir)
        skala = px_per_cm(awal)
        samping = round(dx / skala / MOZAIK_CM, 1)        # + = ke kanan
        depan = round(-dy / skala / MOZAIK_CM, 1)          # + = ke depan (menjauh dari HP)
        galat_arah = abs(sudut_ujung(akhir) - sudut_ujung(awal))
        posisi = math.hypot(samping, depan) * MOZAIK_CM
        setara = PANJANG_PELAMPUNG_MOZAIK * math.tan(math.radians(galat_arah))
        print(f"  {kode:4}{samping:9.1f}{depan:8.1f}{posisi:9.1f}{galat_arah:8.1f}"
              f"   -> arah di Excel: {setara:.2f} per {PANJANG_PELAMPUNG_MOZAIK:.1f} mozaik")


if __name__ == "__main__":
    main()
