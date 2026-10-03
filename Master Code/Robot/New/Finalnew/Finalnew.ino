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
//
// MODUL TERPASANG: papan bersablon "MPU-9250/6500" — satu desain papan untuk
// DUA chip berbeda. WHO_AM_I papan ini terbaca 0x70, yang berarti chip yang
// terpasang adalah MPU-6500: accel + gyro saja, TANPA magnetometer. (MPU-9250
// asli menjawab 0x71.) Jadi yaw HANYA berasal dari integrasi gyro dan pasti
// merayap — terukur 1,1 derajat/menit pada pengujian diam 10 menit.
//
// Konsekuensi untuk navigasi: yaw TIDAK boleh dipakai sebagai arah mutlak
// lintas segmen. Firmware ini memang sudah memakainya secara relatif
// (targetYaw & startYaw diambil ulang tiap gerakan), jadi drift di dalam satu
// segmen tidak berarti (30 detik = 0,55 derajat). Yang tetap menumpuk adalah
// arah fisik robot sepanjang misi: kira-kira 1,1 derajat per menit waktu
// bergerak, atau ~11 derajat untuk misi 10 menit.
//
// WIRING MPU (modul polos 10 pin: VCC GND SCL SDA EDA ECL ADO INT NCS FSYNC)
//   VCC   -> 3V3          SCL -> GPIO22
//   GND   -> GND          SDA -> GPIO21
//   ADO   -> GND          kunci alamat di 0x68; mengambang bisa jadi 0x69
//   NCS   -> 3V3          kunci mode I2C
//   FSYNC -> GND          jangan mengambang
//   EDA/ECL/INT           dibiarkan KOSONG
//
// ADO, NCS, dan FSYNC TIDAK ADA di MPU-6050 dan wajib disambung di sini.
// NCS yang paling menjebak: MPU-6500/9250 MENGUNCI mode antarmuka saat listrik
// masuk, jadi bila NCS terbaca LOW pada saat itu, chip masuk mode SPI dan
// I2C-nya MATI TOTAL di semua alamat — modul sehat pun tampak seperti tidak ada.
//
// STATUS PERAKITAN saat ini: ketiga pin itu masih JUMPER LANGSUNG ke ESP32,
// belum lewat jalur PCB. Berfungsi normal, tapi kabel loncat lebih rentan
// lepas kena getaran motor. Bila PCB direvisi, jadikan ketiganya jalur tetap.

#define SDA_PIN 21
#define SCL_PIN 22
#define I2C_HZ  100000UL   // 100 kHz — paling tahan kabel panjang & noise ESC

MPU6050 mpu(Wire);

// --- Deteksi MPU mati -----------------------------------------------------
// Gejala yang terlihat di GUI: "Roll=-90.0 Pitch=90.0 Yaw=-0.0" TERUS-MENERUS
// dan tidak berubah walau robot digerakkan.
//
// Itu BUKAN pembacaan sensor, melainkan sidik jari khas I2C yang tidak
// menjawab. Bila requestFrom() tidak mendapat satu byte pun, Wire.read()
// mengembalikan -1, sehingga di MPU6050_tockn::update():
//     rawAccX = rawAccY = rawAccZ = (-1 << 8) | -1 = -1
//     accX = accY = accZ = -1/16384 = -6.1e-5
//     angleAccX = atan2(accY, accZ + abs(accX)) = atan2(-6.1e-5, 0) = -90.0 PAS
//     angleAccY = -atan2(accX, accZ + abs(accY)) = +90.0 PAS
// dan Yaw diam di -0.0 karena gyro mentah yang konstan habis dikurangi
// offset kalibrasi. Sudut lalu "terkunci" di situ karena filter komplementer
// menarik angleX/angleY ke angleAcc.
//
// Karena sudut palsu ini dipakai untuk heading-hold (FW) dan penutup putaran
// (CW/CCW), MPU mati HARUS diketahui, bukan dipakai diam-diam untuk mengemudi.

#define MPU6050_ADDR_ALT 0x69           // alamat MPU bila pin AD0 ke-HIGH

bool mpuOk = false;                     // MPU menghasilkan data masuk akal?
bool mpuCalibrated = false;             // calcGyroOffsets() sudah pernah jalan?
bool mpuAlt69 = false;                  // ada perangkat di 0x69 (AD0 HIGH)?
bool mpuAckNoData = false;              // 0x68 meng-ACK tapi data tidak keluar?
bool busIdleHigh = false;               // SDA & SCL diam di HIGH (pull-up ada)?
unsigned long lastMpuRetryMs = 0;       // percobaan sambung ulang terakhir

