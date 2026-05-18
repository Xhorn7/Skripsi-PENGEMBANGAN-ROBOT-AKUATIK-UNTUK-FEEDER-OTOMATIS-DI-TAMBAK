#include <SPI.h>
#include <RF24.h>
#include <nRF24L01.h>

RF24 radio(9, 8); // CE, CSN
const byte address[6] = "ADDR1";

char text[32] = "";

void setup() {
  Serial.begin(9600);
  radio.begin();
  radio.openWritingPipe(address);
  radio.setPALevel(RF24_PA_MIN);
  radio.stopListening();
  Serial.println("READY");
}

void loop() {
  if (Serial.available()) {
    String incoming = Serial.readStringUntil('\n');
    incoming.trim();
    incoming.toCharArray(text, 32);
    radio.write(&text, sizeof(text));
    Serial.print("Data terkirim: ");
    Serial.println(text);
  }
}