#include <SPI.h>
#include <RF24.h>
#include <Wire.h>
#include <MPU6050_tockn.h>
#include <ESP32Servo.h>
#include <math.h>

// ================= NRF24 =================

// CE=GPIO4, CSN=GPIO5 (GPIO bebas & aman).
// JANGAN pakai 9/10 = pin flash internal WROOM (bikin crash/boot-loop).
RF24 radio(4, 5);

const byte address[6] = "00001";

char text[64];

// ================= MPU =================

MPU6050 mpu(Wire);

// ================= ESC =================
// 2x 30A Brushless ESC (tipe RC car/boat).
// Sinyal servo PWM: 1000us = stop/arming, 2000us = full throttle.
// CATATAN: ESC tipe ini UNIDIRECTIONAL (maju saja, tidak bisa mundur).
// Belokan dilakukan dengan differential thrust (satu motor stop, satu maju)
// => robot belok MELINGKAR LEBAR, bukan putar di tempat. Radius putar
// terbatas, jadi TURN_90_MS harus dikalibrasi sesuai ruang gerak nyata.

Servo escLeft;
Servo escRight;

#define ESC_LEFT_PIN  25
#define ESC_RIGHT_PIN 26
// ================= KALIBRASI =================

#define ROBOT_SPEED_MPS   0.5f   // kecepatan robot @ CRUISE_PWM (m/s) — UKUR di air!
#define LANE_WIDTH_M      1.0f   // jarak antar lintasan (m)
#define TURN_90_MS        1500   // durasi belok ~90 derajat (ms) — UKUR! (tergantung radius ESC)
#define CRUISE_PWM        1300   // throttle jelajah
#define KP_HEADING        8.0f   // gain proporsional koreksi heading
#define MAX_CORRECTION    60     // batas koreksi PWM (us) agar tidak ekstrem
#define HEADING_DEADBAND  2.0f   // toleransi error heading (derajat)
#define SIGNAL_TIMEOUT_MS 3000   // failsafe: stop bila tak ada sinyal selama ini (ms)

// ================= DATA =================

int panjangTambak = 0;
int lebarTambak   = 0;
String modeRobot  = "";
bool missionReceived = false;

unsigned long lastSignalMs = 0;  // heartbeat terakhir dari transmitter
bool stopRequested = false;      // di-set true saat menerima paket "STOP"

// Parameter misi OPSIONAL dari paket (default = konstanta kalibrasi di atas).
// Dikirim GUI transmitter lewat "SPD=", "LW=", "DIR="; kalau tidak ada, pakai default.
float robotSpeedMps  = ROBOT_SPEED_MPS;  // kecepatan jelajah (m/s)
float laneWidthM     = LANE_WIDTH_M;     // jarak antar-lintasan (m)
bool  firstTurnRight = true;             // arah U-turn pertama (R=kanan, L=kiri)

// =========================================

void armESC()
{
  escLeft.writeMicroseconds(1000);
  escRight.writeMicroseconds(1000);
  Serial.println("Arming ESC...");
  delay(5000);
  Serial.println("ESC Armed");
}

void stopBoat()
{
  escLeft.writeMicroseconds(1000);
  escRight.writeMicroseconds(1000);
}

void forwardBoat(int speedPWM)
{
  escLeft.writeMicroseconds(speedPWM);
  escRight.writeMicroseconds(speedPWM);
}

// Belok melingkar ke kiri (motor kiri stop, kanan maju)
void turnLeft()
{
  escLeft.writeMicroseconds(1000);
  escRight.writeMicroseconds(CRUISE_PWM);
}

// Belok melingkar ke kanan (motor kanan stop, kiri maju)
void turnRight()
{
  escLeft.writeMicroseconds(CRUISE_PWM);
  escRight.writeMicroseconds(1000);
}

// =========================================
// Cek sinyal transmitter sebagai heartbeat (failsafe).
// Return true bila koneksi masih hidup, false bila timeout.
// =========================================

bool signalAlive()
{
  if (radio.available())
  {
    char buf[64];
    memset(buf, 0, sizeof(buf));
    radio.read(buf, sizeof(buf));   // konsumsi paket (heartbeat / STOP)
    lastSignalMs = millis();

    // Perintah STOP di tengah misi -> tandai untuk abort.
    if (strncmp(buf, "STOP", 4) == 0)
      stopRequested = true;
  }
  return (millis() - lastSignalMs) < SIGNAL_TIMEOUT_MS;
}

// =========================================
// Maju lurus dengan heading-hold proporsional selama durationMs.
// Return true bila selesai normal, false bila di-abort (sinyal hilang).
// =========================================

