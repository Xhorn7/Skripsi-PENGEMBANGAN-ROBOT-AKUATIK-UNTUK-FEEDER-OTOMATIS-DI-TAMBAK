#include <SPI.h>
#include <RF24.h>
#include <nRF24L01.h>

RF24 radio(9, 8); // CE, CSN
const byte address[6] = "ADDR1";

char text[32] = "";

void setup() {
  Serial.begin(9600);
  if (!radio.begin()) {
    Serial.println("NRF24 transmitter tidak terdeteksi");
    while (1) {
    }
  }
  radio.openWritingPipe(address);
  radio.setPALevel(RF24_PA_MIN);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(76);
  radio.stopListening();
  Serial.println("READY");
}

void loop() {
  if (Serial.available()) {
    String incoming = Serial.readStringUntil('\n');
    incoming.trim();

    if (incoming == "INIT") {
      Serial.println("OK");
      return;
    }

    incoming.toCharArray(text, 32);
    bool sent = radio.write(&text, sizeof(text));
    Serial.print(sent ? "Data terkirim: " : "Gagal kirim: ");
    Serial.println(text);
  }
}
