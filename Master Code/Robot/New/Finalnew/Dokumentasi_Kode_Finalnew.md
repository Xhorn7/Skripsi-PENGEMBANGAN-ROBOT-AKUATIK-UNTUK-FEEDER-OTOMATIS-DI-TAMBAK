# Dokumentasi Kode — Firmware Robot `Finalnew.ino`

Dokumen ini menjelaskan logika firmware **`Finalnew.ino`** yang berjalan di **ESP32** sisi *Body Robot*. Firmware menerima perintah gerak dari Pengendali Utama (Raspberry Pi) melalui modul radio **NRF24L01**, menjalankan satu perintah dalam satu waktu, lalu melaporkan hasilnya kembali.

> **Acuan perilaku:** *Dokumen Spesifikasi Teknis — Robot Akuatik untuk Tambak Ikan*, bab **Skema Komunikasi**. Berkas `.docx`-nya ada di folder yang sama.

---

## 1. Gambaran Umum

Firmware ini adalah **pelaksana perintah**, bukan perencana misi. Ia menerima perintah tingkat rendah seperti *"maju 200 cm"* atau *"putar kanan 90 derajat"*, mengeksekusinya, lalu melapor selesai.

**Perubahan peran dari versi sebelumnya.** Dulu robot menerima satu paket misi (`P=10;L=4;MODE=AUTO`) lalu menjalankan **seluruh pola zigzag sendiri** di dalam firmware. Sekarang pola jalur disusun dan dikemudikan **Pengendali Utama**; robot hanya mengeksekusi satu perintah dan melapor lewat `ON` / `FIN`.

Konsekuensinya:

- Firmware jadi jauh lebih sederhana — tidak ada lagi penghitungan lane, durasi lintasan, atau pembalikan arah U-turn.
- Kemajuan misi yang ditampilkan operator adalah **konfirmasi nyata dari robot**, bukan perkiraan berbasis penghitung waktu.
- Mengubah pola jalur cukup dilakukan di aplikasi, **tanpa flash ulang** ESP32.

**Alur kerja singkat:**

1. Robot menunggu paket berformat `[Moves]:[Dist]`.
2. Paket divalidasi terhadap tabel perintah (rentang `[Dist]` harus sah).
3. Robot mengirim `ON [Moves]` **seketika**, lalu mengulanginya tiap 1 detik selama bergerak.
4. Gerakan dijalankan: `FW` berbasis waktu tempuh dengan *heading-hold*, `CW`/`CCW` berbasis umpan balik sudut yaw MPU.
5. Setelah tuntas, robot mengirim `FIN [Moves]:[Dist]`.
6. Selama bergerak robot memantau **heartbeat**. Bila sinyal hilang > 3 detik atau menerima `STOP`, robot langsung berhenti (*failsafe*) dan **tidak** mengirim `FIN`.

**Sifat penting yang membentuk desain kode:**

- **Komunikasi dua arah half-duplex ("gantian").** Pengendali Utama mengirim perintah/PING; robot menerima, lalu bergiliran mengirim balik `ON`/`FIN`/telemetri MPU di sela-selanya — seperti radio HT.
- **Jarak berbasis waktu (open-loop), sudut berbasis sensor (closed-loop).** Robot tidak punya GPS/encoder, jadi *"maju 200 cm"* diwujudkan sebagai *"maju selama sekian milidetik"*. Sebaliknya *"putar 90 derajat"* ditutup memakai pembacaan yaw MPU sehingga **tidak** bergantung kalibrasi durasi.
- **Belok differential thrust.** Tidak ada kemudi; belok dilakukan dengan mematikan satu motor. Robot **berputar melingkar lebar**, bukan di tempat — sudut akhirnya akurat, tapi posisinya ikut bergeser.

---

## 2. Perangkat Keras & Pustaka

**Pustaka yang di-*include*:**

