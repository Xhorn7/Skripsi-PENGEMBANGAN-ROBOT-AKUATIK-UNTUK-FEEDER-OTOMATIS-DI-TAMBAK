# Pengembangan Robot Akuatik untuk Feeder Otomatis di Tambak

Skripsi. Robot perahu otomatis yang menyebar pakan di tambak berbentuk persegi. Operator memasukkan **dimensi tambak, titik awal, lebar lintasan, dan kecepatan** lewat aplikasi; aplikasi menerjemahkannya menjadi **antrean perintah gerak** (`FW` / `CW` / `CCW`), lalu mengirimkannya satu per satu ke robot dan menunggu konfirmasi tiap perintah selesai.

![Gambaran sistem](Flowchart%20Images/01-1-gambaran-sistem.png)

---

## Gambaran Sistem

Dua sub-sistem yang terhubung nirkabel lewat modul radio **NRF24L01+**:

| Sub-sistem | Perangkat | Peran |
|---|---|---|
| **Pengendali Utama** | Raspberry Pi + layar sentuh 7" | Aplikasi GUI: input misi, perencanaan jalur, susun & kirim antrean perintah, pantau status, logging |
| **Body Robot** | ESP32 | Terima & validasi perintah, jalankan **satu** gerakan, heading-hold MPU6050, kendali 2 motor brushless |

Protokol mengikuti **Dokumen Spesifikasi Teknis — Robot Akuatik untuk Tambak Ikan** (bab Skema Komunikasi), mengadopsi skema **DJI Tello SDK 2.0**: pola **Request-Response** dengan sinyal balik `ON` dan `FIN`. Detail alur ada di [flowchart.md](flowchart.md) dan folder [Flowchart Images/](Flowchart%20Images/).

> **Pola jalur ada di aplikasi, bukan di firmware.** Robot hanya eksekutor satu perintah, sehingga pola sapuan bisa diubah **tanpa flash ulang** ESP32.

---

## Fitur

- **Perencanaan jalur (path planning):** dari dimensi tambak + titik awal + lebar lintasan + kecepatan → daftar segmen *maju/belok* (pola *boustrophedon*/zigzag) → **antrean perintah** `FW`/`CW`/`CCW`. Lebar tambak dibagi menjadi `⌈lebar / lebar lintasan⌉` pita, dan jalur ditaruh di **setiap pembatas pita termasuk kedua tepi** — jadi jalur pertama & terakhir menempel di dinding tambak dan lintasan benar-benar mencapai ujung kotak.
- **Deteksi MPU mati:** robot melaporkan kesehatan sensornya (`S=0`) bila bus I2C tidak menjawab; GUI menandainya merah, dan firmware menonaktifkan *heading-hold* serta turun ke putaran open-loop alih-alih mengemudi dengan sudut palsu.
- **Preview jalur:** kanvas peta tambak + daftar perintah yang akan dikirim, sebelum misi dijalankan.
- **Kendali manual:** maju diisi dalam **meter** (0,1–50 m) lalu dipecah otomatis jadi paket `FW` 10–200 cm; putar `CW` / `CCW` (1–180°), plus `STOP` darurat.
- **GUI mengikuti ukuran layar:** dirancang untuk **layar sentuh 7 inci** (800 × 480) bergaya mesin ATM. Beranda hanya menawarkan **MISI** dan **SETTING**; **dashboard terbuka sendiri** begitu misi dikirim (status, koordinat MPU, STOP besar). Papan angka layar penuh — operasi penuh **tanpa keyboard fisik**.
- **Request-Response dengan pengiriman ulang:** bila `ON [Moves]` tak diterima dalam 1 detik, perintah dikirim ulang (maks 5×).
- **Heading-hold proporsional:** robot berjalan lurus dengan koreksi arah dari MPU6050 (Kp × error).
- **Putaran closed-loop:** sudut `CW`/`CCW` ditutup memakai umpan balik yaw MPU — tanpa kalibrasi durasi belok.
- **Zigzag menyapu penuh:** arah U-turn **berselang-seling** sehingga sapuan menutupi seluruh lebar tambak.
- **Failsafe heartbeat:** robot berhenti otomatis bila sinyal Pengendali Utama hilang > 3 detik.
- **Telemetri MPU 2 arah (radio):** robot mengirim balik roll/pitch/yaw lewat NRF — **tanpa port serial sama sekali**. Sudut mengalir di latar belakang selama heartbeat hidup; saklar **Log MPU** menyalakan pencatatannya.
- **Telemetri estimasi:** RPM/kecepatan diperkirakan dari PWM perintah yang sedang berjalan (robot belum punya sensor RPM).
- **Logging:** **menyala sejak aplikasi dibuka** — tiap kejadian (termasuk sudut MPU) langsung ditulis ke `logs/log_feeder_*.txt`, dan berkas **> 3 hari dihapus otomatis** supaya kartu SD Raspberry Pi tidak penuh. Ekspor CSV/TXT sekali jalan tetap ada.
- **Mode REAL/SIMULASI dapat dipindah:** aplikasi **selalu mulai di SIMULASI** (robot tiruan membalas `ON`/`FIN` + telemetri MPU), lalu operator memindahkannya ke NRF sungguhan lewat chip **MODE** di bilah atas, pemilih di SETTING > SISTEM, atau flag `--real`.

