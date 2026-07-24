"""
capture_gui.py — Jalankan GUI dalam kondisi 'hidup' lalu SCREENSHOT ke PNG.

Dipakai untuk dokumentasi. Menyetel state contoh (misi 10x4 berjalan + MPU
mode simulasi), membiarkan gauge beranimasi sebentar, lalu menyimpan
gui_screenshot.png.

Jalankan:  python capture_gui.py
Butuh:     customtkinter, pillow  (opsional pyrf24/pyserial utk data nyata)
"""

import time

from PIL import ImageGrab

from feeder_gui import FeederGUI

OUT = "gui_screenshot.png"


def main():
    app = FeederGUI()
    app.attributes("-topmost", True)
    app.update()

    # --- setel kondisi contoh ---
    app.entry_panjang.delete(0, "end"); app.entry_panjang.insert(0, "10")
    app.entry_lebar.delete(0, "end"); app.entry_lebar.insert(0, "4")
    app.mpu.start_sim()
    app.sw_mpu_record.select(); app.mpu_record = True
    app._on_send_mission()   # kirim misi -> gauge & fase mulai bergerak

    # biarkan animasi berjalan ~3 dtk supaya gauge/telemetri terisi
    end = time.time() + 3.0
    while time.time() < end:
        app.update()
        time.sleep(0.04)

    app.lift(); app.focus_force()
    app.update_idletasks(); app.update()
    time.sleep(0.3)

    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    img.save(OUT)
    print(f"OK -> {OUT}  ({img.width}x{img.height})")

    app.destroy()


if __name__ == "__main__":
    main()
