"""
build_docs_pdf.py — Generator dokumentasi PDF GUI Feeder (metode SDLC Prototyping)
=================================================================================

Menghasilkan: Dokumentasi_GUI_Feeder_SDLC.pdf

Butuh: reportlab   (pip install reportlab)
Jalankan:  python build_docs_pdf.py
"""

import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable, Image, ListFlowable, ListItem, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

SCREENSHOT = "gui_screenshot.png"

OUT = "Dokumentasi_GUI_Feeder_SDLC.pdf"

# --------------------------------------------------------------------- styles
styles = getSampleStyleSheet()
NAVY = colors.HexColor("#1a3c5e")
BLUE = colors.HexColor("#2c6da3")
LIGHT = colors.HexColor("#eaf2f8")
GREY = colors.HexColor("#7f8c8d")

styles.add(ParagraphStyle("TitleBig", parent=styles["Title"], fontSize=22,
                          textColor=NAVY, spaceAfter=6, leading=26))
styles.add(ParagraphStyle("Sub", parent=styles["Normal"], fontSize=12,
                          textColor=GREY, alignment=TA_CENTER, spaceAfter=2))
styles.add(ParagraphStyle("H1", parent=styles["Heading1"], fontSize=15,
                          textColor=NAVY, spaceBefore=14, spaceAfter=6))
styles.add(ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12.5,
                          textColor=BLUE, spaceBefore=10, spaceAfter=4))
styles.add(ParagraphStyle("Body", parent=styles["Normal"], fontSize=10.5,
                          leading=15, alignment=TA_JUSTIFY, spaceAfter=6))
styles.add(ParagraphStyle("BulletB", parent=styles["Body"], leftIndent=6,
                          spaceAfter=2))
styles.add(ParagraphStyle("Cell", parent=styles["Normal"], fontSize=9.5, leading=12))
styles.add(ParagraphStyle("CellB", parent=styles["Cell"], textColor=colors.white,
                          fontName="Helvetica-Bold"))
styles.add(ParagraphStyle("CodeBox", parent=styles["Normal"], fontName="Courier",
                          fontSize=9, leading=12, backColor=LIGHT,
                          borderPadding=6, spaceAfter=6))
styles.add(ParagraphStyle("Note", parent=styles["Body"], fontSize=9.5,
                          textColor=colors.HexColor("#9a3412"), leftIndent=8,
                          borderColor=colors.HexColor("#f39c12"), borderWidth=0,
                          spaceAfter=6))
styles.add(ParagraphStyle("Caption", parent=styles["Normal"], fontSize=9,
                          textColor=GREY, alignment=TA_CENTER, spaceBefore=3,
                          spaceAfter=10, fontName="Helvetica-Oblique"))

story = []


def h1(t): story.append(Paragraph(t, styles["H1"]))
def h2(t): story.append(Paragraph(t, styles["H2"]))
def p(t): story.append(Paragraph(t, styles["Body"]))
def note(t): story.append(Paragraph("<b>Catatan:</b> " + t, styles["Note"]))
def sp(h=4): story.append(Spacer(1, h))
def code(t): story.append(Paragraph(t.replace("\n", "<br/>"), styles["CodeBox"]))


def figure(path, caption, max_w_cm=15.5):
    """Sisipkan gambar (auto-scale ke lebar) + caption. Aman bila file tak ada."""
    if not os.path.exists(path):
        story.append(Paragraph(f"[gambar {path} belum tersedia — "
                               "jalankan capture_gui.py]", styles["Caption"]))
        return
    iw, ih = ImageReader(path).getSize()
    w = max_w_cm * cm
    h = w * ih / iw
    img = Image(path, width=w, height=h)
    img.hAlign = "CENTER"
    story.append(img)
    story.append(Paragraph(caption, styles["Caption"]))


def bullets(items):
    story.append(ListFlowable(
        [ListItem(Paragraph(i, styles["BulletB"]), leftIndent=10) for i in items],
        bulletType="bullet", start="•"))
    sp(4)


