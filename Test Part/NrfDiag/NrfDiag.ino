#include <SPI.h>

// ================= DIAGNOSA NRF24L01 =================
// Flash: pio run -e nrfdiag -t upload  &&  pio device monitor
//
// Dipakai saat Finalnew berhenti di "NRF FAIL". Pesan itu hanya memberitahu
// bahwa radio.begin() mengembalikan false, TANPA menyebutkan kenapa — padahal
// penyebabnya berbeda-beda dan perbaikannya juga berbeda:
//
//   modul tidak tertancap    -> pasang modulnya
//   VCC tidak sampai / 5V    -> perbaiki daya (NRF24 RUSAK bila diberi 5V)
//   MISO putus               -> semua register terbaca 0xFF
//   MOSI/SCK/CSN putus       -> tulis-baca-balik gagal
//   chip rusak               -> SPI jalan tapi isinya ngawur
//
// Sketch ini TIDAK memakai pustaka RF24 sama sekali. Ia bicara SPI mentah,
// sehingga bisa membedakan "pustaka menolak chip" dari "chip memang bisu" —
// sesuatu yang tidak bisa dilakukan lewat radio.begin().
//
// WIRING NRF24L01 -> ESP32 (VSPI bawaan)
//   VCC  -> 3.3V   JANGAN 5V, modul akan rusak permanen
//   GND  -> GND
//   CE   -> GPIO4
//   CSN  -> GPIO5
//   SCK  -> GPIO18
//   MOSI -> GPIO23
//   MISO -> GPIO19
//   IRQ  -> tidak dipakai, biarkan kosong
//
// CATATAN DAYA: NRF24 menarik arus dalam sentakan pendek. Bila rel 3.3V
// dipakai bersama ESC, tegangannya bisa tercelup sesaat dan modul gagal
// diinisialisasi. Obatnya kapasitor 10-100 uF langsung di kaki VCC-GND modul.

#define CE_PIN    4
#define CSN_PIN   5
#define SCK_PIN   18
#define MISO_PIN  19
#define MOSI_PIN  23

// Register nRF24L01+ beserta isi bawaan sesudah power-on. Nilai bawaan inilah
// alat ukur kita: chip yang sehat HARUS memperlihatkan pola ini.
#define REG_CONFIG      0x00
#define REG_EN_AA       0x01
#define REG_EN_RXADDR   0x02
#define REG_SETUP_AW    0x03
#define REG_SETUP_RETR  0x04
#define REG_RF_CH       0x05
#define REG_RF_SETUP    0x06
#define REG_STATUS      0x07

#define CMD_R_REGISTER  0x00
#define CMD_W_REGISTER  0x20

SPISettings spiCfg(4000000, MSBFIRST, SPI_MODE0);

uint8_t regRead(uint8_t reg)
{
  SPI.beginTransaction(spiCfg);
  digitalWrite(CSN_PIN, LOW);
  SPI.transfer(CMD_R_REGISTER | (reg & 0x1F));
  uint8_t v = SPI.transfer(0xFF);
  digitalWrite(CSN_PIN, HIGH);
  SPI.endTransaction();
  return v;
}

void regWrite(uint8_t reg, uint8_t val)
{
  SPI.beginTransaction(spiCfg);
  digitalWrite(CSN_PIN, LOW);
  SPI.transfer(CMD_W_REGISTER | (reg & 0x1F));
  SPI.transfer(val);
  digitalWrite(CSN_PIN, HIGH);
  SPI.endTransaction();
}

