#include <SPI.h>
#include <RF24.h>
#include <nRF24L01.h>

RF24 radio(9, 8); // CE, CSN
const byte address[6] = "ADDR1";

void setup() {
  Serial.begin(9600);
  if (!radio.begin()) {
    Serial.println("NRF24 receiver tidak terdeteksi");
    while (1) {
    }
  }
  radio.openReadingPipe(0, address);
  radio.setPALevel(RF24_PA_MIN);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(76);
  radio.startListening();
  Serial.println("Receiver READY");
};

void loop() {
  if (radio.available()) {
    char txt[32] = "";
    radio.read(&txt, sizeof(txt));
    Serial.println(txt);
  };
};