def table(headers, rows, colw):
    data = [[Paragraph(h, styles["CellB"]) for h in headers]]
    for r in rows:
        data.append([Paragraph(str(c), styles["Cell"]) for c in r])
    t = Table(data, colWidths=colw, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b0bec5")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    sp(8)


# ===================================================================== COVER
story.append(Spacer(1, 3 * cm))
story.append(Paragraph("DOKUMENTASI PERANGKAT LUNAK", styles["Sub"]))
story.append(Paragraph("GUI Panel Kontrol Robot Feeder Akuatik", styles["TitleBig"]))
story.append(Paragraph("Pengembangan dengan Metode SDLC — Prototyping Model",
                       styles["Sub"]))
sp(10)
story.append(HRFlowable(width="60%", thickness=1.2, color=BLUE,
                        spaceBefore=8, spaceAfter=8, hAlign="CENTER"))
sp(10)
story.append(Table(
    [[Paragraph("Judul Skripsi", styles["Cell"]),
      Paragraph("Pengembangan Robot Akuatik untuk Feeder Otomatis di Tambak", styles["Cell"])],
     [Paragraph("Sub-sistem", styles["Cell"]),
      Paragraph("Transmitter — GUI Kendali (Raspberry Pi + NRF24L01)", styles["Cell"])],
     [Paragraph("Metode SDLC", styles["Cell"]),
      Paragraph("Prototyping Model", styles["Cell"])],
     [Paragraph("Framework GUI", styles["Cell"]),
      Paragraph("Python 3 + CustomTkinter", styles["Cell"])],
     [Paragraph("Tanggal", styles["Cell"]),
      Paragraph(datetime.now().strftime("%d %B %Y"), styles["Cell"])]],
    colWidths=[4 * cm, 11 * cm],
    style=TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b0bec5")),
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ])))
story.append(PageBreak())

# ===================================================================== 1
h1("1. Pendahuluan")
h2("1.1 Latar Belakang")
p("Robot akuatik feeder otomatis telah berhasil beroperasi di air: mampu bergerak "
  "lurus dengan <i>heading-hold</i> berbasis MPU6050 dan berbelok melalui "
  "<i>differential thrust</i> dua motor brushless. Kendali sebelumnya dilakukan lewat "
  "antarmuka baris perintah (CLI) pada berkas <b>receiverArduino.py</b> yang "
  "mengharuskan operator mengetik dimensi tambak secara manual dan tidak menampilkan "
  "status sistem. Untuk meningkatkan kegunaan (<i>usability</i>) dan menyediakan "
  "pemantauan, dikembangkan antarmuka grafis (GUI) yang berjalan di Raspberry Pi.")
h2("1.2 Tujuan")
bullets([
    "Menyediakan input dimensi tambak (panjang &amp; lebar dalam meter) yang mudah.",
    "Menerima <b>titik awal robot</b>, <b>lebar lintasan</b>, dan <b>kecepatan</b>, lalu "
    "menerjemahkan tambak persegi menjadi <b>path/jalur</b> berupa daftar langkah "
    "&quot;maju x m / belok y&deg;&quot; (pola zigzag) yang diikuti robot.",
    "Menyediakan <b>keypad numerik pada layar</b> (point-and-click) agar dapat "
    "dioperasikan tanpa keyboard fisik.",
    "Menampilkan <b>preview jalur</b> pada kanvas (peta tambak + arah tempuh) dan daftar "
    "langkah gerak sebelum misi dikirim.",
    "Menampilkan status koneksi modul NRF24 dan keterjangkauan robot secara nyata.",
    "Memberi kontrol manual untuk mematikan komponen yang relevan.",
    "Menampilkan telemetri (estimasi) kecepatan &amp; RPM baling-baling secara realtime.",
    "Menampilkan data sensor MPU6050 (roll, pitch, yaw/heading) secara nyata via serial USB.",
    "Mencatat seluruh aktivitas dan mengekspornya sebagai berkas log (CSV/TXT).",
])
h2("1.3 Ruang Lingkup & Batasan")
p("GUI berjalan di sisi <b>Transmitter</b> (Raspberry Pi) sebagai pengganti CLI. "
  "Pada iterasi ini firmware robot (ESP32, <b>Finalnew.ino</b>) turut <b>diperbarui</b>: "
  "protokol misi diperluas (menerima kecepatan, lebar lintasan, dan arah belok) dan pola "
  "belok diperbaiki agar sapuan menutupi seluruh tambak (lihat 4.5). "
  "Konsekuensi batasan teknis yang teridentifikasi pada tahap analisis:")
