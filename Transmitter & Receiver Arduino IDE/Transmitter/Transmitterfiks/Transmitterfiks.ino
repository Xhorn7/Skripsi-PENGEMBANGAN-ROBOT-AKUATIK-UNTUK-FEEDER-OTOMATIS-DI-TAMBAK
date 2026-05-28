# =========================
# RASPBERRY PI TRANSMITTER
# =========================

from pyrf24 import RF24, RF24_PA_LOW, RF24_250KBPS
import time

radio = RF24(24, 0)

if not radio.begin():
    print("NRF gagal detect")
    quit()

address = b"1Node"

radio.open_tx_pipe(address)

radio.setPALevel(RF24_PA_LOW)
radio.setDataRate(RF24_250KBPS)
radio.setChannel(0x76)

print("Transmitter Ready")

while True:

    # contoh input ukuran tambak
    panjang = 10
    lebar = 5

    # format data
    data = f"{panjang},{lebar}"

    result = radio.write(data.encode())

    if result:
        print("Kirim:", data)
    else:
        print("Gagal kirim")

    time.sleep(2)