---

## Perangkat Keras & Wiring

Robot: **ESP32**, **NRF24L01+**, **MPU6050**, **2× ESC Brushless 30A** (unidirectional) + 2 motor. Pengendali Utama: **Raspberry Pi** + NRF24L01+ + layar sentuh 7".

**Robot (ESP32):**

| Modul | Pin | ESP32 |
|---|---|---|
| NRF24L01+ | CE / CSN | GPIO4 / GPIO5 |
| NRF24L01+ | SCK / MOSI / MISO | GPIO18 / GPIO23 / GPIO19 |
| MPU6050 | SDA / SCL | GPIO21 / GPIO22 |
| ESC Kiri / Kanan | Signal | GPIO25 / GPIO26 |

**Pengendali Utama (Raspberry Pi):** NRF24L01+ pada SPI (CE=GPIO24, CSN=CE0).

> NRF **wajib 3.3V** (bukan 5V). Di ESP32 jangan pakai GPIO9/10 (pin flash internal). Wiring lengkap: [Custom PCB/](Custom%20PCB/) dan `Master Code/Robot/New/Finalnew/Pin Details.txt`.

---

## Protokol Komunikasi

NRF: channel `0x76`, 250 KBPS, PA_LOW. Perintah di alamat `00001`, sinyal balik di alamat `00002`.

**Pengendali Utama → Robot:**

| Paket | Rentang | Makna |
|---|---|---|
| `FW:<dist>` | 10–200 cm | Maju lurus ke depan |
| `CW:<deg>` | 1–180° | Berputar searah jarum jam (ke kanan) |
| `CCW:<deg>` | 1–180° | Berputar berlawanan jarum jam (ke kiri) |
| `STOP:0` | 0 | Hentikan motor — berhenti darurat |
| `PING` | — | Heartbeat tiap 0,5 s (menjaga failsafe + memicu giliran bicara robot) |

**Robot → Pengendali Utama:**

| Paket | Makna |
|---|---|
| `ON <Moves>` | Perintah sedang dijalankan — dikirim tiap 1 detik selama bergerak |
| `FIN <Moves>:<Dist>` | Perintah selesai — izin lanjut ke perintah berikutnya |
| `R=<roll>;P=<pitch>;Y=<yaw>;S=<kode>` | Telemetri sudut MPU (tambahan, di luar spesifikasi wajib). `S`: `1` sehat, `0` bus sehat tanpa jawaban, `2` modul di 0x69, `3` gyro belum terkalibrasi, `4` ACK tanpa data, `5` SDA/SCL diam LOW |

**Siklus satu perintah:**

```
Pi  ->  FW:200
Pi  <-  ON FW              (< 1 detik, kalau tidak -> kirim ulang, maks 5x)
Pi  <-  ON FW              (berulang tiap 1 detik selama bergerak)
Pi  <-  FIN FW:200         (selesai -> lanjut perintah berikutnya)
```

Gerakan yang **tidak tuntas** (kena `STOP` atau sinyal hilang) sengaja **tidak** dibalas `FIN`, sehingga sisa antrean otomatis dibatalkan.

Komunikasi bersifat **half-duplex "gantian"** seperti radio HT — satu modul NRF tidak bisa kirim & terima bersamaan, jadi kedua sisi bergantian bicara.

---

## Struktur Repository