bullets([
    "<b>Komunikasi satu arah.</b> Raspberry hanya mengirim; robot hanya menerima. "
    "Robot tidak mengirim telemetri balik.",
    "<b>Tidak ada sensor RPM/encoder</b> pada robot. Maka nilai RPM &amp; kecepatan "
    "yang ditampilkan adalah <b>ESTIMASI</b> yang dihitung dari nilai PWM throttle, "
    "bukan hasil pengukuran.",
    "<b>Kontrol komponen individual</b> (mis. mematikan satu motor atau MPU) "
    "memerlukan protokol dua arah — di luar lingkup iterasi ini; ditandai sebagai "
    "indikator <i>monitor</i>.",
])
note("Kejujuran teknis ini justru menjadi bahan analisis yang baik: keterbatasan "
     "menjadi 'kebutuhan iterasi berikutnya' — sesuai semangat Prototyping.")

# ===================================================================== 2
h1("2. Metodologi: SDLC Prototyping Model")
p("Dipilih <b>Prototyping Model</b> karena kebutuhan GUI belum sepenuhnya pasti di "
  "awal dan paling baik ditemukan melalui purwarupa yang dievaluasi bersama dosen "
  "pembimbing. Cocok untuk sistem gabungan perangkat keras + lunak yang berevolusi.")
h2("2.1 Alasan Pemilihan (dibanding metode lain)")
table(["Metode", "Kesesuaian untuk proyek ini"],
      [["Waterfall", "Rapi didokumentasikan, tetapi kaku bila kebutuhan berubah."],
       ["V-Model", "Kuat di pengujian, tetapi mengasumsikan kebutuhan sudah pasti."],
       ["Incremental", "Baik, mirip Prototyping namun tiap increment harus 'final'."],
       ["<b>Prototyping (dipilih)</b>",
        "<b>Kebutuhan GUI ditemukan lewat purwarupa &amp; umpan balik; iteratif; "
        "cocok HW+SW.</b>"]],
      [4 * cm, 11 * cm])
h2("2.2 Tahapan Prototyping")
table(["Fase", "Aktivitas pada proyek ini"],
      [["1. Pengumpulan Kebutuhan",
        "Wawancara kebutuhan operator: input P×L, status NRF, kontrol komponen, "
        "telemetri realtime, ekspor log."],
       ["2. Perancangan Cepat (Quick Design)",
        "Rancang tata letak GUI &amp; pemisahan arsitektur core/GUI; definisikan "
        "protokol paket (misi/PING/STOP)."],
       ["3. Bangun Prototipe",
        "Implementasi feeder_core.py (RadioLink, MissionEstimator, ActivityLogger) "
        "dan feeder_gui.py (CustomTkinter)."],
       ["4. Evaluasi oleh Pengguna",
        "Demo ke pembimbing memakai MODE SIMULASI (tanpa hardware), lalu uji nyata "
        "di Raspberry Pi + robot."],
       ["5. Perbaikan (Refinement)",
        "Revisi berdasar umpan balik: iterasi-1 (label 'estimasi', LED status, penanganan "
        "input); iterasi-2 (perencanaan jalur, titik awal &amp; kecepatan, keypad layar, "
        "preview jalur, perbaikan pola belok). Ulangi fase 3–5."],
       ["6. Rekayasa Produk & Pemeliharaan",
        "Stabilkan, dokumentasikan, siapkan iterasi lanjutan (telemetri 2 arah)."]],
      [4.2 * cm, 10.8 * cm])
h2("2.3 Siklus Iterasi (Prototyping Loop)")
code("  Kebutuhan  ->  Quick Design  ->  Bangun Prototipe\n"
     "      ^                                    |\n"
     "      |                                    v\n"
     "  Perbaikan  <----  Evaluasi Pengguna  <---+\n"
     "  (ulangi hingga pengguna puas -> Produk Final)")

