"""
Ukur arah robot dari foto HP tampak atas, memakai tepi kolam sebagai garis 0 derajat.

    python ukur_foto.py foto.jpg                  arah robot terhadap tepi kolam
    python ukur_foto.py sebelum.jpg sesudah.jpg   besar sudut belok

Pada setiap foto klik 4 titik berurutan:
    1. titik di tepi kolam, ke arah BELAKANG robot saat start
    2. titik di tepi kolam, ke arah DEPAN robot saat start
    3. buritan (belakang) robot
    4. haluan (depan) robot
Klik kanan = batalkan titik terakhir. Tombol zoom/geser di toolbar boleh dipakai
agar klik lebih tepat. Setelah 4 titik, tekan Enter (atau tutup jendela).
Hasil beranotasi disimpan sebagai <nama>_ukur.png di samping foto.
"""
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt

LANGKAH = [
    "1/4  Klik TEPI KOLAM, ke arah BELAKANG robot saat start",
    "2/4  Klik TEPI KOLAM, ke arah DEPAN robot saat start",
    "3/4  Klik BURITAN (belakang) robot",
    "4/4  Klik HALUAN (depan) robot",
]


def sudut_terhadap_tepi(titik):
    """Sudut arah robot terhadap tepi kolam (derajat, -180..180, positif = ke kiri/CCW)."""
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = titik
    # sumbu-y gambar mengarah ke bawah; dibalik agar CCW bernilai positif
    ex, ey = x2 - x1, -(y2 - y1)
    rx, ry = x4 - x3, -(y4 - y3)
    return math.degrees(math.atan2(ex * ry - ey * rx, ex * rx + ey * ry))


def normal180(deg):
    return (deg + 180.0) % 360.0 - 180.0


def arah(deg):
    if abs(deg) < 0.05:
        return "lurus"
    return "kiri / CCW" if deg > 0 else "kanan / CW"


def gambar_anotasi(ax, titik):
    for art in list(ax.lines) + list(ax.texts):
        art.remove()
    for p in list(ax.patches):
        p.remove()
    if titik:
        xs, ys = zip(*titik)
        ax.plot(xs[:2], ys[:2], "o", color="#f59e0b", ms=8, mec="black")
        ax.plot(xs[2:], ys[2:], "o", color="#22d3ee", ms=8, mec="black")
    if len(titik) >= 2:
        ax.plot([titik[0][0], titik[1][0]], [titik[0][1], titik[1][1]], "-",
                color="#f59e0b", lw=2.5)
    if len(titik) == 4:
        ax.annotate("", xy=titik[3], xytext=titik[2],
                    arrowprops=dict(arrowstyle="-|>", color="#22d3ee", lw=2.5))


def ukur(path):
    """Tampilkan foto, kumpulkan 4 klik, kembalikan sudut robot terhadap tepi kolam."""
    path = Path(path)
    out = path.with_name(path.stem + "_ukur.png")
    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.imshow(plt.imread(str(path)))
    ax.set_axis_off()
    fig.canvas.manager.set_window_title(f"ukur_foto - {path.name}")
    titik = []

    def perbarui():
        gambar_anotasi(ax, titik)
        if len(titik) < 4:
            ax.set_title(f"{path.name}\n{LANGKAH[len(titik)]}   (klik kanan = batal)",
                         fontsize=11)
        else:
            deg = sudut_terhadap_tepi(titik)
            ax.set_title(f"{path.name}\nArah robot terhadap tepi kolam: {deg:+.1f}°  "
                         f"({arah(deg)})\nEnter = lanjut   |   klik kanan = ulangi titik terakhir",
                         fontsize=11)
        fig.canvas.draw_idle()

    def on_click(ev):
        toolbar = getattr(fig.canvas.manager, "toolbar", None)
        if ev.inaxes is not ax or (toolbar is not None and toolbar.mode):
            return
        if ev.button == 1 and len(titik) < 4:
            titik.append((ev.xdata, ev.ydata))
        elif ev.button == 3 and titik:
            titik.pop()
        perbarui()

    def on_key(ev):
        if ev.key == "enter" and len(titik) == 4:
            plt.close(fig)

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)
    perbarui()
    plt.show()

    if len(titik) < 4:
        sys.exit(f"{path.name}: jendela ditutup sebelum 4 titik diklik.")
    deg = sudut_terhadap_tepi(titik)
    ax.set_title(f"{path.name}\nArah robot terhadap tepi kolam: {deg:+.1f}°  ({arah(deg)})",
                 fontsize=12)
    fig.savefig(out, dpi=120, bbox_inches="tight")
    print(f"{path.name}: arah robot terhadap tepi = {deg:+.1f} derajat  ({arah(deg)})  -> {out.name}")
    return deg


def main(argv):
    if len(argv) not in (1, 2):
        print(__doc__)
        return 1
    for p in argv:
        if not Path(p).is_file():
            print(f"File tidak ditemukan: {p}")
            return 1
    hasil = [ukur(p) for p in argv]
    if len(hasil) == 2:
        belok = normal180(hasil[1] - hasil[0])
        print(f"\nSUDUT BELOK AKTUAL = {abs(belok):.1f} derajat  ke {arah(belok)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