#define MPU_RETRY_INTERVAL_MS 2000
#define ACC_MAG_MIN 0.30f               // |a| yang wajar (g) — sensor sehat ~1 g
#define ACC_MAG_MAX 3.00f

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

#define ROBOT_SPEED_MPS   0.28f  // kecepatan setelah lancar @ CRUISE_PWM (m/s)
#define FW_START_MS       2100   // waktu awal sebelum robot bergerak berarti (ms)
// Kalibrasi kolam uji: motor 4,0 s -> 54 cm, 7,4 s -> 150 cm.
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
// MPU: PROBE, INIT, UPDATE BER-PENGAWASAN
// =========================================

// Normalisasi sudut ke -180..180. Dipakai sebelum kirim telemetri: angleZ
// tockn adalah integral gyro MURNI yang tumbuh tanpa batas, dan "Y=-1234.5"
// bisa membuat paket telemetri melewati batas 32 byte payload NRF24.
float wrap180(float deg)
{
  while (deg >  180.0f) deg -= 360.0f;
  while (deg < -180.0f) deg += 360.0f;
  return deg;
}

// Apakah alamat tertentu meng-ACK di bus I2C?
bool i2cAck(uint8_t addr)
{
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

bool mpuProbe() { return i2cAck(MPU6050_ADDR); }

// Baca n byte dari sebuah register. Mengembalikan false bila bus tidak
// menjawab — inilah yang membedakan "sensor bilang 0" dari "tidak ada sensor".
// Pustaka tockn tidak bisa membedakannya: ia membaca -1 lalu memakainya
// seolah-olah angka sungguhan.
bool i2cReadBytes(uint8_t addr, uint8_t reg, uint8_t *buf, uint8_t n)
{
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)addr, (int)n) != n) return false;
  for (uint8_t i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}

// Melepaskan bus yang DIKUNCI slave. Kalau ESP32 di-reset di TENGAH transaksi
// I2C — saat upload, saat EN ditekan, atau saat brown-out — MPU TIDAK ikut
// ter-reset karena listriknya tidak putus. Ia masih menunggu sisa pulsa clock
// dan menahan SDA tetap LOW, sehingga SEMUA transaksi berikutnya menggantung.
//
// Wire.end() + Wire.begin() saja TIDAK cukup: itu hanya melepas sisi ESP32,
// sementara yang menahan jalur adalah MPU di seberangnya. Urutan baku
// pemulihan bus I2C: kirim hingga 9 pulsa SCL manual supaya slave menuntaskan
// byte yang tertunda lalu melepas SDA, ditutup kondisi STOP. Sembilan karena
// satu byte = 8 bit + 1 ACK.
void i2cBusRecover()
{
  Wire.end();

  pinMode(SDA_PIN, INPUT_PULLUP);
  pinMode(SCL_PIN, OUTPUT);
  digitalWrite(SCL_PIN, HIGH);
  delayMicroseconds(5);

  for (uint8_t i = 0; i < 9 && digitalRead(SDA_PIN) == LOW; i++)
  {
    digitalWrite(SCL_PIN, LOW);  delayMicroseconds(5);
    digitalWrite(SCL_PIN, HIGH); delayMicroseconds(5);
  }

  pinMode(SDA_PIN, OUTPUT);          // kondisi STOP: SDA naik selagi SCL HIGH
  digitalWrite(SDA_PIN, LOW);   delayMicroseconds(5);
  digitalWrite(SCL_PIN, HIGH);  delayMicroseconds(5);
  digitalWrite(SDA_PIN, HIGH);  delayMicroseconds(5);

  pinMode(SDA_PIN, INPUT);
  pinMode(SCL_PIN, INPUT);

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(I2C_HZ);
  Wire.setTimeOut(50);
}

// Probe yang diulang sebelum menyerah. MPU perlu waktu menuntaskan power-on
// reset, dan probe pertama sesudah boot sering jatuh TEPAT sebelum chip siap.
bool mpuProbeRetry(uint8_t tries, uint16_t gapMs)
{
  for (uint8_t i = 0; i < tries; i++)
  {
    if (mpuProbe()) return true;
    delay(gapMs);
  }
  return false;
}