# ===================================================================== 3
h1("3. Analisis Kebutuhan")
h2("3.1 Kebutuhan Fungsional")
table(["Kode", "Kebutuhan", "Status"],
      [["RF-1", "Input panjang &amp; lebar tambak (meter) dan kirim misi AUTO",
        "Terpenuhi"],
       ["RF-2", "Menampilkan status modul NRF &amp; keterjangkauan robot (ACK)",
        "Terpenuhi (real)"],
       ["RF-3", "Mematikan komponen yang dapat dikontrol (NRF TX, PING, Motor)",
        "Terpenuhi"],
       ["RF-4", "Menampilkan RPM &amp; kecepatan baling-baling realtime",
        "Terpenuhi (estimasi)"],
       ["RF-5", "Mencatat &amp; mengekspor log aktivitas (CSV/TXT)", "Terpenuhi"],
       ["RF-6", "Perintah STOP membatalkan misi berjalan", "Terpenuhi (real)"],
       ["RF-7", "Menampilkan data MPU6050 (roll/pitch/yaw) via serial USB",
        "Terpenuhi (real)"],
       ["RF-8", "Input titik awal robot (sudut tambak) &amp; kecepatan &amp; lebar lintasan",
        "Terpenuhi"],
       ["RF-9", "Menerjemahkan path jadi daftar langkah &quot;maju x / belok y&deg;&quot; "
        "&amp; preview kanvas", "Terpenuhi"],
       ["RF-10", "Keypad numerik pada layar (operasi tanpa keyboard fisik)",
        "Terpenuhi"],
       ["RF-11", "Mengirim parameter misi ke robot (kecepatan, lebar lintasan, arah belok)",
        "Terpenuhi (real)"]],
      [1.7 * cm, 10.3 * cm, 3 * cm])
h2("3.2 Kebutuhan Non-Fungsional")
bullets([
    "<b>Keterandalan:</b> heartbeat PING tiap 0,5 s menjaga failsafe robot (stop &lt; 3 s bila sinyal hilang).",
    "<b>Portabilitas:</b> berjalan di Raspberry Pi (NRF real) &amp; PC (auto-fallback simulasi).",
    "<b>Usability:</b> indikator warna (hijau/oranye/merah), label satuan jelas, serta "
    "<b>operasi penuh lewat sentuhan</b> (keypad di layar + preview jalur) tanpa keyboard/mouse.",
    "<b>Kejujuran data:</b> nilai estimasi diberi label eksplisit agar tidak menyesatkan.",
])

# ===================================================================== 4
h1("4. Perancangan (Quick Design)")
h2("4.1 Arsitektur Perangkat Lunak")
p("Menerapkan <i>Separation of Concerns</i>: lapisan presentasi (GUI) dipisah dari "
  "logika (core), sehingga mudah diuji dan dikembangkan.")
table(["Modul", "Tanggung jawab"],
      [["feeder_gui.py", "Presentasi: input, keypad layar, kanvas preview jalur, tombol, "
        "gauge, LED, tampilan log."],
       ["feeder_core.py -&gt; plan_coverage / CoveragePlan",
        "Terjemahkan tambak + titik awal + lebar lintasan -&gt; daftar segmen "
        "&quot;maju/belok&quot; + encode_mission (paket ke robot)."],
       ["feeder_core.py -&gt; RadioLink",
        "Abstraksi NRF24 (pyrf24) + auto-fallback MockRadio (simulasi)."],
       ["feeder_core.py -&gt; MissionEstimator",
        "Cermin timeline zigzag firmware -&gt; estimasi fase/PWM/RPM per waktu."],
       ["feeder_core.py -&gt; ActivityLogger",
        "Pencatatan aktivitas berstempel waktu + ekspor CSV/TXT."]],
      [5.6 * cm, 9.4 * cm])
