from pyrf24 import RF24, RF24_PA_LOW, RF24_250KBPS
import time
import threading

radio = RF24(24, 0)

if not radio.begin():
    print("NRF gagal detect")
    quit()

address = b"00001"

radio.open_tx_pipe(address)

radio.setPALevel(RF24_PA_LOW)
radio.setDataRate(RF24_250KBPS)
radio.setChannel(0x76)

print("=== FEEDER TRANSMITTER ===")

# ================= HEARTBEAT =================
# Receiver punya failsafe: kalau tidak ada paket masuk selama SIGNAL_TIMEOUT_MS
# (3000 ms), motor otomatis STOP. Karena satu misi bisa berjalan lama, kita
# HARUS terus mengirim paket "PING" sebagai heartbeat selama misi aktif —
# kalau tidak, robot berhenti sendiri setelah ~3 detik.
#
# PING dikirim di thread terpisah tiap 500 ms (< 3000 ms) supaya thread utama
# tetap bebas menunggu input() untuk misi berikutnya.

HEARTBEAT_INTERVAL_S = 0.5

lock = threading.Lock()        # radio.write() hanya boleh dipanggil 1 thread pada satu waktu
mission_running = False        # True setelah misi pertama dikirim


def radio_send(payload: bytes) -> bool:
    with lock:
        return radio.write(payload)


def heartbeat_loop():
    while True:
        if mission_running:
            radio_send(b"PING")
        time.sleep(HEARTBEAT_INTERVAL_S)


threading.Thread(target=heartbeat_loop, daemon=True).start()

# ================= INPUT MISI =================

while True:

    panjang = input("Panjang Tambak (m) [ketik STOP untuk batalkan misi]: ").strip()

    # ---- Perintah STOP: batalkan misi yang sedang berjalan ----
    if panjang.upper() == "STOP":
        mission_running = False          # hentikan heartbeat PING lebih dulu
        time.sleep(HEARTBEAT_INTERVAL_S) # beri jeda supaya tak bentrok dgn PING terakhir
        ok = False
        for _ in range(5):
            if radio_send(b"STOP"):
                ok = True
            time.sleep(0.05)
        print("STOP terkirim — misi dibatalkan" if ok else "STOP FAILED — cek NRF")
        print()
        continue

    lebar = input("Lebar Tambak (m): ").strip()

    mode = "AUTO"

    payload = f"P={panjang};L={lebar};MODE={mode}".encode()

    print("SEND :", payload.decode())

    # Kirim misi beberapa kali supaya pasti diterima (mengatasi paket drop).
    ok = False
    for _ in range(5):
        if radio_send(payload):
            ok = True
        time.sleep(0.05)

    if ok:
        print("SUCCESS — heartbeat PING berjalan otomatis")
    else:
        print("FAILED — cek koneksi NRF")

    # Mulai kirim heartbeat PING sampai ada misi baru.
    mission_running = True

    print()