| Pustaka | Fungsi |
|---|---|
| `SPI.h` | Bus SPI untuk komunikasi ke modul NRF24L01 |
| `RF24.h` | Driver modul radio NRF24L01 |
| `Wire.h` | Bus I2C untuk sensor MPU6050 |
| `MPU6050_tockn.h` | Pembacaan sudut (roll/pitch/yaw) dari MPU6050 |
| `ESP32Servo.h` | Menghasilkan sinyal PWM servo 50 Hz untuk ESC brushless |
| `math.h` | Fungsi `fabs()` |

**Pemetaan pin:**

| Modul | Pin ESP32 | Catatan |
|---|---|---|
| NRF24L01 CE / CSN | GPIO4 / GPIO5 | **Jangan** pakai GPIO9/10 — pin flash internal WROOM, bikin boot-loop |
| MPU6050 SDA / SCL | GPIO21 / GPIO22 | `Wire.begin(21, 22)` |
| ESC Kiri / Kanan | GPIO25 / GPIO26 | Sinyal servo 50 Hz, rentang 1000–2000 µs |

**Alamat radio:**

| Alamat | Arah | Isi |
|---|---|---|
| `00001` | Pi → Robot | Perintah gerak & PING |
| `00002` | Robot → Pi | `ON`, `FIN`, dan telemetri MPU |

---

## 3. Konstanta Kalibrasi

| Konstanta | Nilai | Arti |
|---|---|---|
| `ROBOT_SPEED_MPS` | `0.5f` | Kecepatan jelajah pada `CRUISE_PWM` (m/s). **Wajib diukur di air** — menentukan ketepatan jarak `FW` |
| `CRUISE_PWM` | `1300` | Throttle jelajah (µs) |
| `KP_HEADING` | `8.0f` | Gain proporsional koreksi arah saat maju lurus |
| `MAX_CORRECTION` | `60` | Batas koreksi PWM (µs) agar tidak ekstrem |
| `HEADING_DEADBAND` | `2.0f` | Toleransi error arah (derajat) sebelum koreksi aktif |
| `TURN_TOLERANCE` | `3.0f` | Toleransi sudut akhir putaran (derajat) |
| `TURN_RATE_DPS` | `60.0f` | Perkiraan laju putar (derajat/detik) — hanya untuk **batas waktu**, bukan penentu sudut |
| `SIGNAL_TIMEOUT_MS` | `3000` | Failsafe: berhenti bila tak ada sinyal selama ini |
| `ON_INTERVAL_MS` | `1000` | Interval kirim `ON [Moves]` — **ditetapkan spesifikasi**, jangan diubah |
| `TELEMETRY_INTERVAL_MS` | `200` | Pembatas laju kirim telemetri MPU |
| `YAW_SIGN` | `+1` | Arah tanda yaw MPU. **Ubah jadi `-1` bila hasil uji menunjukkan `CW` malah berputar ke kiri** |

**Batas `[Dist]`** — nilainya sama persis dengan tabel perintah pada dokumen spesifikasi:

| Konstanta | Nilai |
|---|---|
| `FW_MIN_CM` / `FW_MAX_CM` | `10` / `200` |
| `TURN_MIN_DEG` / `TURN_MAX_DEG` | `1` / `180` |

> `TURN_90_MS` dari versi lama **sudah dihapus**. Putaran kini ditutup dengan sensor, sehingga konstanta durasi belok yang rawan itu tidak diperlukan lagi.

---

## 4. Variabel Status Global

| Variabel | Peran |
|---|---|
| `lastSignalMs` | Waktu paket terakhir diterima — dasar perhitungan failsafe |
| `stopRequested` | Ditandai `true` saat paket `STOP` masuk di tengah gerakan |
| `lastTelemetryMs` | Pembatas laju telemetri MPU |
| `lastOnMs` | Waktu terakhir `ON [Moves]` dikirim |
| `moveInProgress` | `true` selama sebuah gerakan berjalan |
| `currentMove` | Nama perintah yang sedang dijalankan (`"FW"` / `"CW"` / `"CCW"`) |