bool driveHeadingMS(float targetYaw, unsigned long durationMs)
{
  unsigned long start = millis();

  while (millis() - start < durationMs)
  {
    mpu.update();

    // Failsafe: putus koneksi di tengah misi -> stop & abort
    if (!signalAlive())
    {
      stopBoat();
      Serial.println("!! SINYAL HILANG -> STOP (failsafe)");
      return false;
    }

    // Perintah STOP manual dari transmitter -> abort
    if (stopRequested)
    {
      stopBoat();
      Serial.println("!! STOP diterima -> misi dibatalkan");
      return false;
    }

    float err = targetYaw - mpu.getAngleZ();
    while (err >  180) err -= 360;   // normalisasi ke -180..180
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

    Serial.print("Yaw: ");    Serial.print(mpu.getAngleZ());
    Serial.print("  Tgt: ");  Serial.print(targetYaw);
    Serial.print("  Err: ");  Serial.print(err);
    Serial.print("  Corr: "); Serial.println(correction);

    delay(50);
  }

  stopBoat();
  return true;
}

// =========================================
// Belok ~90 derajat (timed) ke KANAN atau KIRI, dengan cek failsafe.
//   toRight = true  -> belok kanan (motor kanan stop, kiri maju)
//   toRight = false -> belok kiri  (motor kiri stop, kanan maju)
// Return true bila selesai, false bila abort.
// =========================================

bool turn90(bool toRight)
{
  unsigned long start = millis();
  if (toRight) turnRight(); else turnLeft();
  while (millis() - start < TURN_90_MS)
  {
    mpu.update();
    if (!signalAlive())
    {
      stopBoat();
      Serial.println("!! SINYAL HILANG -> STOP (failsafe)");
      return false;
    }
    if (stopRequested)
    {
      stopBoat();
      Serial.println("!! STOP diterima -> misi dibatalkan");
      return false;
    }
    delay(20);
  }
  stopBoat();
  return true;
}

// Cari akhir sebuah token pada string paket: indeks ';' berikutnya, atau akhir string.
int tokenEnd(const String &s, int from)
{
  int e = s.indexOf(';', from);
  return (e < 0) ? (int)s.length() : e;
}

// =========================================

