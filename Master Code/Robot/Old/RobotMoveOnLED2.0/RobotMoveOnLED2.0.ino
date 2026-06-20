#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP8266WiFi.h>

WiFiClient client;
WiFiServer server(80);
const char* ssid = "Damn";
const char* password = "123456789";
String data = "";
int rightF = 16;
int rightB = 5;
int leftF = 4;
int leftB = 0;
const int MENU_OPTIONS = 2;
bool okButtonState = false;
bool cancelButtonState = false;
bool leftButtonState = false;
bool rightButtonState = false;
const int SDA_PIN = D7;
const int SCL_PIN = D6;
bool prevOkButtonState = false;
bool prevCancelButtonState = false;
bool prevLeftButtonState = false;
bool prevRightButtonState = false;

const char* menu[MENU_OPTIONS] = {"Start", "Settings"};
const char* settings[MENU_OPTIONS] = {"Mode", "Control"};
const char* mode[MENU_OPTIONS] = {"Sensor", "Feed"};
const char* control[MENU_OPTIONS] = {"Manual", "Automatic"};
const int OK_BUTTON_PIN = D5;
const int LEFT_BUTTON_PIN = D4;
int currentSelection = 0;
int press = 0;
int choose_menu = 0;
int play_mode = 0;
int play_control = 0;

#define OLED_ADDRESS 0x3C
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32 // Changed to 32 for 128x32 OLED
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_ADDRESS);

void setup() {
Serial.begin(115200);
  
  pinMode(rightF, OUTPUT);
  pinMode(rightB, OUTPUT);
  pinMode(leftF, OUTPUT);
  pinMode(leftB, OUTPUT);
  WiFi.begin(ssid, password);
  
  Serial.print("\n");
  Serial.print("WiFi connected using IP:");
  Serial.print(WiFi.localIP());
  pinMode(OK_BUTTON_PIN, INPUT_PULLUP);
  pinMode(LEFT_BUTTON_PIN, INPUT_PULLUP);
  Wire.begin(SDA_PIN, SCL_PIN);
  display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS);
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
}

void loop() {
  bool okButtonState = digitalRead(OK_BUTTON_PIN) == LOW;
  bool leftButtonState = digitalRead(LEFT_BUTTON_PIN) == LOW;
  
  if (leftButtonState) {
    if (currentSelection == 0) {
      currentSelection = 1;
      menu_1();
    } else {
      currentSelection = 0;
      menu_1();
    }
  }

  // Melakukan aksi berdasarkan tekanan tombol
  if (okButtonState) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.print("Performing:");
    display.display();
    delay(2000);
    if (choose_menu == 0) {
      if (currentSelection == 0) {
        // Aksi untuk opsi Start
        clearScreen();
        display.setCursor(0, 0);
        display.print("Starting...");
        updateDisplay();
        delay(2000); // Delay untuk simulasi aksi
        clearScreen();
      } else if (currentSelection == 1) {
        clearScreen();
        display.setCursor(0, 0);
        display.print("Entering Settings...");
        updateDisplay();
        delay(2000); // Delay untuk simulasi aksi
        clearScreen();
        choose_menu = 1;
      }
    } else if (choose_menu == 1) {
      if (currentSelection == 0) {
        // Aksi untuk opsi Start
        clearScreen();
        display.setCursor(0, 0);
        display.print("Mode...");
        updateDisplay();
        delay(2000); // Delay untuk simulasi aksi
        choose_menu = 2;
      } else if (currentSelection == 1) {
        // Aksi untuk opsi Settings
        clearScreen();
        display.setCursor(0, 0);
        display.print("Control...");
        updateDisplay();
        delay(2000); // Delay untuk simulasi aksi
        clearScreen();
        choose_menu = 3;
      }
    } else if (choose_menu == 2) {
      if (currentSelection == 0) {
        // Aksi untuk opsi Start
        play_mode = 0;
        choose_menu = 0;
      } else if (currentSelection == 1) {
        // Aksi untuk opsi Settings
        play_mode = 1;
        choose_menu = 0;
      }
    } else {
      if (currentSelection == 0) {
        play_control = 0;
        choose_menu = 0;
      } else if (currentSelection == 1) {
        play_control = 1;
        choose_menu = 0;
      }
    }
  }

  if (choose_menu == 0) {
    menu_1();
  } else if (choose_menu == 1) {
    menu_2();
  } else if (choose_menu == 2) {
    menu_3();
  } else {
    menu_4();
  }

  client = server.available();
  if (!client) return;
  data = checkClient();
  if (data == "forward") MotorForward();
  else if (data == "backward") MotorBackward();
  else if (data == "left") MotorLeft();
  else if (data == "right") MotorRight();
  else if (data == "stop") MotorStop();
}void menu_1() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  if (currentSelection == 0) {
    display.setCursor(0, 0);
    display.print(">");
    display.setCursor(8, 0);
    display.print(menu[0]);
    display.setCursor(8, 10);
    display.print(menu[1]);
  } else {
    display.setCursor(8, 0);
    display.print(menu[0]);
    display.setCursor(0, 10);
    display.print(">");
    display.print(menu[1]);
  }
  display.display();
}

