#include <Wire.h>
#include <MPU6050_tockn.h>

// ================= MPU-9250 =================
// Sketch KALIBRASI & DIAGNOSA MPU-9250 (GY-91 / GY-9250). Bisa dipakai di DUA papan:
//
//   ESP32  (pio run -e mputest   -t upload)  -> SDA = GPIO21, SCL = GPIO22
//   Nano   (pio run -e nanotest  -t upload)  -> SDA = A4,     SCL = A5
//
// KENAPA MASIH PAKAI PUSTAKA MPU6050_tockn?
// Inti accel+gyro MPU-9250 (yaitu MPU-6500) memakai PETA REGISTER YANG SAMA
// dengan MPU-6050: alamat 0x68, ACCEL_XOUT di 0x3B, GYRO_XOUT di 0x43,
// PWR_MGMT_1 di 0x6B, dan skala bawaan yang dipasang pustaka ini (gyro +-500
// dps = 65.5 LSB/dps, accel +-2 g = 16384 LSB/g) berlaku persis sama di 9250.
// Jadi seluruh pembacaan sudut & filter komplementer tockn TETAP SAH. Yang
// BEDA hanya tiga hal, dan tiga itulah yang ditangani sketch ini:
//
//   1. WHO_AM_I (0x75) TIDAK berisi 0x68 lagi:
//        0x71 = MPU-9250   0x73 = MPU-9255   0x70 = MPU-6500 (tanpa magnet)
//        0x68 = MPU-6050 (papan LAMA)        0x69/0x98 = klon murahan
//   2. MPU-9250 punya ACCEL_CONFIG_2 (0x1D) yang tidak ada di 6050. Pustaka
//      tockn tidak pernah menulisnya, jadi filter accel-nya tertinggal di
//      460 Hz — terlalu lebar untuk robot yang kena getaran motor. Di sini
//      diturunkan ke 41 Hz.
//   3. ADA MAGNETOMETER AK8963. Ini alasan utama pindah ke 9250: yaw dari
//      gyro SELALU merayap (drift), sementara heading dari magnet bersifat
//      MUTLAK terhadap utara dan tidak merayap. AK8963 duduk di bus I2C
//      terpisah di dalam chip, jadi harus dibuka dulu lewat mode BYPASS
//      (INT_PIN_CFG 0x37 bit 1) supaya bisa dibaca di alamat 0x0C.
//
// Tujuan file ini: KALIBRASI MPU sebelum dipasang di robot.
// 1. Taruh robot/MPU DIAM & DATAR selama proses calcGyroOffsets.
// 2. Catat nilai offset gyro yang tampil (GyroX/Y/Z Offset).
// 3. Putar-putar modul membentuk angka 8 saat kalibrasi magnet, lalu catat
//    hard-iron offset & soft-iron scale yang tampil.
// 4. Setelah kalibrasi, pantau Yaw (AngleZ) harus stabil ~0 saat diam, dan
//    Heading magnet harus KEMBALI ke angka yang sama setiap kali modul
//    dihadapkan ke arah yang sama.
//
// PENTING — cara membaca hasil yang "aneh":
// Library MPU6050_tockn TIDAK memeriksa ACK, jadi mpu.begin() tetap terlihat
// berhasil walau tidak ada sensor sama sekali di bus. Bila I2C tidak menjawab,
// Wire.read() mengembalikan -1 untuk SEMUA byte sehingga:
//     rawAcc X/Y/Z = -1  ->  acc X/Y/Z = -6.1e-5
//     angleAccX = atan2(accY, accZ + abs(accX)) = atan2(-6.1e-5, 0) = -90.0 PAS
//     angleAccY                                                     = +90.0 PAS
// Hasilnya sudut BEKU di X=-90.00  Y=90.00  Z=-0.00 yang tidak berubah walau
// sensor digoyang. Itu tanda KABEL/BUS, bukan sensor yang perlu dikalibrasi.
// Sketch ini mendeteksi & menamai kondisi itu supaya tidak salah baca.
//
// PENTING soal pin di Arduino Nano: I2C-nya TERPAKU di A4/A5 pada perangkat
// keras ATmega328P dan TIDAK BISA dipindah ke pin lain. Hanya ESP32 yang punya
// GPIO matrix sehingga bisa memetakan I2C ke pin mana saja. Karena itu
// SDA_PIN/SCL_PIN di bawah hanya berlaku untuk ESP32.
//
// PENTING soal DAYA: tidak seperti GY-521 (MPU-6050) yang punya regulator 5V,
// modul MPU-9250 polos adalah 3.3V MURNI. Memberi 5V ke modul semacam itu
// MERUSAK chip. Beri 3.3V kecuali modul jelas-jelas bertuliskan 5V-ready.
//
// WIRING MODUL MPU-9250 POLOS 10 PIN (VCC GND SCL SDA EDA ECL ADO INT NCS FSYNC)
//   VCC   -> 3V3          SCL -> GPIO22 (ESP32) / A5 (Nano)
//   GND   -> GND          SDA -> GPIO21 (ESP32) / A4 (Nano)
//   ADO   -> GND          alamat dikunci di 0x68; mengambang bisa jadi 0x69
//   NCS   -> 3V3          mode dikunci di I2C (lihat bawah)
//   FSYNC -> GND          jangan dibiarkan mengambang
//   EDA/ECL/INT           dibiarkan KOSONG (EDA/ECL = bus bantu, tak dipakai)
//
// STATUS PERAKITAN di robot saat ini: ADO, NCS, dan FSYNC masih JUMPER
// LANGSUNG ke ESP32, belum lewat jalur PCB. Berfungsi normal, tapi kabel
// loncat lebih rentan lepas kena getaran motor — bila salah satunya lepas,
// gejalanya persis "MPU hilang dari bus" seperti yang didiagnosa sketch ini.
//
// HASIL PENGUJIAN MODUL YANG TERPASANG: WHO_AM_I = 0x70, yaitu MPU-6500 —
// papannya bersablon "MPU-9250/6500" (satu desain untuk dua chip) tetapi yang
// terpasang varian TANPA magnetometer. Semua kode AK8963 di bawah tetap ada
// dan menyala sendiri bila suatu saat dipasang modul 9250 asli (WHO_AM_I 0x71).
// Drift yaw terukur 1,1 derajat/menit pada pemantauan diam 10 menit.
//
// DUA PIN YANG TIDAK ADA DI MPU-6050 — dan jadi sebab paling sering "modul
// baru kok malah tidak terdeteksi" padahal susunan lama jalan:
//   ADO : penentu alamat. Di GY-521 ditahan ke GND dari pabrik (0x68); di
//         banyak papan 9250 dibiarkan mengambang atau ditahan ke VCC (0x69).
//   NCS : penentu antarmuka. MPU-9250 MENGUNCI mode saat listrik masuk — bila
//         NCS terbaca LOW pada saat itu, chip masuk mode SPI dan I2C-nya MATI
//         TOTAL di semua alamat. MPU-6050 tidak punya perilaku ini.