**Enum `MoveResult`** menyatakan alasan berhentinya gerakan:

| Nilai | Arti |
|---|---|
| `MOVE_DONE` | Gerakan tuntas normal → kirim `FIN` |
| `MOVE_STOPPED` | Dibatalkan perintah `STOP` → **tidak** kirim `FIN` |
| `MOVE_LOST_SIGNAL` | Sinyal hilang (failsafe) → **tidak** kirim `FIN` |

> Enum ini sengaja dideklarasikan **di bagian atas berkas**, sebelum fungsi mana pun. Arduino menyisipkan prototipe fungsi otomatis di awal berkas `.ino`; bila enum dideklarasikan di tengah, kompilasi gagal dengan `'MoveResult' does not name a type`.

---

## 5. Fungsi Gerak Dasar (Motor Primitives)

| Fungsi | Aksi |
|---|---|
| `armESC()` | Kirim 1000 µs ke kedua ESC lalu tunggu 5 detik — prosedur *arming* wajib ESC brushless |
| `stopBoat()` | Kedua ESC ke 1000 µs (diam) |
| `spinCW()` | Motor kiri `CRUISE_PWM`, kanan diam → berputar searah jarum jam (ke kanan) |
| `spinCCW()` | Motor kiri diam, kanan `CRUISE_PWM` → berlawanan jarum jam (ke kiri) |

Karena ESC bersifat **unidirectional** (hanya maju), putaran hanya bisa dilakukan dengan differential thrust. Akibatnya robot berputar sambil bergerak maju melingkar — bukan berputar di tempat.

---

## 6. Komunikasi Balik — `sendPacket()` dan turunannya

Semua kiriman dari robot ke Pi melewati satu fungsi:

```
void sendPacket(const char *msg)
{
  radio.stopListening();
  radio.openWritingPipe(telemetryAddress);   // alamat balik "00002"
  radio.write(msg, strlen(msg) + 1, true);   // multicast=true -> NOACK
  radio.startListening();                    // langsung dengar lagi
}
```

Window TX-nya sangat pendek dan dikirim **NOACK** (*fire-and-forget*) supaya robot tidak nge-*block* menunggu balasan dan tidak melewatkan perintah berikutnya.

Tiga pembungkusnya:

| Fungsi | Kiriman | Kapan |
|---|---|---|
| `sendOn(move)` | `ON <move>` | Saat gerakan dimulai, lalu tiap 1 detik |
| `sendFin(move, dist)` | `FIN <move>:<dist>` | Saat gerakan tuntas |
| `maybeSendTelemetry()` | `R=..;P=..;Y=..` | Setelah menerima paket, dibatasi tiap 200 ms |

`maybeSendOn()` memeriksa apakah sudah lewat `ON_INTERVAL_MS` sejak kiriman terakhir; kalau ya, kirim lagi.

> **Kenapa `ON` pertama dikirim seketika?** Pengendali Utama hanya menunggu **1 detik** sebelum menganggap perintah gagal dan mengirimnya ulang. Kalau robot menunggu satu siklus penuh dulu, hampir setiap perintah akan terkirim ganda.

---

## 7. Failsafe & Pelayanan Radio — `serviceRadio()`

Dipanggil terus-menerus **di dalam** loop gerakan. Tiga tugasnya:

1. **Konsumsi semua paket masuk** dan segarkan `lastSignalMs`.
2. **Layani `STOP`** kapan pun, termasuk di tengah gerakan.
3. **Kirim `ON` berkala** lewat `maybeSendOn()`.

```
bool serviceRadio()
{
  while (radio.available())
  {
    radio.read(buf, sizeof(buf));
    lastSignalMs = millis();
    if (strncmp(buf, "STOP", 4) == 0) { stopRequested = true; continue; }
    maybeSendTelemetry();      // giliran robot bicara
  }
  maybeSendOn();
  return (millis() - lastSignalMs) < SIGNAL_TIMEOUT_MS;
}
```

