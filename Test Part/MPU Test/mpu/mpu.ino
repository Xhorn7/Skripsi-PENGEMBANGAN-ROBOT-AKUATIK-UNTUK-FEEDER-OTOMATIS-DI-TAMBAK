#include <Wire.h>
#include <MPU6050_tockn.h>

// ================= MPU =================
// Pin & library disamakan dengan Finalnew.ino:
//   Wire.begin(21, 22)  => SDA = GPIO21, SCL = GPIO22
//   library MPU6050_tockn (mpu.calcGyroOffsets)
//
// Tujuan file ini: KALIBRASI MPU sebelum dipasang di robot.
// 1. Taruh robot/MPU DIAM & DATAR selama proses calcGyroOffsets.
// 2. Catat nilai offset gyro yang tampil (GyroX/Y/Z Offset).
// 3. Setelah kalibrasi, pantau Yaw (AngleZ) harus stabil ~0 saat diam
//    dan berubah wajar saat diputar.

#define SDA_PIN 21
#define SCL_PIN 22

MPU6050 mpu(Wire);

void setup() {
  Serial.begin(115200);
  delay(200);

  Wire.begin(SDA_PIN, SCL_PIN);   // SDA=21, SCL=22 (sama dgn Finalnew)

  Serial.println();
  Serial.println("=== KALIBRASI MPU6050 ===");
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
