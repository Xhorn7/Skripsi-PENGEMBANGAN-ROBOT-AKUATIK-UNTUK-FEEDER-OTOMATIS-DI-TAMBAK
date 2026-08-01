"""
receiverArduino.py — ENTRY POINT tunggal sisi Transmitter (Raspberry Pi/PC)
===========================================================================

Jalankan SATU file ini untuk menjalankan semuanya (GUI + telemetri + logging):

    python receiverArduino.py               # GUI layar penuh (layar sentuh 7")
    python receiverArduino.py --windowed    # GUI jendela 800x480 (uji di PC)
    python receiverArduino.py --cli         # mode teks (tanpa GUI)

GUI otomatis MODE SIMULASI bila NRF/pyrf24 tidak tersedia (mis. di PC),
dan memakai NRF asli bila dijalankan di Raspberry Pi.

Logika inti ada di:
    - feeder_gui.py    (antarmuka CustomTkinter, gaya ATM, mengikuti layar)
    - feeder_core.py   (RobotCommand, RadioLink, CommandRunner, ActivityLogger,
                        path planner, MPUSerialReader)
"""

import sys


# =====================================================================
# MODE GUI (default) — buka panel kontrol
# =====================================================================

def run_gui(fullscreen: bool = True):
    try:
        from feeder_gui import FeederGUI
    except ImportError as e:
        print("=" * 58)
        print(" Gagal memuat GUI:", e)
        print(" Pasang dependensi dulu:")
        print("     pip install customtkinter          (wajib utk GUI)")
        print("     pip install pyrf24 pyserial         (utk NRF & MPU nyata di Pi)")
        print(" Atau jalankan mode teks:")
        print("     python receiverArduino.py --cli")
        print("=" * 58)
        sys.exit(1)

    FeederGUI(fullscreen=fullscreen).mainloop()


# =====================================================================
# MODE CLI — antarmuka teks memakai protokol Sinyal Kendali
#
# Mengikuti "Dokumen Spesifikasi Teknis", perintah dikirim satu per satu
# dalam format "[Moves]:[Dist]" dan robot membalas "ON [Moves]" lalu
# "FIN [Moves]:[Dist]". Seluruh siklus itu ditangani CommandRunner.
# =====================================================================

def run_cli():
    import time

    from feeder_core import (
        ActivityLogger, CommandRunner, MOVE_RANGE, RadioLink, RobotCommand,
        plan_command_queue, plan_coverage, queue_duration_s,
    )

    link = RadioLink()
    link.begin()
    logger = ActivityLogger(on_new=lambda ev: print(f"  [{ev.category}] {ev.message}"))
    runner = CommandRunner(link, logger=logger)

    print("=== PENGENDALI UTAMA — ROBOT AKUATIK (mode teks) ===")
    print("Mode:", "SIMULASI (tanpa NRF)" if link.simulation else "REAL (NRF aktif)")
    print("Perintah:")
    print("   FW <10-200>     maju sekian sentimeter")
    print("   CW <1-180>      putar kanan sekian derajat")
    print("   CCW <1-180>     putar kiri sekian derajat")
    print("   MISI <p> <l>    susun & jalankan sapuan zigzag tambak p x l meter")
    print("   STOP            berhenti darurat")
    print("   KELUAR")

    def wait_idle():
        while runner.is_busy():
            time.sleep(0.2)
        print(f"  -> {runner.state.status.value}")

    while True:
        try:
            raw = input("\nperintah> ").strip()
        except (EOFError, KeyboardInterrupt):
            raw = "KELUAR"
        if not raw:
            continue

        parts = raw.split()
        verb = parts[0].upper()

        if verb == "KELUAR":
            runner.abort()
            print("Selesai.")
            return

        if verb == "STOP":
            runner.abort()
            continue

        if verb == "MISI":
            if len(parts) < 3:
                print("Format: MISI <panjang_m> <lebar_m>")
                continue
            try:
                plan = plan_coverage(float(parts[1]), float(parts[2]))
            except ValueError:
                print("Panjang & lebar harus angka.")
                continue
            queue = plan_command_queue(plan)
            print(f"{plan.n_lanes} jalur -> {len(queue)} perintah, "
                  f"~{queue_duration_s(queue, plan.speed_mps):.0f} detik")
            ok, msg = runner.run(queue, label="MISI")
            print(msg)
            if ok:
                wait_idle()
            continue

        if verb in MOVE_RANGE and len(parts) >= 2:
            try:
                cmd = RobotCommand(verb, int(parts[1]))
            except ValueError:
                print("[Dist] harus bilangan bulat.")
                continue
            valid, msg = cmd.validate()
            if not valid:
                print(msg)
                continue
            ok, msg = runner.run([cmd], label="MANUAL")
            print(msg)
            if ok:
                wait_idle()
            continue

        print("Perintah tidak dikenali.")


# =====================================================================

def main():
    if "--cli" in sys.argv or "-c" in sys.argv:
        run_cli()
    else:
        run_gui(fullscreen="--windowed" not in sys.argv)


if __name__ == "__main__":
    main()