#if defined(ARDUINO_ARCH_ESP32)
  #define SDA_PIN 21          // hanya ESP32: I2C bisa dipetakan ke GPIO mana saja
  #define SCL_PIN 22
#else
  #define SDA_PIN A4          // Nano: TERPAKU di perangkat keras, sekadar
  #define SCL_PIN A5          // dinamai agar pemulihan bus bisa dipakai juga
#endif

#define I2C_HZ  100000UL

#define ACC_MAG_MIN 0.30f   // |a| wajar (g) — sensor sehat selalu merasakan ~1 g
#define ACC_MAG_MAX 3.00f

// --- Register MPU-9250 yang TIDAK disentuh pustaka tockn ------------------
#define MPU_ADDR            MPU6050_ADDR   // 0x68, sama persis dengan 6050
#define REG_WHO_AM_I        0x75
#define REG_ACCEL_CONFIG_2  0x1D           // hanya ada di 9250/6500
#define REG_INT_PIN_CFG     0x37
#define REG_USER_CTRL       0x6A

// --- Magnetometer AK8963 (di dalam paket MPU-9250) ------------------------
#define AK8963_ADDR   0x0C
#define AK_WIA        0x00     // harus berisi 0x48
#define AK_ST1        0x02     // bit0 DRDY
#define AK_HXL        0x03     // data 6 byte, little-endian
#define AK_ST2        0x09     // bit3 HOFL (overflow); WAJIB dibaca tiap sampel
#define AK_CNTL1      0x0A
#define AK_CNTL2      0x0B
#define AK_ASAX       0x10     // fuse ROM: faktor sensitivitas pabrik

// 16-bit, +-4912 uT full scale -> 0.15 uT per LSB
#define AK_UT_PER_LSB     (4912.0f / 32760.0f)
#define AK_MODE_POWERDOWN 0x00
#define AK_MODE_FUSE      0x0F
#define AK_MODE_CONT2_16  0x16   // continuous 100 Hz, keluaran 16-bit

#define MAG_CAL_MS  20000UL      // lama kalibrasi magnet (putar angka 8)

// Deklinasi magnet: selisih utara-magnet vs utara-sebenarnya. Untuk tambak di
// Indonesia nilainya kecil (sekitar 0..1 derajat), jadi 0 sudah cukup. Heading
// untuk robot toh hanya perlu KONSISTEN, bukan benar secara geografis.
#define MAG_DECLINATION_DEG 0.0f

MPU6050 mpu(Wire);

uint8_t chipId       = 0xFF;           // isi WHO_AM_I
bool    gyroCalOk    = false;          // offset gyro sah (papan benar2 diam)?
bool    magPresent   = false;          // AK8963 menjawab & sudah dinyalakan?
float   magAsa[3]    = {1, 1, 1};      // koreksi sensitivitas pabrik
float   magOffset[3] = {0, 0, 0};      // hard-iron (uT)
float   magScale[3]  = {1, 1, 1};      // soft-iron

// ===================== Utilitas I2C mentah =====================
// Ditulis sendiri (bukan lewat pustaka) karena AK8963 bukan perangkat yang
// dikenal MPU6050_tockn sama sekali.

bool i2cWrite8(uint8_t addr, uint8_t reg, uint8_t val)
{
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

// Mengembalikan false bila bus tidak menjawab — INI yang membedakan "sensor
// bilang 0" dari "tidak ada sensor". Pustaka tockn tidak bisa membedakannya.
bool i2cReadN(uint8_t addr, uint8_t reg, uint8_t *buf, uint8_t n)
{
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)addr, (int)n) != n) return false;
  for (uint8_t i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}

