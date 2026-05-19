#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(9, 10);

const byte address[6] = "00001";

void setup() {

  Serial.begin(9600);

  pinMode(LED_BUILTIN, OUTPUT);

  if (!radio.begin()) {
    Serial.println("NRF gagal");
    while (1);
  }

  radio.openWritingPipe(address);

  radio.setPALevel(RF24_PA_LOW);

  radio.stopListening();

  Serial.println("Transmitter Ready");
}

void loop() {

  const char text[] = "HALO";

  bool hasil = radio.write(&text, sizeof(text));

  if (hasil) {

    Serial.println("Pesan terkirim");

    // LED kedip 2x
    for(int i = 0; i < 2; i++) {

      digitalWrite(LED_BUILTIN, HIGH);
      delay(200);

      digitalWrite(LED_BUILTIN, LOW);
      delay(200);
    }

  } else {

    Serial.println("Gagal kirim");
  }

  delay(1000);
}