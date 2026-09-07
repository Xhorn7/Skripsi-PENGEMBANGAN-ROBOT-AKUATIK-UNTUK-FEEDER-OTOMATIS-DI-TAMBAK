# Panduan Menyalakan Pengendali Utama (Raspberry Pi 4)

**Untuk operator. Tidak perlu tahu apa-apa soal Linux atau pemrograman.**

Raspberry Pi ini **sudah dipasangi semua programnya**. Anda hanya perlu
mencolok kabel, menyalakan, dan mengetik 4 baris perintah.

---

## RINGKASAN — 6 langkah

Kalau sudah pernah, ini saja yang perlu diingat:

1. Colok **HDMI** ke LCD, ujung kecilnya ke lubang Pi yang **dekat colokan listrik**
2. Colok **Type-C** ke terminal listrik → Pi menyala sendiri
3. Tunggu desktop muncul, cek **WiFi `SmartRoomPrototype`** sudah tersambung
4. Tekan `Ctrl` + `Alt` + `T` → Terminal terbuka
5. Ketik:
   ```
   cd Desktop/Skripsi_Tambak
   sudo bash setup.sh
   sudo bash run.sh
   ```
6. GUI terbuka. Selesai.

Penjelasan lengkap tiap langkah ada di bawah.

---

## 1. Yang perlu disiapkan

| Barang | Keterangan |
| --- | --- |
| Raspberry Pi 4 | Sudah berisi semua program — tidak perlu instal apa pun |
| Adaptor USB Type-C | 5V 3A |
| Layar LCD kecil | Layar sentuh 7 inci |
| Kabel HDMI → micro-HDMI | Ujung besar ke LCD, ujung kecil ke Pi |
| Terminal listrik | Colokan untuk adaptor |

Keyboard dibutuhkan untuk mengetik 3 baris perintah di Langkah 4.
Setelah GUI terbuka, semuanya bisa dioperasikan lewat sentuhan layar.

---

## 2. Mencolok kabel

> **Urutannya penting.** Raspberry Pi memeriksa layar **hanya sekali, tepat saat
> menyala**. Kalau HDMI baru dicolok setelah Pi hidup, layarnya tetap gelap
> walaupun Pi-nya normal — dan itu paling sering dikira Pi-nya rusak.
>
> **Colok layar dulu, listrik paling akhir.**

### 2.1 Kabel HDMI ke layar LCD

**Ujung yang besar** dicolok ke port HDMI di belakang LCD.

### 2.2 Ujung micro-HDMI ke Raspberry Pi

**Ujung yang kecil** dicolok ke Raspberry Pi.

> **PERHATIAN — Pi 4 punya DUA lubang micro-HDMI, bentuknya sama persis.**
> Pakai yang **paling dekat dengan lubang listrik Type-C**.
>
> Salah lubang = Pi tetap menyala tapi **layar tidak menampilkan apa-apa**.
> Ini penyebab "layar hitam" nomor satu di Pi 4.

```
        Tampak samping Raspberry Pi 4

   [ Type-C ] [ HDMI ] [ HDMI ] [ Audio ]
    listrik      ^
                 |
        PAKAI YANG INI — paling dekat colokan listrik
```

### 2.3 Nyalakan LCD

Kalau LCD punya adaptor sendiri, colok sekarang. Kalau LCD-nya mengambil
listrik dari USB, colok kabel USB-nya ke port USB Pi.

### 2.4 Terakhir, colok listrik Pi

Colok **adaptor Type-C** ke terminal listrik, lalu ujungnya ke Raspberry Pi.

Pi **tidak punya tombol power** — begitu listrik masuk, ia langsung menyala.

**Yang harus terlihat:**
- Lampu **merah** menyala terus → listrik masuk
- Lampu **hijau** berkedip-kedip → normal, kartu memori sedang dibaca
- Desktop muncul dalam 30–60 detik

---

## 3. Cek WiFi

Lihat **pojok kanan atas layar**. Harus ada ikon WiFi (bentuk kipas/gelombang).

Pi ini seharusnya **tersambung otomatis** ke WiFi **`SmartRoomPrototype`**.

**Kalau ikonnya tampak terputus** (ada tanda silang, atau bentuknya panah
atas-bawah):

1. Sentuh/klik ikon WiFi itu
2. Pilih **`SmartRoomPrototype`** dari daftar
3. Tunggu sampai ikonnya berubah jadi gelombang penuh

Kalau diminta kata sandi, tanyakan ke pemilik jaringan.

---

## 4. Buka Terminal

Tekan bersamaan: **`Ctrl` + `Alt` + `T`**

Akan muncul jendela hitam dengan tulisan seperti:

```
pi@raspberrypi:~ $
```

Tanda `$` di ujung artinya siap menerima perintah.

> Bisa juga lewat ikon Terminal di bilah atas layar — kotak hitam bertanda `>_`.

---

## 5. Menjalankan program

Ketik **tiga baris** berikut. **Tekan `Enter` setelah setiap baris**, dan tunggu
sampai selesai sebelum mengetik baris berikutnya.

### Baris 1 — masuk ke folder program

```bash
cd Desktop/Skripsi_Tambak
```

> **Huruf besar-kecil BERPENGARUH di Raspberry Pi.** `Desktop` harus pakai
> **D besar**, dan `Skripsi_Tambak` pakai **S** dan **T** besar serta garis
> bawah `_` di tengahnya. Kalau salah satu huruf keliru, akan muncul
> `No such file or directory`.
>
> **Cara aman:** ketik `cd Desk` lalu tekan tombol **`Tab`** — Terminal akan
> melengkapi sendiri jadi `cd Desktop/`. Ketik `Skri` lalu **`Tab`** lagi.
> Cara ini menghilangkan risiko salah ketik sepenuhnya.

