// ============================================================
//  MpuDiag — DIAGNOSA BUS I2C & MPU6050 (tanpa pustaka apa pun)
//
//  Dipakai saat sudut MPU "aneh" dan kita perlu FAKTA, bukan tebakan.
//  Sketch ini sengaja TIDAK memakai MPU6050_tockn: ia bicara langsung ke
//  Wire, supaya yang diuji adalah bus & sensornya — bukan pustakanya.
//
//  Flash: pio run -e mpudiag -t upload
//         pio device monitor          (115200)
//
//  Yang dilaporkan tiap 2 detik:
//    1. Pemindaian seluruh alamat I2C 0x01..0x7E
//    2. WHO_AM_I (reg 0x75) — MPU6050 asli menjawab 0x68
//    3. PWR_MGMT_1 (reg 0x6B) — bit 6 (0x40) = SLEEP, sensor tidak mengukur
//    4. Isi mentah 14 byte register data (0x3B..0x48) + terjemahannya
//    5. VONIS: apa yang salah dan apa yang harus diperiksa
// ============================================================

#include <Wire.h>

#define SDA_PIN 21
#define SCL_PIN 22
#define I2C_HZ  100000UL

#define MPU_ADDR_LOW  0x68     // AD0 = GND (yang dipakai firmware robot)
#define MPU_ADDR_HIGH 0x69     // AD0 = 3.3V

uint8_t foundAddr = 0;         // alamat MPU yang benar-benar ditemukan

bool i2cAck(uint8_t addr)
{
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

void printHex8(uint8_t v)
{
  if (v < 16) Serial.print('0');
  Serial.print(v, HEX);
}

// Return jumlah perangkat yang menjawab; set foundAddr bila MPU ketemu.
int scanBus()
{
  int found = 0;
  foundAddr = 0;

  Serial.println("[1] Pemindaian bus I2C (SDA=GPIO21, SCL=GPIO22)");
  for (uint8_t addr = 1; addr < 127; addr++)
  {
    if (!i2cAck(addr)) continue;
    found++;
    Serial.print("    0x"); printHex8(addr);
    if (addr == MPU_ADDR_LOW)
    {
      Serial.print("  <- MPU6050, AD0=GND (alamat yang dipakai firmware)");
      foundAddr = addr;
    }
    else if (addr == MPU_ADDR_HIGH)
    {
      Serial.print("  <- MPU6050, tapi AD0=HIGH");
      if (!foundAddr) foundAddr = addr;
    }
    Serial.println();
  }
  if (found == 0)
    Serial.println("    (KOSONG - tidak ada satu pun perangkat menjawab)");
  return found;
}

uint8_t readReg(uint8_t addr, uint8_t reg, bool *ok)
{
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) { *ok = false; return 0; }
  if (Wire.requestFrom((int)addr, 1) != 1) { *ok = false; return 0; }
  *ok = true;
  return Wire.read();
}

void setup()
{
  Serial.begin(115200);
  delay(300);                 // beri MPU waktu selesai power-on reset

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(I2C_HZ);
  Wire.setTimeOut(50);

  Serial.println();
  Serial.println("================================================");
  Serial.println("      DIAGNOSA BUS I2C & MPU6050");
  Serial.println("================================================");
}

