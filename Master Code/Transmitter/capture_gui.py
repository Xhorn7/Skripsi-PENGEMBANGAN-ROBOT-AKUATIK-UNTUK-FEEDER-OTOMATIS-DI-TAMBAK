"""
capture_gui.py — Jalankan GUI dalam kondisi 'hidup' lalu SCREENSHOT tiap halaman.

Dipakai untuk dokumentasi. GUI dijalankan dalam mode JENDELA berukuran 800x480
— persis resolusi layar sentuh 7 inci yang dipakai Pengendali Utama — supaya
tangkapan layar mewakili tampilan di perangkat sebenarnya.

Menyetel kondisi contoh (misi 10x4 berjalan, log MPU & auto-simpan TXT menyala),
lalu menyimpan satu PNG per halaman.

Jalankan:  python capture_gui.py
Butuh:     customtkinter, pillow  (opsional pyrf24 utk radio nyata)
"""

import time

from PIL import ImageGrab

from feeder_gui import FeederGUI

# halaman utama -> berkas keluaran
SHOTS = {
    "BERANDA":   "gui_beranda.png",     # peluncur: hanya MISI & SETTING
    "MISI":      "gui_misi.png",
    "DASHBOARD": "gui_screenshot.png",  # gambar utama dokumentasi
}

# sub-halaman SETTING -> berkas keluaran
SETTING_SHOTS = {
    "SISTEM": "gui_sistem.png",
    "MANUAL": "gui_manual.png",
    "LOG":    "gui_log.png",
}

KEYPAD_SHOT = "gui_keypad.png"


def pump(app, seconds):
    """Biarkan GUI menggambar & animasi berjalan selama beberapa detik."""
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.03)


def grab(app, path, tries=3):
    """
    Simpan tangkapan jendela. ImageGrab menyalin ISI LAYAR, jadi bila ada
    jendela lain menimpa, hasilnya ikut hitam. Karena itu jendela diangkat
    ulang tiap percobaan dan hasil yang terlalu gelap diulang.
    """
    for percobaan in range(1, tries + 1):
        app.deiconify()
        app.attributes("-topmost", True)
        app.lift()
        app.focus_force()
        app.update_idletasks()
        app.update()
        time.sleep(0.45)
        x, y = app.winfo_rootx(), app.winfo_rooty()
        w, h = app.winfo_width(), app.winfo_height()
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        # bilah atas selalu berisi tombol STOP merah — kalau barisnya hitam
        # total berarti jendela tertimpa saat pengambilan.
        baris = img.convert("L").crop((0, 0, w, max(2, h // 12)))
        if max(baris.getdata()) > 60 or percobaan == tries:
            break
        print(f"   (ulang {percobaan}: jendela tertimpa saat mengambil {path})")
    img.save(path)
    print(f"OK -> {path}  ({img.width}x{img.height})")


def main():
    # jendela 800x480 = acuan layar sentuh 7 inci
    app = FeederGUI(fullscreen=False)
    app.attributes("-topmost", True)
    app.update()

    # --- setel kondisi contoh ---
    # Log MPU & auto-simpan TXT kini menyala sendiri sejak aplikasi start,
    # jadi tidak perlu disetel di sini.
    app._refresh_plan()
    pump(app, 0.6)

    # jalankan misi supaya status, gauge & progres terisi — sekaligus
    # memperlihatkan bahwa DASHBOARD terbuka sendiri sesudah KIRIM MISI
    app._on_send_mission()
    pump(app, 2.5)

    for page, path in SHOTS.items():
        app.show_page(page)
        pump(app, 0.8)
        grab(app, path)

    app.show_page("SETTING")
    for tab, path in SETTING_SHOTS.items():
        app.show_setting_tab(tab)
        pump(app, 0.8)
        grab(app, path)

    # papan angka (lapisan penuh) — input tanpa keyboard di layar sentuh.
    # MAJU kini bersatuan METER, jadi contohnya memakai angka pecahan.
    from feeder_core import MOVE_FW
    app.show_page("SETTING")
    app.show_setting_tab("MANUAL")
    app._open_keypad_manual(MOVE_FW, "MAJU")
    for ch in "2.5":
        app._keypad_press(ch)
    pump(app, 0.6)
    grab(app, KEYPAD_SHOT)
    app._close_keypad()

    app._on_close()


if __name__ == "__main__":
    main()