Perintah gerak lain yang masuk saat robot sibuk **sengaja diabaikan** — itu adalah paket kiriman ulang dari Pengendali Utama yang belum sempat menerima `ON`. Kalau diproses, satu perintah bisa jadi beberapa gerakan.

Telemetri MPU sengaja diselipkan **hanya setelah ada paket masuk**, bukan tiap iterasi loop, supaya tidak bertabrakan dengan paket perintah yang sedang dikirim Pengendali Utama.

`checkAbort()` membungkusnya menjadi pemeriksaan tunggal yang mengembalikan `MOVE_LOST_SIGNAL`, `MOVE_STOPPED`, atau `MOVE_DONE`.

---

## 8. Perintah `FW` — `executeForward(distCm)`

Maju lurus sejauh `distCm` sentimeter. Durasi diturunkan dari jarak dan kecepatan jelajah:

```
durationMs = (distCm / 100.0) / ROBOT_SPEED_MPS * 1000
```

Arah hadap saat perintah diterima **dikunci** sebagai `targetYaw`, lalu dipertahankan dengan kendali proporsional:

```
err = targetYaw - yaw            // dinormalisasi ke -180..180
if (|err| > HEADING_DEADBAND)
    correction = clamp(KP_HEADING * err, ±MAX_CORRECTION)

escKiri  = constrain(CRUISE_PWM + correction, 1000, 2000)
escKanan = constrain(CRUISE_PWM - correction, 1000, 2000)
```

Semakin besar simpangan arah, semakin kuat koreksinya — jauh lebih halus daripada koreksi tetap. *Deadband* 2° mencegah motor terus-menerus dikoreksi karena derau sensor.

Karena tiap perintah `FW` mengunci ulang `targetYaw` dari pembacaan terbaru, akumulasi *drift* giroskop tidak menumpuk lintas perintah.

---

## 9. Perintah `CW` / `CCW` — `executeTurn(deg, clockwise)`

Berputar sejauh `deg` derajat. Berbeda dengan versi lama yang memakai durasi tetap, putaran kini **ditutup dengan umpan balik sensor**:

```
startYaw = yaw saat perintah diterima
loop:
    delta  = yaw - startYaw            // dinormalisasi ke -180..180
    turned = (clockwise ? -delta : delta) * YAW_SIGN
    if (turned >= deg - TURN_TOLERANCE) selesai
```

`turned` selalu dihitung **positif ke arah yang diperintahkan**, sehingga satu rumus melayani kedua arah.

Batas waktu `deg / TURN_RATE_DPS * 3000 + 3000` ms dipasang sebagai pengaman bila MPU tidak merespons atau robot tertahan sesuatu — bukan sebagai penentu sudut.

> **Kalau `CW` malah berbelok ke kiri**, tanda sumbu Z MPU terbalik terhadap pemasangan. Ubah `YAW_SIGN` menjadi `-1`; tidak perlu mengubah logika lain.

---

## 10. Menjalankan Satu Perintah — `runMove()`

Merangkai seluruh siklus untuk satu perintah:

```
void runMove(const char *move, int dist)
{
  currentMove = move;  moveInProgress = true;  stopRequested = false;

  sendOn(currentMove);                       // "ON" pertama SEGERA

  result = (move == "FW") ? executeForward(dist)
                          : executeTurn(dist, move == "CW");

  stopBoat();  moveInProgress = false;

  if (result == MOVE_DONE) sendFin(move, dist);
  else                     /* tidak kirim FIN */ ;
}
```

**Gerakan yang tidak tuntas sengaja tidak dilaporkan.** Dengan begitu Pengendali Utama tahu perintah gagal dan **tidak melanjutkan** ke perintah berikutnya — sisa antrean otomatis batal.

---

## 11. Parsing Paket — `parseCommand()`

Memecah `[Moves]:[Dist]` pada karakter `:`, membersihkan spasi, menaikkan huruf, lalu memvalidasi rentang:

