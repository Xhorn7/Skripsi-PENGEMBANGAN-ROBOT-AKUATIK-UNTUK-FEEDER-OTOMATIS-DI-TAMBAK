"""
receiverArduino.py — ENTRY POINT tunggal sisi Transmitter (Raspberry Pi/PC)
===========================================================================

Jalankan SATU file ini untuk menjalankan semuanya (GUI + telemetri + logging):

    python receiverArduino.py            # buka GUI panel kontrol (default)
    python receiverArduino.py --cli      # mode teks lama (tanpa GUI)

GUI otomatis MODE SIMULASI bila NRF/pyrf24 tidak tersedia (mis. di PC),
dan memakai NRF asli bila dijalankan di Raspberry Pi.

Logika inti ada di:
    - feeder_gui.py    (antarmuka CustomTkinter)
    - feeder_core.py   (RadioLink, MissionEstimator, ActivityLogger, MPUSerialReader)
"""

import sys


# =====================================================================
# MODE GUI (default) — buka panel kontrol
# =====================================================================

def run_gui():
    try:
        from feeder_gui import FeederGUI
    except ImportError as e:
        print("=" * 58)
        print(" Gagal memuat GUI:", e)
        print(" Pasang dependensi dulu:")
        print("     pip install customtkinter          (wajib utk GUI)")
        print("     pip install pyrf24 pyserial         (utk NRF & MPU nyata di Pi)")
        print(" Atau jalankan mode teks lama:")
        print("     python receiverArduino.py --cli")
        print("=" * 58)
        sys.exit(1)

    FeederGUI().mainloop()


# =====================================================================
# MODE CLI (lama) — antarmuka teks, sama seperti versi awal
# =====================================================================

def run_cli():
    import time
    import threading
    from pyrf24 import RF24, RF24_PA_LOW, RF24_250KBPS # type: ignore

    radio = RF24(24, 0)

    if not radio.begin():
        print("NRF gagal detect")
        return

    address = b"00001"
    radio.open_tx_pipe(address)
    radio.setPALevel(RF24_PA_LOW)
    radio.setDataRate(RF24_250KBPS)
    radio.setChannel(0x76)

    print("=== FEEDER TRANSMITTER (mode teks) ===")

    HEARTBEAT_INTERVAL_S = 0.5
    lock = threading.Lock()
    state = {"mission_running": False}

    def radio_send(payload: bytes) -> bool:
        with lock:
            return radio.write(payload)

    def heartbeat_loop():
        while True:
            if state["mission_running"]:
                radio_send(b"PING")
            time.sleep(HEARTBEAT_INTERVAL_S)

    threading.Thread(target=heartbeat_loop, daemon=True).start()

    while True:
        panjang = input("Panjang Tambak (m) [ketik STOP untuk batalkan misi]: ").strip()

        if panjang.upper() == "STOP":
            state["mission_running"] = False
            time.sleep(HEARTBEAT_INTERVAL_S)
            ok = False
            for _ in range(5):
                if radio_send(b"STOP"):
                    ok = True
                time.sleep(0.05)
            print("STOP terkirim — misi dibatalkan" if ok else "STOP FAILED — cek NRF")
            print()
            continue

        lebar = input("Lebar Tambak (m): ").strip()
        payload = f"P={panjang};L={lebar};MODE=AUTO".encode()
        print("SEND :", payload.decode())

        ok = False
        for _ in range(5):
            if radio_send(payload):
                ok = True
            time.sleep(0.05)

        print("SUCCESS — heartbeat PING berjalan otomatis" if ok
              else "FAILED — cek koneksi NRF")
        state["mission_running"] = True
        print()


# =====================================================================

def main():
    if "--cli" in sys.argv or "-c" in sys.argv:
        run_cli()
    else:
        run_gui()


if __name__ == "__main__":
    main()
