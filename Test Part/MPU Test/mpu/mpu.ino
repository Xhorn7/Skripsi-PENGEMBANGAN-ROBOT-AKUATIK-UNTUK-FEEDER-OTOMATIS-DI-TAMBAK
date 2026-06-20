#include <Wire.h>



#define MPU_ADDR 0x68



int16_t AccX, AccY, AccZ;

int16_t GyroX, GyroY, GyroZ;



void setup() {

  Serial.begin(115200);

  

  // Sesuai wiring kamu

  Wire.begin(18, 19); // SDA = 18, SCL = 19



  // Wake up MPU6050

  Wire.beginTransmission(MPU_ADDR);

  Wire.write(0x6B);

  Wire.write(0);

  Wire.endTransmission(true);



  Serial.println("MPU6050 Ready (SDA=18, SCL=19)");

}



void loop() {

  Wire.beginTransmission(MPU_ADDR);

  Wire.write(0x3B);

  Wire.endTransmission(false);

  Wire.requestFrom(MPU_ADDR, 14, true);



  AccX = Wire.read() << 8 | Wire.read();

  AccY = Wire.read() << 8 | Wire.read();

  AccZ = Wire.read() << 8 | Wire.read();



  Wire.read(); Wire.read(); // skip temperature



  GyroX = Wire.read() << 8 | Wire.read();

  GyroY = Wire.read() << 8 | Wire.read();

  GyroZ = Wire.read() << 8 | Wire.read();



  Serial.print("Accel: ");

  Serial.print(AccX); Serial.print(", ");

  Serial.print(AccY); Serial.print(", ");

  Serial.print(AccZ);



  Serial.print(" | Gyro: ");

  Serial.print(GyroX); Serial.print(", ");

  Serial.print(GyroY); Serial.print(", ");

  Serial.println(GyroZ);



  delay(500);

}