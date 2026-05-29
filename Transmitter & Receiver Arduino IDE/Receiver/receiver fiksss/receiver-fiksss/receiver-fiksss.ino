#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(9, 10);

const byte address[6] = "00001";

char text[32];

int panjangTambak = 0;
int lebarTambak = 0;

String modeRobot = "";

void setup()
{
  Serial.begin(115200);

  if (!radio.begin())
  {
    Serial.println("NRF FAIL");
    while (1);
  }

  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(0x76);

  radio.openReadingPipe(0, address);

  radio.startListening();

  Serial.println("=== RECEIVER READY ===");
}

void loop()
{
  if (radio.available())
  {
    memset(text, 0, sizeof(text));

    radio.read(text, sizeof(text));

    String data = String(text);

    Serial.println();
    Serial.println("===== DATA MASUK =====");
    Serial.println(data);

    int pPos = data.indexOf("P=");
    int lPos = data.indexOf("L=");
    int mPos = data.indexOf("MODE=");

    if (pPos >= 0 && lPos >= 0 && mPos >= 0)
    {
      panjangTambak =
        data.substring(
          pPos + 2,
          data.indexOf(";", pPos)
        ).toInt();

      lebarTambak =
        data.substring(
          lPos + 2,
          data.indexOf(";", lPos)
        ).toInt();

      modeRobot =
        data.substring(
          mPos + 5
        );

      Serial.println("===== HASIL PARSE =====");

      Serial.print("Panjang : ");
      Serial.println(panjangTambak);

      Serial.print("Lebar   : ");
      Serial.println(lebarTambak);

      Serial.print("Mode    : ");
      Serial.println(modeRobot);

      if (modeRobot == "AUTO")
      {
        Serial.println("AUTO MODE AKTIF");

        // ===============================
        // TEMPAT ALGORITMA ROBOT FEEDER
        // ===============================

        /*
           nanti disini:

           hitung lintasan zig-zag

           hitung jumlah jalur

           jalankan motor

           feeding
        */
      }
    }
  }
}