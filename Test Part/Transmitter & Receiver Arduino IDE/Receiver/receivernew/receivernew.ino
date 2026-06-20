#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(9,10);

const byte address[6] = "00001";

void setup() {

  Serial.begin(9600);

  radio.begin();

  radio.setPayloadSize(32);

  radio.setChannel(0x76);
  radio.setDataRate(RF24_1MBPS);
  radio.setPALevel(RF24_PA_LOW);

  radio.setAutoAck(false);

  radio.openReadingPipe(0, address);

  radio.startListening();

  Serial.println("Receiver Started");
}

void loop() {

  if (radio.available()) {

    byte data[32];

    radio.read(&data, sizeof(data));

    Serial.print("RAW: ");

    for(int i=0;i<32;i++) {
      Serial.print(data[i]);
      Serial.print(" ");
    }

    Serial.println();

    Serial.print("TEXT: ");

    for(int i=0;i<32;i++) {

      if(data[i] >= 32 && data[i] <= 126) {
        Serial.print((char)data[i]);
      }
    }

    Serial.println();
  }
}