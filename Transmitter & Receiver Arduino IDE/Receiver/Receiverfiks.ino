#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(9, 10);

const byte address[6] = "00001";

char text[32] = "";

void setup() {

  Serial.begin(9600);

  pinMode(LED_BUILTIN, OUTPUT);

  if (!radio.begin()) {
    Serial.println("NRF gagal");
    while (1);
  }

  radio.openReadingPipe(0, address);

  radio.setPALevel(RF24_PA_LOW);

  radio.startListening();

  Serial.println("Receiver Ready");
}

void loop() {

  if (radio.available()) {

    radio.read(&text, sizeof(text));

    Serial.print("Pesan: ");
    Serial.println(text);

    // LED kedip 2x
    for(int i = 0; i < 2; i++) {

      digitalWrite(LED_BUILTIN, HIGH);
      delay(200);

      digitalWrite(LED_BUILTIN, LOW);
      delay(200);
    }
  }
}