// Bus I2C yang SEHAT diam di HIGH, ditahan resistor pull-up pada modul MPU
// (GY-521 punya 4k7 ke VCC). Kalau kedua jalur diam di LOW, berarti tidak ada
// pull-up sama sekali -> modul tidak dapat 3.3V, GND-nya lepas, atau kabel/
// solder SDA-SCL putus. Ini memisahkan "modul mati listrik" dari "modul hidup
// tapi tidak menjawab" — dua hal yang di layar sama-sama tampil sebagai sudut
// beku, padahal perbaikannya berbeda.
void checkBusIdle()
{
  Wire.end();                       // lepas pin dari peripheral I2C

  // INPUT_PULLDOWN, bukan INPUT polos. Pin CMOS yang mengambang gampang
  // terbaca HIGH karena kebocoran/derau, jadi INPUT polos bisa melaporkan
  // "pull-up ada" padahal jalurnya putus. Dengan pull-down internal (~45k):
  //   ada pull-up luar 4k7  -> pembagi tegangan menang di HIGH  -> terbaca 1
  //   jalur mengambang      -> ditarik pull-down internal ke GND -> terbaca 0
  pinMode(SDA_PIN, INPUT_PULLDOWN);
  pinMode(SCL_PIN, INPUT_PULLDOWN);
  delayMicroseconds(200);           // beri waktu jalur mencapai keadaan tunak
  busIdleHigh = digitalRead(SDA_PIN) && digitalRead(SCL_PIN);

  Wire.begin(SDA_PIN, SCL_PIN);     // pasang kembali bus
  Wire.setClock(I2C_HZ);
  Wire.setTimeOut(50);
}

// Sapu seluruh bus & laporkan apa yang benar-benar ada di sana. Dicetak saat
// boot supaya Serial memberi FAKTA, bukan tebakan: kalau tidak ada satu pun
// alamat yang menjawab, masalahnya kabel/daya; kalau yang menjawab 0x69,
// masalahnya pin AD0 (lihat catatan di bawah).
void i2cScanReport()
{
  int found = 0;
  Serial.println("-- Pemindaian bus I2C (SDA=21, SCL=22) --");
  for (uint8_t addr = 1; addr < 127; addr++)
  {
    if (!i2cAck(addr)) continue;
    found++;
    Serial.print("   ADA perangkat di 0x");
    if (addr < 16) Serial.print('0');
    Serial.print(addr, HEX);
    if (addr == 0x68) Serial.print("  <- MPU6050 (AD0 = GND) BENAR");
    if (addr == 0x69) Serial.print("  <- MPU6050 tapi AD0 = HIGH!");
    Serial.println();
  }
  if (found == 0)
    Serial.println("   (KOSONG — tidak ada satu pun perangkat menjawab)");
  Serial.println("----------------------------------------");
}

// Register WHO_AM_I MPU6050 = 0x75, isinya harus 0x68.
uint8_t mpuWhoAmI()
{
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(0x75);
  if (Wire.endTransmission(false) != 0) return 0xFF;
  if (Wire.requestFrom((int)MPU6050_ADDR, 1) != 1) return 0xFF;
  return Wire.read();
}

// =========================================
// KALIBRASI GYRO YANG TIDAK BISA MENGGANTUNG
// =========================================
// Pengganti mpu.calcGyroOffsets(). Pustaka tockn menembak 3000 transaksi I2C
// beruntun TANPA memeriksa satu pun kegagalan; sekali bus tersendat, ia
// menggantung SELAMANYA. Di sketch tes hal itu cuma bikin serial diam, tapi di
// SINI akibatnya jauh lebih serius: kalibrasi dipanggil dari setup(), jadi
// loop() tidak pernah tercapai, radio tidak pernah dilayani, dan robot hanya
// diam tanpa sebab yang terlihat. Kejadian ini bukan teori — terjadi berulang
// saat pengujian MPU di PCB.
//
// Nilai balik:
//   CAL_GAGAL  bus mati; TIDAK ada offset yang dipasang
//   CAL_BERSIH offset dipasang, robot benar-benar diam saat diukur
//   CAL_GOYANG offset dipasang, TAPI robot bergoyang -> offset patut diragukan

#define CAL_GAGAL   0
#define CAL_BERSIH  1
#define CAL_GOYANG  2

#define GYRO_CAL_SAMPLES   600
#define GYRO_LSB_PER_DPS   65.5f    // tockn memasang GYRO_CONFIG = +-500 dps
#define GYRO_STILL_MAX_DPS 3.0f     // rentang wajar saat benar-benar diam

