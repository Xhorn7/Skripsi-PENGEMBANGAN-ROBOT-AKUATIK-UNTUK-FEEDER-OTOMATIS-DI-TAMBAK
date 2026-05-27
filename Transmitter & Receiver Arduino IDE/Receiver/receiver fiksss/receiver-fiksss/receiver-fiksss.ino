#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(9,10);

const byte address[6] = "1Node";

void setup() {
  Serial.begin(9600);
  radio.begin();
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(0x76);
  radio.openReadingPipe(0, address);
  radio.startListening();
  Serial.println("Receiver Ready");
}

void loop() {
  if (radio.available()) {
    char text[32] = "";
    radio.read(&text, sizeof(text));
    Serial.print("Received: ");
    Serial.println(text);
  }
}