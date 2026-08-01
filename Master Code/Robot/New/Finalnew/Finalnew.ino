// =========================================================================
// Finalnew.ino — FIRMWARE BODY ROBOT (ESP32)
//
// Acuan perilaku: "Dokumen Spesifikasi Teknis — Robot Akuatik untuk Tambak
// Ikan", bab SKEMA KOMUNIKASI.
//
// PERAN ROBOT BERUBAH dari versi sebelumnya:
//   DULU  : robot menerima 1 paket misi (P/L/MODE) lalu menjalankan seluruh
//           pola zigzag sendiri di dalam firmware.
//   KINI  : robot adalah EKSEKUTOR PERINTAH. Pola jalur disusun & dikemudikan
//           oleh Pengendali Utama (Raspberry Pi). Robot hanya menjalankan
//           SATU perintah gerak dalam satu waktu, lalu melapor.
//
// Protokol (pola Request-Response, mengikuti skema DJI Tello SDK 2.0):
//
//   Pengendali Utama -> Robot : "[Moves]:[Dist]"
//        FW  : 10-200   maju lurus (satuan sentimeter)
//        CW  : 1-180    putar searah jarum jam / ke kanan (derajat)
//        CCW : 1-180    putar berlawanan jarum jam / ke kiri (derajat)
//        STOP: 0        hentikan motor (berhenti darurat)
//
//   Robot -> Pengendali Utama : "ON [Moves]"          tiap 1 detik saat bergerak
//                               "FIN [Moves]:[Dist]"  saat gerakan selesai
//
//   Bila Pengendali Utama tidak menerima "ON [Moves]" dalam 1 detik, perintah
//   dianggap gagal dan akan DIKIRIM ULANG. Karena itu robot MENGABAIKAN
//   perintah gerak baru selama masih ada gerakan berjalan (kecuali STOP),
//   supaya paket kiriman ulang tidak menumpuk jadi gerakan ganda.
// =========================================================================

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

const byte address[6] = "00001";          // Pi -> Robot (perintah/PING)
const byte telemetryAddress[6] = "00002"; // Robot -> Pi (ON/FIN + telemetri MPU)

char text[64];

// ================= MPU =================

MPU6050 mpu(Wire);

// ================= ESC =================
// 2x 30A Brushless ESC (tipe RC car/boat).
// Sinyal servo PWM: 1000us = stop/arming, 2000us = full throttle.
// CATATAN: ESC tipe ini UNIDIRECTIONAL (maju saja, tidak bisa mundur).
// Belokan dilakukan dengan differential thrust (satu motor stop, satu maju)
// => robot berputar MELINGKAR LEBAR, bukan berputar di tempat. Sudut akhir
// tetap akurat karena putaran ditutup lewat umpan balik yaw MPU, tapi robot
// ikut berpindah posisi selama berputar — pertimbangkan ini saat kalibrasi.

Servo escLeft;
Servo escRight;

#define ESC_LEFT_PIN  25
#define ESC_RIGHT_PIN 26

// ================= KALIBRASI =================

#define ROBOT_SPEED_MPS   0.5f   // kecepatan robot @ CRUISE_PWM (m/s) — UKUR di air!
#define CRUISE_PWM        1300   // throttle jelajah
#define KP_HEADING        8.0f   // gain proporsional koreksi heading
#define MAX_CORRECTION    60     // batas koreksi PWM (us) agar tidak ekstrem
#define HEADING_DEADBAND  2.0f   // toleransi error heading (derajat)
#define TURN_TOLERANCE    3.0f   // toleransi sudut akhir putaran (derajat)
#define TURN_RATE_DPS     60.0f  // perkiraan laju putar (derajat/detik) utk batas waktu
#define SIGNAL_TIMEOUT_MS 3000   // failsafe: stop bila tak ada sinyal selama ini (ms)
#define ON_INTERVAL_MS    1000   // interval kirim "ON [Moves]" sesuai spesifikasi
#define TELEMETRY_INTERVAL_MS 200 // interval kirim telemetri MPU saat menganggur (ms)

// Arah tanda yaw MPU. Bila hasil uji bench menunjukkan robot berputar ke arah
// yang TERBALIK dari perintah (CW malah ke kiri), ubah nilai ini menjadi -1.
#define YAW_SIGN          (+1)