uint8_t calcGyroOffsetsSafe()
{
  float sum[3] = {0, 0, 0};
  float mn[3]  = { 9999,  9999,  9999};
  float mx[3]  = {-9999, -9999, -9999};
  uint16_t ok = 0, fail = 0;

  for (uint16_t i = 0; i < GYRO_CAL_SAMPLES; i++)
  {
    uint8_t b[6];
    if (!i2cReadBytes(MPU6050_ADDR, 0x43, b, 6))   // 0x43 = GYRO_XOUT_H
    {
      if (++fail > 60) return CAL_GAGAL;
      i2cBusRecover();
      delay(5);
      continue;
    }

    float v[3];
    for (uint8_t a = 0; a < 3; a++)
    {
      int16_t raw = (int16_t)((uint16_t)b[a * 2] << 8 | b[a * 2 + 1]);
      v[a] = raw / GYRO_LSB_PER_DPS;
      sum[a] += v[a];
      if (v[a] < mn[a]) mn[a] = v[a];
      if (v[a] > mx[a]) mx[a] = v[a];
    }
    ok++;
    delay(3);
  }

  if (ok < GYRO_CAL_SAMPLES / 2) return CAL_GAGAL;

  mpu.setGyroOffsets(sum[0] / ok, sum[1] / ok, sum[2] / ok);

  // Rentang simpangan = bukti robot benar-benar diam atau tidak. Ini yang
  // memisahkan "sensornya jelek" dari "robot kesenggol/kena ombak saat
  // dikalibrasi" — dua hal yang sama-sama tampil sebagai yaw yang merayap
  // cepat. Saat pengujian, offset yang diambil sambil dipegang menghasilkan
  // drift 150 deg/menit; yang diambil saat diam, 1,1 deg/menit.
  float worst = 0;
  for (uint8_t a = 0; a < 3; a++)
    if (mx[a] - mn[a] > worst) worst = mx[a] - mn[a];

  Serial.print("Offset gyro: X="); Serial.print(sum[0] / ok, 3);
  Serial.print(" Y=");             Serial.print(sum[1] / ok, 3);
  Serial.print(" Z=");             Serial.print(sum[2] / ok, 3);
  Serial.print("  simpangan=");    Serial.print(worst, 2);
  Serial.print(" deg/s  gagal=");  Serial.println(fail);

  return (worst > GYRO_STILL_MAX_DPS) ? CAL_GOYANG : CAL_BERSIH;
}

// calibrate=false dipakai saat sambung ulang di TENGAH GERAKAN: kalibrasi
// menuntut sensor benar-benar diam, jadi menjalankannya saat robot bergerak
// justru menghasilkan offset yang salah.
bool initMPU(bool calibrate)
{
  if (!mpuProbe()) return false;
  mpu.begin();
  if (calibrate)
  {
    // Offset TETAP dipakai walau hasilnya CAL_GOYANG — offset yang diukur
    // sambil bergoyang masih jauh lebih baik daripada nol. Yang berbeda hanya
    // mpuCalibrated: dibiarkan salah supaya nanti diulang saat benar-benar
    // tenang, dan supaya GUI tetap melihat kode status 3.
    uint8_t r = calcGyroOffsetsSafe();
    if (r == CAL_BERSIH) mpuCalibrated = true;
    else if (r == CAL_GOYANG)
      Serial.println("!! Robot BERGOYANG saat kalibrasi — offset dipakai "
                     "sementara, akan diulang saat tenang");
    else
      Serial.println("!! Kalibrasi gyro GAGAL — bus I2C tidak menjawab");
  }
  mpu.update();
  return true;
}

// Kode status MPU yang ikut dikirim pada telemetri (bidang "S").
// ESP32 di robot sering tidak bisa dicolok Serial saat sudah terpasang, jadi
// hasil diagnosa HARUS bisa dibaca dari GUI lewat radio — bukan cuma dari
// Serial monitor. Satu digit ini cukup untuk membedakan semua penyebab yang
// selama ini tampil sama saja di layar (sudut yang tidak masuk akal).
//   1 = sehat
//   0 = bus SEHAT (pull-up ada) tapi tak ada yang menjawab -> SDA/SCL tertukar
//       atau chip MPU rusak
//   2 = perangkat ada di 0x69, bukan 0x68   -> pin AD0 ke-HIGH
//   3 = terbaca, tapi gyro belum terkalibrasi -> yaw merayap pelan
//   4 = 0x68 meng-ACK tapi data tidak keluar -> kabel goyang / 3.3V drop
//   5 = SDA & SCL diam di LOW (tanpa pull-up) -> modul tidak bertenaga,
//       GND/VCC lepas, atau kabel putus
uint8_t mpuStatusCode()
{
  if (mpuOk) return mpuCalibrated ? 1 : 3;
  if (mpuAckNoData) return 4;
  if (mpuAlt69) return 2;
  return busIdleHigh ? 0 : 5;
}