h2("4.2 Protokol Komunikasi (diperluas, tetap kompatibel-mundur)")
table(["Paket", "Arah", "Makna"],
      [["P=&lt;m&gt;;L=&lt;m&gt;;MODE=AUTO;<br/>SPD=&lt;m/s&gt;;LW=&lt;m&gt;;DIR=&lt;R|L&gt;",
        "Pi -&gt; Robot",
        "Perintah misi zigzag + kecepatan (SPD), lebar lintasan (LW), arah belok "
        "pertama (DIR). Field SPD/LW/DIR opsional; bila tak ada robot memakai default."],
       ["PING", "Pi -&gt; Robot", "Heartbeat (jaga failsafe) tiap 0,5 s"],
       ["STOP", "Pi -&gt; Robot", "Batalkan misi / matikan motor"],
       ["(ACK otomatis)", "Robot -&gt; Pi",
        "Auto-ACK NRF; True = robot hidup &amp; terjangkau"]],
      [6 * cm, 2.6 * cm, 6.4 * cm])
p("Paket lama <b>P=..;L=..;MODE=AUTO</b> tetap valid — firmware baru mengabaikan "
  "field yang tak ada dan memakai konstanta default, sehingga tidak memutus kompatibilitas.")
h2("4.3 Dasar Estimasi Telemetri")
p("Karena tak ada sensor, GUI menghitung PWM yang <i>seharusnya</i> dijalankan robot "
  "pada detik ke-t (mengikuti pola gerak firmware), lalu mengonversinya:")
code("throttle = (PWM - 1000) / (2000 - 1000)\n"
     "RPM_est  = throttle * MOTOR_KV * BATTERY_V     (default KV=2200, V=11.1)\n"
     "speed_est= ROBOT_SPEED_MPS * throttle / throttle(CRUISE_PWM)")
note("Konstanta MOTOR_KV, BATTERY_V, CRUISE_PWM, TURN_90_MS wajib disamakan dengan "
     "firmware &amp; dikalibrasi pada pengujian air agar estimasi mendekati kenyataan.")
h2("4.4 Integrasi Data MPU6050 (Serial USB)")
p("Berbeda dengan telemetri gerak yang berupa estimasi, data orientasi diambil "
  "<b>langsung dari sensor MPU6050</b>. Sketsa <b>mpu.ino</b> (Test Part/MPU Test) "
  "pada ESP32 mencetak orientasi ke Serial tiap 200 ms; GUI membacanya melalui "
  "<b>pyserial</b> pada jalur USB yang <b>terpisah dari NRF</b>. Kelas "
  "<b>MPUSerialReader</b> mem-parse baris berikut:")
code("Angle -> X: &lt;roll&gt;  Y: &lt;pitch&gt;  Z(Yaw): &lt;yaw&gt;  "
     "| Gyro -> X: &lt;gx&gt; Y: &lt;gy&gt; Z: &lt;gz&gt;")
p("Roll (X), Pitch (Y), dan Yaw/heading (Z) ditampilkan realtime dan dapat "
  "direkam ke log (1 Hz) untuk diekspor. Jalur serial cocok untuk fase "
  "<b>kalibrasi/uji bench</b> saat board tertambat kabel; saat robot berlayar "
  "bebas, data MPU realtime memerlukan telemetri NRF dua arah (iterasi berikutnya).")

h2("4.5 Perencanaan Jalur (Path Planning)")
p("Fungsi <b>plan_coverage()</b> menerjemahkan tambak persegi menjadi jalur sapuan "
  "<i>boustrophedon</i> (zigzag). Dari masukan pengguna &mdash; panjang, lebar, "
  "<b>lebar lintasan</b>, <b>kecepatan</b>, dan <b>titik awal</b> (sudut tambak) &mdash; "
  "dihitung titik-titik belok (waypoint), lalu diturunkan menjadi daftar langkah "
  "eksplisit &quot;maju x meter&quot; dan &quot;belok kanan/kiri y&deg;&quot;. Daftar ini "
  "ditampilkan ke pengguna dan dasar paket yang dikirim ke robot (SPD/LW/DIR).")
p("Koordinat: sumbu-x menyusuri lebar, sumbu-y menyusuri panjang. Robot menjelajah "
  "lurus arah-y tiap lintasan, lalu U-turn menggeser sejauh satu lebar lintasan arah-x.")