```
Master Code/
  Robot/New/Finalnew/
    Finalnew.ino                      Firmware ESP32 (aktif)
    Dokumen Spesifikasi Teknis_*.docx Acuan perilaku robot & protokol
    Dokumentasi_Kode_Finalnew.*       Dokumentasi firmware
  Robot/Old/...                       Versi firmware lama
  Transmitter/
    receiverArduino.py                ENTRY POINT (--windowed, --real, --cli)
    feeder_gui.py                     GUI CustomTkinter (6 halaman, gaya ATM)
    feeder_core.py                    RobotCommand, RadioLink (REAL/SIMULASI),
                                      CommandRunner, path planner,
                                      logger + auto-simpan, MPUMonitor
    logs/                             Berkas auto-simpan TXT (dibuat otomatis)
    capture_gui.py                    Screenshot tiap halaman GUI
    build_docs_pdf.py                 Generator PDF dokumentasi SDLC
    build_code_docs_pdf.py            Generator PDF dokumentasi kode (md -> pdf)
    requirements.txt                  Dependensi Python
    setup_pi.sh / run.sh              Instalasi & run di Raspberry Pi
Flowchart Images/                     PNG hasil render flowchart.md
flowchart.md                          Diagram alur (mermaid)
render_flowcharts.py                  Render flowchart.md -> PNG
Custom PCB/  Schematic/               Desain PCB & skematik
platformio.ini  select_sketch.py      Build firmware (PlatformIO)
Test Part/                            Sketsa uji (mis. MPU Test)
```

---

## Cara Menjalankan

### Pengendali Utama (aplikasi GUI)

```bash
cd "Master Code/Transmitter"
pip install customtkinter                   # cukup ini untuk mode simulasi
# di Raspberry Pi tambahkan:  pip install pyrf24

python receiverArduino.py                   # GUI layar penuh (mulai mode SIMULASI)
python receiverArduino.py --windowed        # jendela 800x480 (uji di PC)
python receiverArduino.py --real            # langsung memakai NRF sungguhan
python receiverArduino.py --cli             # mode teks
```

GUI **selalu terbuka di mode SIMULASI** — aman untuk latihan & demo. Pindah ke NRF sungguhan dengan menyentuh chip **MODE** di bilah atas, memilih **REAL** pada SETTING > SISTEM, atau menjalankan dengan `--real`; perpindahan ditolak selagi ada perintah berjalan. Kendali nyata butuh Raspberry Pi (`pyrf24`) dengan sesi Desktop (HDMI/VNC), lihat `setup_pi.sh`. Saat layar penuh, **Escape** atau **F11** mengembalikan ke mode jendela.

![Antarmuka GUI](Master%20Code/Transmitter/gui_screenshot.png)

Alur: **BERANDA** (MISI · SETTING) → **MISI** (ukur tambak, preview jalur) → **DASHBOARD** (terbuka otomatis: status, koordinat MPU, STOP). **SETTING** memuat SISTEM · MANUAL · LOG. Tombol STOP merah di bilah atas aktif dari halaman mana pun.

### Firmware Robot (ESP32)

Build via PlatformIO (`platformio.ini` sudah disiapkan):

```bash
pio run -e esp32dev -t upload      # flash firmware produksi (radio + MPU + ESC)
pio run -e movetest -t upload      # tes gerak tanpa radio
pio run -e mputest  -t upload      # kalibrasi MPU + cek bus I2C
pio run -e mpudiag  -t upload      # diagnosa I2C (scan bus + dump register)
pio run -e esctest  -t upload      # tes ESC/motor murni
pio device monitor                 # pantau Serial 115200
```

Atau buka `Master Code/Robot/New/Finalnew/Finalnew.ino` di Arduino IDE dengan library **RF24, MPU6050_tockn, ESP32Servo**.

**Kalau upload gagal**, bedakan dulu pesannya — dua ini sangat berbeda artinya:

| Pesan esptool | Arti | Tindakan |
|---|---|---|
| `Wrong boot mode detected (0x13)` | Chip ter-reset tapi masuk boot normal, bukan mode download. Rangkaian auto-reset tidak menarik GPIO0 ke LOW. **Bukan kerusakan.** | Tahan `BOOT` selama fase `Connecting...`, lepas saat muncul `Writing at`. Tanpa tombol BOOT: jumper GPIO0→GND, ketuk EN, lalu cabut jumper. |
| `Failed to communicate with the flash chip` | ESP32 tidak bisa membaca flash internalnya. Hampir selalu **rel 3,3 V tidak stabil**, bukan chip rusak. | Cabut semua modul (MPU/NRF/ESC) lalu upload lagi. Kalau berhasil, ada modul yang menarik rel — ukur resistansi VCC–GND tiap modul. |

> Pengalaman nyata di proyek ini: modul MPU6050 yang short membuat ESP32 gagal di-flash **dan** Arduino Nano gagal masuk bootloader. Kalau upload tiba-tiba gagal padahal sebelumnya lancar, curigai modul yang tersambung sebelum mencurigai board-nya.

**Kalibrasi saat uji di air:**