// Pengganti mpu.update(): baca sensor, nilai kewarasannya, dan coba pulihkan
// bus I2C bila mati. SEMUA pemanggilan mpu.update() di firmware ini lewat sini.
void mpuUpdate()
{
  bool retryDue = (millis() - lastMpuRetryMs >= MPU_RETRY_INTERVAL_MS);

  // MPU yang SUDAH DIKETAHUI MATI jangan dibaca tiap iterasi. Satu pembacaan
  // gagal berarti dua transaksi I2C yang bisa memblokir sampai batas waktu
  // 50 ms masing-masing. Di dalam loop gerak (yang hanya ber-delay 20 ms),
  // itu membuat robot telat melayani radio sampai heartbeat 3 detik dianggap
  // hilang — gerakan lalu dibatalkan diam-diam TANPA mengirim FIN, dan
  // Pengendali Utama melaporkan "tidak ada FIN dalam 9 detik".
  // Cukup dicoba lagi tiap MPU_RETRY_INTERVAL_MS; sudutnya toh tidak dipakai
  // selagi mpuOk salah.
  if (!mpuOk && !retryDue) return;

  mpu.update();

  // (a) ketiga sumbu akselerometer tepat -1 = tidak ada byte yang terbaca.
  bool noReply = (mpu.getRawAccX() == -1 &&
                  mpu.getRawAccY() == -1 &&
                  mpu.getRawAccZ() == -1);

  // (b) akselerometer sehat SELALU merasakan gravitasi ~1 g, apa pun posisinya.
  float ax = mpu.getAccX(), ay = mpu.getAccY(), az = mpu.getAccZ();
  float mag = sqrtf(ax * ax + ay * ay + az * az);

  bool healthy = !noReply && (mag > ACC_MAG_MIN) && (mag < ACC_MAG_MAX);

  if (healthy != mpuOk)
  {
    mpuOk = healthy;
    if (mpuOk)
      Serial.println("MPU OK — sudut valid, heading-hold & putaran closed-loop aktif");
    else
      Serial.println("!! MPU TIDAK MENJAWAB I2C — sudut TIDAK valid "
                     "(cek SDA=21 / SCL=22 / 3.3V / GND)");
  }

  if (!mpuOk && retryDue)
  {
    lastMpuRetryMs = millis();

    // i2cBusRecover() DULU, baru checkBusIdle(). Wire.end()+Wire.begin() di
    // dalam checkBusIdle hanya memasang ulang sisi ESP32; kalau yang menahan
    // jalur adalah MPU yang tertinggal di tengah transaksi, bus tetap mati
    // sampai slave-nya diberi pulsa clock untuk menuntaskan byte-nya.
    i2cBusRecover();
    checkBusIdle();

    // Cukup 2 detik sekali — murah, dan inilah yang membuat GUI bisa
    // membedakan "kabel putus" dari "AD0 salah" tanpa colok Serial.
    mpuAckNoData = mpuProbe();              // 0x68 ACK padahal data tak sehat
    mpuAlt69     = i2cAck(MPU6050_ADDR_ALT);

    // Kalibrasi HANYA bila belum pernah dilakukan DAN robot sedang diam.
    // Tanpa syarat pertama, MPU yang baru terdeteksi setelah boot akan
    // berjalan dengan gyroZoffset = 0 selamanya — gejalanya yaw merayap
    // pelan-pelan dengan laju tetap walau robot tidak bergerak sama sekali.
    bool bolehKalibrasi = (!mpuCalibrated && !moveInProgress);
    if (initMPU(bolehKalibrasi))
    {
      if (bolehKalibrasi)
        Serial.println("MPU tersambung — offset gyro BARU dihitung");
      else
        Serial.println("MPU tersambung kembali — offset gyro lama dipakai");
    }
  }
}

// Yaw yang merayap tetap walau robot diam = gyro belum terkalibrasi.
// Dipanggil saat menganggur supaya tidak pernah menahan gerakan.
// Jeda antar-percobaan. TANPA ini, robot yang mengapung di air bergelombang
// akan gagal uji "diam" terus-menerus dan mencoba ulang tiap iterasi idle —
// tiap percobaan menahan loop ~2 detik, jadi radio telat dilayani dan failsafe
// heartbeat 3 detik bisa ikut terpicu. Justru kalibrasi yang niatnya menolong
// malah membuat robot tampak putus sambungan.
#define GYRO_CAL_RETRY_MS   15000UL
#define GYRO_CAL_MAX_TRIES  5

unsigned long lastGyroCalMs = 0;
uint8_t       gyroCalTries  = 0;