code("Contoh: tambak 10 x 4 m, lebar lintasan 1 m, mulai Kiri-Bawah -> 4 lintasan:\n"
     "  1. Maju 10.0 m        5. Maju 10.0 m         9. Maju 10.0 m\n"
     "  2. Belok kanan 90     6. Belok kiri 90      10. Belok kanan 90\n"
     "  3. Maju 1.0 m         7. Maju 1.0 m         11. Maju 1.0 m\n"
     "  4. Belok kanan 90     8. Belok kiri 90      12. Belok kanan 90\n"
     "                                              13. Maju 10.0 m\n"
     "  Paket: P=10;L=4;MODE=AUTO;SPD=0.5;LW=1;DIR=R")
p("<b>Perbaikan pola belok (temuan iterasi ini).</b> Versi sebelumnya melakukan U-turn "
  "yang <b>selalu belok kanan</b>. Secara geometri hal ini menggeser robot ke kanan lalu "
  "ke kiri bergantian, sehingga robot hanya bolak-balik di dua kolom dan <b>tidak menyapu "
  "seluruh lebar tambak</b>. Diperbaiki menjadi arah U-turn <b>berselang-seling</b> "
  "(kanan-kanan, lalu kiri-kiri, dst) sehingga geseran selalu ke sisi yang sama &mdash; "
  "sapuan menutupi seluruh tambak. GUI dan firmware kini menghitung arah belok dari sumber "
  "yang sama, jadi <b>preview jalur = gerak nyata robot</b>.")
note("Titik awal dapat dipilih lewat menu atau <b>diklik langsung pada kanvas peta</b>; "
     "arah belok pertama (DIR) dihitung dari titik awal agar robot menyapu ke arah dalam "
     "tambak.")

# ===================================================================== 5
h1("5. Implementasi Prototipe")
h2("5.1 Fitur GUI")
bullets([
    "<b>Panel Misi:</b> input Panjang, Lebar, Lebar lintasan, Kecepatan (m/s), dan "
    "Titik awal (sudut tambak); tombol PREVIEW JALUR, KIRIM MISI &amp; STOP.",
    "<b>Keypad numerik:</b> tombol 0&ndash;9, titik, hapus &amp; backspace pada layar &mdash; "
    "ketuk kolom lalu ketik; memungkinkan operasi <b>tanpa keyboard fisik</b> (layar sentuh).",
    "<b>Preview Jalur:</b> kanvas peta tambak menggambar lintasan zigzag berpanah + titik "
    "START (klik peta = pilih titik awal), disertai daftar langkah &quot;maju/belok&quot; "
    "dan ringkasan (jumlah lintasan, jarak, estimasi waktu).",
    "<b>Status Koneksi:</b> mode (REAL/SIMULASI), deteksi modul NRF, status robot.",
    "<b>Kontrol Komponen:</b> saklar NRF TX, Heartbeat PING, Motor (efek nyata "
    "lewat STOP); indikator monitor Motor Kiri/Kanan &amp; MPU.",
    "<b>Telemetri:</b> fase misi, progress bar, gauge RPM/throttle/speed L &amp; R.",
    "<b>Sensor MPU6050:</b> pilih port serial, tampil Roll/Pitch/Yaw realtime, "
    "opsi rekam ke log.",
    "<b>Log:</b> tampilan realtime + tombol Export CSV / Export TXT / Clear.",
])
h2("5.2 Mode Simulasi")
p("Bila pyrf24 tidak tersedia atau NRF tak terdeteksi, RadioLink otomatis memakai "
  "MockRadio; demikian pula MPUSerialReader menyediakan mode simulasi bila serial "
  "tidak tersedia. Dengan begitu GUI tetap dapat didemokan dan diuji tanpa "
  "perangkat keras — sangat membantu pada fase evaluasi Prototyping.")
h2("5.3 Tampilan Antarmuka")
figure(SCREENSHOT,
       "Gambar 1. Antarmuka GUI: panel misi (dimensi, lebar lintasan, kecepatan, titik "
       "awal), keypad numerik &amp; preview jalur di kolom kiri; status, telemetri, "
       "panel MPU6050 &amp; log aktivitas di kolom kanan.")