| Perintah | Rentang sah | Bila di luar |
|---|---|---|
| `FW` | 10–200 cm | Ditolak, dicetak ke Serial, paket diabaikan |
| `CW` / `CCW` | 1–180 derajat | Ditolak, dicetak ke Serial, paket diabaikan |

Toleran terhadap spasi, jadi `FW : 100` maupun `FW:100` sama-sama diterima. Perintah tak dikenal langsung ditolak dengan petunjuk format.

Validasi ini adalah **lapisan kedua** — aplikasi sudah menolak nilai di luar rentang sebelum mengirim. Firmware tetap memeriksanya sendiri agar aman terhadap paket rusak atau pengirim lain.

---

## 12. Inisialisasi — `setup()`

Urutan inisialisasi **penting dan disengaja**:

1. **NRF24 lebih dulu** — `begin()`, PA_LOW, 250 KBPS, channel `0x76`, reading pipe 1, `enableDynamicAck()`, `startListening()`.
2. **MPU6050** — `Wire.begin(21, 22)`, `calcGyroOffsets(true)`.
3. **ESC** — alokasi 4 timer PWM, `setPeriodHertz(50)`, `attach(pin, 1000, 2000)`, lalu `armESC()`.

> **Kenapa NRF paling awal?** `calcGyroOffsets` bisa menggantung selamanya bila I2C bermasalah, dan `armESC()` menahan 5 detik. Kalau radio diinisialisasi belakangan, `startListening()` baru aktif ~8 detik setelah boot — Pengendali Utama tidak ter-ACK dan melaporkan gagal.

> `ESP32PWM::allocateTimer()` **wajib** dipanggil sebelum `attach()`. Tanpa itu PWM ke ESC bisa gagal diam-diam dan baling-baling tidak bergerak sama sekali.

Bila `radio.begin()` gagal, firmware masuk perulangan tak berujung sambil mencetak petunjuk wiring — lebih baik berhenti terang-terangan daripada berjalan tanpa kendali.

---

## 13. Loop Utama — `loop()`

Jauh lebih ringkas dari versi sebelumnya karena tidak ada lagi algoritma misi:

```
void loop()
{
  mpu.update();

  if (radio.available())
  {
    radio.read(text, sizeof(text));
    lastSignalMs = millis();          // paket APAPUN = koneksi hidup

    if (data.startsWith("PING")) { maybeSendTelemetry(); return; }

    if (data.startsWith("STOP"))
    {
      stopBoat();  stopRequested = false;
      sendFin("STOP", 0);
      return;
    }

    if (parseCommand(data, move, &dist)) runMove(move, dist);
    else  Serial.println("Format: FW:100 | CW:90 | CCW:90 | STOP:0");
  }
}
```

Tiga jenis paket dilayani berurutan menurut prioritas: **PING** (heartbeat murni), **STOP** (berhenti darurat, dilayani lebih dulu dari apa pun), lalu **perintah gerak**.

Perhatikan `runMove()` bersifat **blocking** — selama gerakan berlangsung `loop()` tidak kembali. Pelayanan radio tetap berjalan karena `serviceRadio()` dipanggil dari dalam loop gerakan.

---

## 14. Protokol Paket

**Pi → Robot** (alamat `00001`, channel `0x76`, 250 KBPS, PA_LOW):

| Paket | Makna |
|---|---|
| `FW:<10-200>` | Maju lurus sekian sentimeter |
| `CW:<1-180>` | Putar searah jarum jam (ke kanan) sekian derajat |
| `CCW:<1-180>` | Putar berlawanan jarum jam (ke kiri) sekian derajat |
| `STOP:0` | Hentikan motor — berhenti darurat |
| `PING` | Heartbeat tiap 0,5 detik (menjaga failsafe + memicu giliran bicara robot) |

**Robot → Pi** (alamat `00002`, NOACK):