uint8_t i2cRead8(uint8_t addr, uint8_t reg)
{
  uint8_t v = 0xFF;
  i2cReadN(addr, reg, &v, 1);
  return v;
}

// Apakah ada perangkat yang meng-ACK alamat 0x68?
bool mpuProbe()
{
  Wire.beginTransmission(MPU_ADDR);
  return Wire.endTransmission() == 0;
}

// Nama chip dari WHO_AM_I. Membedakan 9250 asli, 6500 (accel+gyro saja, TANPA
// magnet), 6050 lama, dan klon — supaya "kok magnetnya tidak terbaca?" langsung
// terjawab di baris pertama serial, bukan setelah setengah jam menebak.
const __FlashStringHelper *chipName(uint8_t who)
{
  switch (who)
  {
    case 0x71: return F("MPU-9250 (asli, ada magnetometer)");
    case 0x73: return F("MPU-9255 (ada magnetometer)");
    case 0x70: return F("MPU-6500 / modul '9250' PALSU — TIDAK ada magnetometer");
    case 0x68: return F("MPU-6050 (modul LAMA, tidak ada magnetometer)");
    case 0x69: return F("klon MPU-6050");
    case 0xFF: return F("TIDAK MENJAWAB");
    default:   return F("tidak dikenal (klon; accel+gyro biasanya tetap jalan)");
  }
}

// Data yang keluar masuk akal, atau sekadar sisa pembacaan gagal?
bool mpuHealthy()
{
  if (mpu.getRawAccX() == -1 && mpu.getRawAccY() == -1 && mpu.getRawAccZ() == -1)
    return false;
  float ax = mpu.getAccX(), ay = mpu.getAccY(), az = mpu.getAccZ();
  float mag = sqrt(ax * ax + ay * ay + az * az);
  return (mag > ACC_MAG_MIN) && (mag < ACC_MAG_MAX);
}

// ===================== Magnetometer AK8963 =====================

// AK8963 duduk di bus I2C AUXILIARY di dalam MPU-9250, jadi dari luar ia tidak
// terlihat sampai kita memerintahkan MPU jadi "kabel sambungan": USER_CTRL
// I2C_MST_EN dimatikan, lalu INT_PIN_CFG BYPASS_EN dinyalakan. Setelah itu
// 0x0C muncul di bus I2C yang sama dengan 0x68.
// Harus dipanggil SETELAH mpu.begin() — chip yang masih tidur tidak melayani.
bool magBegin()
{
  i2cWrite8(MPU_ADDR, REG_USER_CTRL, 0x00);   // lepas master I2C internal
  i2cWrite8(MPU_ADDR, REG_INT_PIN_CFG, 0x02); // BYPASS_EN = 1
  delay(10);

  if (i2cRead8(AK8963_ADDR, AK_WIA) != 0x48) return false;

  i2cWrite8(AK8963_ADDR, AK_CNTL2, 0x01);     // soft reset
  delay(50);

  // Faktor sensitivitas per-sumbu dibakar di pabrik dan HANYA bisa dibaca
  // dalam mode FUSE ROM. Tanpa koreksi ini ketiga sumbu punya penguatan
  // berbeda, dan heading jadi lonjong (meleset beberapa derajat).
  i2cWrite8(AK8963_ADDR, AK_CNTL1, AK_MODE_POWERDOWN);
  delay(10);
  i2cWrite8(AK8963_ADDR, AK_CNTL1, AK_MODE_FUSE);
  delay(10);

  uint8_t asa[3];
  if (!i2cReadN(AK8963_ADDR, AK_ASAX, asa, 3)) return false;
  for (uint8_t i = 0; i < 3; i++)
    magAsa[i] = ((float)asa[i] - 128.0f) / 256.0f + 1.0f;

  i2cWrite8(AK8963_ADDR, AK_CNTL1, AK_MODE_POWERDOWN);
  delay(10);
  i2cWrite8(AK8963_ADDR, AK_CNTL1, AK_MODE_CONT2_16);
  delay(10);
  return true;
}

// Keluaran dalam uT, SUDAH diputar ke sumbu accel/gyro.
// Di dalam MPU-9250 die magnet dipasang miring terhadap die accel/gyro:
//     magnet X  = accel  Y
//     magnet Y  = accel  X
//     magnet Z  = accel -Z
// Lupa memutar ini adalah penyebab paling umum heading yang "berputar ke arah
// yang salah" atau tidak nyambung dengan Yaw gyro.
bool magReadRaw(float *mx, float *my, float *mz)
{
  if (!magPresent) return false;
  if ((i2cRead8(AK8963_ADDR, AK_ST1) & 0x01) == 0) return false;  // belum siap

  uint8_t b[7];   // 6 byte data + ST2; ST2 WAJIB ikut terbaca supaya AK8963
                  // menandai sampel selesai dan menyiapkan yang berikutnya.
  if (!i2cReadN(AK8963_ADDR, AK_HXL, b, 7)) return false;
  if (b[6] & 0x08) return false;                                  // overflow

  int16_t rawX = (int16_t)((uint16_t)b[1] << 8 | b[0]);           // little-endian!
  int16_t rawY = (int16_t)((uint16_t)b[3] << 8 | b[2]);
  int16_t rawZ = (int16_t)((uint16_t)b[5] << 8 | b[4]);

  float ax = rawX * AK_UT_PER_LSB * magAsa[0];
  float ay = rawY * AK_UT_PER_LSB * magAsa[1];
  float az = rawZ * AK_UT_PER_LSB * magAsa[2];

  *mx =  ay;    // ke kerangka accel/gyro
  *my =  ax;
  *mz = -az;
  return true;
}