# ===================================================================== 6
h1("6. Pengujian (Black-Box)")
table(["Uji", "Skenario", "Hasil Diharapkan"],
      [["T-1", "Input P=10 L=4, klik KIRIM MISI",
        "Paket terkirim, 4 jalur terhitung, gauge bergerak"],
       ["T-2", "Robot online (ACK) di simulasi",
        "Status ROBOT = TERHUBUNG (hijau)"],
       ["T-3", "Robot offline",
        "Status ROBOT = TERPUTUS (merah) &lt; 3 s"],
       ["T-4", "Matikan saklar Motor",
        "STOP terkirim, misi berhenti, LED motor merah"],
       ["T-5", "Input non-angka",
        "Muncul dialog error, misi tidak dikirim"],
       ["T-6", "Klik Export CSV/TXT",
        "Berkas log tersimpan &amp; berisi seluruh event"],
       ["T-7", "Timeline estimasi habis",
        "Fase = SELESAI, misi &amp; heartbeat berhenti otomatis"],
       ["T-8", "Hubungkan MPU (serial/simulasi) + Rekam ke log",
        "Roll/Pitch/Yaw tampil realtime, data MPU masuk log &amp; ekspor"],
       ["T-9", "Isi dimensi/lebar lintasan/titik awal lalu Preview",
        "Kanvas &amp; daftar langkah &quot;maju/belok&quot; sesuai &amp; berubah realtime"],
       ["T-10", "Ketuk kolom input lalu tekan keypad angka",
        "Nilai kolom terisi tanpa keyboard fisik; preview ikut ter-update"],
       ["T-11", "Ganti titik awal (menu / klik kanvas)",
        "Jalur &amp; arah belok pertama (DIR) berubah sesuai sudut awal"],
       ["T-12", "Kirim misi dgn kecepatan berbeda",
        "Paket memuat SPD/LW/DIR; estimasi waktu menyesuaikan kecepatan"]],
      [1.4 * cm, 6.6 * cm, 7 * cm])

# ===================================================================== 7
h1("7. Panduan Instalasi & Penggunaan")
h2("7.1 Instalasi")
code("# Di Raspberry Pi (kendali nyata):\n"
     "pip install customtkinter pyrf24\n\n"
     "# Di PC (mode simulasi, tanpa NRF):\n"
     "pip install customtkinter")
h2("7.2 Menjalankan")
p("Cukup jalankan satu berkas entry point <b>receiverArduino.py</b>; GUI, "
  "telemetri, dan logging berjalan otomatis:")
code("cd Master Code/Transmitter\n"
     "python receiverArduino.py          # buka GUI (default)\n"
     "python receiverArduino.py --cli    # mode teks lama (opsional)")
h2("7.3 Berkas Terkait")
table(["Berkas", "Keterangan"],
      [["receiverArduino.py",
        "ENTRY POINT — jalankan ini -&gt; GUI (opsi --cli utk mode teks lama)"],
       ["feeder_gui.py", "Aplikasi GUI (CustomTkinter)"],
       ["feeder_core.py",
        "Backend: RadioLink, MissionEstimator, ActivityLogger, MPUSerialReader"],
       ["capture_gui.py", "Skrip pengambil screenshot GUI untuk dokumentasi"],
       ["build_docs_pdf.py", "Generator dokumen PDF ini"],
       ["Robot/New/Finalnew/Finalnew.ino",
        "Firmware robot (ESP32) — diperbarui: parse SPD/LW/DIR + belok berselang-seling"],
       ["Test Part/MPU Test/mpu/mpu.ino", "Sketsa sumber data MPU6050 via serial"]],
      [6 * cm, 9 * cm])

h2("7.4 Deploy di Raspberry Pi (rekomendasi)")
p("GUI dijalankan di Raspberry Pi karena memiliki GPIO/SPI untuk modul NRF24. "
  "GUI membutuhkan sesi <b>Desktop</b> (monitor HDMI atau VNC) — tidak bisa lewat "
  "SSH polos. Wiring NRF24L01 mengikuti pemetaan pin berikut (kode: RF24(24, 0) -&gt; "
  "CE=GPIO24, CSN=CE0):")