void setup()
{
  Serial.begin(115200);

  // ================= NRF (SOLUSI 5A) =================
  // Init radio PALING AWAL, sebelum MPU & ESC. Alasan: MPU (calcGyroOffsets)
  // bisa nge-hang selamanya kalau I2C bermasalah, dan armESC() ada delay(5000).
  // Kalau NRF diinit belakangan, startListening() baru jalan ~8 detik setelah
  // boot (atau tidak pernah) -> receiver tidak nge-ACK -> transmitter FAILED.
  // Dengan dipindah ke atas, radio langsung listening & tidak keblok subsistem lain.
  if (!radio.begin())
  {
    while (1)
    {
      Serial.println("NRF FAIL - cek wiring NRF24 (CE=4, CSN=5, VCC=3.3V)");
      delay(1000);
    }
  }

  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(0x76);
  radio.openReadingPipe(1, address);  // pipe 1 (pipe 0 reserved untuk auto-ACK)
  radio.startListening();

  Serial.println("Radio Ready (listening)");

  // MPU
  Wire.begin(21, 22);
  mpu.begin();
  mpu.calcGyroOffsets(true);

  // ESC
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
    lastSignalMs = millis();   // heartbeat: paket APAPUN menandakan koneksi hidup

    String data = String(text);

    // Paket PING = heartbeat murni (jaga failsafe), BUKAN misi baru.
    // Cukup update lastSignalMs di atas, lalu abaikan — supaya misi yang
    // sedang jalan tidak ter-trigger ulang oleh heartbeat.
    if (data.startsWith("PING"))
    {
      return;
    }

    // Paket STOP saat idle (di luar misi): pastikan motor mati, lalu abaikan.
    if (data.startsWith("STOP"))
    {
      stopBoat();
      stopRequested = false;   // sudah ditangani, jangan sampai membatalkan misi berikutnya
      Serial.println("STOP diterima (idle) — motor dipastikan mati");
      return;
    }

    Serial.println();
    Serial.println("MISSION RECEIVED");
    Serial.println(data);

    int pPos = data.indexOf("P=");
    int lPos = data.indexOf("L=");
    int mPos = data.indexOf("MODE=");

    if (pPos >= 0 && lPos >= 0 && mPos >= 0)
    {
      panjangTambak = data.substring(pPos + 2, tokenEnd(data, pPos)).toInt();
      lebarTambak   = data.substring(lPos + 2, tokenEnd(data, lPos)).toInt();
      modeRobot     = data.substring(mPos + 5, tokenEnd(data, mPos));
      modeRobot.trim();   // MODE bukan lagi field terakhir -> potong di ';'

      // Parameter OPSIONAL (kompatibel-mundur). Reset ke default tiap misi baru.
      robotSpeedMps  = ROBOT_SPEED_MPS;
      laneWidthM     = LANE_WIDTH_M;
      firstTurnRight = true;

      int sPos = data.indexOf("SPD=");
      if (sPos >= 0)
      {
        float v = data.substring(sPos + 4, tokenEnd(data, sPos)).toFloat();
        if (v > 0) robotSpeedMps = v;
      }
      int wPos = data.indexOf("LW=");
      if (wPos >= 0)
      {
        float v = data.substring(wPos + 3, tokenEnd(data, wPos)).toFloat();
        if (v > 0) laneWidthM = v;
      }
      int dPos = data.indexOf("DIR=");
      if (dPos >= 0)
      {
        String d = data.substring(dPos + 4, tokenEnd(data, dPos));
        d.trim();
        firstTurnRight = !d.startsWith("L");   // "L" -> kiri, selain itu kanan
      }

      missionReceived = true;

      Serial.print("Panjang : "); Serial.println(panjangTambak);
      Serial.print("Lebar   : "); Serial.println(lebarTambak);
      Serial.print("Mode    : "); Serial.println(modeRobot);
      Serial.print("Speed   : "); Serial.println(robotSpeedMps);
      Serial.print("LaneW   : "); Serial.println(laneWidthM);
      Serial.print("Belok-1 : "); Serial.println(firstTurnRight ? "KANAN" : "KIRI");
    }
    else
    {
      Serial.println("ERROR: Format tidak valid. Harap: P=10;L=5;MODE=AUTO");
    }
  }

  // ================= AUTO MODE — POLA ZIGZAG =================

  if (missionReceived && modeRobot == "AUTO")
  {
    missionReceived = false;

    if (panjangTambak <= 0 || lebarTambak <= 0)
    {
      Serial.println("ERROR: Dimensi tambak tidak valid, misi dibatalkan");
      return;
    }

    int nLanes = (int)ceil((float)lebarTambak / laneWidthM);
    unsigned long laneDurationMs  = (unsigned long)((float)panjangTambak / robotSpeedMps * 1000.0f);
    unsigned long shiftDurationMs = (unsigned long)(laneWidthM / robotSpeedMps * 1000.0f);

    lastSignalMs = millis();  // reset heartbeat di awal misi
    stopRequested = false;    // bersihkan sisa STOP lama agar tak membatalkan misi baru

    Serial.print("Jumlah jalur  : "); Serial.println(nLanes);
    Serial.print("Durasi 1 jalur: "); Serial.print(laneDurationMs); Serial.println(" ms");

    bool aborted = false;
    bool turnToRight = firstTurnRight;   // arah U-turn; dibalik tiap ganti lane

    for (int lane = 0; lane < nLanes && !aborted; lane++)
    {
      Serial.print("\n=== Jalur "); Serial.print(lane + 1);
      Serial.print(" / ");          Serial.print(nLanes); Serial.println(" ===");

      // RE-ZERO: kunci heading saat ini sebagai target lurus
      // (lawan akumulasi gyro drift — tiap lane pakai acuan baru)
      mpu.update();
      float targetYaw = mpu.getAngleZ();

      if (!driveHeadingMS(targetYaw, laneDurationMs)) { aborted = true; break; }
      delay(500);

      if (lane < nLanes - 1)
      {
        // U-turn = dua kali belok 90 derajat KE ARAH SAMA (total 180 derajat),
        // diselingi geser 1 lebar lane. Arah U-turn BERSELANG-SELING tiap ganti
        // lane (kanan-kanan lalu kiri-kiri, dst) supaya geseran selalu ke sisi
        // yang sama -> benar-benar menyapu seluruh lebar tambak (boustrophedon).
        if (!turn90(turnToRight)) { aborted = true; break; }
        delay(300);

        mpu.update();
        float shiftYaw = mpu.getAngleZ();   // kunci heading setelah belok pertama
        if (!driveHeadingMS(shiftYaw, shiftDurationMs)) { aborted = true; break; }
        delay(300);

        if (!turn90(turnToRight)) { aborted = true; break; }
        delay(500);

        turnToRight = !turnToRight;   // lane berikutnya belok ke arah sebaliknya
      }
    }

    stopBoat();

    if (aborted)
      Serial.println("\nMISI DIBATALKAN (sinyal hilang)");
    else
      Serial.println("\nMISI SELESAI");
  }
}