// Batas [Dist] — sama persis dengan tabel perintah pada dokumen spesifikasi.
#define FW_MIN_CM   10
#define FW_MAX_CM   200
#define TURN_MIN_DEG 1
#define TURN_MAX_DEG 180

// ================= STATE =================

// Alasan berhentinya sebuah gerakan. WAJIB dideklarasikan sebelum fungsi mana
// pun: Arduino menyisipkan prototipe fungsi otomatis di bagian atas berkas,
// sehingga tipe yang dipakai sebagai nilai kembali harus sudah dikenal.
enum MoveResult { MOVE_DONE, MOVE_STOPPED, MOVE_LOST_SIGNAL };

unsigned long lastSignalMs = 0;     // heartbeat terakhir dari Pengendali Utama
bool stopRequested = false;         // di-set true saat menerima paket STOP
unsigned long lastTelemetryMs = 0;  // waktu terakhir kirim telemetri MPU
unsigned long lastOnMs = 0;         // waktu terakhir kirim "ON [Moves]"
bool moveInProgress = false;        // sedang menjalankan sebuah perintah gerak
char currentMove[8] = "";           // nama perintah yang sedang berjalan

// =========================================
// KENDALI MOTOR
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

// Putar ke kiri / berlawanan jarum jam (motor kiri stop, kanan maju)
void spinCCW()
{
  escLeft.writeMicroseconds(1000);
  escRight.writeMicroseconds(CRUISE_PWM);
}

// Putar ke kanan / searah jarum jam (motor kanan stop, kiri maju)
void spinCW()
{
  escLeft.writeMicroseconds(CRUISE_PWM);
  escRight.writeMicroseconds(1000);
}

// =========================================
// KOMUNIKASI BALIK (half-duplex "gantian" — seperti radio HT).
// Robot berhenti listening SEBENTAR, mengirim satu paket tanpa menunggu ACK
// (fire-and-forget), lalu langsung listening lagi. Window TX yang sangat
// pendek menjaga perintah dari Pengendali Utama tidak terlewat.
// =========================================

void sendPacket(const char *msg)
{
  radio.stopListening();
  radio.openWritingPipe(telemetryAddress);
  radio.write(msg, strlen(msg) + 1, true);  // multicast=true -> NOACK, non-blocking
  radio.startListening();
}

// "ON [Moves]" — bukti bagi Pengendali Utama bahwa perintah sedang dijalankan.
void sendOn(const char *move)
{
  char buf[16];
  snprintf(buf, sizeof(buf), "ON %s", move);
  sendPacket(buf);
  lastOnMs = millis();
}

// "FIN [Moves]:[Dist]" — perintah selesai dieksekusi dengan baik.
void sendFin(const char *move, int dist)
{
  char buf[24];
  snprintf(buf, sizeof(buf), "FIN %s:%d", move, dist);
  sendPacket(buf);
  Serial.print(">> "); Serial.println(buf);
}

// Kirim "ON" bila sudah lewat 1 detik sejak kiriman terakhir.
void maybeSendOn()
{
  if (moveInProgress && (millis() - lastOnMs >= ON_INTERVAL_MS))
    sendOn(currentMove);
}

// Telemetri sudut MPU (di luar spesifikasi wajib — dipakai panel sensor GUI).
// Format ASCII: "R=<roll>;P=<pitch>;Y=<yaw>"
void maybeSendTelemetry()
{
  if (millis() - lastTelemetryMs < TELEMETRY_INTERVAL_MS)
    return;
  lastTelemetryMs = millis();

  char tel[32];
  snprintf(tel, sizeof(tel), "R=%.1f;P=%.1f;Y=%.1f",
           mpu.getAngleX(), mpu.getAngleY(), mpu.getAngleZ());
  sendPacket(tel);
}

// =========================================
// Layani radio selama gerakan berlangsung:
//   - konsumsi paket masuk (heartbeat / STOP / perintah kiriman ulang),
//   - kirim "ON [Moves]" berkala.
// Return true bila koneksi masih hidup, false bila timeout failsafe.
// =========================================

