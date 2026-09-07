# Panduan Operasional Pengendali Utama (Raspberry Pi 4)

Panduan ini untuk **menyalakan dan menjalankan** Pengendali Utama robot feeder,
langkah demi langkah, dengan bahasa sehari-hari. Tidak perlu pengalaman Linux.

> **Bedanya dengan `README_RASPBERRY.md`:**
> Berkas itu untuk **memasang** program pertama kali (sekali seumur hidup Pi).
> Berkas **ini** untuk **memakai** alatnya sehari-hari — urutan colok kabel,
> menyalakan, dan membuka GUI.
>
> Kalau Pi Anda **belum pernah** dipasangi program ini, kerjakan dulu
> [Bagian 6 — Pemasangan Pertama Kali](#6-pemasangan-pertama-kali-sekali-saja).

---

## 1. Yang perlu disiapkan

| Barang | Keterangan |
| --- | --- |
| Raspberry Pi 4 | Sudah terpasang kartu microSD berisi Raspberry Pi OS |
| Adaptor USB Type-C | 5V 3A. Pakai adaptor resmi kalau ada |
| Layar LCD kecil | Layar sentuh 7 inci (800 × 480) |
| Kabel HDMI → micro-HDMI | Ujung besar ke LCD, ujung kecil ke Pi |
| Terminal listrik | Colokan/stop kontak untuk adaptor |
| Modul NRF24L01 | Sudah terpasang di pin Pi (lihat `README_RASPBERRY.md`) |

Keyboard dan mouse **tidak wajib** — GUI-nya dirancang untuk layar sentuh.
Tapi untuk pertama kali, keyboard sangat membantu.

---

## 2. Urutan mencolok kabel

> **Urutannya penting.** Raspberry Pi memeriksa layar **hanya sekali, saat
> menyala**. Kalau HDMI baru dicolok setelah Pi hidup, layarnya akan tetap
> gelap walaupun semuanya normal — dan itu sering dikira Pi-nya rusak.
>
> Jadi: **colok layar dulu, listrik paling akhir.**

### Langkah 2.1 — Pasang kabel HDMI ke layar LCD

Ambil kabel HDMI. **Ujung yang besar** dicolokkan ke port HDMI di belakang
layar LCD 7 inci.

### Langkah 2.2 — Pasang ujung micro-HDMI ke Raspberry Pi

**Ujung yang kecil (micro-HDMI)** dicolokkan ke Raspberry Pi 4.

> **PERHATIAN — Pi 4 punya DUA lubang micro-HDMI yang bentuknya sama persis.**
> Pakai yang **paling dekat dengan lubang listrik Type-C**. Lubang itu namanya
> **HDMI0**.
>
> Kalau salah colok ke lubang yang satunya (HDMI1), Pi tetap menyala normal
> tetapi **layar tidak menampilkan apa-apa**. Ini penyebab "layar hitam" yang
> paling sering terjadi pada Pi 4.

```
        Tampak samping Raspberry Pi 4

   [ Type-C ] [ HDMI0 ] [ HDMI1 ] [ Audio ]
    listrik      ^
                 |
        PAKAI YANG INI — paling dekat colokan listrik
```

### Langkah 2.3 — Nyalakan layar LCD

Kalau LCD punya adaptor sendiri, colokkan ke terminal listrik sekarang.
Sebagian LCD 7 inci mengambil listrik dari USB Pi — kalau begitu, colokkan
kabel USB-nya ke port USB Pi.

### Langkah 2.4 — Baru colokkan listrik Raspberry Pi

Colokkan **adaptor USB Type-C** ke terminal listrik, lalu **ujung Type-C-nya
ke Raspberry Pi**.

Raspberry Pi **tidak punya tombol power**. Begitu listrik masuk, ia langsung
menyala sendiri.

**Yang harus terlihat:**
- Lampu **merah** di Pi menyala terus → listrik masuk
- Lampu **hijau** berkedip-kedip → kartu microSD sedang dibaca (ini normal dan bagus)
- Layar menampilkan logo Raspberry lalu masuk ke desktop, sekitar 30–60 detik

---

## 3. Membuka Terminal

Setelah desktop muncul, buka **Terminal** — jendela hitam tempat mengetik perintah.

**Cara 1 (paling cepat):** tekan bersamaan `Ctrl` + `Alt` + `T`

**Cara 2 (pakai sentuhan):** sentuh ikon Terminal di bilah atas layar — bentuknya
kotak hitam dengan tanda `>_`

Akan muncul tulisan seperti ini:

```
pi@raspberrypi:~ $
```

Tanda `$` di ujung artinya Terminal siap menerima perintah.

---

## 4. Menjalankan GUI

Ketik dua perintah berikut. **Tekan `Enter` setelah setiap baris.**

```bash
cd ~/feeder
```

```bash
./run.sh
```

Penjelasan singkat supaya tidak sekadar menghafal:

- `cd ~/feeder` artinya "masuk ke folder bernama `feeder`". Di situlah programnya
  disimpan. Tanda `~` berarti folder milik Anda sendiri.
- `./run.sh` artinya "jalankan berkas `run.sh` yang ada di folder ini". Berkas itu
  yang membuka GUI-nya.

**Yang harus terjadi:** layar berubah menjadi tampilan GUI Feeder layar penuh,
dengan dua tombol besar: **MISI** dan **SETTING**.

Kalau sudah muncul, Pengendali Utama siap dipakai.

---

## 5. Hal penting saat memakai

### Program selalu mulai dalam MODE SIMULASI

Ini disengaja demi keamanan. Di mode simulasi, semua perintah dijalankan oleh
**robot virtual** — robot sungguhan **tidak akan bergerak**. Aman untuk berlatih
dan demo.

Untuk benar-benar menggerakkan robot, sentuh tombol **MODE** di bilah atas, lalu
pilih **REAL**.

> Perpindahan mode **ditolak** selagi ada perintah yang sedang berjalan. Tekan
> **STOP** dulu, baru ganti mode.

### Alur pemakaian

**BERANDA → MISI → DASHBOARD**

1. Sentuh **MISI**
2. Isi panjang dan lebar tambak (papan angka akan terbuka saat kolomnya disentuh)
3. Sentuh **KIRIM MISI KE ROBOT** — layar otomatis pindah ke DASHBOARD
4. Pantau dari DASHBOARD: status robot, perintah yang sedang jalan, sudut MPU
   (Roll/Pitch/Yaw), dan tombol **STOP** merah besar

Tombol **STOP** merah aktif dari halaman mana pun. Itu tombol berhenti darurat.

### Menutup program

- Tekan `Escape` atau `F11` → keluar dari layar penuh menjadi jendela biasa
- Atau lewat **SETTING → SISTEM → tombol keluar**

### Mematikan Raspberry Pi

**Jangan langsung cabut listrik.** Kartu microSD bisa rusak kalau dicabut
paksa saat sedang menulis data.

Cara benar: menu Raspberry (pojok kiri atas) → **Shutdown**. Tunggu sampai lampu
hijau berhenti berkedip, **baru** cabut listriknya.

Lewat Terminal juga bisa:

```bash
sudo shutdown -h now
```

---

## 6. Pemasangan pertama kali (sekali saja)

Lewati bagian ini kalau Pi Anda sudah pernah dipasangi program ini.

### 6.1 Salin program ke Raspberry Pi

Pindahkan berkas `raspberry_feeder.zip` ke Pi (lewat flashdisk atau unduh dari
GitHub), lalu di Terminal:

```bash
cd ~
unzip raspberry_feeder.zip
mv raspberry_feeder feeder
cd ~/feeder
```

Sekarang program ada di folder `~/feeder`.

### 6.2 Jalankan skrip pemasangan

```bash
chmod +x setup_pi.sh run.sh
```

```bash
./setup_pi.sh
```

Perintah pertama memberi izin agar kedua berkas itu boleh dijalankan. Perintah
kedua memasang semua yang dibutuhkan: mengaktifkan SPI (untuk radio NRF24),
memasang paket Python, dan membuat lingkungan kerjanya.

Proses ini makan waktu beberapa menit dan butuh **koneksi internet**.

### 6.3 Logout lalu login lagi

**Langkah ini wajib, jangan dilewat.** Skrip tadi menambahkan akun Anda ke grup
`spi`, `gpio`, dan `dialout` supaya program boleh memakai radio NRF24. Perubahan
grup baru berlaku setelah login ulang.

Menu Raspberry → **Logout**, lalu masuk kembali.

Setelah itu, pemakaian sehari-hari cukup mengikuti Bagian 2 sampai 4.

---

## 7. Kalau ada masalah

| Yang terjadi | Kemungkinan sebab | Yang dilakukan |
| --- | --- | --- |
| Layar gelap, lampu merah Pi menyala | micro-HDMI salah lubang | Pindah ke **HDMI0** — yang dekat colokan Type-C |
| Layar gelap, sudah di HDMI0 | HDMI dicolok setelah Pi menyala | Matikan Pi, colok HDMI, baru nyalakan |
| Lampu hijau tidak pernah berkedip | microSD tidak terbaca | Cabut-pasang ulang kartu microSD |
| Muncul gambar petir ⚡ di layar | Listrik kurang kuat | Ganti adaptor dengan yang 5V 3A |
| `cd ~/feeder` → `No such file or directory` | Folder belum ada | Kerjakan Bagian 6 dulu |
| `./run.sh` → `Permission denied` | Berkas belum boleh dijalankan | Ketik `chmod +x run.sh` lalu ulangi |
| `./run.sh` → `command not found` | Salah folder | Ketik `cd ~/feeder` dulu |
| GUI muncul tapi robot diam | Masih mode SIMULASI | Sentuh **MODE** → pilih **REAL** |
| Mode REAL tapi robot tetap diam | Radio NRF tidak tersambung | Cek wiring NRF di `README_RASPBERRY.md`, pastikan VCC **3.3V** |

### Perintah cadangan kalau `run.sh` bermasalah

Kalau `./run.sh` tetap gagal, GUI bisa dibuka manual:

```bash
cd ~/feeder
source ~/feeder-venv/bin/activate
python3 receiverArduino.py
```

### Pilihan lain saat menjalankan

```bash
./run.sh --windowed    # tampil sebagai jendela, tidak layar penuh
./run.sh --real        # langsung mode REAL, tanpa lewat tombol MODE
./run.sh --cli         # mode teks, tanpa GUI
```

---

## 8. Ringkasan sekali lihat

Untuk pemakaian sehari-hari, hanya ini yang perlu diingat:

1. Colok **HDMI** ke LCD, ujung kecilnya ke **HDMI0** Pi (dekat colokan listrik)
2. Nyalakan **LCD**
3. Colok **Type-C** ke terminal listrik, lalu ke Pi — Pi menyala sendiri
4. Tunggu desktop muncul, tekan `Ctrl` + `Alt` + `T`
5. Ketik `cd ~/feeder` lalu `./run.sh`
6. Sentuh **MODE** → **REAL** kalau mau menggerakkan robot sungguhan
7. Selesai: **Shutdown** dari menu, baru cabut listrik