// Setelah dikoreksi hard-iron (besi/magnet yang IKUT berputar bersama sensor,
// misal sekrup & motor) dan soft-iron (pelenturan medan oleh logam sekitar).
bool magRead(float *mx, float *my, float *mz)
{
  float x, y, z;
  if (!magReadRaw(&x, &y, &z)) return false;
  *mx = (x - magOffset[0]) * magScale[0];
  *my = (y - magOffset[1]) * magScale[1];
  *mz = (z - magOffset[2]) * magScale[2];
  return true;
}

// Kalibrasi hard/soft-iron: kumpulkan min & max tiap sumbu sambil modul
// diputar ke SEGALA arah. TANPA ini heading bisa meleset puluhan derajat —
// dan di robot, besi/motor di sekitar sensor membuatnya WAJIB diulang setelah
// modul terpasang di badan robot, bukan cuma di atas meja.
void magCalibrate()
{
  float mn[3] = { 1e6f,  1e6f,  1e6f};
  float mx[3] = {-1e6f, -1e6f, -1e6f};
  float v[3];
  uint16_t n = 0;

  Serial.println();
  Serial.println(F("=== KALIBRASI MAGNET (AK8963) ==="));
  Serial.print(F("Putar modul membentuk angka 8 ke SEGALA arah selama "));
  Serial.print(MAG_CAL_MS / 1000); Serial.println(F(" detik..."));
  Serial.println(F("Jauhkan dari meja besi, laptop, speaker, dan kabel daya."));

  unsigned long t0 = millis();
  unsigned long lastDot = t0;
  while (millis() - t0 < MAG_CAL_MS)
  {
    if (magReadRaw(&v[0], &v[1], &v[2]))
    {
      for (uint8_t i = 0; i < 3; i++)
      {
        if (v[i] < mn[i]) mn[i] = v[i];
        if (v[i] > mx[i]) mx[i] = v[i];
      }
      n++;
    }
    if (millis() - lastDot >= 1000) { Serial.print(F(".")); lastDot += 1000; }
    delay(12);          // AK8963 mode 2 = 100 Hz, jangan dipacu lebih cepat
  }
  Serial.println();

  if (n < 100)
  {
    Serial.println(F("!! Sampel magnet terlalu sedikit — kalibrasi DIBATALKAN."));
    Serial.println(F("   (offset tetap 0; heading akan meleset)"));
    return;
  }

  // Hard-iron = titik tengah bola data. Soft-iron = penyamaan jari-jari tiap
  // sumbu terhadap jari-jari rata-rata.
  float rad[3], radAvg = 0;
  for (uint8_t i = 0; i < 3; i++)
  {
    magOffset[i] = (mx[i] + mn[i]) / 2.0f;
    rad[i]       = (mx[i] - mn[i]) / 2.0f;
    radAvg      += rad[i];
  }
  radAvg /= 3.0f;
  for (uint8_t i = 0; i < 3; i++)
    magScale[i] = (rad[i] > 1.0f) ? (radAvg / rad[i]) : 1.0f;

  Serial.print(F("Sampel: ")); Serial.println(n);
  Serial.println(F("Hard-iron offset (uT):"));
  Serial.print(F("  X = ")); Serial.println(magOffset[0], 2);
  Serial.print(F("  Y = ")); Serial.println(magOffset[1], 2);
  Serial.print(F("  Z = ")); Serial.println(magOffset[2], 2);
  Serial.println(F("Soft-iron scale:"));
  Serial.print(F("  X = ")); Serial.println(magScale[0], 3);
  Serial.print(F("  Y = ")); Serial.println(magScale[1], 3);
  Serial.print(F("  Z = ")); Serial.println(magScale[2], 3);

  // Medan bumi 25-65 uT. Jauh di luar itu artinya ada logam/magnet menempel
  // di sensor, dan angka kalibrasinya tidak bisa dipercaya.
  Serial.print(F("Kuat medan rata-rata: ")); Serial.print(radAvg, 1);
  Serial.println(F(" uT  (wajar: 25-65 uT)"));
  if (radAvg < 20.0f || radAvg > 80.0f)
    Serial.println(F("   !! DI LUAR WAJAR — ada logam/magnet dekat sensor, ulangi."));
}

// Heading dengan kompensasi kemiringan. Tanpa kompensasi, memiringkan sensor
// 10 derajat saja sudah menggeser heading belasan derajat — dan robot di air
// TIDAK PERNAH benar-benar datar.
// Bila hasilnya berputar berlawanan dengan gerak nyata, balik tanda pada atan2
// di bawah (JANGAN tukar sumbu — pemetaan sumbu sudah benar di magReadRaw).
float magHeadingDeg(float mx, float my, float mz)
{
  float roll  = mpu.getAngleX() * DEG_TO_RAD;
  float pitch = mpu.getAngleY() * DEG_TO_RAD;

  float xh = mx * cos(pitch) + mz * sin(pitch);
  float yh = mx * sin(roll) * sin(pitch) + my * cos(roll) - mz * sin(roll) * cos(pitch);

  float h = atan2(yh, xh) * RAD_TO_DEG + MAG_DECLINATION_DEG;
  if (h < 0)       h += 360.0f;
  if (h >= 360.0f) h -= 360.0f;
  return h;
}

