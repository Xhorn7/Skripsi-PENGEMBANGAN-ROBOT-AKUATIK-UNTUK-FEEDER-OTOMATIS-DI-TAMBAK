# Flowchart — Robot Akuatik Feeder Otomatis

> Render di VS Code: install extension **"Markdown Preview Mermaid Support"**, lalu Ctrl+Shift+V
>
> Versi PNG dari tiap diagram ada di folder **Flowchart Images/** (regenerate dengan `python render_flowcharts.py`).
>
> Protokol mengikuti **Dokumen Spesifikasi Teknis — Robot Akuatik untuk Tambak Ikan**, bab Skema Komunikasi.

---

## 1. Gambaran Sistem

```mermaid
flowchart TB
    subgraph RPi["🖥️ Raspberry Pi — Pengendali Utama"]
        direction LR
        A["Input Ukuran Tambak<br/>+ Titik Awal + Kecepatan"] --> P["Rencanakan Jalur<br/>maju / belok + preview"]
        P --> Q["Susun Antrean Perintah<br/>FW / CW / CCW"]
        Q --> R["CommandRunner<br/>kirim 1 perintah,<br/>tunggu balasan"]
        M["Input Manual<br/>Maju (meter) / CW / CCW / STOP"] --> R
        T["Tampil Status + Heading<br/>dari sinyal balik"]
        T --> L["Log aktivitas + sudut MPU<br/>auto-simpan TXT"]
    end

    subgraph ESP32["⚙️ ESP32 — Body Robot"]
        direction LR
        C["Terima & Validasi<br/>[Moves]:[Dist]"] --> D["Jalankan SATU Gerakan"]
        D --> E["MPU6050<br/>Heading-Hold + Sudut Putar"]
        D --> F["2x ESC Brushless 30A<br/>Kiri & Kanan - Differential"]
    end

    R == "perintah — addr 00001<br/>FW:200 · CW:90 · CCW:90 · STOP:0" ==> C
    D -. "sinyal balik — addr 00002<br/>ON [Moves] · FIN [Moves]:[Dist] · R=;P=;Y=" .-> T
```

> **Perubahan peran robot.** Pola zigzag kini disusun & dikemudikan Pengendali Utama; robot hanya eksekutor satu perintah. Mengubah pola jalur cukup di aplikasi, tanpa flash ulang ESP32.

---

## 2. Flowchart Pengendali Utama (Transmitter)

Alur aplikasi GUI. Operasi penuh lewat **layar sentuh** (papan angka di layar), tanpa keyboard fisik.

```mermaid
flowchart TD
    START([▶ START GUI]) --> SCR["Ambil ukuran layar perangkat<br/>skala = min(W/800, H/480)"]
    SCR --> SIM["Mode awal SIMULASI<br/>MockRadio (robot virtual)"]
    SIM --> HOME[Halaman BERANDA]

    HOME --> PICK{Operator<br/>pilih apa?}

    PICK -- "Sentuh chip MODE" --> MODE{Minta mode<br/>REAL?}
    MODE -- Ya --> TRY["set_mode: init RF24<br/>CE=24, CSN=0<br/>Ch=0x76, 250KBPS"]
    TRY --> OK{NRF24<br/>terdeteksi?}
    OK -- Ya --> REAL[Mode REAL<br/>perintah ke robot nyata]
    OK -- Tidak --> BACK["Kembali ke SIMULASI<br/>+ tampilkan sebabnya"]
    MODE -- Tidak --> SIM
    REAL --> HOME
    BACK --> HOME

    PICK -- MISI --> INPUT[/"Input via papan angka:<br/>Panjang, Lebar,<br/>Lebar lintasan, Kecepatan,<br/>Titik awal"/]
    INPUT --> PLAN["plan_coverage:<br/>hitung jalur zigzag<br/>+ daftar maju/belok"]
    PLAN --> QUEUE["plan_command_queue:<br/>pecah jadi FW/CW/CCW<br/>(FW dibatasi 10-200 cm)"]
    QUEUE --> PREVIEW[Preview kanvas<br/>+ daftar antrean perintah]
    PREVIEW --> SENDBTN{Tekan<br/>KIRIM MISI?}
    SENDBTN -- Belum --> INPUT
    SENDBTN -- Ya --> RUN

    PICK -- MANUAL --> MAN[/"Maju (meter) atau<br/>CW / CCW (derajat)<br/>+ isi nilai"/]
    MAN --> VAL{Nilai dalam<br/>rentang sah?}
    VAL -- Tidak --> REJECT[Tolak + tampilkan<br/>rentang yang benar]
    REJECT --> MAN
    VAL -- "Ya, maju" --> SPLITM["split_forward:<br/>meter → paket FW 10-200 cm"]
    SPLITM --> RUN
    VAL -- "Ya, putar" --> RUN

    RUN["CommandRunner.run(antrean)"] --> CYCLE[Siklus Request-Response<br/>per perintah - lihat diagram 4]
    CYCLE --> NEXT{Masih ada<br/>perintah?}
    NEXT -- Ya --> CYCLE
    NEXT -- Tidak --> DONE([✅ SELESAI])
    DONE --> HOME

    PICK -- STOP --> SSTOP["Kirim STOP:0 berulang<br/>batalkan sisa antrean"]
    SSTOP --> HOME

    PICK -- "SENSOR / LOG" --> TOG["Saklar Log MPU<br/>& Auto-simpan TXT"]
    TOG --> HOME
```

> Tombol **STOP** ada di bilah atas sehingga dapat ditekan dari halaman mana pun, termasuk saat antrean sedang berjalan.
>
> **Mode awal selalu SIMULASI**; perpindahan ke REAL adalah keputusan sadar operator lewat chip **MODE** (atau flag `--real`), dan ditolak selagi ada perintah berjalan. Sementara itu sudut MPU mengalir sendiri dari telemetri NRF di latar belakang — **tanpa port serial** — dan saklar **Log MPU** / **Auto-simpan TXT** menentukan apakah ikut dicatat ke berkas.

---

## 3. Flowchart Body Robot (Receiver)

```mermaid
flowchart TD
    START([▶ START]) --> INITRF["Init RF24 DULU<br/>CE=4, CSN=5<br/>Ch=0x76, Pipe 1, Listen"]
    INITRF --> CHECK{NRF24<br/>OK?}
    CHECK -- Tidak --> HALT([❌ Halt - cek wiring])
    CHECK -- Ya --> INITMPU["Init MPU6050<br/>SDA=21, SCL=22<br/>Calc Gyro Offsets"]
    INITMPU --> INITESC["Attach ESC<br/>Kiri=25, Kanan=26<br/>Arm PWM=1000 selama 5 detik"]
    INITESC --> LISTEN[Tunggu Sinyal RF24]

    LISTEN --> RF24{Data<br/>Masuk?}
    RF24 -- Tidak --> UPDATEMPU[Update MPU6050]
    UPDATEMPU --> LISTEN

    RF24 -- Ya --> PKT{Jenis<br/>paket?}
    PKT -- PING --> HBEAT["Segarkan heartbeat<br/>+ balas telemetri MPU"]
    HBEAT --> LISTEN
    PKT -- "STOP:0" --> STOPM["stopBoat - matikan motor<br/>+ kirim FIN STOP:0"]
    STOPM --> LISTEN

    PKT -- "[Moves]:[Dist]" --> PARSE["parseCommand:<br/>pecah di ':' , rapikan spasi"]
    PARSE --> VALID{"Perintah dikenal &<br/>[Dist] dalam rentang?"}
    VALID -- Tidak --> ERRMSG["Serial: Format Error<br/>paket diabaikan"]
    ERRMSG --> LISTEN

    VALID -- Ya --> BUSY{Sedang ada<br/>gerakan berjalan?}
    BUSY -- Ya --> IGNORE["Abaikan - ini paket<br/>kiriman ulang dari Pi"]
    IGNORE --> LISTEN

    BUSY -- Tidak --> RUNMOVE["runMove:<br/>kirim ON SEGERA,<br/>lalu eksekusi gerakan"]
    RUNMOVE --> RESULT{Hasil<br/>gerakan?}
    RESULT -- Tuntas --> FIN(["✅ Kirim FIN [Moves]:[Dist]"])
    RESULT -- "STOP / sinyal hilang" --> NOFIN(["🛑 stopBoat<br/>TIDAK kirim FIN"])
    FIN --> LISTEN
    NOFIN --> LISTEN
```

> **NRF di-init paling awal** (sebelum MPU & ESC). `calcGyroOffsets` dan `armESC` menahan beberapa detik; bila NRF telat listening, Pengendali Utama tak ter-ACK dan melaporkan gagal.
>
> **Gerakan gagal sengaja tidak dilaporkan.** Tanpa `FIN`, Pengendali Utama tahu perintah tidak tuntas dan tidak melanjutkan ke perintah berikutnya.

---

## 4. Siklus Request-Response (Satu Perintah)

Inti protokol Sinyal Kendali. Setiap perintah dihitung sebagai satu paket komunikasi.

```mermaid
sequenceDiagram
    participant Pi as Pengendali Utama
    participant Robot as Body Robot
    Note over Pi,Robot: Sinyal Kendali selalu diinisiasi Pengendali Utama

    Pi->>Robot: FW:200
    Robot-->>Pi: auto-ACK hardware
    Note over Robot: validasi rentang, mulai gerakan
    Robot->>Pi: ON FW (SEGERA)
    Note over Pi: ON diterima < 1 detik → lanjut menunggu FIN

    loop tiap 1 detik selama bergerak
        Robot->>Pi: ON FW
        Pi->>Robot: PING (jaga failsafe)
    end

    Robot->>Pi: FIN FW:200
    Note over Pi: perintah tuntas → kirim perintah berikutnya
```

**Bila `ON` tidak datang dalam 1 detik:**

```mermaid
flowchart TD
    SEND["Kirim [Moves]:[Dist]"] --> WAIT{"ON [Moves] diterima<br/>dalam 1 detik?"}
    WAIT -- Ya --> WFIN{"FIN [Moves]:[Dist]<br/>diterima?"}
    WAIT -- Tidak --> RETRY{Percobaan<br/>< 5 kali?}
    RETRY -- Ya --> SEND
    RETRY -- Tidak --> FAIL(["❌ GAGAL<br/>kirim STOP:0, batalkan antrean"])
    WFIN -- Ya --> OK([✅ Lanjut perintah berikutnya])
    WFIN -- "Tidak (habis waktu)" --> FAIL
```

> Karena Pengendali Utama mengirim ulang saat `ON` telat, robot **mengabaikan perintah gerak baru selama masih sibuk** — kecuali `STOP`, yang selalu dilayani seketika. Tanpa aturan ini satu perintah bisa jadi beberapa gerakan.

---

## 5. Perintah FW — Heading-Hold Proporsional (`executeForward`)

```mermaid
flowchart TD
    ENTRY(["Mulai executeForward(distCm)"]) --> CALC["targetYaw = yaw saat ini<br/>durationMs = (distCm/100) / speed × 1000"]
    CALC --> TIMECHECK{Waktu<br/>habis?}
    TIMECHECK -- Ya --> STOPFN([Stop Boat → MOVE_DONE])
    TIMECHECK -- Tidak --> UPD[mpu.update]
    UPD --> SIG{"serviceRadio:<br/>sinyal masih hidup?"}
    SIG -- Tidak --> FAIL([🛑 Stop Boat → MOVE_LOST_SIGNAL])
    SIG -- Ya --> STOPQ{STOP<br/>diterima?}
    STOPQ -- Ya --> ABORT([🛑 Stop Boat → MOVE_STOPPED])
    STOPQ -- Tidak --> ERR["error = targetYaw - yaw<br/>normalisasi ke -180..180"]
    ERR --> DEAD{"|error| > 2°?"}
    DEAD -- Tidak --> STRAIGHT["correction = 0<br/>(lurus)"]
    DEAD -- Ya --> PROP["correction = Kp × error<br/>clamp ±MAX_CORRECTION"]
    PROP --> WRITE
    STRAIGHT --> WRITE["Kiri = 1300 + correction<br/>Kanan = 1300 - correction<br/>(constrain 1000..2000)"]
    WRITE --> ESC[writeMicroseconds ke 2 ESC]
    ESC --> DELAY[delay 20ms]
    DELAY --> TIMECHECK
```

> Koreksi **proporsional** (`Kp × error`): makin besar simpangan, makin kuat koreksi — gerak lurus lebih halus. *Deadband* 2° mencegah motor terus dikoreksi karena derau sensor.
>
> Tiap perintah `FW` **mengunci ulang** `targetYaw` dari pembacaan terbaru, sehingga *drift* giroskop tidak menumpuk lintas perintah.

---

## 6. Perintah CW / CCW — Putaran Closed-Loop Yaw (`executeTurn`)

```mermaid
flowchart TD
    ENTRY(["Mulai executeTurn(deg, clockwise)"]) --> INIT["startYaw = yaw saat ini<br/>limitMs = deg/TURN_RATE × 3000 + 3000"]
    INIT --> SPIN{clockwise?}
    SPIN -- Ya --> CW["spinCW<br/>Kiri = 1300, Kanan = diam"]
    SPIN -- Tidak --> CCW["spinCCW<br/>Kiri = diam, Kanan = 1300"]
    CW --> LOOP
    CCW --> LOOP{Batas waktu<br/>terlampaui?}
    LOOP -- Ya --> TIMEOUT([Stop Boat → MOVE_DONE<br/>batas waktu pengaman])
    LOOP -- Tidak --> UPD[mpu.update]
    UPD --> SIG{"serviceRadio +<br/>cek STOP"}
    SIG -- "Gagal" --> ABORT([🛑 Stop Boat<br/>MOVE_STOPPED / LOST_SIGNAL])
    SIG -- OK --> DELTA["delta = yaw - startYaw<br/>normalisasi ke -180..180"]
    DELTA --> TURNED["turned = (clockwise ? -delta : delta) × YAW_SIGN"]
    TURNED --> REACH{"turned ≥ deg - 3°?"}
    REACH -- Ya --> DONE([✅ Stop Boat → MOVE_DONE])
    REACH -- Tidak --> DELAY[delay 20ms]
    DELAY --> LOOP
```

> **Sudut ditutup oleh sensor, bukan oleh waktu.** Konstanta `TURN_90_MS` yang dulu rawan sudah dihapus; `TURN_RATE_DPS` kini hanya dipakai untuk menghitung batas waktu pengaman.
>
> ESC **unidirectional** → putaran memakai *differential thrust*, jadi robot berputar melingkar lebar (posisi ikut bergeser), bukan berputar di tempat. Sudut akhirnya tetap akurat.
>
> Kalau `CW` malah berputar ke kiri, tanda sumbu Z MPU terbalik → ubah `YAW_SIGN` menjadi `-1`.

---

## 7. Perencanaan Jalur → Antrean Perintah

Terjemahan tambak persegi menjadi daftar paket Sinyal Kendali, seluruhnya di sisi aplikasi.

```mermaid
flowchart TD
    IN[/"Panjang, Lebar,<br/>Lebar lintasan, Kecepatan,<br/>Titik awal (sudut tambak)"/] --> N["nLanes = ⌈lebar / lebar lintasan⌉"]
    N --> WP["Bangun waypoint zigzag<br/>x menyusuri lebar,<br/>y menyusuri panjang"]
    WP --> SEG["Turunkan segmen:<br/>Maju x m / Belok kanan-kiri y°"]
    SEG --> DIR["Arah belok berselang-seling<br/>(R,R lalu L,L, dst)"]
    DIR --> SPLIT["split_forward:<br/>pecah RATA jadi FW 10-200 cm<br/>10 m → 5 × FW:200"]
    DIR --> TURN["turn_command:<br/>kanan → CW, kiri → CCW"]
    SPLIT --> OUT2
    TURN --> OUT2["Antrean perintah<br/>FW:200 FW:200 ... CW:90 FW:100 CW:90 ..."]
    DIR --> OUT1[Preview kanvas<br/>+ daftar perintah]
    OUT2 --> RUNNER[CommandRunner<br/>kirim satu per satu]
```

> **Pemecahan dibuat RATA** agar tidak menyisakan potongan di bawah batas minimum. Contoh: 10,05 m menjadi 6 × 167 cm, bukan 5 × 200 cm + sisa 5 cm yang tak bisa diperintahkan.
>
> **Arah U-turn berselang-seling** (kanan-kanan lalu kiri-kiri, dst) sehingga geseran selalu ke sisi yang sama — sapuan menutupi seluruh lebar tambak (*boustrophedon*). Selalu belok kanan hanya menghasilkan bolak-balik di dua kolom.

---

## 8. Sinyal Balik & Telemetri (Half-Duplex "Gantian")

Komunikasi 2 arah di atas modul NRF24 yang **sama** — bergantian bicara seperti radio HT.

```mermaid
sequenceDiagram
    participant Pi as Pengendali Utama
    participant Robot as Body Robot
    Note over Pi,Robot: Half-duplex, gantian bicara (seperti radio HT)

    Pi->>Robot: perintah / PING (Pi mode TX)
    Robot-->>Pi: auto-ACK hardware = robot terjangkau
    Note over Pi: pump() - pindah ke RX sebentar
    Note over Robot: giliran kirim, stopListening

    alt sedang menjalankan gerakan
        Robot->>Pi: ON [Moves]  atau  FIN [Moves]:[Dist]
    else menganggur
        Robot->>Pi: R=.. P=.. Y=.. (telemetri MPU, NOACK)
    end

    Note over Robot: startListening lagi
    Note over Pi: rutekan paket menurut awalannya,<br/>perbarui status & heading
```

Semua paket balik memakai alamat `00002`, terpisah dari alamat perintah `00001`. `RadioLink._route_packet()` mengenalinya dari awalan:

| Awalan | Ditafsirkan sebagai |
|---|---|
| `FIN ` | Perintah selesai — izin lanjut ke perintah berikutnya |
| `ON ` | Perintah sedang dijalankan |
| `R=` | Telemetri sudut MPU |

> Telemetri MPU dikirim robot **hanya setelah ada paket masuk**, bukan tiap iterasi loop, supaya tidak bertabrakan dengan perintah yang sedang dikirim Pengendali Utama. Semuanya **NOACK** (*fire-and-forget*) agar robot tak nge-*block*.

---

## Pola Fisik Zigzag di Tambak

```
START
 │
 ▼
┌─────────────────────────────┐
│ →→→→→→→→→→→→ Lane 1         │
│                          ↓  │  U-turn (CW:90 ×2)
│ ←←←←←←←←←←←← Lane 2        │
│ ↓  U-turn (CCW:90 ×2)       │
│ →→→→→→→→→→→→ Lane 3         │
│                          ↓  │  U-turn (CW:90 ×2)
│ ←←←←←←←←←←←← Lane 4   STOP│
└─────────────────────────────┘
     TAMBAK (panjang × lebar)
```

Contoh nyata — tambak **10 × 4 m**, lebar lintasan 1 m, mulai Kiri-Bawah → 4 lintasan, **29 perintah**:

```
FW:200  FW:200  FW:200  FW:200  FW:200      Lane 1 (10 m dipecah 5x)
CW:90   FW:100  CW:90                        U-turn kanan + geser 1 m
FW:200  FW:200  FW:200  FW:200  FW:200      Lane 2
CCW:90  FW:100  CCW:90                       U-turn kiri + geser 1 m
...                                          dst hingga Lane 4
```

> Arah U-turn berganti tiap lane agar geseran konsisten ke satu sisi dan menutupi seluruh lebar tambak.
