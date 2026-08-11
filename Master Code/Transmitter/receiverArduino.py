"""
receiverArduino.py — ENTRY POINT tunggal sisi Transmitter (Raspberry Pi/PC)
===========================================================================

Jalankan SATU file ini untuk menjalankan semuanya (GUI + telemetri + logging):

    python receiverArduino.py               # GUI layar penuh (layar sentuh 7")
    python receiverArduino.py --windowed    # GUI jendela 800x480 (uji di PC)
    python receiverArduino.py --real        # langsung pakai NRF sungguhan
    python receiverArduino.py --cli         # mode teks (tanpa GUI)

Aplikasi MULAI DI MODE SIMULASI (robot virtual) supaya aman dipakai latihan &
demo di mana pun. Pindah ke NRF sungguhan lewat tombol MODE di bilah atas GUI,
lewat pemilih MODE KERJA di SETTING > SISTEM, atau lewat flag --real di atas.

Alur GUI mengikuti pekerjaan operator, bukan menu: BERANDA hanya menawarkan
MISI dan SETTING, lalu DASHBOARD (status, koordinat MPU, tombol berhenti)
terbuka SENDIRI begitu misi/perintah dikirim. Pencatatan aktivitas + sudut MPU
menyala sejak start ke logs/*.txt, dan berkas berumur > 3 hari dibuang otomatis
supaya kartu SD Raspberry Pi tidak penuh.

Logika inti ada di:
    - feeder_gui.py    (antarmuka CustomTkinter, gaya ATM, mengikuti layar)
    - feeder_core.py   (RobotCommand, RadioLink, CommandRunner, ActivityLogger,
                        path planner, MPUMonitor)
"""

import sys


# =====================================================================
# MODE GUI (default) — buka panel kontrol
# =====================================================================

def run_gui(fullscreen: bool = True, simulation: bool = True):
    try:
        from feeder_gui import FeederGUI
    except ImportError as e:
        print("=" * 58)
        print(" Gagal memuat GUI:", e)
        print(" Pasang dependensi dulu:")
        print("     pip install customtkinter          (wajib utk GUI)")
        print("     pip install pyrf24                 (utk NRF nyata di Pi)")
        print(" Atau jalankan mode teks:")
        print("     python receiverArduino.py --cli")
        print("=" * 58)
        sys.exit(1)

    FeederGUI(fullscreen=fullscreen, simulation=simulation).mainloop()


# =====================================================================
# MODE CLI — antarmuka teks memakai protokol Sinyal Kendali
#
# Mengikuti "Dokumen Spesifikasi Teknis", perintah dikirim satu per satu
# dalam format "[Moves]:[Dist]" dan robot membalas "ON [Moves]" lalu
# "FIN [Moves]:[Dist]". Seluruh siklus itu ditangani CommandRunner.
# =====================================================================

def run_cli(simulation: bool = True):
    import threading
    import time

    from feeder_core import (
        ActivityLogger, CommandRunner, HEARTBEAT_INTERVAL_S, LOG_RETENTION_DAYS,
        MPUMonitor, MANUAL_FW_MAX_M, MANUAL_FW_MIN_M, MOVE_RANGE, RadioLink,
        RobotCommand, default_log_path, plan_command_queue, plan_coverage,
        purge_old_logs, queue_duration_s, split_forward,
    )

    link = RadioLink()
    link.begin(force_sim=simulation)
    logger = ActivityLogger(on_new=lambda ev: print(f"  [{ev.category}] {ev.message}"))
    runner = CommandRunner(link, logger=logger)
    mpu = MPUMonitor(link, logger=logger)

    # Heartbeat + tarikan telemetri di latar belakang: menjaga failsafe robot
    # sekaligus membuat sudut MPU mengalir sendiri (sama seperti di GUI).
    def background():
        while True:
            if not runner.is_busy():
                link.ping()
            mpu.poll()
            time.sleep(HEARTBEAT_INTERVAL_S)

    threading.Thread(target=background, daemon=True).start()

    # Sama seperti GUI: bersihkan log kedaluwarsa lalu catat sejak awal.
    terhapus, _ = purge_old_logs()
    if terhapus:
        print(f"  {len(terhapus)} berkas log > {LOG_RETENTION_DAYS} hari dihapus")
    ok, msg = logger.set_autosave(default_log_path())
    print(" ", msg)
    mpu.set_logging(True)

    print("=== PENGENDALI UTAMA — ROBOT AKUATIK (mode teks) ===")
    print("Mode:", "SIMULASI (robot virtual)" if link.simulation
                   else "REAL (NRF aktif)")
    print("Perintah:")
    print(f"   MAJU <{MANUAL_FW_MIN_M:g}-{MANUAL_FW_MAX_M:g}>   maju sekian METER "
          "(dipecah otomatis jadi paket FW)")
    print("   FW <10-200>     satu paket maju, satuan sentimeter")
    print("   CW <1-180>      putar kanan sekian derajat")
    print("   CCW <1-180>     putar kiri sekian derajat")
    print("   MISI <p> <l>    susun & jalankan sapuan zigzag tambak p x l meter")
    print("   MODE <real|sim> pindah lawan bicara radio")
    print("   MPU <on|off>    catat sudut MPU dari telemetri NRF")
    print("   SIMPAN <on|off> auto-simpan log ke berkas TXT (default: nyala)")
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

        if verb == "MODE":
            want_sim = len(parts) < 2 or parts[1].upper().startswith(("S", "V"))
            ok, msg = link.set_mode(want_sim)
            print(("  " if ok else "  GAGAL: ") + msg)
            continue

        if verb == "MPU":
            print("  " + mpu.set_logging(len(parts) > 1
                                         and parts[1].lower() in ("on", "1", "ya")))
            continue

        if verb == "SIMPAN":
            hidup = len(parts) > 1 and parts[1].lower() in ("on", "1", "ya")
            ok, msg = logger.set_autosave(default_log_path() if hidup else None)
            print(("  " if ok else "  GAGAL: ") + msg)
            continue

        if verb == "MAJU":
            if len(parts) < 2:
                print("Format: MAJU <meter>")
                continue
            try:
                meters = float(parts[1].replace(",", "."))
            except ValueError:
                print("Jarak harus angka (meter).")
                continue
            cmds = split_forward(meters)
            if not cmds:
                print(f"Jarak minimal {MANUAL_FW_MIN_M:g} m.")
                continue
            print(f"{meters:g} m -> {len(cmds)} paket: "
                  + "  ".join(c.encode().decode() for c in cmds[:8])
                  + (" ..." if len(cmds) > 8 else ""))
            ok, msg = runner.run(cmds, label="MANUAL")
            print(msg)
            if ok:
                wait_idle()
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
    # Default SIMULASI; --real meminta NRF sungguhan sejak awal.
    simulation = "--real" not in sys.argv
    if "--cli" in sys.argv or "-c" in sys.argv:
        run_cli(simulation=simulation)
    else:
        run_gui(fullscreen="--windowed" not in sys.argv, simulation=simulation)


if __name__ == "__main__":
    main()