// ===================== TRIASE BUS I2C =====================
// Beberapa modul yang gagal dengan gejala SAMA PERSIS hampir tidak pernah
// berarti beberapa chip rusak sekaligus — hampir selalu satu sebab sistematis.
// Masalahnya, tiga sebab di bawah ini tampil IDENTIK di layar ("tidak menjawab
// di 0x68") padahal perbaikannya berbeda jauh:
//
//   A. Modul ada, tapi di alamat 0x69  -> pin AD0/SDO ke-HIGH
//   B. Modul tidak bertenaga           -> jalur SDA/SCL diam di LOW
//   C. Modul bertenaga tapi bisu total -> chip masuk mode SPI, atau sudah mati
//
// Ketiganya dipisahkan di sini supaya tidak jadi tebak-tebakan.

bool busIdleHigh = true;    // jalur SDA/SCL diam di HIGH (berarti ada pull-up)?

bool i2cAck(uint8_t addr)
{
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

// Bus I2C yang SEHAT diam di HIGH, ditahan resistor pull-up pada modul (modul
// MPU umumnya punya 4k7 ke VCC). Kalau kedua jalur diam di LOW, berarti tidak
// ada pull-up sama sekali -> modul tidak dapat tegangan, GND-nya lepas, atau
// kabel/solder SDA-SCL putus. Ini memisahkan "modul mati listrik" dari "modul
// hidup tapi tidak menjawab".
void checkBusIdle()
{
#if defined(ARDUINO_ARCH_ESP32)
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
#else
  // ATmega328 tidak punya pull-down internal, jadi uji ini tidak bisa
  // dipercaya di Nano. Anggap saja HIGH supaya tidak salah menuduh.
  busIdleHigh = true;
#endif
}

// Melepaskan bus yang DIKUNCI oleh slave. Kalau ESP32 di-reset di TENGAH
// transaksi I2C — saat upload, saat tombol EN ditekan, atau saat monitor serial
// menarik jalur RTS — MPU TIDAK ikut ter-reset karena listriknya tidak putus.
// Ia masih menunggu sisa pulsa clock dan menahan SDA tetap LOW, sehingga SEMUA
// transaksi berikutnya menggantung, termasuk pemindaian bus (gejalanya: serial
// berhenti tepat setelah baris "Pemindaian bus I2C" dan tidak pernah lanjut).
//
// Obatnya adalah urutan baku pemulihan bus I2C: kirim hingga 9 pulsa SCL secara
// manual supaya slave menyelesaikan byte yang tertunda dan melepas SDA, lalu
// tutup dengan kondisi STOP. Sembilan karena satu byte = 8 bit + 1 ACK.
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

  // Kondisi STOP: SDA naik SELAGI SCL HIGH.
  pinMode(SDA_PIN, OUTPUT);
  digitalWrite(SDA_PIN, LOW);   delayMicroseconds(5);
  digitalWrite(SCL_PIN, HIGH);  delayMicroseconds(5);
  digitalWrite(SDA_PIN, HIGH);  delayMicroseconds(5);

  pinMode(SDA_PIN, INPUT);
  pinMode(SCL_PIN, INPUT);

#if defined(ARDUINO_ARCH_ESP32)
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setTimeOut(50);
#else
  Wire.begin();
#endif
  Wire.setClock(I2C_HZ);
}

// Probe yang diulang beberapa kali sebelum menyerah. MPU butuh waktu
// menyelesaikan power-on reset, dan probe pertama sesudah boot sering jatuh
// TEPAT sebelum chip siap menjawab — menghasilkan laporan "tidak ada MPU"
// yang langsung dibantah oleh pemindaian bus beberapa milidetik kemudian.
bool mpuProbeRetry(uint8_t tries, uint16_t gapMs)
{
  for (uint8_t i = 0; i < tries; i++)
  {
    if (mpuProbe()) return true;
    delay(gapMs);
  }
  return false;
}

// Sapu seluruh bus & laporkan apa yang BENAR-BENAR ada di sana.
uint8_t i2cScanReport()
{
  uint8_t found = 0;
  Serial.println(F("-- Pemindaian bus I2C --"));
  for (uint8_t addr = 1; addr < 127; addr++)
  {
    if (!i2cAck(addr)) continue;
    found++;
    Serial.print(F("   ADA perangkat di 0x"));
    if (addr < 16) Serial.print('0');
    Serial.print(addr, HEX);
    if (addr == 0x68) Serial.print(F("  <- MPU (AD0 = GND) BENAR"));
    if (addr == 0x69) Serial.print(F("  <- MPU tapi AD0 = HIGH!"));
    if (addr == 0x0C) Serial.print(F("  <- AK8963 (magnetometer)"));
    if (addr == 0x76 || addr == 0x77) Serial.print(F("  <- BMP280 (modul GY-91)"));
    Serial.println();
  }
  if (found == 0)
    Serial.println(F("   (KOSONG — tidak ada satu pun perangkat menjawab)"));
  return found;
}

