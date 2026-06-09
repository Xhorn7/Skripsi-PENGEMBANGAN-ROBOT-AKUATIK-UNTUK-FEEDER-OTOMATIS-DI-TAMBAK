#include <SPI.h>
#include <RF24.h>
#include <Wire.h>
#include <MPU6050_tockn.h>
#include <ESP32Servo.h>

// ================= NRF24 =================

RF24 radio(9, 10);

const byte address[6] = "00001";

char text[64];

// ================= MPU =================

MPU6050 mpu(Wire);

// ================= ESC =================

Servo escLeft;
Servo escRight;

#define ESC_LEFT_PIN 25
#define ESC_RIGHT_PIN 26

// ================= DATA =================

int panjangTambak = 0;
int lebarTambak = 0;

String modeRobot = "";

bool missionReceived = false;

// =========================================

void armESC()
{
  escLeft.writeMicroseconds(1000);
  escRight.writeMicroseconds(1000);

  Serial.println("Arming ESC...");

  delay(5000);

  Serial.println("ESC Armed");
}

// =========================================

void stopBoat()
{
  escLeft.writeMicroseconds(1000);
  escRight.writeMicroseconds(1000);
}

// =========================================

void forwardBoat(int speedPWM)
{
  escLeft.writeMicroseconds(speedPWM);
  escRight.writeMicroseconds(speedPWM);
}

// =========================================

void turnLeft()
{
  escLeft.writeMicroseconds(1000);
  escRight.writeMicroseconds(1300);
}

// =========================================

void turnRight()
{
  escLeft.writeMicroseconds(1300);
  escRight.writeMicroseconds(1000);
}

// =========================================

void setup()
{
  Serial.begin(115200);

  // MPU

  Wire.begin(21,22);

  mpu.begin();
  mpu.calcGyroOffsets(true);

  // ESC

  escLeft.attach(ESC_LEFT_PIN);
  escRight.attach(ESC_RIGHT_PIN);

  armESC();

  // NRF

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

  Serial.println("Receiver Ready");
}

// =========================================

void loop()
{
  mpu.update();

  if (radio.available())
  {
    memset(text, 0, sizeof(text));

    radio.read(text, sizeof(text));

    String data = String(text);

    Serial.println();
    Serial.println("MISSION RECEIVED");
    Serial.println(data);

    int pPos = data.indexOf("P=");
    int lPos = data.indexOf("L=");
    int mPos = data.indexOf("MODE=");

    if (pPos >= 0 && lPos >= 0)
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

      missionReceived = true;

      Serial.print("Panjang: ");
      Serial.println(panjangTambak);

      Serial.print("Lebar: ");
      Serial.println(lebarTambak);

      Serial.print("Mode: ");
      Serial.println(modeRobot);
    }
  }

  // ================= AUTO MODE =================

  if (missionReceived && modeRobot == "AUTO")
  {
    missionReceived = false;

    float targetYaw = mpu.getAngleZ();

    Serial.print("Target Yaw: ");
    Serial.println(targetYaw);

    unsigned long startTime = millis();

    while (millis() - startTime < 5000)
    {
      mpu.update();

      float currentYaw = mpu.getAngleZ();

      float error = targetYaw - currentYaw;

      int leftPWM = 1300;
      int rightPWM = 1300;

      if (error > 2)
      {
        leftPWM += 20;
        rightPWM -= 20;
      }

      if (error < -2)
      {
        leftPWM -= 20;
        rightPWM += 20;
      }

      escLeft.writeMicroseconds(leftPWM);
      escRight.writeMicroseconds(rightPWM);

      Serial.print("Yaw: ");
      Serial.print(currentYaw);

      Serial.print(" Error: ");
      Serial.println(error);

      delay(50);
    }

    stopBoat();

    delay(2000);

    Serial.println("TURN RIGHT");

    turnRight();

    delay(1500);

    stopBoat();

    Serial.println("MISSION STEP DONE");
  }
}