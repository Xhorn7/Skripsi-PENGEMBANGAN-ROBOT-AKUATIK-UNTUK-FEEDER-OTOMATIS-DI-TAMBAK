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

# halaman -> berkas keluaran
SHOTS = {
    "BERANDA": "gui_screenshot.png",   # gambar utama dokumentasi
    "MISI":    "gui_misi.png",
    "MANUAL":  "gui_manual.png",
    "SENSOR":  "gui_sensor.png",
    "LOG":     "gui_log.png",
    "SISTEM":  "gui_sistem.png",
}

KEYPAD_SHOT = "gui_keypad.png"


def pump(app, seconds):
    """Biarkan GUI menggambar & animasi berjalan selama beberapa detik."""
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.03)


def grab(app, path):
    app.lift()
    app.focus_force()
    app.update_idletasks()
    app.update()
    time.sleep(0.35)
    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    img.save(path)
    print(f"OK -> {path}  ({img.width}x{img.height})")


def main():
    # jendela 800x480 = acuan layar sentuh 7 inci
    app = FeederGUI(fullscreen=False)
    app.attributes("-topmost", True)
    app.update()

    # --- setel kondisi contoh ---
    # MPU tidak lagi butuh port: sudutnya ikut telemetri NRF, cukup nyalakan
    # tombol log-nya. Auto-simpan TXT juga dinyalakan supaya tangkapan layar
    # halaman LOG memperlihatkan berkas tujuannya.
    app.sw_mpu_record.select()
    app._on_mpu_record()
    app.sw_autosave.select()
    app._on_toggle_autosave()
    app._refresh_plan()
    pump(app, 0.6)

    # jalankan misi supaya status, gauge & progres terisi
    app._on_send_mission()
    pump(app, 2.5)

    for page, path in SHOTS.items():
        app.show_page(page)
        pump(app, 0.8)
        grab(app, path)

    # papan angka (lapisan penuh) — input tanpa keyboard di layar sentuh.
    # MAJU kini bersatuan METER, jadi contohnya memakai angka pecahan.
    from feeder_core import MOVE_FW
    app.show_page("MANUAL")
    app._open_keypad_manual(MOVE_FW, "MAJU")
    for ch in "2.5":
        app._keypad_press(ch)
    pump(app, 0.6)
    grab(app, KEYPAD_SHOT)
    app._close_keypad()

    app._on_close()


if __name__ == "__main__":
    main()