// Sebutkan penyebab yang PALING MUNGKIN berdasarkan fakta di bus, bukan daftar
// panjang semua kemungkinan.
void printDiagnosis()
{
  // URUTAN PENTING: periksa kesehatan jalur DULU, baru memindai.
  // Memindai 126 alamat di atas bus yang tersangkut membuat SETIAP alamat
  // menunggu habis waktu tunggunya — pemindaian bisa makan lebih dari dua
  // menit dan tampak seperti program yang mati total. Padahal kalau jalurnya
  // diam di LOW, sudah pasti tidak ada yang akan menjawab. Jadi: jangan
  // dipindai, langsung simpulkan.
  checkBusIdle();

  if (!busIdleHigh)
  {
    Serial.println(F(">> SEBAB: SDA & SCL diam di LOW — tidak ada pull-up hidup."));
    Serial.println(F("   Modul TIDAK BERTENAGA atau jalurnya putus."));
    Serial.println(F("   (pemindaian bus dilewati — di bus mati hasilnya pasti"));
    Serial.println(F("    kosong dan hanya membuat program tampak menggantung)"));
    Serial.println(F("   PERBAIKAN: cek VCC modul (3.3V) & GND benar-benar nyambung,"));
    Serial.println(F("   dan solderan header SDA/SCL/VCC/GND tidak retak."));
    return;
  }

  uint8_t found = i2cScanReport();

  // 0x68 DULU. Kalau pemindaian menemukannya, semua cabang di bawah keliru —
  // dan melaporkan "ada perangkat lain tapi MPU tidak" tepat setelah baris
  // "ADA perangkat di 0x68" hanya membuat pembaca ragu pada alat ukurnya.
  if (i2cAck(MPU_ADDR))
  {
    Serial.println(F(">> MPU SEBENARNYA ADA di 0x68 — probe pertama kepagian,"));
    Serial.println(F("   chip belum selesai power-on reset saat ditanya."));
    Serial.println(F("   Tidak ada yang perlu diperbaiki; program lanjut sendiri."));
    return;
  }

  if (i2cAck(0x69))
  {
    Serial.println(F(">> SEBAB: modul ada, tapi di alamat 0x69 (bukan 0x68)."));
    Serial.println(F("   Pin AD0/SDO ke-HIGH. Ini BEDA dari modul GY-521 lama:"));
    Serial.println(F("   banyak papan MPU-9250 menahan AD0/SDO ke VCC dari pabrik,"));
    Serial.println(F("   jadi alamat bawaannya 0x69 — sementara GY-521 (MPU-6050)"));
    Serial.println(F("   menahannya ke GND sehingga 0x68."));
    Serial.println(F("   PERBAIKAN: sambungkan pin AD0/SDO modul ke GND."));
    Serial.println(F("   Pustaka MPU6050_tockn mematok 0x68 di dalam kodenya, jadi"));
    Serial.println(F("   ini HARUS dibetulkan di kabel, bukan di program."));
  }
  else if (found > 0)
  {
    Serial.println(F(">> Bus HIDUP dan ada perangkat lain menjawab, tapi MPU tidak."));
    Serial.println(F("   Kalau yang menjawab hanya 0x76/0x77 (BMP280 di GY-91),"));
    Serial.println(F("   berarti modulnya bertenaga & bus baik — hanya chip MPU-nya"));
    Serial.println(F("   yang bisu. Lihat sebab mode SPI di bawah."));
    Serial.println(F("   PERBAIKAN: pastikan pin NCS/CS modul disambung ke 3.3V."));
  }
  else
  {
    Serial.println(F(">> Bus diam di HIGH (pull-up modul hidup = modul BERTENAGA),"));
    Serial.println(F("   tapi tidak ada satu pun alamat menjawab. Dua kemungkinan:"));
    Serial.println(F("   1. Chip masuk MODE SPI. MPU-9250 mengunci mode saat menyala:"));
    Serial.println(F("      bila pin NCS/CS terbaca LOW ketika listrik masuk, I2C-nya"));
    Serial.println(F("      MATI TOTAL di semua alamat. MPU-6050 tidak punya perilaku"));
    Serial.println(F("      ini, jadi gejalanya baru muncul setelah ganti ke 9250."));
    Serial.println(F("      PERBAIKAN: sambungkan NCS/CS ke 3.3V (bukan dibiarkan"));
    Serial.println(F("      mengambang), lalu cabut-pasang daya."));
    Serial.println(F("   2. SDA & SCL tertukar."));
  }

  Serial.println(F("   Cek juga: modul MPU-9250 polos adalah 3.3V MURNI — bila"));
  Serial.println(F("   sempat diberi 5V, chip-nya rusak permanen."));
  Serial.println(F("-- Wiring modul 9250 polos 10 pin --"));
#if defined(ARDUINO_ARCH_ESP32)
  Serial.println(F("   VCC->3V3  GND->GND  SCL->GPIO22  SDA->GPIO21"));
#else
  Serial.println(F("   VCC->3V3  GND->GND  SCL->A5  SDA->A4  (Nano terpaku)"));
#endif
  Serial.println(F("   ADO->GND (kunci 0x68)   NCS->3V3 (kunci mode I2C)"));
  Serial.println(F("   FSYNC->GND              EDA/ECL/INT dibiarkan KOSONG"));
  Serial.println(F("   ADO & NCS tidak ada di MPU-6050 — dua pin inilah yang"));
  Serial.println(F("   paling sering bikin modul baru diam padahal wiring lama jalan."));
}

