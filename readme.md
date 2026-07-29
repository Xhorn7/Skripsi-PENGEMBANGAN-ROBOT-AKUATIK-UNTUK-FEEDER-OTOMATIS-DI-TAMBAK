# Pengembangan Robot Akuatik untuk Feeder Otomatis di Tambak

Skripsi. Robot perahu otomatis yang menyebar pakan di tambak berbentuk persegi. Operator memasukkan **dimensi tambak, titik awal, lebar lintasan, dan kecepatan** lewat aplikasi; aplikasi menerjemahkannya menjadi **jalur zigzag** (daftar langkah *maju x m / belok y°*), lalu robot menjalankannya secara otomatis dengan penstabil arah berbasis giroskop.

![Gambaran sistem](Flowchart%20Images/01-1-gambaran-sistem.png)

---

## Gambaran Sistem

Dua sub-sistem yang terhubung nirkabel lewat modul radio **NRF24L01+**:

| Sub-sistem | Perangkat | Peran |
|---|---|---|
| **Transmitter** | Raspberry Pi 4 / PC | Aplikasi GUI: input misi, perencanaan jalur, kirim perintah, telemetri & logging |
| **Robot (Receiver)** | ESP32 | Terima perintah, jalankan pola zigzag, heading-hold MPU6050, kendali 2 motor brushless |

Komunikasi **dua arah half-duplex** ("gantian" seperti radio HT): Pi mengirim perintah/PING, robot membalas telemetri MPU di sela-selanya. Detail alur ada di [flowchart.md](flowchart.md) dan folder [Flowchart Images/](Flowchart%20Images/).

---

## Fitur

- **Perencanaan jalur (path planning):** dari dimensi tambak + titik awal + lebar lintasan + kecepatan → daftar segmen *maju/belok* (pola *boustrophedon*/zigzag).
- **Preview jalur:** kanvas peta tambak + daftar langkah, sebelum misi dikirim.
- **Keypad di layar:** operasi penuh lewat layar sentuh, **tanpa keyboard fisik**.
- **Heading-hold proporsional:** robot berjalan lurus dengan koreksi arah dari MPU6050 (Kp × error).
- **Zigzag menyapu penuh:** arah U-turn **berselang-seling** sehingga sapuan menutupi seluruh lebar tambak.
- **Failsafe heartbeat:** robot berhenti otomatis bila sinyal transmitter hilang > 3 detik.
- **Telemetri MPU 2 arah (radio):** robot mengirim balik roll/pitch/yaw lewat NRF (half-duplex "gantian") — heading terbaca real **saat robot berlayar bebas**, bukan cuma saat tertambat kabel USB.
- **Telemetri estimasi:** fase misi, RPM/kecepatan estimasi dari PWM (robot belum punya sensor RPM).
- **Logging:** semua aktivitas tercatat, ekspor CSV/TXT.
- **Mode simulasi:** GUI jalan tanpa hardware NRF (di PC) untuk pengujian/demo.

---

## Perangkat Keras & Wiring

Robot: **ESP32**, **NRF24L01+**, **MPU6050**, **2× ESC Brushless 30A** (unidirectional) + 2 motor. Transmitter: **Raspberry Pi 4** + NRF24L01+.

**Robot (ESP32):**

| Modul | Pin | ESP32 |
|---|---|---|
| NRF24L01+ | CE / CSN | GPIO4 / GPIO5 |
| NRF24L01+ | SCK / MOSI / MISO | GPIO18 / GPIO23 / GPIO19 |
| MPU6050 | SDA / SCL | GPIO21 / GPIO22 |
| ESC Kiri / Kanan | Signal | GPIO25 / GPIO26 |

**Transmitter (Raspberry Pi):** NRF24L01+ pada SPI (CE=GPIO24, CSN=CE0).

> NRF **wajib 3.3V** (bukan 5V). Di ESP32 jangan pakai GPIO9/10 (pin flash internal). Wiring lengkap: [Custom PCB/](Custom%20PCB/) dan `Master Code/Robot/New/Finalnew/Pin Details.txt`.

---

## Protokol Komunikasi

Paket dari Transmitter ke Robot (NRF: alamat `00001`, channel `0x76`, 250 KBPS, PA_LOW):