void menu_2() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  if (currentSelection == 0) {
    display.setCursor(0, 0);
    display.print(">");
    display.setCursor(8, 0);
    display.print(settings[0]);
    display.setCursor(8, 10);
    display.print(settings[1]);
  } else {
    display.setCursor(8, 0);
    display.print(settings[0]);
    display.setCursor(0, 10);
    display.print(">");
    display.print(settings[1]);
  }
  display.display();
}

void menu_3() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  if (currentSelection == 0) {
    display.setCursor(0, 0);
    display.print(">");
    display.setCursor(8, 0);
    display.print(mode[0]);
    display.setCursor(8, 10);
    display.print(mode[1]);
  } else {
    display.setCursor(8, 0);
    display.print(mode[0]);
    display.setCursor(0, 10);
    display.print(">");
    display.print(mode[1]);
  }
  display.display();
}

void menu_4() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  if (currentSelection == 0) {
    display.setCursor(0, 0);
    display.print(">");
    display.setCursor(8, 0);
    display.print(control[0]);
    display.setCursor(8, 10);
    display.print(control[1]);
  } else {
    display.setCursor(8, 0);
    display.print(control[0]);
    display.setCursor(0, 10);
    display.print(">");
    display.print(control[1]);
  }
  display.display();
}

void MotorForward() {
  digitalWrite(rightF, HIGH);
  digitalWrite(rightB, LOW);
  digitalWrite(leftF, HIGH);
  digitalWrite(leftB, LOW);
}

void MotorBackward() {
  digitalWrite(rightF, LOW);
  digitalWrite(rightB, HIGH);
  digitalWrite(leftF, LOW);
  digitalWrite(leftB, HIGH);
}

void MotorLeft() {
  digitalWrite(rightF, HIGH);
  digitalWrite(rightB, LOW);
  digitalWrite(leftF, LOW);
  digitalWrite(leftB, HIGH);
}

void MotorRight() {
  digitalWrite(rightF, LOW);
  digitalWrite(rightB, HIGH);
  digitalWrite(leftF, HIGH);
  digitalWrite(leftB, LOW);
}

void MotorStop() {
  digitalWrite(rightF, LOW);
  digitalWrite(rightB, LOW);
  digitalWrite(leftF, LOW);
  digitalWrite(leftB, LOW);
}

String checkClient() {
  while (!client.available()) delay(1);
  String request = client.readStringUntil('\r');
  request.remove(0, 5);
  request.remove(request.length() - 9, 9);
  return request;  
}

void clearScreen() {
  display.clearDisplay();
}

void updateDisplay() {
  display.display();
}