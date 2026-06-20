#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(4, 5); // CE, CSN

const byte address[6] = "00001";

char text[32] = "";

void setup() {

  Serial.begin(9600);

  if (!radio.begin()) {
    Serial.println("NRF gagal");
    while (1);
  }

  radio.openReadingPipe(0, address);

  radio.setPALevel(RF24_PA_LOW);

  radio.setDataRate(RF24_250KBPS);

  radio.startListening();

  Serial.println("=== RECEIVER READY ===");
}

void loop() {

  if (radio.available()) {

    radio.read(&text, sizeof(text));

    Serial.print("Pesan diterima: ");
    Serial.println(text);

    memset(text, 0, sizeof(text));
  }
}