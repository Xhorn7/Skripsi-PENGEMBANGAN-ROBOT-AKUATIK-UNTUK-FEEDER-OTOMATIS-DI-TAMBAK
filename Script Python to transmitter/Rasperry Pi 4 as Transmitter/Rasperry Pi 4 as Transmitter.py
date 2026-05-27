from pyrf24 import RF24, RF24_PA_LOW, RF24_250KBPS
import time

radio = RF24(24, 0)

if not radio.begin():
    print("Radio gagal detect")
    quit()

address = b"1Node"

radio.open_tx_pipe(address)

radio.setPALevel(RF24_PA_LOW)

radio.setDataRate(RF24_250KBPS)

radio.setChannel(0x76)

print("Transmitter jalan")

while True:

    text = b"HELLO"

    result = radio.write(text)

    if result:
        print("Kirim:", text)
    else:
        print("Gagal kirim")

    time.sleep(1)