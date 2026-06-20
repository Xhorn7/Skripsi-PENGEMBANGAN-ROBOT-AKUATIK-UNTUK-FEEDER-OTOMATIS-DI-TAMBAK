// ============================================================
//  EscTest — TES ESC MURNI (tanpa MPU, tanpa NRF)
//  Tujuan: isolasi masalah "ESC beep tapi motor gak muter".
//   - Langsung attach + arming ESC (gak nunggu MPU)
//   - Ramp throttle pelan 1000->1300us biar ketahuan titik motor mulai muter
//  Kalau di sini motor MUTER  -> tadi MPU yang ngeblok di MoveTest.
//  Kalau tetap beep "no signal" -> kabel signal ESC (cek GPIO25/26).
//  Flash: pio run -e esctest -t upload
// ============================================================

#include <ESP32Servo.h>

Servo escLeft;
Servo escRight;
#define ESC_LEFT_PIN  25
#define ESC_RIGHT_PIN 26

void setAll(int us)
{
  escLeft.writeMicroseconds(us);
  escRight.writeMicroseconds(us);
}

void setup()
{
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== ESC TEST (tanpa MPU/NRF) ===");

  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);
  escLeft.setPeriodHertz(50);
  escRight.setPeriodHertz(50);
  escLeft.attach(ESC_LEFT_PIN, 1000, 2000);
  escRight.attach(ESC_RIGHT_PIN, 1000, 2000);

  // Arming: tahan throttle minimum. ESC harusnya BERHENTI beep "no signal"
  // dan kasih nada "armed".
  Serial.println("Arming @1000us (tahan 4 detik)... ESC harusnya berhenti beep no-signal.");
  setAll(1000);
  delay(4000);
  Serial.println("Selesai arming. Mulai ramp throttle.");
}

void loop()
{
  // Ramp pelan biar ketahuan di PWM berapa motor mulai muter.
  for (int us = 1000; us <= 1300; us += 20)
  {
    setAll(us);
    Serial.print("PWM = "); Serial.print(us);
    Serial.println(us >= 1100 ? "  <- harusnya udah muter di sekitar sini" : "");
    delay(700);
  }
  Serial.println("Tahan 1300us 2 detik...");
  delay(2000);

  Serial.println("Balik ke 1000us (stop) 3 detik.\n");
  setAll(1000);
  delay(3000);
}
