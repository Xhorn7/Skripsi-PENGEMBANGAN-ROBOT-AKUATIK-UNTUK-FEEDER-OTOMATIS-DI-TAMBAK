#include <SPI.h>
#include <RF24.h>
#include <nRF24L01.h>

RF24 radio(9, 8); // CE, CSN
const byte address[6] = "ADDR1";

char text[32] = "";
bool radioReady = false;

void blinkLed(int count, int durationMs) {
  for (int i = 0; i < count; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(durationMs);
    digitalWrite(LED_BUILTIN, LOW);
    delay(durationMs);
  }
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(9600);

  radioReady = radio.begin();
  if (radioReady) {
    radio.openWritingPipe(address);
    radio.setPALevel(RF24_PA_MIN);
    radio.setDataRate(RF24_250KBPS);
    radio.setChannel(76);
    radio.stopListening();
  } else {
    Serial.println("NRF24 transmitter tidak terdeteksi, mode serial tetap aktif");
  }

  Serial.println("TRANSMITTER_READY");
}

void loop() {
  if (Serial.available()) {
    String incoming = Serial.readStringUntil('\n');
    incoming.trim();

    if (incoming == "INIT") {
      Serial.println("TRANSMITTER_OK");
      return;
    }

    incoming.toCharArray(text, 32);
    blinkLed(1, 60);

    if (!radioReady) {
      Serial.print("Input diterima, radio belum aktif: ");
      Serial.println(text);
      return;
    }

    bool sent = radio.write(&text, sizeof(text));
    Serial.print(sent ? "Data terkirim ke receiver: " : "Input masuk, tapi receiver tidak membalas ACK: ");
    Serial.println(text);
  }
}
