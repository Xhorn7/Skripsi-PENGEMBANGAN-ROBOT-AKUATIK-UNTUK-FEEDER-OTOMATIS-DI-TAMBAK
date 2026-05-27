#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(4, 15); // CE, CSN

const byte address[6] = "00001";

char text[32];

void setup() {

  Serial.begin(9600);

  if (!radio.begin()) {
    Serial.println("NRF gagal");
    while (1);
  }

  radio.openWritingPipe(address);

  radio.setPALevel(RF24_PA_LOW);

  radio.setDataRate(RF24_250KBPS);

  radio.stopListening();

  Serial.println("=== TRANSMITTER READY ===");
  Serial.println("Ketik pesan:");
}

void loop() {

  if (Serial.available()) {

    String pesan = Serial.readStringUntil('\n');

    pesan.trim();

    memset(text, 0, sizeof(text));

    pesan.toCharArray(text, sizeof(text));

    bool hasil = radio.write(&text, sizeof(text));

    if (hasil) {

      Serial.print("Terkirim: ");
      Serial.println(text);

    } else {

      Serial.println("Gagal mengirim");
    }
  }
}