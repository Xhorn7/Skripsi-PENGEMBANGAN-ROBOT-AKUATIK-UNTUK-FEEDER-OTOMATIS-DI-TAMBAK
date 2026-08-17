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

#define SDA_PIN 21
#define SCL_PIN 22
#define I2C_HZ  100000UL

MPU6050 mpu(Wire);

// --- Deteksi MPU mati (disamakan dengan Finalnew.ino) ---------------------
// Kalau I2C tidak menjawab, Wire.read() mengembalikan -1 untuk SEMUA byte,
// dan MPU6050_tockn menerjemahkannya jadi sudut yang BEKU di
//     Roll = -90.0   Pitch = +90.0   Yaw = -0.0
// (atan2(-6.1e-5, 0) = -90 derajat PAS). Angka itu tanda sensor tak terbaca,
// BUKAN hasil pengukuran — dan kalau dipakai heading-hold, robot dikemudikan
// oleh sudut palsu. Jadi harus dideteksi, bukan dipercaya.

bool mpuOk = false;
unsigned long lastMpuRetryMs = 0;

#define MPU_RETRY_INTERVAL_MS 2000
#define ACC_MAG_MIN 0.30f          // |a| wajar (g) — sensor sehat merasakan ~1 g
#define ACC_MAG_MAX 3.00f

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

// ===== MPU: probe, init, update ber-pengawasan =====

bool mpuProbe()
{
  Wire.beginTransmission(MPU6050_ADDR);
  return Wire.endTransmission() == 0;   // 0 = ada yang meng-ACK 0x68
}

bool initMPU(bool calibrate)
{
  if (!mpuProbe()) return false;
  mpu.begin();
  if (calibrate) mpu.calcGyroOffsets(true);
  mpu.update();
  return true;
}

// Pengganti mpu.update(): SEMUA pembacaan MPU di sketch ini lewat sini.
void mpuUpdate()
{
  mpu.update();

  bool noReply = (mpu.getRawAccX() == -1 &&
                  mpu.getRawAccY() == -1 &&
                  mpu.getRawAccZ() == -1);
  float ax = mpu.getAccX(), ay = mpu.getAccY(), az = mpu.getAccZ();
  float mag = sqrtf(ax * ax + ay * ay + az * az);
  bool healthy = !noReply && (mag > ACC_MAG_MIN) && (mag < ACC_MAG_MAX);

  if (healthy != mpuOk)
  {
    mpuOk = healthy;
    Serial.println(mpuOk
        ? "MPU OK — heading-hold aktif"
        : "!! MPU TIDAK MENJAWAB I2C — heading-hold DIMATIKAN "
          "(cek SDA=21 / SCL=22 / 3.3V / GND)");
  }

  if (!mpuOk && (millis() - lastMpuRetryMs >= MPU_RETRY_INTERVAL_MS))
  {
    lastMpuRetryMs = millis();
    Wire.begin(SDA_PIN, SCL_PIN);
    Wire.setClock(I2C_HZ);
    Wire.setTimeOut(50);
    if (initMPU(false))
      Serial.println("MPU tersambung kembali");
  }
}

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
    mpuUpdate();
    float err = targetYaw - mpu.getAngleZ();
    while (err >  180) err -= 360;
    while (err < -180) err += 360;

    // MPU mati -> err dihitung dari sudut palsu. Lebih baik maju lurus
    // dengan dua motor sama besar daripada dikoreksi ke arah yang ngawur.
    int correction = 0;
    if (mpuOk && fabs(err) > HEADING_DEADBAND)
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
    Serial.print("  Corr: ");Serial.print(correction);
    Serial.println(mpuOk ? "" : "   [MPU MATI - sudut tidak sah]");
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
    mpuUpdate();
    delay(20);
  }
  stopBoat();
}

void setup()
{
  Serial.begin(115200);

  // Bus di-probe DULU: library tockn tidak memeriksa ACK, jadi mpu.begin()
  // tetap "berhasil" walau tidak ada sensor sama sekali.
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(I2C_HZ);
  Wire.setTimeOut(50);

  if (mpuProbe())
  {
    Serial.println("MPU6050 terdeteksi di 0x68 — kalibrasi gyro, JANGAN digerakkan");
    initMPU(true);
    mpuUpdate();
  }
  else
  {
    Serial.println("!! MPU6050 TIDAK terdeteksi di I2C 0x68");
    Serial.println("   cek SDA=GPIO21, SCL=GPIO22, VCC=3.3V, GND, AD0->GND.");
    Serial.println("   Tes tetap jalan, tapi TANPA heading-hold.");
  }

  // ESP32Servo WAJIB alokasi timer dulu sebelum attach; kalau tidak,
  // PWM ke ESC bisa gagal diam-diam -> baling-baling nggak gerak.
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);
  escLeft.setPeriodHertz(50);   // ESC = sinyal servo 50 Hz
  escRight.setPeriodHertz(50);
  escLeft.attach(ESC_LEFT_PIN, 1000, 2000);
  escRight.attach(ESC_RIGHT_PIN, 1000, 2000);
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

  // Geometri jalur DISAMAKAN dengan path planner di Pengendali Utama
  // (feeder_core.plan_coverage): lebar dibagi jadi nBands pita, lalu jalur
  // ditaruh di SETIAP pembatas pita termasuk kedua tepi -> nLanes = nBands+1.
  // Jarak geser antar-jalur = spasi pita, bukan LANE_WIDTH_M mentah; kalau
  // memakai LANE_WIDTH_M, jalur terakhir tidak sampai ke tepi seberang.
  int nBands = (int)ceil((float)TEST_LEBAR / LANE_WIDTH_M);
  if (nBands < 1) nBands = 1;
  int nLanes = nBands + 1;
  float spacingM = (float)TEST_LEBAR / nBands;

  unsigned long laneMs  = (unsigned long)((float)TEST_PANJANG / ROBOT_SPEED_MPS * 1000.0f);
  unsigned long shiftMs = (unsigned long)(spacingM / ROBOT_SPEED_MPS * 1000.0f);

  Serial.print("Jumlah jalur: "); Serial.print(nLanes);
  Serial.print("  spasi antar-jalur: "); Serial.print(spacingM);
  Serial.println(" m");

  for (int lane = 0; lane < nLanes; lane++)
  {
    Serial.print("\n=== Jalur "); Serial.print(lane + 1);
    Serial.print("/"); Serial.print(nLanes); Serial.println(" ===");

    mpuUpdate();
    float targetYaw = mpu.getAngleZ();
    driveHeadingMS(targetYaw, laneMs);
    delay(500);

    if (lane < nLanes - 1)
    {
      turnRight90();
      delay(300);
      mpuUpdate();
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
