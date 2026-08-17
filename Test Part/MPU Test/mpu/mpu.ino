#include <Wire.h>
#include <MPU6050_tockn.h>

// ================= MPU =================
// Sketch KALIBRASI & DIAGNOSA MPU6050. Bisa dipakai di DUA papan:
//
//   ESP32  (pio run -e mputest   -t upload)  -> SDA = GPIO21, SCL = GPIO22
//   Nano   (pio run -e nanotest  -t upload)  -> SDA = A4,     SCL = A5
//
// PENTING soal pin di Arduino Nano: I2C-nya TERPAKU di A4/A5 pada perangkat
// keras ATmega328P dan TIDAK BISA dipindah ke pin lain. Hanya ESP32 yang punya
// GPIO matrix sehingga bisa memetakan I2C ke pin mana saja. Karena itu
// SDA_PIN/SCL_PIN di bawah hanya berlaku untuk ESP32.
//
// Tujuan file ini: KALIBRASI MPU sebelum dipasang di robot.
// 1. Taruh robot/MPU DIAM & DATAR selama proses calcGyroOffsets.
// 2. Catat nilai offset gyro yang tampil (GyroX/Y/Z Offset).
// 3. Setelah kalibrasi, pantau Yaw (AngleZ) harus stabil ~0 saat diam
//    dan berubah wajar saat diputar.
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

#if defined(ARDUINO_ARCH_ESP32)
  #define SDA_PIN 21          // hanya ESP32: I2C bisa dipetakan ke GPIO mana saja
  #define SCL_PIN 22
#endif

#define I2C_HZ  100000UL

#define ACC_MAG_MIN 0.30f   // |a| wajar (g) — sensor sehat selalu merasakan ~1 g
#define ACC_MAG_MAX 3.00f

MPU6050 mpu(Wire);

// Apakah ada perangkat yang meng-ACK alamat 0x68?
bool mpuProbe()
{
  Wire.beginTransmission(MPU6050_ADDR);
  return Wire.endTransmission() == 0;
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

// Petunjuk wiring yang benar untuk papan yang sedang dipakai.
void printWiringHint()
{
#if defined(ARDUINO_ARCH_ESP32)
  Serial.println("   cek: SDA=GPIO21, SCL=GPIO22, VCC=3.3V, GND tersambung,");
#else
  Serial.println("   cek: SDA=A4, SCL=A5 (TERPAKU di Nano, tidak bisa pin lain),");
  Serial.println("        VCC modul ke 5V, GND tersambung,");
#endif
  Serial.println("        AD0 ke GND (alamat 0x68), kabel I2C jangan terlalu");
  Serial.println("        panjang, dan jauhkan dari kabel daya ESC.");
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
  Serial.println("=== KALIBRASI MPU6050 ===");
#if defined(ARDUINO_ARCH_ESP32)
  Serial.println("Papan: ESP32  (SDA=GPIO21, SCL=GPIO22)");
#else
  Serial.println("Papan: Arduino Nano  (SDA=A4, SCL=A5)");
#endif

  // Probe DULU — percuma mengkalibrasi bus yang tidak menjawab.
  while (!mpuProbe())
  {
    Serial.println("!! MPU6050 TIDAK menjawab di I2C 0x68.");
    printWiringHint();
    Serial.println("   (menunggu MPU tersambung...)");
    delay(1000);
  }
  Serial.println("MPU6050 terdeteksi di 0x68.");
  Serial.println("Pastikan MPU DIAM & DATAR. Jangan disentuh...");

  mpu.begin();
  mpu.calcGyroOffsets(true);      // true = tampilkan progress kalibrasi

  Serial.println();
  Serial.println("Kalibrasi selesai. Gyro offset:");
  Serial.print("  X = "); Serial.println(mpu.getGyroXoffset());
  Serial.print("  Y = "); Serial.println(mpu.getGyroYoffset());
  Serial.print("  Z = "); Serial.println(mpu.getGyroZoffset());
  Serial.println("-------------------------------------");
  Serial.println("Sekarang pantau angle. Yaw(Z) harus ~0 saat diam.");
  delay(1000);
}

void loop() {
  mpu.update();

  // Kalau bus mati di tengah jalan, katakan apa adanya — jangan biarkan
  // pembaca mengira X=-90.00 / Y=90.00 itu sudut sungguhan.
  if (!mpuHealthy())
  {
    Serial.println("!! MPU TIDAK TERBACA — angka di bawah BEKU, bukan ukuran");
  }

  Serial.print("Angle -> X: ");
  Serial.print(mpu.getAngleX());
  Serial.print("\tY: ");
  Serial.print(mpu.getAngleY());
  Serial.print("\tZ(Yaw): ");
  Serial.print(mpu.getAngleZ());

  Serial.print("   | Gyro -> X: ");
  Serial.print(mpu.getGyroX());
  Serial.print("\tY: ");
  Serial.print(mpu.getGyroY());
  Serial.print("\tZ: ");
  Serial.println(mpu.getGyroZ());

  delay(200);
}