| Paket | Makna |
|---|---|
| `P=<m>;L=<m>;MODE=AUTO;SPD=<m/s>;LW=<m>;DIR=<R\|L>` | Misi zigzag: dimensi + kecepatan + lebar lintasan + arah belok pertama. `SPD/LW/DIR` opsional (robot pakai default bila tak ada). |
| `PING` | Heartbeat tiap 0,5 s (menjaga failsafe + memicu giliran telemetri) |
| `STOP` | Batalkan misi / matikan motor |

Jalur balik **Robot → Pi** (alamat `00002`, half-duplex "gantian"): robot mengirim telemetri MPU `R=<roll>;P=<pitch>;Y=<yaw>` sesudah menerima PING; Pi mendengarkan sebentar untuk menangkapnya. Window TX robot ~1 ms + throttle sehingga heartbeat tidak terganggu.

---

## Struktur Repository

```
Master Code/
  Robot/New/Finalnew/Finalnew.ino     Firmware ESP32 (aktif)
  Robot/Old/...                       Versi firmware lama
  Transmitter/
    receiverArduino.py                ENTRY POINT (GUI default, --cli mode teks)
    feeder_gui.py                     GUI CustomTkinter (keypad, preview, telemetri)
    feeder_core.py                    Backend: RadioLink, plan_coverage, estimator, logger, MPU
    requirements.txt                  Dependensi Python
    setup_pi.sh / run.sh              Instalasi & run di Raspberry Pi
    Dokumentasi_*.pdf                 Dokumentasi kode & SDLC
Flowchart Images/                     PNG hasil render flowchart.md
flowchart.md                          Diagram alur (mermaid)
Custom PCB/  Schematic/               Desain PCB & skematik
platformio.ini  select_sketch.py      Build firmware (PlatformIO)
Test Part/                            Sketsa uji (mis. MPU Test)
```

---

## Cara Menjalankan

### Transmitter (aplikasi GUI)

```bash
cd "Master Code/Transmitter"
pip install customtkinter pyserial          # di PC (mode simulasi)
# di Raspberry Pi tambahkan:  pip install pyrf24
python receiverArduino.py                    # buka GUI (default)
python receiverArduino.py --cli              # mode teks lama
```

Di PC (tanpa NRF) GUI otomatis **mode simulasi**. Di Raspberry Pi (dengan `pyrf24`) memakai NRF asli — butuh sesi Desktop (HDMI/VNC), lihat `setup_pi.sh`.

![Antarmuka GUI](Master%20Code/Transmitter/gui_screenshot.png)

### Firmware Robot (ESP32)

Buka `Master Code/Robot/New/Finalnew/Finalnew.ino` di Arduino IDE (atau build via PlatformIO / `platformio.ini`), pasang library **RF24, MPU6050_tockn, ESP32Servo**, lalu flash ke ESP32. Kalibrasi `ROBOT_SPEED_MPS` dan `TURN_90_MS` saat uji di air.

---

## Dokumentasi

- **[Dokumentasi GUI Feeder (SDLC Prototyping)](Master%20Code/Transmitter/Dokumentasi_GUI_Feeder_SDLC.pdf)** — analisis, perancangan, pengujian aplikasi.
- **[Dokumentasi Kode — Firmware Finalnew.ino](Master%20Code/Robot/New/Finalnew/Dokumentasi_Kode_Finalnew.pdf)** — penjelasan firmware baris demi baris.
- **[Dokumentasi Kode — receiverArduino.py](Master%20Code/Transmitter/Dokumentasi_Kode_receiverArduino.pdf)** — entry point Transmitter.
- **[Troubleshooting NRF24](Master%20Code/Robot/New/Finalnew/Dokumentasi_Troubleshooting_NRF.pdf)** — masalah wiring/koneksi radio.
- **[flowchart.md](flowchart.md)** — diagram alur sistem, transmitter, receiver, misi zigzag, heading-hold, path planning.

---

## Status & Iterasi Berikutnya

Sudah berjalan: kendali zigzag otomatis di air, heading-hold, perencanaan jalur + preview, keypad layar, protokol diperluas, failsafe, dan **telemetri MPU 2 arah lewat radio** (half-duplex "gantian"). Rencana lanjutan:

- **Sensor RPM/encoder** menggantikan estimasi kecepatan/RPM.
- Belok berbasis **sudut yaw MPU** (bukan durasi timer).
- **Path waypoint bebas** (klik banyak titik), bukan hanya sapuan persegi.
- Perluas telemetri balik (status komponen, throttle nyata, baterai).