void loop()
{
  Serial.println();
  int nDev = scanBus();

  if (foundAddr == 0)
  {
    Serial.println();
    Serial.println("[VONIS] MPU6050 TIDAK ADA di bus.");
    if (nDev == 0)
    {
      Serial.println("  Bus benar-benar kosong. Periksa berurutan:");
      Serial.println("   a. GND MPU <-> GND ESP32 HARUS tersambung (paling sering lupa)");
      Serial.println("   b. VCC MPU ke 3.3V (bukan 5V kalau modul tanpa regulator)");
      Serial.println("   c. SDA ke GPIO21, SCL ke GPIO22 (jangan tertukar)");
      Serial.println("   d. Kabel I2C < 20 cm & jauhkan dari kabel daya ESC");
      Serial.println("   e. Coba modul MPU lain - modulnya bisa saja mati");
    }
    else
    {
      Serial.println("  Ada perangkat lain di bus, tapi tak satu pun MPU6050.");
      Serial.println("  Berarti kabel SDA/SCL SEHAT - yang bermasalah modul MPU-nya.");
    }
    delay(2000);
    return;
  }

  if (foundAddr == MPU_ADDR_HIGH)
  {
    Serial.println();
    Serial.println("[VONIS] MPU ada, tapi di 0x69 - pin AD0 ke-HIGH.");
    Serial.println("  Firmware robot hanya bicara ke 0x68, jadi tidak akan pernah");
    Serial.println("  terbaca. SOLUSI: sambungkan pin AD0 modul ke GND.");
    delay(2000);
    return;
  }

  bool ok = false;
  uint8_t who = readReg(foundAddr, 0x75, &ok);
  Serial.print("[2] WHO_AM_I (0x75) = ");
  if (!ok) Serial.println("GAGAL DIBACA");
  else { Serial.print("0x"); printHex8(who);
         Serial.println(who == 0x68 ? "  (MPU6050 asli)" : "  (klon - biasanya tetap jalan)"); }

  uint8_t pwr = readReg(foundAddr, 0x6B, &ok);
  Serial.print("[3] PWR_MGMT_1 (0x6B) = 0x");
  if (!ok) Serial.println("?? GAGAL DIBACA");
  else
  {
    printHex8(pwr);
    Serial.println((pwr & 0x40) ? "  <- bit SLEEP MENYALA, sensor tidak mengukur!"
                                : "  (sensor aktif)");
  }

  // Ambil 14 byte data sekaligus, persis seperti yang dilakukan pustaka.
  Wire.beginTransmission(foundAddr);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  int n = Wire.requestFrom((int)foundAddr, 14);

  Serial.print("[4] requestFrom(14) mengembalikan ");
  Serial.print(n); Serial.println(" byte");

  if (n != 14)
  {
    Serial.println("    Alamat meng-ACK tapi DATA tidak keluar.");
    Serial.println("    Khas kabel SDA/SCL goyang, pull-up lemah, atau catu 3.3V drop.");
    delay(2000);
    return;
  }

  int16_t raw[7];
  for (int i = 0; i < 7; i++) raw[i] = Wire.read() << 8 | Wire.read();

  Serial.print("    mentah  aX="); Serial.print(raw[0]);
  Serial.print(" aY=");            Serial.print(raw[1]);
  Serial.print(" aZ=");            Serial.print(raw[2]);
  Serial.print(" | gX=");          Serial.print(raw[4]);
  Serial.print(" gY=");            Serial.print(raw[5]);
  Serial.print(" gZ=");            Serial.println(raw[6]);

  float ax = raw[0] / 16384.0f, ay = raw[1] / 16384.0f, az = raw[2] / 16384.0f;
  float mag = sqrtf(ax * ax + ay * ay + az * az);
  Serial.print("    percepatan  aX="); Serial.print(ax, 3);
  Serial.print("g aY=");               Serial.print(ay, 3);
  Serial.print("g aZ=");               Serial.print(az, 3);
  Serial.print("g  |a|=");             Serial.print(mag, 3);
  Serial.println(" g   (sehat: |a| sekitar 1.0)");

  Serial.print("[5] VONIS: ");
  if (raw[0] == -1 && raw[1] == -1 && raw[2] == -1)
  {
    Serial.println("SEMUA BYTE -1 - bus menjawab tapi tidak mengirim data.");
    Serial.println("    Inilah yang bikin sudut BEKU di Roll=-90 / Pitch=+90 / Yaw=-0.0,");
    Serial.println("    karena atan2(-6.1e-5, 0) = -90 derajat PAS. Bukan sudut sungguhan.");
  }
  else if (mag < 0.30f)
  {
    Serial.println("Percepatan hampir NOL - sensor tidak mengukur.");
    Serial.println("    Cek bit SLEEP di atas, atau catu daya modul.");
  }
  else if (mag > 3.0f)
  {
    Serial.println("Percepatan tidak masuk akal - data rusak / bus berderau.");
  }
  else
  {
    Serial.println("SENSOR SEHAT. Goyangkan modul - angka di atas harus ikut berubah.");
    Serial.println("    Kalau di robot tetap beku, masalahnya ada di wiring robot,");
    Serial.println("    bukan di modul MPU ini.");
  }

  delay(2000);
}
