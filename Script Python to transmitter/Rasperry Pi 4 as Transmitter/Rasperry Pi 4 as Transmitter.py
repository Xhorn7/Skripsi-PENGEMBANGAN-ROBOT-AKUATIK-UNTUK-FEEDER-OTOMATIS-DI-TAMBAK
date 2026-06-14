# =========================
# RASPBERRY PI TRANSMITTER
# =========================

from pyrf24 import RF24, RF24_PA_LOW, RF24_250KBPS
import time

radio = RF24(24, 0)

if not radio.begin():
    print("NRF gagal detect")
    quit()

address = b"00001"

radio.open_tx_pipe(address)

radio.setPALevel(RF24_PA_LOW)
radio.setDataRate(RF24_250KBPS)
radio.setChannel(0x76)

print("Transmitter Ready")
print("=" * 30)

panjang = int(input("Masukkan panjang tambak (meter): "))
lebar   = int(input("Masukkan lebar tambak (meter)  : "))

print(f"\nMengirim misi: Panjang={panjang}m, Lebar={lebar}m, Mode=AUTO")
print("Tekan Ctrl+C untuk berhenti\n")

while True:

    data = f"P={panjang};L={lebar};MODE=AUTO"

    result = radio.write(data.encode())

    if result:
        print("Terkirim :", data)
    else:
        print("Gagal kirim — cek koneksi NRF24")

    time.sleep(2)