void maybeCalibrateWhenIdle()
{
  if (!(mpuOk && !mpuCalibrated && !moveInProgress)) return;
  if (gyroCalTries > 0 && millis() - lastGyroCalMs < GYRO_CAL_RETRY_MS) return;

  lastGyroCalMs = millis();
  gyroCalTries++;

  Serial.println("Gyro belum terkalibrasi — robot harus DIAM sebentar...");
  uint8_t r = calcGyroOffsetsSafe();
  mpu.update();
  lastSignalMs = millis();   // kalibrasi memakan ~2 s: jangan picu failsafe

  if (r == CAL_BERSIH)
  {
    mpuCalibrated = true;
    Serial.println("Kalibrasi gyro selesai — yaw seharusnya berhenti merayap");
  }
  else if (r == CAL_GOYANG && gyroCalTries >= GYRO_CAL_MAX_TRIES)
  {
    // Air yang tidak pernah tenang tidak boleh membuat robot mengulang
    // kalibrasi selamanya. Offset dari gerakan berayun tetap berguna: riak
    // naik-turun rata-ratanya nol, jadi biasnya masih terukur cukup baik.
    mpuCalibrated = true;
    Serial.println("Air tidak pernah tenang setelah beberapa percobaan — "
                   "offset terakhir DIPAKAI, yaw mungkin merayap sedikit");
  }
  else
  {
    Serial.print("Kalibrasi ditunda (percobaan ");
    Serial.print(gyroCalTries);
    Serial.print("/"); Serial.print(GYRO_CAL_MAX_TRIES);
    Serial.println(") — robot masih bergerak");
  }
}

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

// Pada robot ini kabel ESC tersilang: ESC_LEFT_PIN (GPIO25) menggerakkan motor
// KANAN secara fisik dan ESC_RIGHT_PIN (GPIO26) motor KIRI. Uji kolam: CW:45
// lama berbelok ke kiri. Heading-hold FW sudah benar dengan susunan ini, jadi
// hanya fungsi putar yang disesuaikan. Jangan tukar kabel ESC tanpa mengubah ini.

// Putar ke kiri / berlawanan jarum jam: motor kanan fisik (GPIO25) maju
void spinCCW()
{
  escLeft.writeMicroseconds(CRUISE_PWM);
  escRight.writeMicroseconds(1000);
}