table(["NRF24L01", "Raspberry Pi (BCM)", "Pin fisik"],
      [["VCC (3.3V)", "3.3V", "1 / 17"],
       ["GND", "GND", "6, 9, ..."],
       ["CE", "GPIO24", "18"],
       ["CSN", "GPIO8 (CE0)", "24"],
       ["SCK", "GPIO11", "23"],
       ["MOSI", "GPIO10", "19"],
       ["MISO", "GPIO9", "21"]],
      [4 * cm, 6 * cm, 5 * cm])
note("VCC NRF wajib 3.3V (bukan 5V); tambahkan kapasitor 10µF antara VCC–GND "
     "modul agar catu daya stabil.")
p("<b>Instalasi otomatis</b> — ekstrak paket <b>raspberry_feeder.zip</b>, lalu "
  "jalankan skrip setup sekali:")
code("cd ~/feeder            # lokasi hasil ekstrak\n"
     "chmod +x setup_pi.sh run.sh\n"
     "./setup_pi.sh          # aktifkan SPI, apt, venv, pip install")
p("<b>Instalasi manual</b> (bila ingin bertahap):")
code("sudo raspi-config nonint do_spi 0            # aktifkan SPI\n"
     "sudo apt install -y python3-venv python3-tk\n"
     "sudo usermod -aG spi,gpio,dialout $USER      # lalu logout-login\n"
     "python3 -m venv --system-site-packages ~/feeder-venv\n"
     "source ~/feeder-venv/bin/activate\n"
     "pip install -r requirements.txt")
p("<b>Menjalankan:</b>")
code("./run.sh            # buka GUI\n"
     "./run.sh --cli      # mode teks lama")
note("Gunakan venv dengan --system-site-packages agar python3-tk (dari apt) "
     "terlihat di dalam venv; tanpa itu GUI gagal import tkinter. Bila status "
     "MODE tetap SIMULASI di Pi, berarti SPI belum aktif / wiring NRF salah "
     "(cek: ls /dev/spidev*).")

# ===================================================================== 8
h1("8. Kesimpulan & Iterasi Berikutnya")
p("Prototipe GUI berhasil memenuhi seluruh kebutuhan fungsional sesuai lingkup "
  "iterasi ini, dengan pemisahan arsitektur yang bersih dan mode simulasi yang "
  "mempermudah evaluasi. <b>Iterasi ini</b> &mdash; menindaklanjuti umpan balik pembimbing "
  "&mdash; menambahkan <b>perencanaan jalur</b> (dimensi + titik awal + lebar lintasan + "
  "kecepatan -&gt; daftar langkah maju/belok), <b>keypad layar</b> untuk operasi tanpa "
  "keyboard, <b>preview jalur</b> point-and-click, protokol misi diperluas, serta "
  "<b>perbaikan pola belok</b> agar sapuan menutupi seluruh tambak. Sesuai Prototyping "
  "Model, keterbatasan yang tersisa menjadi rencana iterasi selanjutnya:")
bullets([
    "Menambah <b>telemetri dua arah</b> (ACK payload NRF) agar status komponen &amp; "
    "throttle asli dikirim balik dari robot.",
    "Memasang <b>sensor RPM (hall/encoder)</b> untuk mengganti estimasi dengan data ukur.",
    "Menambah perintah firmware untuk <b>kontrol komponen individual</b> (motor kiri/kanan, MPU).",
    "Belok berbasis <b>sudut yaw MPU</b> (bukan durasi), agar belokan presisi tanpa "
    "kalibrasi TURN_90_MS yang rawan.",
    "Mendukung <b>path waypoint bebas</b> (klik banyak titik) selain sapuan persegi.",
    "Kalibrasi konstanta (ROBOT_SPEED_MPS, TURN_90_MS, KV) pada pengujian air.",
])

story.append(Spacer(1, 12))
story.append(HRFlowable(width="100%", thickness=0.6, color=GREY))


# --------------------------------------------------------------------- footer
def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(2 * cm, 1.2 * cm,
                      "GUI Feeder Robot Akuatik — SDLC Prototyping")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Hal. {doc.page}")
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4,
                        topMargin=2 * cm, bottomMargin=2 * cm,
                        leftMargin=2 * cm, rightMargin=2 * cm,
                        title="Dokumentasi GUI Feeder — SDLC Prototyping")
doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
print(f"OK -> {OUT}")