// Membedakan jalur yang DITAHAN dari jalur yang MENGAMBANG.
// Register yang terbaca 0x00 semua bisa berarti dua hal yang jauh berbeda:
// MISO dikorsletkan ke GND (kerusakan jalur), atau tidak ada yang menggerakkan
// MISO sama sekali (modul tanpa daya / kabel MISO putus / kabel CSN putus,
// sebab chip yang tidak pernah dipilih memang membiarkan MISO bebas).
//
// Caranya: pasang pull-up internal, baca; lalu pull-down internal, baca.
//   ikut naik & ikut turun -> tidak ada yang melawan  = MENGAMBANG
//   tetap LOW walau ditarik naik -> ada yang menahan  = KORSLET KE GND
//   tetap HIGH walau ditarik turun                    = tersambung ke VCC
// Pull-up/pull-down internal ESP32 (~45k) lemah, jadi apa pun yang lebih kuat
// akan menang — persis yang kita mau ukur.
const __FlashStringHelper *lineState(uint8_t pin)
{
  pinMode(pin, INPUT_PULLUP);
  delayMicroseconds(300);
  bool up = digitalRead(pin);

  pinMode(pin, INPUT_PULLDOWN);
  delayMicroseconds(300);
  bool dn = digitalRead(pin);

  pinMode(pin, INPUT);

  if (up && !dn) return F("MENGAMBANG (tak ada yang menggerakkan)");
  if (!up && !dn) return F("DITAHAN LOW  <- korslet ke GND / chip menahan");
  if (up && dn)   return F("DITAHAN HIGH <- tersambung VCC / ada pull-up kuat");
  return F("berubah-ubah (derau — sambungan longgar?)");
}

void lineStateReport()
{
  SPI.end();                       // lepas pin dari peripheral SPI dulu

  Serial.println(F("-- Keadaan jalur (SPI dilepas sementara) --"));
  Serial.print(F("  MISO (19) : ")); Serial.println(lineState(MISO_PIN));
  Serial.print(F("  MOSI (23) : ")); Serial.println(lineState(MOSI_PIN));
  Serial.print(F("  SCK  (18) : ")); Serial.println(lineState(SCK_PIN));
  Serial.print(F("  CSN  (5)  : ")); Serial.println(lineState(CSN_PIN));

  pinMode(CE_PIN, OUTPUT);         // pasang kembali seperti semula
  pinMode(CSN_PIN, OUTPUT);
  digitalWrite(CE_PIN, LOW);
  digitalWrite(CSN_PIN, HIGH);
  SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN, CSN_PIN);
  delay(10);
}

struct RegInfo { uint8_t addr; uint8_t deflt; const char *name; };

const RegInfo REGS[] = {
  { REG_CONFIG,     0x08, "CONFIG    " },
  { REG_EN_AA,      0x3F, "EN_AA     " },
  { REG_EN_RXADDR,  0x03, "EN_RXADDR " },
  { REG_SETUP_AW,   0x03, "SETUP_AW  " },
  { REG_SETUP_RETR, 0x03, "SETUP_RETR" },
  { REG_RF_CH,      0x02, "RF_CH     " },
  { REG_RF_SETUP,   0x0E, "RF_SETUP  " },
  { REG_STATUS,     0x0E, "STATUS    " },
};
const uint8_t NREGS = sizeof(REGS) / sizeof(REGS[0]);

void printHex(uint8_t v)
{
  if (v < 16) Serial.print('0');
  Serial.print(v, HEX);
}

void setup()
{
  Serial.begin(115200);
  delay(300);

  Serial.println();
  Serial.println(F("=== DIAGNOSA NRF24L01 ==="));
  Serial.println(F("CE=GPIO4  CSN=GPIO5  SCK=18  MOSI=23  MISO=19"));

  pinMode(CE_PIN, OUTPUT);
  pinMode(CSN_PIN, OUTPUT);
  digitalWrite(CE_PIN, LOW);      // mode standby: cukup untuk bicara register
  digitalWrite(CSN_PIN, HIGH);

  SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN, CSN_PIN);
  delay(100);                     // beri modul waktu selesai power-on reset
}

