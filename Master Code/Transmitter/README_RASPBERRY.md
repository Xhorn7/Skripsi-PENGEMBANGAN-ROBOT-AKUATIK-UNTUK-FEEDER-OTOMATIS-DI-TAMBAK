# Panduan Menjalankan GUI Feeder di Raspberry Pi

Panel kontrol robot feeder akuatik. Jalankan **satu** berkas `receiverArduino.py`
→ GUI + telemetri + logging langsung aktif.

---

## 1. Kebutuhan

### Perangkat keras
- Raspberry Pi (3/4/5) dengan **Raspberry Pi OS Desktop** (butuh layar/desktop untuk GUI —
  langsung ke monitor HDMI **atau** lewat VNC).
- Modul **NRF24L01** terhubung ke pin SPI Pi (lihat tabel wiring di bawah).
- *(Opsional untuk data MPU)* board **ESP32 berisi `mpu.ino`** dicolok via **USB** ke Pi.

### Perangkat lunak
- Python 3 (sudah bawaan Raspberry Pi OS).
- Paket sistem: `python3-tk` (untuk GUI), `python3-venv`.
- Paket Python: `customtkinter`, `pyrf24`, `pyserial` (lihat `requirements.txt`).

---

## 2. Wiring NRF24L01 → Raspberry Pi

Kode memakai `RF24(24, 0)` → **CE = GPIO24**, **CSN = CE0 (SPI0)**.

| NRF24L01 | Raspberry Pi (BCM) | Pin fisik |
| -------- | ------------------ | --------- |
| VCC      | 3.3V               | 1 atau 17 |
| GND      | GND                | 6, 9, ... |
| CE       | GPIO24             | 18        |
| CSN      | GPIO8 (CE0)        | 24        |
| SCK      | GPIO11 (SCLK)      | 23        |
| MOSI     | GPIO10 (MOSI)      | 19        |
| MISO     | GPIO9 (MISO)       | 21        |

> **PENTING:** VCC NRF **wajib 3.3V** (bukan 5V). Disarankan tambah kapasitor
> 10µF antara VCC–GND modul NRF agar stabil.

---

## 3. Instalasi (sekali saja)

### Cara CEPAT (otomatis) — disarankan

Ekstrak zip ke `~/feeder`, lalu jalankan skrip setup sekali:

```bash
cd ~/feeder
chmod +x setup_pi.sh run.sh
./setup_pi.sh          # aktifkan SPI + apt + venv + pip install
# lalu LOGOUT-LOGIN sekali (agar grup spi/gpio/dialout aktif)
```

Setelah itu langsung ke **bagian 4 (Menjalankan)**.

### Cara MANUAL (kalau ingin bertahap)

Buka Terminal di Raspberry Pi:

```bash
# 3.1 Aktifkan SPI (untuk NRF24)
sudo raspi-config nonint do_spi 0        # 0 = enable
# (atau: sudo raspi-config -> Interface Options -> SPI -> Enable)

# 3.2 Paket sistem
sudo apt update
sudo apt install -y python3-venv python3-tk

# 3.3 Hak akses SPI / GPIO / Serial (lalu logout-login sekali)
sudo usermod -aG spi,gpio,dialout "$USER"

# 3.4 Salin folder ini ke Pi, mis. ke ~/feeder, lalu:
cd ~/feeder

# 3.5 Buat virtualenv (pakai --system-site-packages agar python3-tk terlihat)
python3 -m venv --system-site-packages ~/feeder-venv
source ~/feeder-venv/bin/activate

# 3.6 Install paket Python
pip install -r requirements.txt
```

---

## 4. Menjalankan

```bash
cd ~/feeder
./run.sh                 # buka GUI (default)
# atau manual:
source ~/feeder-venv/bin/activate
python3 receiverArduino.py

# mode teks lama (tanpa GUI):
./run.sh --cli
```

Kalau `run.sh` belum bisa dieksekusi: `chmod +x run.sh` sekali saja.

### Di dalam GUI
1. Isi **Panjang** & **Lebar** tambak (meter) → **KIRIM MISI**.
2. Panel **Status Koneksi**: MODE = REAL, MODUL NRF = TERDETEKSI, ROBOT =
   TERHUBUNG saat robot meng-ACK.
3. **MPU6050**: isi port (mis. `/dev/ttyUSB0` atau `/dev/ttyACM0`) → **Hubungkan**.
   Nyalakan **Rekam ke log** bila ingin data MPU ikut tersimpan.
4. **Export CSV / TXT** untuk menyimpan log aktivitas.

---

## 5. Masalah Umum

| Gejala | Penyebab / Solusi |
| ------ | ----------------- |
| GUI tak muncul, error `no display` | Jalankan dari sesi Desktop/VNC, bukan SSH polos. Untuk SSH pakai `export DISPLAY=:0` atau aktifkan VNC. |
| Status MODE = SIMULASI padahal di Pi | pyrf24 gagal / SPI belum aktif / wiring salah. Cek `ls /dev/spidev*` harus ada. |
| ROBOT = TERPUTUS terus | Robot belum menyala/listening, channel/address beda, atau NRF kurang daya (kapasitor 3.3V). |
| MPU tak terbaca | Salah port. Cek dengan `ls /dev/ttyUSB* /dev/ttyACM*`; pastikan user di grup `dialout`. |
| `ModuleNotFoundError: customtkinter` | venv belum diaktifkan / `pip install -r requirements.txt` belum jalan. |

---

## 6. (Opsional) Auto-start saat boot

Buat file `~/.config/autostart/feeder.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=Feeder GUI
Exec=/home/pi/feeder/run.sh
```

Ganti `/home/pi/feeder/` sesuai lokasi foldermu.

---

## 7. Isi Paket

| Berkas | Fungsi |
| ------ | ------ |
| `receiverArduino.py` | **Entry point** — jalankan ini |
| `feeder_gui.py` | Antarmuka GUI (CustomTkinter) |
| `feeder_core.py` | Backend: radio, estimator, logger, MPU reader |
| `requirements.txt` | Daftar dependensi Python |
| `setup_pi.sh` | Skrip instalasi otomatis (jalankan sekali) |
| `run.sh` | Launcher (aktifkan venv + jalankan) |
| `Dokumentasi_GUI_Feeder_SDLC.pdf` | Dokumentasi lengkap (metode SDLC) |
