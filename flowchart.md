# Flowchart — Robot Akuatik Feeder Otomatis

> Render di VS Code: install extension **"Markdown Preview Mermaid Support"**, lalu Ctrl+Shift+V
>
> Versi PNG dari tiap diagram ada di folder **Flowchart Images/**.

---

## 1. Gambaran Sistem

```mermaid
flowchart LR
    subgraph RPi["🖥️ Raspberry Pi 4 (Transmitter)"]
        A["Input Ukuran Tambak<br/>+ Titik Awal + Kecepatan"] --> P["Rencanakan Jalur<br/>(maju/belok + preview)"]
        P --> B[Format Paket RF24]
    end

    subgraph Radio["📡 RF24 NRF24L01+<br/>250 KBPS / Ch 0x76"]
        B -- "P=10;L=4;MODE=AUTO;<br/>SPD=0.5;LW=1;DIR=R" --> C
    end

    subgraph ESP32["⚙️ ESP32 (Receiver)"]
        C[Terima & Parse] --> D[Jalankan Misi]
        D --> E["MPU6050<br/>Heading-Hold Proporsional"]
        D --> F["2x ESC Brushless 30A<br/>Kiri & Kanan - Differential"]
        D --> G["Pola Zigzag<br/>Belok Berselang-seling"]
    end
```

---

## 2. Flowchart Raspberry Pi (Transmitter)

Alur aplikasi GUI (panel kontrol). Operasi penuh lewat **layar sentuh + keypad**, tanpa keyboard fisik.

```mermaid
flowchart TD
    START([▶ START GUI]) --> INIT["Init RF24<br/>CE=24, CSN=0<br/>Ch=0x76, 250KBPS"]
    INIT --> DET{NRF24<br/>Terdeteksi?}
    DET -- Tidak --> SIM[Mode SIMULASI<br/>MockRadio]
    DET -- Ya --> REAL[Mode REAL]
    SIM --> INPUT
    REAL --> INPUT[/"Input via keypad:<br/>Panjang, Lebar,<br/>Lebar lintasan, Kecepatan,<br/>Titik awal"/]
    INPUT --> PLAN["plan_coverage:<br/>hitung jalur zigzag<br/>+ daftar maju/belok"]
    PLAN --> PREVIEW[Preview kanvas<br/>+ daftar segmen]
    PREVIEW --> SENDBTN{Klik<br/>KIRIM MISI?}
    SENDBTN -- Belum --> INPUT
    SENDBTN -- Ya --> ENCODE["Encode paket:<br/>P=..;L=..;MODE=AUTO;<br/>SPD=..;LW=..;DIR=.."]
    ENCODE --> SEND[Kirim via RF24<br/>retry 5x]
    SEND --> HB["Heartbeat PING tiap 0.5s<br/>selama misi berjalan"]
    HB --> STOPCHK{Klik STOP?}
    STOPCHK -- Tidak --> HB
    STOPCHK -- Ya --> SENDSTOP[Kirim STOP<br/>hentikan heartbeat]
    SENDSTOP --> INPUT
```

---

## 3. Flowchart ESP32 (Receiver)

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
    PKT -- PING --> HBEAT[Segarkan heartbeat<br/>lalu abaikan]
    HBEAT --> LISTEN
    PKT -- STOP --> STOPM[stopBoat<br/>matikan motor]
    STOPM --> LISTEN

    PKT -- "MISI (P/L/MODE)" --> PARSE["Parse P= / L= / MODE=<br/>+ SPD / LW / DIR (opsional)"]
    PARSE --> VALID{Format<br/>Valid?}
    VALID -- Tidak --> ERRMSG[Serial: Format Error]
    ERRMSG --> LISTEN

    VALID -- Ya --> STORE["Simpan dimensi, speed,<br/>lebar lintasan,<br/>arah belok pertama"]
    STORE --> MODECHECK{MODE<br/>== AUTO?}
    MODECHECK -- Tidak --> LISTEN
    MODECHECK -- Ya --> MISI[Jalankan Misi Zigzag]
    MISI --> DONE([✅ MISI SELESAI<br/>stopBoat])
    DONE --> LISTEN
```

> Catatan: NRF di-init **paling awal** (sebelum MPU & ESC). MPU `calcGyroOffsets` dan `armESC` menahan beberapa detik; bila NRF telat listening, transmitter tak ter-ACK dan melaporkan gagal.

---

## 4. Flowchart Misi Zigzag (AUTO MODE)

```mermaid
flowchart TD
    ENTRY([Masuk AUTO MODE]) --> VALID{"panjang & lebar<br/>> 0?"}
    VALID -- Tidak --> CANCEL([❌ Misi dibatalkan])
    VALID -- Ya --> CALC["Hitung:<br/>nLanes = ⌈lebar / laneWidthM⌉<br/>laneDuration = panjang / speed × 1000 ms<br/>shiftDuration = laneWidthM / speed × 1000 ms"]
    CALC --> HB["Reset heartbeat<br/>turnToRight = firstTurnRight (dari DIR)"]
    HB --> LOOP{"lane < nLanes<br/>& tidak abort?"}

    LOOP -- Tidak --> STOP([✅ Stop Boat])

    LOOP -- Ya --> REZERO["RE-ZERO: targetYaw = yaw saat ini<br/>(kunci heading baru tiap lane,<br/>lawan gyro drift)"]
    REZERO --> DRIVE["driveHeadingMS lurus<br/>(heading-hold proporsional + failsafe)"]
    DRIVE --> ABORT1{Sinyal hilang<br/>atau STOP?}
    ABORT1 -- Ya --> ABORTED([🛑 MISI DIBATALKAN])
    ABORT1 -- Tidak --> PAUSE1[Stop + delay 500ms]

    PAUSE1 --> LASTLANE{Lane<br/>Terakhir?}
    LASTLANE -- Ya --> STOP

    LASTLANE -- Tidak --> T1["Belok 90° #1<br/>(arah = turnToRight)"]
    T1 --> SHIFT["Geser 1 lintasan<br/>(shiftDuration ms, kunci heading baru)"]
    SHIFT --> T2["Belok 90° #2 arah SAMA<br/>→ total 180°, hadap balik"]
    T2 --> FLIP["turnToRight = NOT turnToRight<br/>lane++"]
    FLIP --> LOOP
```

> Catatan: arah U-turn **berselang-seling** (kanan-kanan, lalu kiri-kiri, dst) sehingga geseran selalu ke sisi yang sama — sapuan menutupi **seluruh** lebar tambak (boustrophedon). Versi sebelumnya selalu belok kanan sehingga hanya bolak-balik di dua kolom.

---

## 5. Logika Heading-Hold Proporsional (driveHeadingMS)

```mermaid
flowchart TD
    ENTRY([Mulai driveHeadingMS]) --> TIMER[Set timer]
    TIMER --> TIMECHECK{Waktu<br/>habis?}
    TIMECHECK -- Ya --> STOPFN([Stop Boat → return true])
    TIMECHECK -- Tidak --> UPD[mpu.update]
    UPD --> SIG{"signalAlive?<br/>(< 3 detik sejak sinyal terakhir)"}
    SIG -- Tidak --> FAIL([🛑 Stop Boat → return false])
    SIG -- Ya --> ERR["error = targetYaw - currentYaw<br/>normalisasi ke -180..180"]
    ERR --> DEAD{"|error| > 2°?"}
    DEAD -- Tidak --> STRAIGHT["correction = 0<br/>(lurus)"]
    DEAD -- Ya --> PROP["correction = Kp × error<br/>clamp ±MAX_CORRECTION"]
    PROP --> WRITE
    STRAIGHT --> WRITE["Kiri = 1300 + correction<br/>Kanan = 1300 - correction<br/>(constrain 1000..2000)"]
    WRITE --> ESC[writeMicroseconds ke 2 ESC]
    ESC --> DELAY[delay 50ms]
    DELAY --> TIMECHECK
```

> Koreksi **proporsional** (`Kp × error`) menggantikan koreksi tetap ±20 — makin besar simpangan, makin kuat koreksi, sehingga gerak lurus lebih halus dan tidak zig-zag kecil.

---

## 6. Perencanaan Jalur (Path Planning)

Terjemahan tambak persegi menjadi path eksplisit di sisi aplikasi (fungsi `plan_coverage`).

```mermaid
flowchart TD
    IN[/"Panjang, Lebar,<br/>Lebar lintasan, Kecepatan,<br/>Titik awal (sudut tambak)"/] --> N["nLanes = ⌈lebar / lebar lintasan⌉"]
    N --> WP["Bangun waypoint zigzag<br/>x menyusuri lebar,<br/>y menyusuri panjang"]
    WP --> SEG["Turunkan segmen:<br/>Maju x m / Belok kanan/kiri y°"]
    SEG --> DIR["Arah belok berselang-seling<br/>(R,R lalu L,L, dst)"]
    DIR --> OUT1[Preview kanvas<br/>+ daftar langkah]
    DIR --> OUT2["Encode paket ke robot:<br/>SPD, LW, DIR"]
```

---

## Pola Fisik Zigzag di Tambak

```
START
 │
 ▼
┌─────────────────────────────┐
│ →→→→→→→→→→→→ Lane 1         │
│                          ↓  │  U-turn (belok kanan ×2)
│ ←←←←←←←←←←←← Lane 2        │
│ ↓  U-turn (belok kiri ×2)   │
│ →→→→→→→→→→→→ Lane 3         │
│                          ↓  │  U-turn (belok kanan ×2)
│ ←←←←←←←←←←←← Lane 4   STOP│
└─────────────────────────────┘
     TAMBAK (panjang × lebar)
```

> Arah U-turn berganti tiap lane (kanan-kanan, lalu kiri-kiri, dst) agar geseran konsisten ke satu sisi dan menutupi seluruh lebar tambak.