// ===================== KALIBRASI GYRO YANG TIDAK BISA MENGGANTUNG ==========
// Pengganti mpu.calcGyroOffsets(). Pustaka tockn menembak 3000 transaksi I2C
// beruntun TANPA memeriksa satu pun kegagalan: sekali bus tersendat, ia
// menggantung selamanya dan program tidak pernah sampai ke loop().
//
// Versi ini berbeda dalam tiga hal:
//   1. Tiap pembacaan diperiksa. Bus yang mati dilaporkan, bukan digantung.
//   2. Bus yang terkunci dicoba dibebaskan, lalu pengambilan sampel lanjut.
//   3. Simpangan gyro selama kalibrasi ikut diukur. Kalau papan BERGERAK saat
//      kalibrasi, offset yang dihasilkan salah dan yaw langsung merayap cepat
//      — dulu ini tampil sebagai "drift sensor" padahal cuma tangan yang
//      menyenggol. Sekarang dikatakan terus terang.

#define GYRO_CAL_SAMPLES   600
#define GYRO_LSB_PER_DPS   65.5f    // tockn memasang GYRO_CONFIG = +-500 dps
#define GYRO_STILL_MAX_DPS 3.0f     // rentang wajar saat benar-benar diam

bool calcGyroOffsetsSafe()
{
  float sum[3] = {0, 0, 0};
  float mn[3]  = { 9999,  9999,  9999};
  float mx[3]  = {-9999, -9999, -9999};
  uint16_t ok = 0, fail = 0;

  Serial.println(F("Kalibrasi gyro — JANGAN sentuh papan..."));

  for (uint16_t i = 0; i < GYRO_CAL_SAMPLES; i++)
  {
    uint8_t b[6];
    if (!i2cReadN(MPU_ADDR, 0x43, b, 6))    // 0x43 = GYRO_XOUT_H
    {
      if (++fail > 60)
      {
        Serial.println();
        Serial.println(F("!! Kalibrasi DIBATALKAN — bus I2C gagal terus."));
        return false;
      }
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
    if (ok % 150 == 0) Serial.print('.');
    delay(3);
  }
  Serial.println();

  if (ok < GYRO_CAL_SAMPLES / 2)
  {
    Serial.println(F("!! Sampel gyro terlalu sedikit — kalibrasi tidak sah."));
    return false;
  }

  mpu.setGyroOffsets(sum[0] / ok, sum[1] / ok, sum[2] / ok);

  Serial.print(F("Sampel sah: ")); Serial.print(ok);
  Serial.print(F("   gagal: "));   Serial.println(fail);
  Serial.println(F("Gyro offset (deg/s):"));
  Serial.print(F("  X = ")); Serial.println(sum[0] / ok, 3);
  Serial.print(F("  Y = ")); Serial.println(sum[1] / ok, 3);
  Serial.print(F("  Z = ")); Serial.println(sum[2] / ok, 3);

  // Rentang = bukti papan benar-benar diam atau tidak. Ini yang memisahkan
  // "sensornya jelek" dari "papannya kesenggol saat dikalibrasi".
  float worst = 0;
  for (uint8_t a = 0; a < 3; a++)
    if (mx[a] - mn[a] > worst) worst = mx[a] - mn[a];

  Serial.print(F("Simpangan selama kalibrasi: "));
  Serial.print(worst, 2);
  Serial.println(F(" deg/s"));

  if (worst > GYRO_STILL_MAX_DPS)
  {
    Serial.println(F("!! PAPAN BERGERAK saat kalibrasi — offset ini TIDAK SAH."));
    Serial.println(F("   Yaw akan merayap cepat. Letakkan papan datar di meja,"));
    Serial.println(F("   lepas tangan sepenuhnya, lalu reset dan ulangi."));
    return false;
  }

  Serial.println(F("Papan cukup diam — offset sah."));
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(200);

#if defined(ARDUINO_ARCH_ESP32)
  Wire.begin(SDA_PIN, SCL_PIN);   // ESP32: pin I2C bebas dipilih
  Wire.setTimeOut(50);            // ms — bus nyangkut tidak boleh nge-hang
#else
  Wire.begin();                   // AVR/Nano: selalu A4=SDA, A5=SCL
#endif
  Wire.setClock(I2C_HZ);

  Serial.println();
  Serial.println(F("=== KALIBRASI MPU-9250 ==="));
#if defined(ARDUINO_ARCH_ESP32)
  Serial.println(F("Papan: ESP32  (SDA=GPIO21, SCL=GPIO22)"));
#else
  Serial.println(F("Papan: Arduino Nano  (SDA=A4, SCL=A5)"));
#endif

  // Bebaskan bus SEBELUM transaksi pertama. ESP32 sering di-reset tanpa MPU
  // ikut mati (upload, tombol EN, RTS dari serial monitor), dan MPU yang
  // tertinggal di tengah transaksi akan menahan SDA sampai dibebaskan.
  i2cBusRecover();

  delay(100);       // beri MPU waktu menyelesaikan power-on reset-nya sendiri

  // Probe DULU — percuma mengkalibrasi bus yang tidak menjawab. Diagnosa
  // dicetak SEKALI dengan lengkap, lalu hanya diulang tiap 10 detik: pesan
  // yang membanjir tiap detik justru menutupi hasil pemindaian bus.
  if (!mpuProbeRetry(10, 100))    // beri 1 detik sebelum menyerah
  {
    Serial.println();
    Serial.println(F("!! MPU-9250 TIDAK menjawab di I2C 0x68."));
    printDiagnosis();
    Serial.println(F("   (menunggu MPU tersambung...)"));

    while (!mpuProbe())
    {
      delay(10000);
      i2cBusRecover();            // barangkali sekadar bus terkunci
      if (mpuProbeRetry(5, 100)) break;
      Serial.println();
      Serial.println(F("-- masih belum menjawab, memindai ulang --"));
      printDiagnosis();
    }
    Serial.println(F("MPU akhirnya menjawab."));
  }

  chipId = i2cRead8(MPU_ADDR, REG_WHO_AM_I);
  Serial.print(F("Terdeteksi di 0x68. WHO_AM_I = 0x"));
  if (chipId < 16) Serial.print('0');
  Serial.print(chipId, HEX);
  Serial.print(F("  -> ")); Serial.println(chipName(chipId));

  Serial.println(F("Pastikan MPU DIAM & DATAR. Jangan disentuh..."));

  mpu.begin();

  // Register ini tidak dikenal tockn (tidak ada di 6050). DLPF accel 41 Hz
  // jauh lebih tenang terhadap getaran motor daripada 460 Hz bawaan.
  if (chipId != 0x68)
    i2cWrite8(MPU_ADDR, REG_ACCEL_CONFIG_2, 0x03);

  // BUKAN mpu.calcGyroOffsets() — lihat catatan di calcGyroOffsetsSafe().
  gyroCalOk = calcGyroOffsetsSafe();

  // --- Magnetometer ---
  magPresent = magBegin();
  if (magPresent)
  {
    Serial.println(F("AK8963 terdeteksi di 0x0C (mode bypass, 100 Hz, 16-bit)."));
    Serial.print(F("Faktor sensitivitas pabrik: "));
    Serial.print(magAsa[0], 3); Serial.print(F(" / "));
    Serial.print(magAsa[1], 3); Serial.print(F(" / "));
    Serial.println(magAsa[2], 3);
    magCalibrate();
  }
  else
  {
    Serial.println(F("!! AK8963 TIDAK menjawab di 0x0C — heading magnet DIMATIKAN."));
    if (chipId == 0x70)
    {
      Serial.println(F("   WHO_AM_I 0x70 = chip MPU-6500: modul ini memang TIDAK"));
      Serial.println(F("   punya magnetometer (dijual sebagai '9250' tapi bukan)."));
    }
    Serial.println(F("   Kalau chip-nya memang 9250: pastikan pin NCS modul GY-91"));
    Serial.println(F("   HIGH, dan tidak ada kode lain yang menyalakan I2C master."));
  }

  Serial.println(F("-------------------------------------"));
  Serial.println(F("Pantau angle. Yaw(Z) harus ~0 saat diam."));
  if (!gyroCalOk)
    Serial.println(F("!! OFFSET GYRO TIDAK SAH — drift di bawah JANGAN dipercaya."));
  if (magPresent)
  {
    Serial.println(F("Head = heading magnet (MUTLAK, tidak merayap). Bandingkan"));
    Serial.println(F("dengan Yaw gyro: selisih yang menumpuk = drift gyro."));
  }
  delay(1000);
}

void loop() {
  mpu.update();

  // Kalau bus mati di tengah jalan, katakan apa adanya — jangan biarkan
  // pembaca mengira X=-90.00 / Y=90.00 itu sudut sungguhan.
  if (!mpuHealthy())
  {
    Serial.println(F("!! MPU TIDAK TERBACA — angka di bawah BEKU, bukan ukuran"));
    i2cBusRecover();      // paling sering cuma bus terkunci, bukan modul lepas
  }

  Serial.print(F("Angle -> X: "));
  Serial.print(mpu.getAngleX());
  Serial.print(F("\tY: "));
  Serial.print(mpu.getAngleY());
  Serial.print(F("\tZ(Yaw): "));
  Serial.print(mpu.getAngleZ());

  Serial.print(F("   | Gyro -> X: "));
  Serial.print(mpu.getGyroX());
  Serial.print(F("\tY: "));
  Serial.print(mpu.getGyroY());
  Serial.print(F("\tZ: "));
  Serial.print(mpu.getGyroZ());

  if (magPresent)
  {
    float mx, my, mz;
    if (magRead(&mx, &my, &mz))
    {
      Serial.print(F("   | Mag(uT) -> X: "));
      Serial.print(mx, 1);
      Serial.print(F("\tY: "));
      Serial.print(my, 1);
      Serial.print(F("\tZ: "));
      Serial.print(mz, 1);
      Serial.print(F("\tHead: "));
      Serial.print(magHeadingDeg(mx, my, mz), 1);
    }
    else
    {
      Serial.print(F("   | Mag: (sampel belum siap / overflow)"));
    }
  }
  Serial.println();

  delay(200);
}