| Paket | Makna |
|---|---|
| `ON <Moves>` | Perintah sedang dijalankan — dikirim tiap 1 detik selama bergerak |
| `FIN <Moves>:<Dist>` | Perintah selesai dieksekusi dengan baik |
| `R=<roll>;P=<pitch>;Y=<yaw>` | Telemetri sudut MPU (tambahan, di luar spesifikasi wajib) |

**Siklus lengkap satu perintah:**

```
Pi  ->  FW:200
Pi  <-  ON FW              (< 1 detik, kalau tidak -> Pi kirim ulang)
Pi  <-  ON FW              (berulang tiap 1 detik selama bergerak)
Pi  <-  FIN FW:200         (selesai -> Pi lanjut ke perintah berikutnya)
```

Parameter radio (**alamat, channel `0x76`, 250 KBPS, PA_LOW**) **harus identik** dengan sisi Pengendali Utama; kalau berbeda, kedua modul tidak akan terhubung.

---

## 15. Panduan Kalibrasi (Ringkas)

| Yang dikalibrasi | Cara | Gejala bila salah |
|---|---|---|
| `ROBOT_SPEED_MPS` | Perintahkan `FW:200` di air, ukur jarak tempuh nyata, sesuaikan nilainya | Jarak tempuh meleset konsisten (selalu kurang / selalu lebih) |
| `YAW_SIGN` | Perintahkan `CW:90`, amati arah putaran | Robot berputar ke arah **berlawanan** dari perintah |
| `KP_HEADING` | Amati kelurusan saat `FW` panjang | Terlalu kecil: melenceng. Terlalu besar: bergoyang kiri-kanan |
| `CRUISE_PWM` | Sesuaikan dengan daya motor & beban | Robot terlalu lambat / terlalu kencang untuk dikendalikan |
| `TURN_RATE_DPS` | Ukur berapa lama putaran 90° | Hanya memengaruhi batas waktu pengaman, bukan ketepatan sudut |

> Kalibrasi `ROBOT_SPEED_MPS` **wajib dilakukan di air**, bukan di darat — hambatan air sangat berbeda. Nilai ini juga dipakai aplikasi untuk menghitung perkiraan waktu misi.

---

## 16. Keterbatasan & Iterasi Berikutnya

**Sudah teratasi pada iterasi ini:**

- Belok berbasis durasi → sekarang **closed-loop yaw MPU**, `TURN_90_MS` tidak diperlukan lagi.
- Pola jalur tertanam di firmware → sekarang **dikemudikan aplikasi**, bisa diubah tanpa flash ulang.
- Tidak ada konfirmasi eksekusi → sekarang ada **`ON` / `FIN`** dengan pengiriman ulang otomatis.

**Masih terbuka:**

- **Jarak masih open-loop.** `FW` diturunkan dari waktu tempuh, jadi rentan terhadap arus air dan perubahan beban. Perlu **odometri** atau GPS.
- **Tidak ada sensor RPM/encoder**, sehingga gauge kecepatan di aplikasi tetap berupa estimasi.
- **Putaran menggeser posisi** karena ESC unidirectional. Solusi sebenarnya adalah ESC bidirectional agar bisa berputar di tempat.
- **Belum ada perintah kontrol komponen individual** (mematikan satu motor, mengatur ulang MPU) pada tabel protokol.
- **Isi sinyal balik masih terbatas** — bisa diperluas dengan tegangan baterai, throttle nyata, dan status komponen.

---

## 17. Ringkasan

Firmware berperan sebagai **eksekutor perintah yang jujur**: menjalankan satu gerakan, melapor bahwa ia sedang berjalan, dan melapor lagi saat selesai — atau diam saja bila gagal, sehingga Pengendali Utama tahu harus berhenti. Pemisahan tanggung jawab ini membuat pola jalur bisa dikembangkan sepenuhnya di sisi aplikasi, sementara firmware tetap kecil, mudah diuji, dan mudah dikalibrasi.
