# Flowchart — Robot Akuatik Feeder Otomatis

> Render di VS Code: install extension **"Markdown Preview Mermaid Support"**, lalu Ctrl+Shift+V

---

## 1. Gambaran Sistem

```mermaid
flowchart LR
    subgraph RPi["🖥️ Raspberry Pi 4 (Transmitter)"]
        A[Input Ukuran Tambak] --> B[Format Data RF24]
    end

    subgraph Radio["📡 RF24 NRF24L01+\n250 KBPS / Ch 0x76"]
        B -- "P=X;L=Y;MODE=AUTO" --> C
    end

    subgraph ESP32["⚙️ ESP32 (Receiver)"]
        C[Terima Data] --> D[Parse & Jalankan Misi]
        D --> E[MPU6050\nHeading-Hold Proporsional]
        D --> F[2x ESC Brushless 30A\nKiri & Kanan - Differential]
        D --> G[Pola Zigzag\nCoverage Tambak]
    end
```

---

## 2. Flowchart Raspberry Pi (Transmitter)

```mermaid
flowchart TD
    START([▶ START]) --> INIT[Init RF24\nCE=24, CSN=0\nCh=0x76, 250KBPS]
    INIT --> CHECK{NRF24\nTerdeteksi?}
    CHECK -- Tidak --> ERR1([❌ Quit])
    CHECK -- Ya --> INPUT1[/Input: Panjang Tambak/]
    INPUT1 --> INPUT2[/Input: Lebar Tambak/]
    INPUT2 --> FORMAT["Format: P={p};L={l};MODE=AUTO"]
    FORMAT --> SEND[Kirim via RF24]
    SEND --> ACK{Berhasil\nTerkirim?}
    ACK -- Ya --> LOG1[Print: Terkirim]
    ACK -- Tidak --> LOG2[Print: Gagal Kirim]
    LOG1 --> WAIT[Tunggu 2 detik]
    LOG2 --> WAIT
    WAIT --> SEND
```

---

## 3. Flowchart ESP32 (Receiver)

```mermaid
flowchart TD
    START([▶ START]) --> INITMPU[Init MPU6050\nSDA=21, SCL=22\nCalc Gyro Offsets]
    INITMPU --> INITESC[Attach ESC\nLeft=25, Right=26]
    INITESC --> ARM[Arm ESC\nPWM=1000 selama 5 detik]
    ARM --> INITRF[Init RF24\nCE=9, CSN=10\nPipe 1, Listen]
    INITRF --> CHECK{NRF24\nOK?}
    CHECK -- Tidak --> HALT([❌ Halt])
    CHECK -- Ya --> LISTEN[Tunggu Sinyal RF24]

    LISTEN --> RF24{Data\nMasuk?}
    RF24 -- Tidak --> UPDATEMPU[Update MPU6050]
    UPDATEMPU --> LISTEN

    RF24 -- Ya --> PARSE[Parse:\nP= / L= / MODE=]
    PARSE --> VALID{Format\nValid?}
    VALID -- Tidak --> ERRMSG[Serial: Format Error]
    ERRMSG --> LISTEN

    VALID -- Ya --> STORE[Simpan:\npanjangTambak, lebarTambak\nmodeRobot]
    STORE --> MODECHECK{MODE\n== AUTO?}
    MODECHECK -- Tidak --> LISTEN
    MODECHECK -- Ya --> MISI[Jalankan Misi Zigzag]
    MISI --> DONE([✅ MISI SELESAI\nstopBoat])
    DONE --> LISTEN
```

---

## 4. Flowchart Misi Zigzag (AUTO MODE)

```mermaid
flowchart TD
    ENTRY([Masuk AUTO MODE]) --> VALID{"panjang & lebar\n> 0?"}
    VALID -- Tidak --> CANCEL([❌ Misi dibatalkan])
    VALID -- Ya --> CALC["Hitung:\nnLanes = ⌈lebar / LANE_WIDTH⌉\nlaneDuration = panjang / SPEED × 1000 ms\nshiftDuration = LANE_WIDTH / SPEED × 1000 ms"]
    CALC --> HB[Reset heartbeat\nlastSignalMs = millis]
    HB --> LOOP{lane < nLanes\n& tidak abort?}

    LOOP -- Tidak --> STOP([✅ Stop Boat])

    LOOP -- Ya --> REZERO["RE-ZERO: targetYaw = yaw saat ini\n(kunci heading baru tiap lane,\nlawan gyro drift)"]
    REZERO --> DRIVE["driveHeadingMS lurus\n(heading-hold proporsional + failsafe)"]
    DRIVE --> ABORT1{Sinyal hilang?}
    ABORT1 -- Ya --> ABORTED([🛑 MISI DIBATALKAN])
    ABORT1 -- Tidak --> PAUSE1[Stop + delay 500ms]

    PAUSE1 --> LASTLANE{Lane\nTerakhir?}
    LASTLANE -- Ya --> STOP

    LASTLANE -- Tidak --> T1["Belok Kanan 90° #1\n(TURN_90_MS)"]
    T1 --> SHIFT["Geser 1 jalur\n(shiftDuration ms, kunci heading baru)"]
    SHIFT --> T2["Belok Kanan 90° #2\n→ total 180°, hadap balik"]
    T2 --> INC[lane++]
    INC --> LOOP
```

> Catatan: arah balik tiap lane dihasilkan dari **dua kali belok kanan 90°** (total 180°), bukan dari aritmetika yaw. Cocok dengan ESC unidirectional yang hanya bisa belok melingkar.

---

## 5. Logika Heading-Hold Proporsional (driveHeadingMS)

```mermaid
flowchart TD
    ENTRY([Mulai driveHeadingMS]) --> TIMER[Set timer]
    TIMER --> TIMECHECK{Waktu\nhabis?}
    TIMECHECK -- Ya --> STOPFN([Stop Boat → return true])
    TIMECHECK -- Tidak --> UPD[mpu.update]
    UPD --> SIG{"signalAlive?\n(< 3 detik sejak sinyal terakhir)"}
    SIG -- Tidak --> FAIL([🛑 Stop Boat → return false])
    SIG -- Ya --> ERR["error = targetYaw - currentYaw\nnormalisasi ke -180..180"]
    ERR --> DEAD{"|error| > 2°?"}
    DEAD -- Tidak --> STRAIGHT["correction = 0\n(lurus)"]
    DEAD -- Ya --> PROP["correction = Kp × error\nclamp ±MAX_CORRECTION"]
    PROP --> WRITE
    STRAIGHT --> WRITE["Left = 1300 + correction\nRight = 1300 - correction\n(constrain 1000..2000)"]
    WRITE --> ESC[writeMicroseconds ke 2 ESC]
    ESC --> DELAY[delay 50ms]
    DELAY --> TIMECHECK
```

> Koreksi **proporsional** (`Kp × error`) menggantikan koreksi tetap ±20 — makin besar simpangan, makin kuat koreksi, sehingga gerak lurus lebih halus dan tidak zig-zag kecil.

---

## Pola Fisik Zigzag di Tambak

```
START
 │
 ▼
┌─────────────────────────────┐
│ →→→→→→→→→→→→ Lane 1         │
│                          ↓  │
│ ←←←←←←←←←←←← Lane 2        │
│ ↓                           │
│ →→→→→→→→→→→→ Lane 3         │
│                          ↓  │
│ ←←←←←←←←←←←← Lane 4   STOP│
└─────────────────────────────┘
     TAMBAK (panjang × lebar)
```
