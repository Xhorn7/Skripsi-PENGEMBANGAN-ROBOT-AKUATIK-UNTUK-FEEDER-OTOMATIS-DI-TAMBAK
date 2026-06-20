// ============================================================
//  Motor test — TES ESC + MOTOR MURNI
//  Tujuan: mastiin motor & ESC jalan secara HARDWARE.
//  - TANPA MPU, TANPA NRF, TANPA logika zigzag.
//  - Ramp throttle pelan: motor KIRI, lalu KANAN, lalu DUA-DUANYA.
//  Flash: pio run -e esctest -t upload
//
//  ⚠️ AMANKAN BALING-BALING / ANGKAT ROBOT sebelum tes!
// ============================================================

#include <ESP32Servo.h>

Servo escLeft;
Servo escRight;

#define ESC_LEFT_PIN  25
#define ESC_RIGHT_PIN 26

#define MIN_US   1000   // stop / arming
#define MAX_US   1400   // throttle maksimum buat bench test (pelan, aman)
#define STEP_US  25
#define STEP_MS  150

bool done = false;

void armESC()
{
  escLeft.writeMicroseconds(MIN_US);
  escRight.writeMicroseconds(MIN_US);
  Serial.println("Arming ESC (throttle minimum 5 detik)...");
  delay(5000);
  Serial.println("ESC Armed");
}

// Ramp naik -> tahan -> ramp turun, untuk motor yang dipilih
void rampTest(const char *label, bool useLeft, bool useRight)
{
  Serial.print("\n>>> "); Serial.println(label);

  for (int us = MIN_US; us <= MAX_US; us += STEP_US)
  {
    escLeft.writeMicroseconds(useLeft ? us : MIN_US);
    escRight.writeMicroseconds(useRight ? us : MIN_US);
    Serial.print("  PWM = "); Serial.println(us);
    delay(STEP_MS);
  }

  Serial.println("  (tahan di throttle maks 1.5 detik)");
  delay(1500);

  for (int us = MAX_US; us >= MIN_US; us -= STEP_US)
  {
    escLeft.writeMicroseconds(useLeft ? us : MIN_US);
    escRight.writeMicroseconds(useRight ? us : MIN_US);
    delay(STEP_MS);
  }

  escLeft.writeMicroseconds(MIN_US);
  escRight.writeMicroseconds(MIN_US);
  Serial.println("  selesai, stop.");
  delay(2000);
}

void setup()
{
  Serial.begin(115200);

  escLeft.attach(ESC_LEFT_PIN);
  escRight.attach(ESC_RIGHT_PIN);

  Serial.println("=== TES ESC + MOTOR (tanpa MPU/NRF) ===");
  Serial.println("AMANKAN BALING-BALING / ANGKAT ROBOT!");
  armESC();
}

void loop()
{
  if (done) { escLeft.writeMicroseconds(MIN_US); escRight.writeMicroseconds(MIN_US); return; }

  // Countdown keselamatan
  for (int i = 5; i > 0; i--)
  {
    Serial.print("Mulai tes dalam "); Serial.print(i); Serial.println(" detik...");
    delay(1000);
  }

  rampTest("MOTOR KIRI saja (GPIO25)",  true,  false);
  rampTest("MOTOR KANAN saja (GPIO26)", false, true);
  rampTest("DUA MOTOR bareng",          true,  true);

  Serial.println("\n=== SEMUA TES SELESAI === (tekan tombol EN untuk ulang)");
  done = true;
}
