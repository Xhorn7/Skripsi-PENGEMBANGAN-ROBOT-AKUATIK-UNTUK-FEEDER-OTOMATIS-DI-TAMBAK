// ============================================================
//  MoveTest — TES GERAK TANPA RADIO
//  Buat ngetes MOTOR + MPU6050 + POLA ZIGZAG sebelum NRF24 dipindah.
//  - Radio NRF24 TIDAK dipakai (jadi pin 9/10 aman, board nggak crash)
//  - Dimensi tambak di-HARDCODE (lihat TEST_PANJANG / TEST_LEBAR)
//  - Failsafe sinyal di-skip (kan nggak ada radio)
//  Flash: pio run -e movetest -t upload
// ============================================================

#include <Wire.h>
#include <MPU6050_tockn.h>
#include <ESP32Servo.h>
#include <math.h>

MPU6050 mpu(Wire);

Servo escLeft;
Servo escRight;
#define ESC_LEFT_PIN  25
#define ESC_RIGHT_PIN 26

// ===== Kalibrasi (samain dengan Finalnew.ino) =====
#define ROBOT_SPEED_MPS   0.5f
#define LANE_WIDTH_M      1.0f
#define TURN_90_MS        1500
#define CRUISE_PWM        1300
#define KP_HEADING        8.0f
#define MAX_CORRECTION    60
#define HEADING_DEADBAND  2.0f

// ===== Dimensi HARDCODE buat tes (ganti sesuka hati) =====
#define TEST_PANJANG      4    // meter
#define TEST_LEBAR        2    // meter

bool missionDone = false;

void stopBoat()
{
  escLeft.writeMicroseconds(1000);
  escRight.writeMicroseconds(1000);
}

void armESC()
{
  escLeft.writeMicroseconds(1000);
  escRight.writeMicroseconds(1000);
  Serial.println("Arming ESC...");
  delay(5000);
  Serial.println("ESC Armed");
}

void turnRight()
{
  escLeft.writeMicroseconds(CRUISE_PWM);
  escRight.writeMicroseconds(1000);
}

// Maju lurus + heading-hold proporsional (tanpa failsafe radio)
void driveHeadingMS(float targetYaw, unsigned long durationMs)
{
  unsigned long start = millis();
  while (millis() - start < durationMs)
  {
    mpu.update();
    float err = targetYaw - mpu.getAngleZ();
    while (err >  180) err -= 360;
    while (err < -180) err += 360;

    int correction = 0;
    if (fabs(err) > HEADING_DEADBAND)
    {
      correction = (int)(KP_HEADING * err);
      correction = constrain(correction, -MAX_CORRECTION, MAX_CORRECTION);
    }
    int lPWM = constrain(CRUISE_PWM + correction, 1000, 2000);
    int rPWM = constrain(CRUISE_PWM - correction, 1000, 2000);
    escLeft.writeMicroseconds(lPWM);
    escRight.writeMicroseconds(rPWM);

    Serial.print("Yaw: ");   Serial.print(mpu.getAngleZ());
    Serial.print("  Err: "); Serial.print(err);
    Serial.print("  Corr: ");Serial.println(correction);
    delay(50);
  }
  stopBoat();
}

void turnRight90()
{
  unsigned long start = millis();
  turnRight();
  while (millis() - start < TURN_90_MS)
  {
    mpu.update();
    delay(20);
  }
  stopBoat();
}

void setup()
{
  Serial.begin(115200);

  Wire.begin(21, 22);
  mpu.begin();
  mpu.calcGyroOffsets(true);

  escLeft.attach(ESC_LEFT_PIN);
  escRight.attach(ESC_RIGHT_PIN);
  armESC();

  Serial.println("=== MODE TES GERAK (TANPA RADIO) ===");
  Serial.print("Dimensi tes: ");
  Serial.print(TEST_PANJANG); Serial.print(" x "); Serial.println(TEST_LEBAR);
}

void loop()
{
  if (missionDone) { stopBoat(); return; }

  // Countdown keselamatan — amankan baling-baling dulu!
  for (int i = 5; i > 0; i--)
  {
    Serial.print("Mulai dalam "); Serial.print(i);
    Serial.println(" detik... (ANGKAT robot / amankan baling-baling!)");
    delay(1000);
  }

  int nLanes = (int)ceil((float)TEST_LEBAR / LANE_WIDTH_M);
  unsigned long laneMs  = (unsigned long)((float)TEST_PANJANG / ROBOT_SPEED_MPS * 1000.0f);
  unsigned long shiftMs = (unsigned long)(LANE_WIDTH_M / ROBOT_SPEED_MPS * 1000.0f);

  Serial.print("Jumlah jalur: "); Serial.println(nLanes);

  for (int lane = 0; lane < nLanes; lane++)
  {
    Serial.print("\n=== Jalur "); Serial.print(lane + 1);
    Serial.print("/"); Serial.print(nLanes); Serial.println(" ===");

    mpu.update();
    float targetYaw = mpu.getAngleZ();
    driveHeadingMS(targetYaw, laneMs);
    delay(500);

    if (lane < nLanes - 1)
    {
      turnRight90();
      delay(300);
      mpu.update();
      float shiftYaw = mpu.getAngleZ();
      driveHeadingMS(shiftYaw, shiftMs);
      delay(300);
      turnRight90();
      delay(500);
    }
  }

  stopBoat();
  Serial.println("\n=== TES SELESAI ===");
  missionDone = true;
}
