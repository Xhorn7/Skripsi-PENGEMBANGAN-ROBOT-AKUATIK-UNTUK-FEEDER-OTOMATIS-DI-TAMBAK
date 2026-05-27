
#include <WiFi.h>
#include <WiFiManager.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Arduino.h>
#include <Wire.h>
#include <Update.h>
#define VREE 3300    //VREF (mv)
#define ADC_RES 4096 //ADC Resolution
#define TWO_POINT_CALIBRATION 0
#define READ_TEMP (25) 
#define CAL1_V (1250) //mv
#define CAL1_T (25)   //℃
#define CAL2_V (1300) //mv
#define CAL2_T (15)   //℃
//ph
const int pin_pH = 34;  // Change to your desired analog pin
int pH_analog;
float Po = 0;
float pH_step;
double voltage;
//
unsigned long previousMilliss = 0;
const long interval = 1000; 

///Temp
const int oneWireBus = 4;
OneWire oneWire(oneWireBus);
DallasTemperature sensors(&oneWire);
unsigned long lasttime = 0;
unsigned long timerDelay = 2000;

// TDS
#define TdsSensorPin 36
#define VREF 3.3      // analog reference voltage(Volt) of the ADC
#define SCOUNT  30           // sum of sample point
int analogBuffer[SCOUNT];    // store the analog value in the array, read from ADC
int analogBufferTemp[SCOUNT];
int analogBufferIndex = 0, copyIndex = 0;
float averageVoltage = 0, tdsValue = 0, temperature = 25;
//

//wifi
const char* ssid = "Dam";
const char* pass = "adam12345";
String serverName = "http://103.102.152.249/data/data_entry.php";
//
///ph
float PH4 = 3.1;
float PH7 = 2.6;
///

//Temp value processing
int getMedianNum(int bArray[], int iFilterLen) 
{
      int bTab[iFilterLen];
      for (byte i = 0; i < iFilterLen; i++)
      bTab[i] = bArray[i];
      int i, j, bTemp;
      for (j = 0; j < iFilterLen - 1; j++){
        for (i = 0; i < iFilterLen - j - 1; i++){
          if (bTab[i] > bTab[i + 1]){
            bTemp = bTab[i];
            bTab[i] = bTab[i + 1];
            bTab[i + 1] = bTemp; }}}
      if ((iFilterLen & 1) > 0)
       bTemp = bTab[(iFilterLen - 1) / 2];
      else
       bTemp = (bTab[iFilterLen / 2] + bTab[iFilterLen / 2 - 1]) / 2;
      return bTemp;
}

//oxygen 
const int pind = 35;
const uint16_t DO_Table[41] = {
    14460, 14220, 13820, 13440, 13090, 12740, 12420, 12110, 11810, 11530,
    11260, 11010, 10770, 10530, 10300, 10080, 9860, 9660, 9460, 9270,
    9080, 8900, 8730, 8570, 8410, 8250, 8110, 7960, 7820, 7690,
    7560, 7430, 7300, 7180, 7070, 6950, 6840, 6730, 6630, 6530, 6410};
 
uint8_t Temperaturet;
uint16_t ADC_Raw;
uint16_t ADC_Voltage;
uint16_t DO;

int16_t readDO(uint32_t voltage_mv, uint8_t temperature_c)
{
  uint16_t V_saturation = (int16_t)((int8_t)temperature_c - CAL2_T) * ((uint16_t)CAL1_V - CAL2_V) / ((uint8_t)CAL1_T - CAL2_T) + CAL2_V;
  return (voltage_mv * DO_Table[temperature_c] / V_saturation);
}
//
void setup() {
   ///tds
  pinMode(TdsSensorPin, INPUT);
  ///
  sensors.begin();
  Serial.begin(9600);
  WiFi.begin(ssid, pass);
  Serial.println("Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print("./");
  }
}

void loop() {
  ///Temp 
  sensors.requestTemperatures();
  float temperatureC = sensors.getTempCByIndex(0);
  //Serial.print(temperatureC);
  //Serial.println("ºC");
  
  //ph
  pH_analog = analogRead(pin_pH);

  //Serial.print("ADC Value: ");
  //Serial.println(pH_analog);
  
  // Calculate voltage
  voltage = pH_analog * (3.3 / 4095.0);  // For ESP32, ADC resolution is 12 bits (4095)
  //Serial.print("Voltage: ");
  //Serial.println(voltage, 4);

  // Calculate pH value of the liquid
  pH_step = (PH4 - PH7) / 3;
  Po = 7 + ((PH7 - voltage) / pH_step);
  //Serial.print("pH Value: ");
  //Serial.println(Po, 2);
  //Serial.println();
  //

  //oxygen
  Temperaturet = (uint8_t)READ_TEMP;
  ADC_Raw = analogRead(pind);
  ADC_Voltage = uint32_t(VREE) * ADC_Raw / ADC_RES;
  DO = readDO(ADC_Voltage, Temperaturet);
  //Serial.print("Temperaturet:\t" + String(Temperaturet) + "\t");
  //Serial.print("ADC RAW:\t" + String(ADC_Raw) + "\t");
  //Serial.print("ADC Voltage:\t" + String(ADC_Voltage) + "\t");
  //Serial.println("DO:\t" +String(DO) + "\t");
  //
  ///TDS
  static unsigned long analogSampleTimepoint = millis();
  if(millis() - analogSampleTimepoint > 40U){     // every 40 milliseconds, read the analog value from the ADC
    analogSampleTimepoint = millis();
    analogBuffer[analogBufferIndex] = analogRead(TdsSensorPin);    // read the analog value and store into the buffer
    analogBufferIndex++;
    if(analogBufferIndex == SCOUNT){ 
      analogBufferIndex = 0;}   
    static unsigned long printTimepoint = millis();
    if(millis() - printTimepoint > 800U){
      printTimepoint = millis();
      for(copyIndex = 0; copyIndex < SCOUNT; copyIndex++){
        analogBufferTemp[copyIndex] = analogBuffer[copyIndex];}
      averageVoltage = getMedianNum(analogBufferTemp, SCOUNT) * (float)VREF / 1024.0; // read the analog value more stable by the median filtering algorithm, and convert to voltage value
      float compensationCoefficient = 1.0 + 0.02 * (temperature - 25.0);    // temperature compensation formula: fFinalResult(25^C) = fFinalResult(current)/(1.0+0.02*(fTP-25.0));
      float compensationVoltage = averageVoltage / compensationCoefficient;  // temperature compensation
      tdsValue = (133.42 * compensationVoltage * compensationVoltage * compensationVoltage - 255.86 * compensationVoltage * compensationVoltage + 857.39 * compensationVoltage) * 0.5; // convert voltage value to tds value
      //Serial.print("TDS Value:");
      //Serial.print(tdsValue/2, 0);
      //Serial.println("ppm");
   }
///
  unsigned long currentMilliss = millis();

  if (WiFi.status() == WL_CONNECTED) {
      WiFiClient client;
      HTTPClient http;
      String path;
      //String path = serverName + "?type=tmp&data=28.09"; //data ini harus diganti dengan bacaan dari sensor
      http.begin(client, path.c_str());
      int httpResponse = http.GET();
      if (currentMilliss - previousMilliss >= interval) {
        path = serverName + "?type=td&data=" + tdsValue;
        path = serverName + "?type=tp&data=" + temperatureC;
        path = serverName + "?type=ox&data=" + DO ;
        path = serverName + "?type=ph&data=" + Po ;

        previousMilliss = currentMilliss;}
        http.end();
    }else{
      Serial.println("WiFi disconnected!");
    }
}
