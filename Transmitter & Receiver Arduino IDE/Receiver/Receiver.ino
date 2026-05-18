#include <SPI.h>
#include <RF24.h>
#include <nRF24L01.h>

RF24 radio(9, 8); // CE, CSN
const byte address[6] = "ADDR1";
bool radioReady = false;
unsigned long lastHeartbeat = 0;
unsigned long lastWaitingLog = 0;

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
    radio.openReadingPipe(0, address);
    radio.setPALevel(RF24_PA_MIN);
    radio.setDataRate(RF24_250KBPS);
    radio.setChannel(76);
    radio.startListening();
    Serial.println("NRF24 receiver aktif, menunggu data");
  } else {
    Serial.println("NRF24 receiver tidak terdeteksi");
  }

  Serial.println("RECEIVER_READY");
};

void loop() {
  if (!radioReady) {
    if (millis() - lastHeartbeat >= 1000) {
      lastHeartbeat = millis();
      blinkLed(1, 80);
      Serial.println("Receiver hidup, tapi NRF24 belum terbaca");
    }
    return;
  }

  if (millis() - lastWaitingLog >= 3000) {
    lastWaitingLog = millis();
    Serial.println("Menunggu data dari transmitter...");
  }

  if (radio.available()) {
    char txt[32] = "";
    radio.read(&txt, sizeof(txt));
    blinkLed(2, 60);
    Serial.print("Data diterima: ");
    Serial.println(txt);
  };
};