void loop()
{
  Serial.println();
  lineStateReport();

  Serial.println(F("-- Isi register --"));

  uint8_t vals[NREGS];
  uint8_t allFF = 0, all00 = 0, cocok = 0;

  for (uint8_t i = 0; i < NREGS; i++)
  {
    vals[i] = regRead(REGS[i].addr);
    if (vals[i] == 0xFF) allFF++;
    if (vals[i] == 0x00) all00++;
    if (vals[i] == REGS[i].deflt) cocok++;

    Serial.print(F("  "));
    Serial.print(REGS[i].name);
    Serial.print(F(" = 0x")); printHex(vals[i]);
    Serial.print(F("   (bawaan 0x"));  printHex(REGS[i].deflt);
    Serial.println(F(")"));
  }

  // Uji tulis-baca-balik. Membaca saja hanya menguji MISO; menulis lalu membaca
  // kembali menguji SELURUH rantai: MOSI, SCK, CSN, dan MISO sekaligus.
  // RF_CH dipilih karena isinya bebas dan tidak mengubah perilaku apa pun.
  uint8_t asli = regRead(REG_RF_CH);
  regWrite(REG_RF_CH, 0x2A);
  uint8_t balik = regRead(REG_RF_CH);
  regWrite(REG_RF_CH, asli);            // kembalikan seperti semula

  Serial.print(F("-- Uji tulis-baca-balik RF_CH: tulis 0x2A, terbaca 0x"));
  printHex(balik);
  Serial.println(balik == 0x2A ? F("  OK") : F("  GAGAL"));

  Serial.println();
  Serial.println(F("-- KESIMPULAN --"));

  if (allFF == NREGS)
  {
    Serial.println(F(">> SEMUA register 0xFF — tidak ada yang menjawab di MISO."));
    Serial.println(F("   Jalur MISO terbaca HIGH terus, seolah tidak ada chip."));
    Serial.println(F("   SEBAB paling sering, urut dari yang paling mungkin:"));
    Serial.println(F("   1. VCC modul tidak menerima 3.3V (ukur di kaki modul!)"));
    Serial.println(F("   2. Kabel MISO putus / tidak masuk GPIO19"));
    Serial.println(F("   3. Modul tidak benar-benar duduk di soketnya"));
    Serial.println(F("   4. Modul rusak — pernah diberi 5V?"));
  }
  else if (all00 == NREGS)
  {
    Serial.println(F(">> SEMUA register 0x00 — chip tidak menjawab sama sekali."));
    Serial.println(F("   Baca baris 'MISO (19)' di atas untuk tahu sebabnya:"));
    Serial.println(F("   * DITAHAN LOW  -> jalur MISO korslet ke GND. Cari"));
    Serial.println(F("     jembatan timah di sekitar kaki MISO modul."));
    Serial.println(F("   * MENGAMBANG   -> tidak ada yang menggerakkan MISO."));
    Serial.println(F("     Tiga kemungkinan, ukur VCC modul dulu (harus 3.3V):"));
    Serial.println(F("       1. VCC modul tidak sampai / 0V"));
    Serial.println(F("       2. kabel MISO putus ke GPIO19"));
    Serial.println(F("       3. kabel CSN putus ke GPIO5 — chip tak pernah"));
    Serial.println(F("          dipilih, jadi MISO memang dibiarkan bebas"));
    Serial.println(F("     Kalau VCC 3.3V & ketiga kabel tersambung: modul rusak."));
  }
  else if (balik == 0x2A && cocok >= 5)
  {
    Serial.println(F(">> SPI JALAN & CHIP SEHAT. Register bawaan cocok dan"));
    Serial.println(F("   tulis-baca-balik berhasil."));
    Serial.println(F("   Artinya wiring Anda BENAR. Kalau Finalnew tetap"));
    Serial.println(F("   'NRF FAIL', penyebabnya bukan kabel:"));
    Serial.println(F("   - modul KLON (Si24R1) yang ditolak pemeriksaan pustaka"));
    Serial.println(F("   - atau tegangan tercelup saat ESC menarik arus"));
    Serial.println(F("     -> pasang kapasitor 10-100 uF di kaki VCC-GND modul"));
  }
  else if (balik == 0x2A)
  {
    Serial.println(F(">> SPI jalan (tulis-baca-balik OK), tapi isi register"));
    Serial.println(F("   TIDAK sesuai bawaan. Kemungkinan modul klon, atau"));
    Serial.println(F("   catu dayanya tidak stabil sehingga isinya teracak."));
  }
  else
  {
    Serial.println(F(">> Register terbaca sesuatu, tapi tulis-baca-balik GAGAL."));
    Serial.println(F("   Berarti MISO menjawab tetapi perintah tidak sampai."));
    Serial.println(F("   Curigai MOSI (GPIO23), SCK (GPIO18), atau CSN (GPIO5)"));
    Serial.println(F("   — salah satu putus, tertukar, atau tersolder dingin."));
  }

  Serial.println();
  Serial.println(F("   Ingat: NRF24 HARUS 3.3V. 5V merusaknya permanen."));
  Serial.println(F("   (mengulang tiap 5 detik — goyangkan kabel untuk"));
  Serial.println(F("    menemukan sambungan yang longgar)"));

  delay(5000);
}