bool serviceRadio()
{
  while (radio.available())
  {
    char buf[64];
    memset(buf, 0, sizeof(buf));
    radio.read(buf, sizeof(buf));
    lastSignalMs = millis();

    // STOP harus dilayani kapan pun, termasuk di tengah gerakan.
    if (strncmp(buf, "STOP", 4) == 0)
    {
      stopRequested = true;
      continue;
    }

    // Baru saja menerima paket = giliran robot bicara. Selipkan telemetri MPU
    // di sini saja (bukan tiap loop) supaya tidak bertabrakan dengan paket
    // perintah yang sedang dikirim Pengendali Utama.
    maybeSendTelemetry();

    // Perintah gerak lain yang datang saat sibuk = kiriman ulang dari
    // Pengendali Utama. Diabaikan; balasan "ON" di bawah sudah cukup.
  }

  maybeSendOn();
  return (millis() - lastSignalMs) < SIGNAL_TIMEOUT_MS;
}

// Cek kondisi yang membatalkan gerakan (dipakai di dalam loop gerak).
MoveResult checkAbort()
{
  if (!serviceRadio())
  {
    stopBoat();
    Serial.println("!! SINYAL HILANG -> STOP (failsafe)");
    return MOVE_LOST_SIGNAL;
  }
  if (stopRequested)
  {
    stopBoat();
    Serial.println("!! STOP diterima -> gerakan dibatalkan");
    return MOVE_STOPPED;
  }
  return MOVE_DONE;
}

// =========================================
// PERINTAH FW — maju lurus sejauh distCm sentimeter.
// Jarak diturunkan dari waktu: t = (jarak / kecepatan jelajah). Heading
// dikunci ke arah hadap saat perintah diterima memakai kendali proporsional.
// =========================================

MoveResult executeForward(int distCm)
{
  mpu.update();
  float targetYaw = mpu.getAngleZ();
  unsigned long durationMs =
      (unsigned long)((distCm / 100.0f) / ROBOT_SPEED_MPS * 1000.0f);
  unsigned long start = millis();

  Serial.print("FW "); Serial.print(distCm);
  Serial.print(" cm -> "); Serial.print(durationMs); Serial.println(" ms");

  while (millis() - start < durationMs)
  {
    mpu.update();

    MoveResult r = checkAbort();
    if (r != MOVE_DONE) return r;

    float err = targetYaw - mpu.getAngleZ();
    while (err >  180) err -= 360;   // normalisasi ke -180..180
    while (err < -180) err += 360;

    int correction = 0;
    if (fabs(err) > HEADING_DEADBAND)
    {
      correction = (int)(KP_HEADING * err);
      correction = constrain(correction, -MAX_CORRECTION, MAX_CORRECTION);
    }

    escLeft.writeMicroseconds(constrain(CRUISE_PWM + correction, 1000, 2000));
    escRight.writeMicroseconds(constrain(CRUISE_PWM - correction, 1000, 2000));

    delay(20);
  }

  stopBoat();
  return MOVE_DONE;
}

// =========================================
// PERINTAH CW / CCW — putar sejauh deg derajat.
// Putaran ditutup dengan umpan balik yaw MPU (bukan berbasis waktu), sehingga
// sudut akhir tidak bergantung pada kalibrasi durasi. Batas waktu dipasang
// sebagai pengaman bila MPU tidak merespons atau robot tertahan.
// =========================================

MoveResult executeTurn(int deg, bool clockwise)
{
  mpu.update();
  float startYaw = mpu.getAngleZ();
  unsigned long limitMs = (unsigned long)(deg / TURN_RATE_DPS * 3000.0f) + 3000;
  unsigned long start = millis();

  Serial.print(clockwise ? "CW " : "CCW ");
  Serial.print(deg); Serial.println(" derajat");

  if (clockwise) spinCW(); else spinCCW();

  while (millis() - start < limitMs)
  {
    mpu.update();

    MoveResult r = checkAbort();
    if (r != MOVE_DONE) return r;

    float delta = mpu.getAngleZ() - startYaw;
    while (delta >  180) delta -= 360;
    while (delta < -180) delta += 360;

    // Kemajuan putaran selalu dihitung positif ke arah yang diperintahkan.
    float turned = (clockwise ? -delta : delta) * YAW_SIGN;
    if (turned >= (float)deg - TURN_TOLERANCE)
      break;

    delay(20);
  }

  stopBoat();
  return MOVE_DONE;
}

// =========================================
// Jalankan satu perintah gerak lalu laporkan hasilnya.
// =========================================