### Baris 2 — siapkan program

```bash
sudo bash setup.sh
```

Akan muncul banyak tulisan berjalan. **Itu normal.** Tunggu sampai berhenti dan
tanda `$` muncul lagi.

Kalau diminta kata sandi, ketik kata sandi Raspberry Pi lalu `Enter`.
**Kata sandi tidak akan terlihat saat diketik** — tidak ada bintang, tidak ada
titik, layarnya diam saja. Itu memang perilaku normal Linux, bukan keyboard
yang rusak. Ketik saja sampai selesai lalu tekan `Enter`.

### Baris 3 — buka GUI

```bash
sudo bash run.sh
```

**Yang harus terjadi:** layar berubah jadi tampilan GUI Feeder layar penuh,
dengan dua tombol besar: **MISI** dan **SETTING**.

Kalau sudah muncul, alatnya siap dipakai.

> **Jangan tutup jendela Terminal-nya** selama GUI berjalan. Terminal itu yang
> menjalankan programnya — kalau ditutup, GUI ikut mati.

---

## 6. Memakai GUI

### Program selalu mulai di MODE SIMULASI

Ini disengaja demi keamanan. Di mode simulasi, semua perintah dijalankan
**robot virtual** — robot sungguhan **tidak akan bergerak**. Aman untuk
berlatih dan demo.

Untuk benar-benar menggerakkan robot: sentuh tombol **MODE** di bilah atas,
lalu pilih **REAL**.

> Ganti mode **ditolak** selagi ada perintah berjalan. Tekan **STOP** dulu.

### Alur pemakaian

**BERANDA → MISI → DASHBOARD**

1. Sentuh **MISI**
2. Isi **panjang** dan **lebar** tambak — papan angka terbuka saat kolomnya disentuh
3. Sentuh **KIRIM MISI KE ROBOT** — layar pindah sendiri ke DASHBOARD
4. Pantau dari DASHBOARD: status robot, perintah yang sedang jalan, sudut
   Roll/Pitch/Yaw, dan tombol **STOP** merah besar

Tombol **STOP** merah aktif dari halaman mana pun. Itu tombol berhenti darurat.

---

## 7. Menutup dan mematikan

### Menutup GUI

- Tekan **`Escape`** atau **`F11`** → keluar dari layar penuh
- Atau lewat **SETTING → SISTEM → tombol keluar**
- Atau di jendela Terminal, tekan **`Ctrl` + `C`**

### Mematikan Raspberry Pi

> **JANGAN langsung cabut listrik.** Kartu memori bisa rusak kalau dicabut
> paksa saat sedang menulis data, dan Pi-nya jadi tidak bisa dipakai lagi.

Cara benar: menu **Raspberry** (pojok kiri atas) → **Shutdown**.

Tunggu sampai **lampu hijau berhenti berkedip**, **baru** cabut listriknya.

Lewat Terminal juga bisa:

```bash
sudo shutdown -h now
```

---

## 8. Kalau ada masalah

| Yang terjadi | Sebabnya | Yang dilakukan |
| --- | --- | --- |
| Layar gelap, lampu merah Pi menyala | micro-HDMI salah lubang | Pindah ke lubang yang **dekat colokan Type-C** |
| Layar gelap, lubang sudah benar | HDMI dicolok setelah Pi menyala | Matikan Pi, colok HDMI, baru nyalakan |
| Lampu hijau tidak pernah berkedip | Kartu memori tidak terbaca | Cabut-pasang ulang kartu microSD |
| Muncul gambar petir ⚡ | Listrik kurang kuat | Ganti adaptor dengan 5V 3A |
| `No such file or directory` | Salah ketik huruf besar/kecil | Pakai tombol **`Tab`** untuk melengkapi otomatis |
| Kata sandi tidak muncul saat diketik | Normal di Linux | Ketik terus lalu `Enter` |
| GUI muncul tapi robot diam | Masih mode SIMULASI | Sentuh **MODE** → pilih **REAL** |
| Mode REAL tapi robot tetap diam | Radio NRF tidak tersambung | Cek modul NRF di Pi dan di robot |
| Ikon WiFi terputus | Belum tersambung | Klik ikon WiFi → pilih `SmartRoomPrototype` |
| GUI tiba-tiba tertutup | Terminal ikut tertutup | Buka Terminal lagi, ulangi Langkah 5 |

### Kalau macet dan ingin mengulang dari awal

Tutup Terminal, buka Terminal baru (`Ctrl` + `Alt` + `T`), lalu ulangi:

```bash
cd Desktop/Skripsi_Tambak
sudo bash setup.sh
sudo bash run.sh
```

Mengulang tidak merusak apa pun — aman dilakukan berkali-kali.

---

## Catatan untuk pengembang

Panduan ini mengikuti susunan **Raspberry Pi yang sedang dipakai**: program ada
di `~/Desktop/Skripsi_Tambak`, dijalankan lewat `sudo bash setup.sh` lalu
`sudo bash run.sh`.

Berkas [`README_RASPBERRY.md`](README_RASPBERRY.md) menjelaskan pemasangan dari
nol memakai `raspberry_feeder.zip` (`~/feeder`, `setup_pi.sh`, `./run.sh`).
Susunan itu **berbeda** dengan Pi yang dipakai sekarang — pakai berkas ini
untuk pengoperasian sehari-hari, dan berkas itu bila suatu saat memasang dari
awal di Pi yang masih kosong.