// Putar ke kanan / searah jarum jam: motor kiri fisik (GPIO26) maju
void spinCW()
{
  escLeft.writeMicroseconds(1000);
  escRight.writeMicroseconds(CRUISE_PWM);
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

// --- Pengiriman ulang FIN -------------------------------------------------
// FIN dikirim NOACK (fire-and-forget) dan dulu hanya SEKALI. Radio ini
// half-duplex: kalau paket FIN itu kebetulan lepas saat Pengendali Utama
// sedang giliran mengirim, paketnya hilang selamanya. Gerakan yang sebenarnya
// SUDAH TUNTAS lalu terlihat "tidak direspon", dan seluruh sisa antrean misi
// dibatalkan. Berbeda dengan "ON" yang memang diulang tiap 1 detik, FIN tidak
// punya jaring pengaman sama sekali.
//
// Karena itu FIN kini diulang beberapa kali. Pengulangan DIHENTIKAN begitu
// perintah gerak berikutnya datang — itu bukti Pengendali Utama sudah
// menerimanya, sekaligus mencegah FIN basi tertukar dengan FIN perintah
// berikutnya bila jenis geraknya sama (mis. FW:200 dua kali berturut-turut).

char finMove[8] = "";
int  finDist = 0;
uint8_t finRepeatsLeft = 0;
unsigned long lastFinMs = 0;

#define FIN_REPEAT_MS    150
#define FIN_REPEAT_COUNT 6

// "FIN [Moves]:[Dist]" — perintah selesai dieksekusi dengan baik.
void sendFin(const char *move, int dist)
{
  char buf[24];
  snprintf(buf, sizeof(buf), "FIN %s:%d", move, dist);
  sendPacket(buf);
  Serial.print(">> "); Serial.println(buf);

  strncpy(finMove, move, sizeof(finMove) - 1);
  finMove[sizeof(finMove) - 1] = '\0';
  finDist = dist;
  finRepeatsLeft = FIN_REPEAT_COUNT;
  lastFinMs = millis();
}

void maybeResendFin()
{
  if (finRepeatsLeft == 0) return;
  if (millis() - lastFinMs < FIN_REPEAT_MS) return;

  lastFinMs = millis();
  finRepeatsLeft--;

  char buf[24];
  snprintf(buf, sizeof(buf), "FIN %s:%d", finMove, finDist);
  sendPacket(buf);
}

// Pengendali Utama sudah lanjut -> hentikan pengulangan FIN lama.
void clearPendingFin() { finRepeatsLeft = 0; }

// --- Ledakan "ON" di awal gerakan ----------------------------------------
// Balapan turnaround half-duplex: Pengendali Utama baru saja SELESAI mengirim
// perintah dan belum tentu sudah pindah ke mode dengar, sedangkan robot
// membalas "ON" dalam hitungan mikrodetik. "ON" pertama karena itu gampang
// terlewat. Karena ulangan berikutnya baru datang 1 detik kemudian — persis
// sama dengan batas tunggu Pengendali Utama — perintahnya kerap dianggap
// gagal lalu dikirim ulang, memboroskan 1 detik per kejadian.
//
// Solusinya: beberapa "ON" tambahan berjarak dekat di awal gerakan saja.
// Irama 1 detik yang diminta dokumen spesifikasi tetap dipertahankan sesudahnya.

uint8_t onBurstLeft = 0;
unsigned long lastOnBurstMs = 0;

#define ON_BURST_MS    120
#define ON_BURST_COUNT 3

// Kirim "ON" bila sudah lewat 1 detik sejak kiriman terakhir.
void maybeSendOn()
{
  if (!moveInProgress) return;

  if (onBurstLeft && (millis() - lastOnBurstMs >= ON_BURST_MS))
  {
    lastOnBurstMs = millis();
    onBurstLeft--;
    sendOn(currentMove);     // sendOn() menyegarkan lastOnMs juga
    return;
  }

  if (millis() - lastOnMs >= ON_INTERVAL_MS)
    sendOn(currentMove);
}

// Telemetri sudut MPU (di luar spesifikasi wajib — dipakai panel sensor GUI).
// Format ASCII: "R=<roll>;P=<pitch>;Y=<yaw>;S=<kode>"
// Kode status lihat mpuStatusCode(). Bidang S ditaruh di belakang supaya
// pembaca lama (regex R=..;P=..;Y=..) tetap cocok.
// Panjang maksimum "R=-180.0;P=-180.0;Y=-180.0;S=4" = 30 byte + NUL = 31,
// masih di bawah batas 32 byte payload NRF24.
void maybeSendTelemetry()
{
  if (millis() - lastTelemetryMs < TELEMETRY_INTERVAL_MS)
    return;
  lastTelemetryMs = millis();

  char tel[32];
  snprintf(tel, sizeof(tel), "R=%.1f;P=%.1f;Y=%.1f;S=%d",
           wrap180(mpu.getAngleX()), wrap180(mpu.getAngleY()),
           wrap180(mpu.getAngleZ()), mpuStatusCode());
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
  mpuUpdate();
  float targetYaw = mpu.getAngleZ();
  unsigned long durationMs = FW_START_MS +
      (unsigned long)((distCm / 100.0f) / ROBOT_SPEED_MPS * 1000.0f);
  unsigned long start = millis();

  Serial.print("FW "); Serial.print(distCm);
  Serial.print(" cm -> "); Serial.print(durationMs); Serial.println(" ms");

  while (millis() - start < durationMs)
  {
    mpuUpdate();

    MoveResult r = checkAbort();
    if (r != MOVE_DONE) return r;

    float err = targetYaw - mpu.getAngleZ();
    while (err >  180) err -= 360;   // normalisasi ke -180..180
    while (err < -180) err += 360;

    // MPU mati -> err dihitung dari sudut palsu. Lebih baik maju lurus dengan
    // dua motor sama besar daripada dikoreksi ke arah yang ngawur.
    int correction = 0;
    if (mpuOk && fabs(err) > HEADING_DEADBAND)
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
  mpuUpdate();
  float startYaw = mpu.getAngleZ();

  // Perkiraan lama putaran bila dijalankan open-loop (tanpa umpan balik yaw).
  unsigned long openLoopMs = (unsigned long)(deg / TURN_RATE_DPS * 1000.0f);
  // Batas waktu pengaman mode closed-loop: 3x perkiraan + 3 detik.
  unsigned long limitMs = openLoopMs * 3 + 3000;
  unsigned long start = millis();

  Serial.print(clockwise ? "CW " : "CCW ");
  Serial.print(deg); Serial.print(" derajat");
  Serial.println(mpuOk ? " (closed-loop yaw)"
                       : " (OPEN-LOOP — MPU mati, sudut akhir tidak dijamin)");

  if (clockwise) spinCW(); else spinCCW();

  while (millis() - start < limitMs)
  {
    mpuUpdate();

    MoveResult r = checkAbort();
    if (r != MOVE_DONE) return r;

    if (!mpuOk)
    {
      // Tanpa yaw yang sah, acuan satu-satunya tinggal waktu. Berhenti di
      // perkiraan open-loop — JANGAN dibiarkan berjalan sampai limitMs, sebab
      // itu 3x lebih lama dan robot akan berputar jauh melewati sudut yang
      // diminta. (Inilah yang terjadi sebelum perbaikan: sudut tidak pernah
      // tercapai karena sensor mati, jadi setiap CW/CCW selalu habis timeout.)
      if (millis() - start >= openLoopMs) break;
      delay(20);
      continue;
    }

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
  clearPendingFin();   // perintah baru datang = FIN sebelumnya sudah diterima

  // "ON" pertama dikirim SEGERA: Pengendali Utama hanya menunggu 1 detik
  // sebelum menganggap perintah gagal dan mengirimnya ulang. Beberapa ulangan
  // rapat menyusul supaya satu paket yang terlewat tidak memicu kirim ulang.
  sendOn(currentMove);
  onBurstLeft = ON_BURST_COUNT;
  lastOnBurstMs = millis();

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
  // Bus di-probe DULU sebelum mpu.begin(). Tanpa probe, library tockn tetap
  // "berhasil" walau tidak ada perangkat sama sekali — ia hanya menulis ke
  // bus tanpa memeriksa ACK, lalu membaca -1 terus-menerus dan melaporkan
  // Roll=-90 / Pitch=+90 / Yaw=-0.0 yang beku (lihat catatan di atas).
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(I2C_HZ);
  Wire.setTimeOut(50);          // ms — bus nyangkut tidak boleh nge-hang robot

  delay(100);                   // beri MPU waktu selesai power-on reset

  checkBusIdle();
  Serial.print("Level diam SDA/SCL: ");
  Serial.println(busIdleHigh
      ? "HIGH (pull-up terpasang, modul bertenaga)"
      : "LOW  <- tidak ada pull-up: modul TIDAK bertenaga / GND-VCC lepas / kabel putus");

  i2cScanReport();              // cetak APA yang benar-benar ada di bus

  // Dicatat sejak boot supaya paket telemetri PERTAMA pun sudah membawa
  // hasil diagnosa ke GUI — robot yang sudah terpasang biasanya tidak bisa
  // lagi dicolok kabel Serial.
  mpuAlt69     = i2cAck(MPU6050_ADDR_ALT);
  mpuAckNoData = mpuProbe();

  // mpuProbeRetry, bukan mpuProbe: probe tunggal sesudah boot sering jatuh
  // TEPAT sebelum MPU selesai power-on reset, lalu firmware berjalan seumur
  // hidup tanpa heading-hold padahal sensornya sehat.
  if (mpuProbeRetry(10, 100))
  {
    uint8_t who = mpuWhoAmI();
    Serial.print("MPU di 0x68, WHO_AM_I = 0x");
    Serial.print(who, HEX);
    // Nomor ini dibaca dari silikon, bukan dari sablon papan. Modul bersablon
    // "MPU-9250/6500" adalah satu desain untuk DUA chip, dan yang terpasang di
    // robot ini adalah 6500 — accel+gyro saja, tanpa magnetometer. Artinya yaw
    // hanya berasal dari integrasi gyro dan akan merayap (terukur 1,1 deg/menit),
    // jadi arah TIDAK boleh diandalkan sebagai acuan mutlak lintas segmen.
    switch (who)
    {
      case 0x68: Serial.println("  -> MPU-6050"); break;
      case 0x70: Serial.println("  -> MPU-6500 (tanpa magnetometer)"); break;
      case 0x71: Serial.println("  -> MPU-9250 (punya magnetometer)"); break;
      case 0x73: Serial.println("  -> MPU-9255 (punya magnetometer)"); break;
      default:   Serial.println("  -> tidak dikenal (klon; biasanya tetap jalan)");
    }

    Serial.println("Kalibrasi gyro — robot harus DIAM & DATAR, jangan disentuh");
    initMPU(true);              // kalibrasi offset gyro: robot harus DIAM & DATAR
    mpuUpdate();
  }
  else
  {
    Serial.println("!! MPU TIDAK menjawab di I2C 0x68");
    Serial.println("   Baca hasil pemindaian di atas:");
    Serial.println("   - KOSONG        -> kabel/daya: SDA=GPIO21, SCL=GPIO22,");
    Serial.println("                      VCC=3.3V, GND robot & MPU HARUS nyambung.");
    Serial.println("   - ada 0x69      -> pin AD0 modul ke-HIGH. Sambungkan AD0 ke GND.");
    Serial.println("   Robot tetap jalan, tapi FW/CW/CCW open-loop tanpa heading-hold.");
  }

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
  mpuUpdate();
  maybeCalibrateWhenIdle();   // menyusul bila MPU baru terdeteksi setelah boot
  maybeResendFin();           // jaring pengaman bila FIN pertama hilang

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