void runMove(const char *move, int dist)
{
  strncpy(currentMove, move, sizeof(currentMove) - 1);
  currentMove[sizeof(currentMove) - 1] = '\0';
  moveInProgress = true;
  stopRequested = false;

  // "ON" pertama dikirim SEGERA: Pengendali Utama hanya menunggu 1 detik
  // sebelum menganggap perintah gagal dan mengirimnya ulang.
  sendOn(currentMove);

  MoveResult result;
  if (strcmp(move, "FW") == 0)
    result = executeForward(dist);
  else
    result = executeTurn(dist, strcmp(move, "CW") == 0);

  stopBoat();
  moveInProgress = false;

  if (result == MOVE_DONE)
  {
    sendFin(move, dist);   // hanya gerakan tuntas yang dilaporkan selesai
  }
  else
  {
    // Dibatalkan (STOP atau sinyal hilang) -> TIDAK mengirim FIN, supaya
    // Pengendali Utama tahu perintah tidak selesai dan tidak lanjut ke
    // perintah berikutnya.
    Serial.println("Gerakan tidak tuntas — FIN tidak dikirim");
    stopRequested = false;
  }
  currentMove[0] = '\0';
}

// =========================================
// Parsing paket "[Moves]:[Dist]" dan validasi rentang [Dist].
// Return true bila paket berupa perintah gerak yang sah.
// =========================================

bool parseCommand(const String &data, char *moveOut, int *distOut)
{
  int sep = data.indexOf(':');
  if (sep < 0) return false;

  String move = data.substring(0, sep);
  String dist = data.substring(sep + 1);
  move.trim();
  dist.trim();
  move.toUpperCase();

  int value = dist.toInt();

  if (move == "FW")
  {
    if (value < FW_MIN_CM || value > FW_MAX_CM)
    {
      Serial.print("ERROR: FW di luar rentang 10-200 cm -> "); Serial.println(value);
      return false;
    }
  }
  else if (move == "CW" || move == "CCW")
  {
    if (value < TURN_MIN_DEG || value > TURN_MAX_DEG)
    {
      Serial.print("ERROR: sudut di luar rentang 1-180 -> "); Serial.println(value);
      return false;
    }
  }
  else
  {
    return false;
  }

  strncpy(moveOut, move.c_str(), 7);
  moveOut[7] = '\0';
  *distOut = value;
  return true;
}

// =========================================

void setup()
{
  Serial.begin(115200);

  // Init radio PALING AWAL, sebelum MPU & ESC. Alasan: MPU (calcGyroOffsets)
  // bisa nge-hang selamanya kalau I2C bermasalah, dan armESC() ada delay(5000).
  // Kalau NRF diinit belakangan, startListening() baru jalan ~8 detik setelah
  // boot (atau tidak pernah) -> receiver tidak nge-ACK -> transmitter FAILED.
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
  radio.enableDynamicAck();           // izinkan write NOACK utk sinyal balik
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

  Serial.println("Receiver Ready — menunggu perintah [Moves]:[Dist]");
}

// =========================================

void loop()
{
  mpu.update();

  if (radio.available())
  {
    memset(text, 0, sizeof(text));
    radio.read(text, sizeof(text));
    lastSignalMs = millis();   // paket APAPUN menandakan koneksi hidup

    String data = String(text);
    data.trim();

    // --- PING = heartbeat murni, bukan perintah gerak ---
    if (data.startsWith("PING"))
    {
      maybeSendTelemetry();
      return;
    }

    // --- STOP = berhenti darurat, dilayani lebih dulu dari apa pun ---
    if (data.startsWith("STOP"))
    {
      stopBoat();
      stopRequested = false;   // sudah ditangani saat idle
      Serial.println("STOP diterima (idle) — motor dipastikan mati");
      sendFin("STOP", 0);
      return;
    }

    // --- Perintah gerak "[Moves]:[Dist]" ---
    char move[8];
    int dist = 0;
    if (parseCommand(data, move, &dist))
    {
      Serial.println();
      Serial.print("PERINTAH DITERIMA: "); Serial.println(data);
      runMove(move, dist);
    }
    else
    {
      Serial.print("ERROR: paket tidak dikenali -> "); Serial.println(data);
      Serial.println("Format: FW:100 | CW:90 | CCW:90 | STOP:0");
    }
  }
}
