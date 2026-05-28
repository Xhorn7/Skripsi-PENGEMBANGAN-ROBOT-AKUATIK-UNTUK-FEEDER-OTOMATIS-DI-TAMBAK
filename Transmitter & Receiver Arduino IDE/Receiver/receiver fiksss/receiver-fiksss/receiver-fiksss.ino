// =========================
// ESP MASTER RECEIVER
// =========================

#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

// ================= NRF24 =================
RF24 radio(D9, D10);

const byte address[6] = "1Node";

char text[32] = "";

// ================= MOTOR =================
int rightF = 16;
int rightB = 5;
int leftF  = 4;
int leftB  = 0;

// ================= DATA =================
int panjangTambak = 0;
int lebarTambak = 0;

// ================= ROBOT =================
void maju() {

  digitalWrite(rightF, HIGH);
  digitalWrite(rightB, LOW);

  digitalWrite(leftF, HIGH);
  digitalWrite(leftB, LOW);
}

void berhenti() {

  digitalWrite(rightF, LOW);
  digitalWrite(rightB, LOW);

  digitalWrite(leftF, LOW);
  digitalWrite(leftB, LOW);
}

void setup() {

  Serial.begin(115200);

  // ================= MOTOR =================
  pinMode(rightF, OUTPUT);
  pinMode(rightB, OUTPUT);

  pinMode(leftF, OUTPUT);
  pinMode(leftB, OUTPUT);

  berhenti();

  // ================= NRF =================
  if (!radio.begin()) {

    Serial.println("NRF gagal detect");

    while (1);
  }

  radio.setPALevel(RF24_PA_LOW);

  radio.setDataRate(RF24_250KBPS);

  radio.setChannel(0x76);

  radio.openReadingPipe(0, address);

  radio.startListening();

  Serial.println("Receiver Ready");
}

void loop() {

  if (radio.available()) {

    memset(text, 0, sizeof(text));

    radio.read(&text, sizeof(text));

    Serial.print("Raw Data: ");
    Serial.println(text);

    // ================= PARSE DATA =================
    String data = String(text);

    int commaIndex = data.indexOf(',');

    if (commaIndex > 0) {

      panjangTambak = data.substring(0, commaIndex).toInt();

      lebarTambak = data.substring(commaIndex + 1).toInt();

      Serial.print("Panjang Tambak: ");
      Serial.println(panjangTambak);

      Serial.print("Lebar Tambak: ");
      Serial.println(lebarTambak);

      // ================= CONTOH LOGIC =================
      // kalau ukuran valid robot jalan

      if (panjangTambak > 0 && lebarTambak > 0) {

        Serial.println("Robot Maju");

        maju();

        delay(3000);

        berhenti();

        Serial.println("Robot Stop");
      }
    }
  }
}