| Konstanta | Cara |
|---|---|
| `ROBOT_SPEED_MPS` | Perintahkan `FW:200`, ukur jarak nyata, sesuaikan |
| `YAW_SIGN` | Perintahkan `CW:90`; kalau robot berputar ke kiri, ubah jadi `-1` |
| `KP_HEADING` | Terlalu kecil: melenceng. Terlalu besar: bergoyang kiri-kanan |

> **Sebelum mengkalibrasi, pastikan MPU benar-benar terbaca.** Serial akan mencetak `MPU6050 terdeteksi di 0x68` saat boot. Kalau telemetri diam di `Roll=-90.0 Pitch=90.0 Yaw=-0.0`, itu **bukan** sudut sungguhan melainkan sidik jari bus I2C yang tidak menjawab — periksa SDA=GPIO21, SCL=GPIO22, 3.3 V, GND, dan AD0→GND. Mengkalibrasi `KP_HEADING`/`YAW_SIGN` dalam kondisi itu percuma.

### Regenerate dokumentasi

```bash
cd "Master Code/Transmitter"
python capture_gui.py            # screenshot tiap halaman GUI
python build_docs_pdf.py         # Dokumentasi_GUI_Feeder_SDLC.pdf
python build_code_docs_pdf.py    # 3 PDF dokumentasi kode
python build_raspberry_zip.py    # raspberry_feeder.zip (paket untuk Pi)

cd ../..
python render_flowcharts.py      # Flowchart Images/*.png dari flowchart.md
```

### Pengujian gerak

Skrip di folder `Pengujian/` bisa dijalankan dari PC maupun laptop (path relatif, tidak bergantung mesin):

```bash
pip install -r Pengujian/requirements.txt
python Pengujian/build_skenario.py                        # Rancangan_Skenario_Pengujian_Gerak.docx + .pdf
python Pengujian/ukur_foto.py sebelum.jpg sesudah.jpg     # sudut belok aktual dari foto HP tampak atas
```

PDF dibuat lewat Microsoft Word atau LibreOffice bila tersedia; kalau tidak ada, cukup DOCX-nya.

---

## Dokumentasi

- **[Dokumentasi GUI Feeder (SDLC Prototyping)](Master%20Code/Transmitter/Dokumentasi_GUI_Feeder_SDLC.pdf)** — analisis, perancangan, pengujian aplikasi.
- **[Dokumentasi Kode — Firmware Finalnew.ino](Master%20Code/Robot/New/Finalnew/Dokumentasi_Kode_Finalnew.pdf)** — penjelasan firmware.
- **[Dokumentasi Kode — receiverArduino.py](Master%20Code/Transmitter/Dokumentasi_Kode_receiverArduino.pdf)** — entry point Pengendali Utama.
- **[Troubleshooting NRF24](Master%20Code/Robot/New/Finalnew/Dokumentasi_Troubleshooting_NRF.pdf)** — masalah wiring/koneksi radio.
- **[Rancangan Skenario Pengujian Gerak](Pengujian/Rancangan_Skenario_Pengujian_Gerak.pdf)** — 9 skenario uji (lurus, belok, kotak, zigzag) dengan pengukuran cukup HP + meteran.
- **[flowchart.md](flowchart.md)** — diagram alur sistem, kedua sisi, siklus Request-Response, heading-hold, putaran closed-loop, path planning, sinyal balik.

---

## Status & Iterasi Berikutnya

Sudah berjalan: perencanaan jalur + preview, antrean perintah `FW`/`CW`/`CCW`, kendali manual bersatuan meter, protokol Request-Response dengan `ON`/`FIN` dan pengiriman ulang, heading-hold, putaran closed-loop yaw, failsafe, GUI layar sentuh 7", telemetri MPU 2 arah tanpa kabel, pemilihan mode REAL/SIMULASI, serta auto-simpan log TXT.

> **Catatan:** protokol baru sudah diverifikasi penuh lewat **mode simulasi** (robot tiruan membalas `ON`/`FIN`); firmware **belum diuji di hardware nyata**.

Rencana lanjutan:

- **Odometri / GPS** agar jarak `FW` tidak lagi diturunkan dari waktu tempuh — tahan terhadap arus air.
- **Sensor RPM/encoder** menggantikan estimasi kecepatan/RPM.
- **Path waypoint bebas** (sentuh banyak titik), bukan hanya sapuan persegi.
- Perluas isi sinyal balik (status komponen, throttle nyata, tegangan baterai).
- Perintah untuk **kontrol komponen individual** (motor kiri/kanan, MPU).
