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
     [Paragraph("Target Tampilan", styles["Cell"]),
      Paragraph("Layar sentuh 7&quot; (800 &times; 480 px) — adaptif mengikuti layar perangkat",
                styles["Cell"])],
     [Paragraph("Protokol Kendali", styles["Cell"]),
      Paragraph("FW / CW / CCW / STOP + ON &amp; FIN "
                "(Dokumen Spesifikasi Teknis)", styles["Cell"])],
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
    "Menerapkan <b>protokol Sinyal Kendali</b> sesuai Dokumen Spesifikasi Teknis: "
    "perintah <b>FW / CW / CCW / STOP</b> dengan pola Request-Response beserta sinyal "
    "balik <b>ON</b> dan <b>FIN</b>.",
    "Menyediakan <b>kendali manual</b> untuk memasukkan sendiri perintah maju "
    "(<b>dalam satuan meter</b>, dipecah otomatis menjadi paket FW) serta CW dan CCW "
    "di samping STOP yang sudah ada.",
    "Menyesuaikan tampilan dengan <b>ukuran layar perangkat</b> &mdash; dirancang untuk "
    "<b>layar sentuh 7 inci</b> bergaya mesin ATM: minimalis dan bertombol besar, "
    "namun seluruh fitur dipertahankan.",
    "Menyediakan <b>papan angka pada layar</b> agar dapat dioperasikan tanpa keyboard fisik.",
    "Menampilkan <b>preview jalur</b> pada kanvas (peta tambak + arah tempuh) dan daftar "
    "perintah yang akan dikirim sebelum misi dijalankan.",
    "Menampilkan status koneksi modul NRF24 dan keterjangkauan robot secara nyata.",
    "Memberi kontrol manual untuk mematikan komponen yang relevan.",
    "Menampilkan telemetri (estimasi) kecepatan &amp; RPM baling-baling secara realtime.",
    "Menampilkan data sensor MPU (roll, pitch, yaw/heading) secara nyata &mdash; "
    "<b>dikirim robot lewat radio, tanpa port serial</b> &mdash; berjalan di latar "
    "belakang dengan saklar nyala/mati pencatatannya.",
    "Mencatat seluruh aktivitas, <b>menyimpannya otomatis ke berkas TXT sejak "
    "aplikasi dibuka</b>, membuang berkas yang lebih tua dari 3 hari, serta "
    "mengekspornya sebagai CSV/TXT.",
    "Menuntun operator lewat <b>alur kerja</b> (BERANDA &rarr; MISI &rarr; DASHBOARD) "
    "alih-alih menyodorkan menu berisi enam halaman.",
    "Memberi operator <b>pilihan mode kerja REAL atau SIMULASI</b> yang dapat dipindah "
    "kapan saja, dengan SIMULASI sebagai keadaan awal yang aman.",
])
h2("1.3 Ruang Lingkup & Batasan")
p("GUI berjalan di sisi <b>Transmitter</b> (Raspberry Pi) sebagai pengganti CLI. "
  "Pada iterasi ini firmware robot (ESP32, <b>Finalnew.ino</b>) turut <b>ditulis ulang</b> "
  "agar perilakunya mengikuti Dokumen Spesifikasi Teknis: robot berubah dari penjalan "
  "misi mandiri menjadi <b>eksekutor perintah</b> yang menjalankan satu gerakan dalam satu "
  "waktu dan melapor lewat ON/FIN (lihat 4.2). Konsekuensi batasan teknis yang "
  "teridentifikasi pada tahap analisis:")
bullets([
    "<b>Komunikasi dua arah half-duplex.</b> Radio NRF dipakai bergantian (&quot;gantian&quot; "
    "seperti radio HT): Pi mengirim perintah/PING, robot membalas ON/FIN dan telemetri MPU "
    "di sela-selanya (alamat balik 00002). Bukan full-duplex, jadi kirim/terima tidak bersamaan.",
    "<b>Tidak ada sensor RPM/encoder</b> pada robot. Maka nilai RPM &amp; kecepatan "
    "yang ditampilkan adalah <b>ESTIMASI</b> yang dihitung dari nilai PWM throttle, "
    "bukan hasil pengukuran.",
    "<b>Jarak FW diturunkan dari waktu tempuh</b> (jarak &divide; kecepatan jelajah), "
    "bukan dari odometri. Ketepatan jarak karena itu bergantung pada kalibrasi "
    "ROBOT_SPEED_MPS dan dipengaruhi arus air.",
    "<b>ESC bersifat unidirectional</b> (hanya maju), sehingga CW/CCW dilakukan dengan "
    "<i>differential thrust</i>: robot berputar melingkar lebar, bukan di tempat. Sudut "
    "akhirnya tetap akurat karena putaran ditutup memakai umpan balik yaw MPU, tetapi "
    "robot ikut berpindah posisi selama berputar.",
    "<b>Kontrol komponen individual</b> (mis. mematikan satu motor atau MPU) belum "
    "memiliki perintah pada tabel protokol; ditandai sebagai indikator <i>monitor</i>.",
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
        "Implementasi feeder_core.py (RobotCommand, RadioLink, CommandRunner, "
        "ActivityLogger) dan feeder_gui.py (CustomTkinter)."],
       ["4. Evaluasi oleh Pengguna",
        "Demo ke pembimbing memakai MODE SIMULASI (tanpa hardware), lalu uji nyata "
        "di Raspberry Pi + robot."],
       ["5. Perbaikan (Refinement)",
        "Revisi berdasar umpan balik: iterasi-1 (label 'estimasi', LED status, penanganan "
        "input); iterasi-2 (perencanaan jalur, titik awal &amp; kecepatan, keypad layar, "
        "preview jalur, perbaikan pola belok); iterasi-3 (tampilan mengikuti layar "
        "perangkat bergaya ATM, perilaku robot mengikuti Dokumen Spesifikasi Teknis, "
        "kendali manual FW/CW/CCW). Ulangi fase 3–5."],
       ["6. Rekayasa Produk & Pemeliharaan",
        "Stabilkan, dokumentasikan, siapkan iterasi lanjutan (odometri &amp; sensor RPM)."]],
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
       ["RF-7", "Menampilkan data MPU6050 (roll/pitch/yaw) tanpa port serial &mdash; "
        "mengalir sendiri lewat telemetri radio", "Terpenuhi (real)"],
       ["RF-8", "Input titik awal robot (sudut tambak) &amp; kecepatan &amp; lebar lintasan",
        "Terpenuhi"],
       ["RF-9", "Menerjemahkan path jadi daftar langkah &quot;maju x / belok y&deg;&quot; "
        "&amp; preview kanvas", "Terpenuhi"],
       ["RF-10", "Keypad numerik pada layar (operasi tanpa keyboard fisik)",
        "Terpenuhi"],
       ["RF-11", "Mengirim parameter misi ke robot (kecepatan, lebar lintasan, arah belok)",
        "Terpenuhi (real)"],
       ["RF-12", "Menerima telemetri MPU (roll/pitch/yaw) balik dari robot via radio (2 arah)",
        "Terpenuhi (real)"],
       ["RF-13", "Protokol Request-Response &quot;[Moves]:[Dist]&quot; dengan sinyal balik "
        "ON &amp; FIN sesuai Dokumen Spesifikasi Teknis", "Terpenuhi (real)"],
       ["RF-14", "Mengirim ulang perintah bila &quot;ON [Moves]&quot; tak diterima dalam 1 detik",
        "Terpenuhi (real)"],
       ["RF-15", "Input manual perintah FW, CW, dan CCW (STOP sudah ada)",
        "Terpenuhi (real)"],
       ["RF-16", "Menolak [Dist] di luar rentang tabel perintah sebelum paket dikirim",
        "Terpenuhi"],
       ["RF-17", "Tampilan mengikuti ukuran layar perangkat (layar sentuh 7 inci, gaya ATM)",
        "Terpenuhi"],
       ["RF-18", "Perintah maju manual diisi dalam <b>meter</b> lalu dipecah otomatis "
        "menjadi paket FW 10&ndash;200 cm", "Terpenuhi"],
       ["RF-19", "Saklar nyala/mati <b>pencatatan sudut MPU</b> ke log", "Terpenuhi"],
       ["RF-20", "Saklar <b>auto-simpan log ke berkas TXT</b> selama operasi berjalan",
        "Terpenuhi"],
       ["RF-21", "Pemilihan <b>mode kerja REAL/SIMULASI</b> saat aplikasi berjalan "
        "(default SIMULASI)", "Terpenuhi"],
       ["RF-22", "Layar pembuka hanya berisi <b>MISI</b> &amp; <b>SETTING</b>; "
        "DASHBOARD terbuka otomatis sesudah misi dikirim", "Terpenuhi"],
       ["RF-23", "DASHBOARD menampilkan <b>koordinat sudut MPU</b> robot berjalan "
        "beserta tombol berhenti berukuran besar", "Terpenuhi"],
       ["RF-24", "Auto-simpan log <b>menyala sejak aplikasi dibuka</b> (tanpa perlu "
        "dinyalakan operator)", "Terpenuhi"],
       ["RF-25", "Berkas log lebih tua dari <b>3 hari dihapus otomatis</b> agar kartu "
        "SD Raspberry Pi tidak penuh", "Terpenuhi"]],
      [1.7 * cm, 10.3 * cm, 3 * cm])
h2("3.2 Kebutuhan Non-Fungsional")
bullets([
    "<b>Keterandalan:</b> heartbeat PING tiap 0,5 s menjaga failsafe robot (stop &lt; 3 s bila sinyal hilang).",
    "<b>Portabilitas:</b> berjalan di Raspberry Pi (NRF real) &amp; PC; mode SIMULASI "
    "tidak menuntut pustaka perangkat keras apa pun.",
    "<b>Keselamatan operasi:</b> aplikasi selalu terbuka di mode SIMULASI sehingga robot "
    "tidak pernah bergerak tanpa keputusan sadar operator; perpindahan mode ditolak "
    "selagi ada perintah berjalan.",
    "<b>Ketahanan catatan:</b> auto-simpan menulis tiap baris log begitu terjadi, "
    "sehingga data uji lapangan tidak hilang bila aplikasi ditutup paksa atau daya mati.",
    "<b>Hemat penyimpanan:</b> log MPU menulis sekitar satu baris per detik, maka "
    "berkas berumur lebih dari 3 hari dibuang otomatis &mdash; kartu SD Raspberry Pi "
    "tidak menggelembung walau alat dipakai berhari-hari.",
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
      [["feeder_gui.py", "Presentasi: halaman bergaya ATM, papan angka layar, kanvas "
        "preview jalur, tombol, gauge, LED, tampilan log."],
       ["feeder_core.py -&gt; RobotCommand",
        "Satu paket Sinyal Kendali &quot;[Moves]:[Dist]&quot; + validasi rentang "
        "sesuai tabel perintah dokumen spesifikasi."],
       ["feeder_core.py -&gt; plan_coverage / plan_command_queue",
        "Terjemahkan tambak + titik awal + lebar lintasan -&gt; daftar segmen "
        "&quot;maju/belok&quot; -&gt; ANTREAN perintah FW/CW/CCW."],
       ["feeder_core.py -&gt; RadioLink",
        "Abstraksi NRF24 (pyrf24) dan MockRadio (simulasi) yang dapat DIPINDAH saat "
        "berjalan lewat set_mode(); merutekan sinyal balik ON/FIN dan telemetri MPU."],
       ["feeder_core.py -&gt; CommandRunner",
        "Pelaksana pola Request-Response: kirim perintah, tunggu ON (kirim ulang bila "
        "lewat 1 detik), tunggu FIN, lanjut perintah berikutnya."],
       ["feeder_core.py -&gt; ActivityLogger",
        "Pencatatan aktivitas berstempel waktu, ekspor CSV/TXT, dan auto-simpan tiap "
        "baris ke berkas TXT."],
       ["feeder_core.py -&gt; MPUMonitor",
        "Mengambil sudut MPU dari telemetri NRF di latar belakang, menyaring paket "
        "kembar, dan mencatatnya ke log bila saklar Log MPU menyala."]],
      [5.6 * cm, 9.4 * cm])
h2("4.2 Protokol Sinyal Kendali (mengikuti Dokumen Spesifikasi Teknis)")
p("Protokol mengikuti bab <b>Skema Komunikasi</b> pada <i>Dokumen Spesifikasi Teknis "
  "&mdash; Robot Akuatik untuk Tambak Ikan</i>, yang mengadopsi skema <b>DJI Tello "
  "SDK 2.0</b>. Sinyal Kendali <b>selalu diinisiasi Pengendali Utama</b>; Body Robot "
  "memberi respon. Setiap perintah dihitung sebagai satu paket komunikasi dengan pola "
  "<b>Request-Response</b>.")
table(["Paket", "Arah", "Makna"],
      [["[Moves]:[Dist]", "Pi -&gt; Robot",
        "Perintah gerak. Contoh &quot;FW:100&quot; = maju lurus 100 cm; "
        "&quot;CCW:90&quot; = berputar berlawanan jarum jam 90&deg;."],
       ["ON [Moves]", "Robot -&gt; Pi",
        "Dikirim berkali-kali dengan jeda 1 detik SELAMA gerakan berlangsung, agar "
        "Pengendali Utama tahu perintah sedang dijalankan."],
       ["FIN [Moves]:[Dist]", "Robot -&gt; Pi",
        "Gerakan selesai dieksekusi dengan baik. Menjadi izin bagi Pengendali Utama "
        "untuk mengirim perintah berikutnya."],
       ["PING", "Pi -&gt; Robot",
        "Heartbeat (jaga failsafe robot) tiap 0,5 s + pemicu giliran bicara robot"],
       ["(ACK otomatis)", "Robot -&gt; Pi",
        "Auto-ACK NRF; True = robot hidup &amp; terjangkau"],
       ["R=&lt;roll&gt;;P=&lt;pitch&gt;;Y=&lt;yaw&gt;", "Robot -&gt; Pi",
        "Telemetri MPU (tambahan di luar spesifikasi wajib) — alamat balik 00002, NOACK"]],
      [4.6 * cm, 2.6 * cm, 7.8 * cm])
p("<b>Daftar perintah</b> beserta rentang [Dist] yang sah (tabel perintah pada dokumen "
  "spesifikasi). GUI menolak nilai di luar rentang ini sebelum paket dikirim, dan "
  "firmware memvalidasinya sekali lagi saat paket diterima:")
table(["No", "Moves", "Dist Range", "Deskripsi"],
      [["1", "FW", "10&ndash;200", "Maju lurus ke depan (satuan sentimeter)"],
       ["2", "CW", "1&ndash;180",
        "Berputar searah jarum jam / ke kanan (satuan derajat)"],
       ["3", "CCW", "1&ndash;180",
        "Berputar berlawanan arah jarum jam / ke kiri (satuan derajat)"],
       ["4", "STOP", "0",
        "Menghentikan motor. Digunakan untuk berhenti secara darurat."]],
      [1.2 * cm, 2 * cm, 2.6 * cm, 9.2 * cm])
p("<b>Penanganan kegagalan.</b> Bila Pengendali Utama tidak menerima "
  "<b>ON [Moves]</b> dalam <b>1 detik</b>, perintah dianggap gagal dijalankan dan "
  "<b>dikirim ulang</b> (hingga 5 percobaan). Agar paket kiriman ulang tidak menjadi "
  "gerakan ganda, robot mengabaikan perintah gerak baru selama masih ada gerakan "
  "berjalan &mdash; kecuali STOP, yang selalu dilayani seketika.")
code("Pi  ->  FW:200                      (kirim perintah)\n"
     "Pi  <-  ON FW                       (< 1 detik, kalau tidak -> kirim ulang)\n"
     "Pi  <-  ON FW                       (berulang tiap 1 detik selama bergerak)\n"
     "Pi  <-  FIN FW:200                  (gerakan selesai -> lanjut perintah ke-2)")
p("<b>Perubahan peran robot.</b> Pada iterasi sebelumnya robot menerima satu paket misi "
  "(P/L/MODE) lalu menjalankan seluruh pola zigzag sendiri di dalam firmware. Kini "
  "seluruh pola disusun dan dikemudikan <b>Pengendali Utama</b>, sedangkan robot menjadi "
  "<b>eksekutor satu perintah</b> yang melapor lewat ON/FIN. Konsekuensinya kemajuan misi "
  "yang ditampilkan GUI adalah <b>konfirmasi nyata dari robot</b>, bukan lagi perkiraan "
  "berbasis penghitung waktu.")
p("<b>Komunikasi 2 arah half-duplex (&quot;gantian&quot;).</b> NRF24 tidak bisa kirim &amp; "
  "terima bersamaan, jadi kedua sisi bergantian seperti radio HT: Pi mengirim paket "
  "(mode TX) lalu mendengar sejenak (mode RX); robot yang menerima paket sebentar "
  "<i>stopListening</i>, mengirim ON/FIN/telemetri tanpa ACK, lalu <i>startListening</i> "
  "lagi. Window TX yang sangat pendek menjaga perintah tidak terlewat.")
h2("4.3 Dasar Estimasi Telemetri Baling-baling")
p("Robot tidak memiliki sensor RPM, sehingga gauge baling-baling tetap berupa "
  "<b>estimasi</b>. Bedanya dengan iterasi lalu: estimasi kini diturunkan dari "
  "<b>perintah yang sedang benar-benar dijalankan</b> (diketahui dari sinyal ON/FIN), "
  "bukan dari cermin penghitung waktu firmware.")
table(["Perintah berjalan", "PWM kiri", "PWM kanan", "Alasan"],
      [["FW", "CRUISE", "CRUISE", "Kedua motor maju"],
       ["CW (kanan)", "CRUISE", "STOP", "Differential thrust ke kanan"],
       ["CCW (kiri)", "STOP", "CRUISE", "Differential thrust ke kiri"],
       ["tidak ada / STOP", "STOP", "STOP", "Motor diam"]],
      [3.6 * cm, 2.6 * cm, 2.6 * cm, 6.2 * cm])
code("throttle = (PWM - 1000) / (2000 - 1000)\n"
     "RPM_est  = throttle * MOTOR_KV * BATTERY_V     (default KV=2200, V=11.1)\n"
     "speed_est= ROBOT_SPEED_MPS * throttle / throttle(CRUISE_PWM)")
note("Konstanta MOTOR_KV, BATTERY_V, CRUISE_PWM, dan ROBOT_SPEED_MPS wajib disamakan "
     "dengan firmware &amp; dikalibrasi pada pengujian air agar estimasi mendekati kenyataan.")
h2("4.4 Integrasi Data MPU6050 (lewat Telemetri Radio, tanpa Port Serial)")
p("Data orientasi diambil <b>langsung dari sensor MPU6050</b> (bukan estimasi). Pada "
  "iterasi ini jalur <b>serial USB dihapus</b>: menuntut operator memilih port "
  "(<i>/dev/ttyUSB0</i>, <i>COM11</i>, &hellip;) hanya masuk akal saat board tertambat "
  "kabel di meja, padahal robot bekerja mengapung. Sudut kini <b>dikirim robot sendiri</b> "
  "menumpang telemetri balik NRF setiap kali Pengendali Utama mengirim PING, sehingga "
  "mengalir di <b>latar belakang</b> selama heartbeat hidup — tanpa satu pun pengaturan "
  "di layar.")
code("Robot --(NRF, alamat 00002)--&gt; RadioLink.pump() --&gt; get_telemetry()\n"
     "                                          |\n"
     "                                    MPUMonitor.poll() --&gt; tampilan + log")
p("Format yang di-parse: <b>R=&lt;roll&gt;;P=&lt;pitch&gt;;Y=&lt;yaw&gt;</b>. Kelas "
  "<b>MPUMonitor</b> menyimpan cuplikan terakhir beserta sumber &amp; umurnya, "
  "<b>menyaring paket kembar</b> (poll dipanggil jauh lebih sering daripada laju "
  "telemetri, jadi paket yang sama akan terlihat berkali-kali), lalu mencatat satu baris "
  "per detik ke <b>ActivityLogger</b> bila saklar <b>Log MPU</b> dinyalakan operator. "
  "Karena pencatatan berada di lapisan core — bukan di halaman SENSOR — log tetap "
  "berjalan walau operator sedang membuka halaman lain, dan ikut tersimpan ke berkas TXT "
  "bila auto-simpan menyala.")
note("Konsekuensinya <b>pyserial tidak lagi menjadi dependensi</b>, dan halaman SENSOR "
     "kehilangan kolom port beserta tombol Hubungkan/Putus — satu bidang input yang "
     "hilang, satu sumber kesalahan operator yang hilang pula.")

h2("4.5 Mode Kerja REAL / SIMULASI sebagai Pilihan Operator")
p("Sebelumnya mode ditentukan <b>otomatis</b>: bila pyrf24 ada dipakai NRF nyata, bila "
  "tidak jatuh ke simulasi. Perilaku itu membuat operator tidak pernah memutuskan apa pun "
  "— padahal di Raspberry Pi hasilnya <b>selalu REAL</b>, sehingga latihan atau demo di "
  "darat berisiko benar-benar menggerakkan motor. Kini mode menjadi <b>pilihan sadar</b>:")
bullets([
    "<b>Keadaan awal selalu SIMULASI</b> (robot virtual) di perangkat mana pun.",
    "Tombol <b>MODE</b> di bilah status atas — terlihat dari semua halaman — "
    "memindahkan mode dengan satu sentuhan; pemilih <b>MODE KERJA</b> di halaman SISTEM "
    "melakukan hal yang sama dan keduanya selalu sinkron.",
    "Flag <b>--real</b> tersedia bagi pemakaian rutin di lapangan agar tidak perlu "
    "menyentuh apa pun setelah aplikasi terbuka.",
    "<b>RadioLink.set_mode()</b> melepas radio lama, membersihkan sisa ON/FIN &amp; "
    "telemetri, lalu memasang lawan bicara baru — sehingga data antar-mode tidak "
    "tercampur.",
    "Bila REAL diminta tetapi pyrf24/NRF tidak tersedia, sistem kembali ke SIMULASI dan "
    "<b>melaporkan sebabnya</b> lewat dialog dan log (tidak diam-diam).",
    "Perpindahan mode <b>ditolak selagi ada perintah berjalan</b>; operator diminta "
    "menekan STOP dahulu agar robot tidak ditinggalkan bergerak tanpa pengendali.",
])

h2("4.6 Pencatatan Aktivitas &amp; Auto-Simpan TXT")
p("Ekspor CSV/TXT hanya menyimpan <b>saat tombol ditekan</b>, sehingga catatan uji "
  "lapangan bisa lenyap bila aplikasi ditutup paksa atau Raspberry Pi kehilangan daya. "
  "Karena itu <b>ActivityLogger</b> dilengkapi <b>auto-simpan</b>: saklar pada halaman LOG "
  "membuat berkas <b>logs/log_feeder_&lt;tanggal&gt;_&lt;jam&gt;.txt</b>, menuliskan "
  "catatan yang sudah ada, lalu menulis <b>tiap baris baru begitu terjadi</b>. Berkas "
  "dibuka mode <i>append</i> dan ditutup setiap baris supaya isinya benar-benar sudah "
  "berada di kartu SD, bukan menunggu di penyangga memori — biaya yang tak berarti pada "
  "laju sekitar satu baris per detik.")
p("Bila penulisan gagal di tengah operasi (kartu penuh, media hanya-baca), auto-simpan "
  "dimatikan sendiri dengan sebabnya disimpan; GUI menarik keadaan itu tiap tick lalu "
  "mengembalikan saklar ke posisi mati dan menampilkan alasannya — sehingga tidak ada "
  "layar yang mengaku &apos;aktif&apos; padahal tidak ada yang tersimpan.")
p("<b>Menyala sejak start &amp; membersihkan diri.</b> Menuruti arahan pembimbing, "
  "pencatatan tidak lagi menunggu ditekan: begitu aplikasi dibuka, auto-simpan TXT dan "
  "log MPU langsung aktif, sehingga setiap uji lapangan pasti meninggalkan berkas. "
  "Konsekuensinya folder log tumbuh terus &mdash; log MPU saja menulis sekitar satu baris "
  "per detik &mdash; maka <b>purge_old_logs()</b> membuang berkas yang lebih tua dari "
  "<b>LOG_RETENTION_DAYS = 3 hari</b> saat aplikasi dibuka dan mengulangnya tiap 6 jam "
  "selagi aplikasi hidup. Berkas yang <i>sedang</i> ditulis selalu dikecualikan, sehingga "
  "sesi berjalan tidak mungkin ikut terhapus walau jam sistem Raspberry Pi melompat "
  "(kejadian lumrah pada papan tanpa RTC).")
code("start aplikasi\n"
     "   -> purge_old_logs(): hapus logs/*.txt umur &gt; 3 hari\n"
     "   -> set_autosave(logs/log_feeder_&lt;tgl&gt;_&lt;jam&gt;.txt)\n"
     "   -> MPUMonitor.set_logging(True)\n"
     "   -> ulangi pemeriksaan retensi tiap 6 jam")

h2("4.7 Perencanaan Jalur &amp; Penyusunan Antrean Perintah")
p("Fungsi <b>plan_coverage()</b> menerjemahkan tambak persegi menjadi jalur sapuan "
  "<i>boustrophedon</i> (zigzag). Dari masukan pengguna &mdash; panjang, lebar, "
  "<b>lebar lintasan</b>, <b>kecepatan</b>, dan <b>titik awal</b> (sudut tambak) &mdash; "
  "dihitung titik-titik belok (waypoint), lalu diturunkan menjadi daftar langkah "
  "eksplisit &quot;maju x meter&quot; dan &quot;belok kanan/kiri y&deg;&quot;.")
p("Selanjutnya <b>plan_command_queue()</b> mengubah daftar langkah itu menjadi "
  "<b>antrean paket Sinyal Kendali</b>. Karena rentang FW dibatasi 10&ndash;200 cm, "
  "lintasan panjang otomatis <b>dipecah rata</b> menjadi beberapa perintah FW "
  "berurutan &mdash; pembagian dibuat rata agar tidak menyisakan potongan di bawah "
  "batas minimum (mis. 10,05 m menjadi 6&times;167 cm, bukan 5&times;200 cm + sisa 5 cm "
  "yang tak bisa diperintahkan). Belok kanan menjadi <b>CW</b>, belok kiri menjadi "
  "<b>CCW</b>.")
p("Koordinat: sumbu-x menyusuri lebar, sumbu-y menyusuri panjang. Robot menjelajah "
  "lurus arah-y tiap lintasan, lalu U-turn menggeser sejauh satu lebar lintasan arah-x.")
code("Contoh: tambak 10 x 4 m, lebar lintasan 1 m, mulai Kiri-Bawah -> 4 lintasan\n"
     "\n"
     "  Langkah jalur                  Antrean perintah kendali (29 paket)\n"
     "  1. Maju 10.0 m           ->    FW:200  FW:200  FW:200  FW:200  FW:200\n"
     "  2. Belok kanan 90        ->    CW:90\n"
     "  3. Maju 1.0 m            ->    FW:100\n"
     "  4. Belok kanan 90        ->    CW:90\n"
     "  5. Maju 10.0 m           ->    FW:200 x5\n"
     "  6. Belok kiri 90         ->    CCW:90\n"
     "  ...                            (dst hingga seluruh lebar tersapu)")
p("<b>Pola belok berselang-seling.</b> U-turn yang <b>selalu belok kanan</b> secara "
  "geometri menggeser robot ke kanan lalu ke kiri bergantian, sehingga robot hanya "
  "bolak-balik di dua kolom dan <b>tidak menyapu seluruh lebar tambak</b>. Arah U-turn "
  "karena itu dibuat <b>berselang-seling</b> (kanan-kanan, lalu kiri-kiri, dst) sehingga "
  "geseran selalu ke sisi yang sama. Karena antrean perintah dihitung dari jalur yang "
  "sama dengan yang digambar di layar, <b>preview jalur = gerak nyata robot</b>.")
note("Titik awal dapat dipilih lewat menu atau <b>disentuh langsung pada kanvas peta</b>; "
     "arah belok pertama dihitung dari titik awal agar robot menyapu ke arah dalam tambak.")

h2("4.8 Rancangan Antarmuka: Alur Kerja, Bukan Menu")
p("Menindaklanjuti umpan balik pembimbing (dua putaran evaluasi), tata letak dirancang "
  "ulang agar "
  "<b>mengikuti ukuran layar perangkat</b> dan nyaman disentuh pada "
  "<b>layar sentuh 7 inci</b> (800 &times; 480 piksel) &mdash; dengan gaya "
  "<b>mesin ATM</b>: minimalis, target sentuh besar, satu layar untuk satu tugas, "
  "namun <b>seluruh fitur dipertahankan</b>.")
bullets([
    "<b>Fullscreen adaptif.</b> Jendela mengambil resolusi layar perangkat "
    "(<i>winfo_screenwidth/height</i>) dan berjalan tanpa bilah judul. Ukuran huruf, "
    "tinggi tombol, dan jarak antar elemen dikalikan faktor skala "
    "<i>S = min(lebar/800, tinggi/480)</i> yang dijepit pada rentang 0,85&ndash;2,0 "
    "sehingga tampilan tetap proporsional di layar 7 inci maupun monitor besar.",
    "<b>Dari menu enam tombol menjadi alur.</b> Iterasi sebelumnya memakai bilah "
    "navigasi berisi enam halaman. Umpan balik pembimbing: operator tidak perlu memilih "
    "&quot;mau ke halaman mana&quot; &mdash; ia hanya punya dua urusan, yaitu "
    "<b>menjalankan misi</b> atau <b>mengatur alat</b>. Bilah navigasi karena itu "
    "DIHAPUS: beranda menyisakan dua tombol besar (MISI &amp; SETTING), dan "
    "<b>DASHBOARD terbuka sendiri</b> begitu misi dikirim karena itulah yang ingin "
    "dilihat operator pada saat itu.",
    "<b>Tidak ada fitur yang hilang.</b> Halaman MANUAL, LOG, dan SISTEM berkumpul "
    "sebagai tiga sub-halaman SETTING yang dipilih lewat satu pemilih segmen; halaman "
    "SENSOR melebur ke DASHBOARD karena isinya memang untuk dipantau saat robot bergerak.",
    "<b>Satu jalan pulang.</b> Tombol &lsquo;&lsaquo;&rsquo; di kiri bilah status "
    "menggantikan seluruh bilah navigasi &mdash; disembunyikan di BERANDA karena di "
    "sana tidak ada tempat untuk kembali.",
    "<b>Tombol STOP permanen.</b> Berhenti darurat diletakkan di bilah status atas "
    "sehingga <b>selalu terlihat dan terjangkau dari halaman mana pun</b>.",
    "<b>Papan angka sebagai lapisan penuh.</b> Menyentuh sebuah kolom membuka papan "
    "angka satu layar penuh dengan tombol besar dan tombol OK / HAPUS / BATAL, "
    "sehingga halaman tetap lega tanpa kehilangan kemampuan input tanpa keyboard.",
])
code("BERANDA              MISI                    DASHBOARD (berjalan)\n"
     "+-----------+  -&gt;  +---------------+  -&gt;  +-------------------+\n"
     "|   MISI    |      | ukuran tambak |      | status + progres  |\n"
     "+-----------+      | preview jalur |      | sudut MPU (real)  |\n"
     "|  SETTING  |      | [KIRIM MISI]  |      | [ HENTIKAN/STOP ] |\n"
     "+-----------+      +---------------+      +-------------------+\n"
     "\n"
     "+--------------------------------------------------+\n"
     "| [&lt;]  judul   [MODE*][NRF][ROBOT]      [ STOP ]   |  bilah status\n"
     "+--------------------------------------------------+\n"
     "|                  ISI HALAMAN                     |\n"
     "+--------------------------------------------------+\n"
     "   * chip MODE dapat disentuh: REAL &lt;-&gt; SIMULASI")
table(["Halaman", "Isi"],
      [["BERANDA", "Dua tombol besar: <b>MISI</b> dan <b>SETTING</b>. Selagi ada misi "
        "berjalan muncul jalan pintas <b>LIHAT DASHBOARD</b>."],
       ["MISI", "Panjang, lebar, lebar lintasan, kecepatan, titik awal; preview jalur "
        "pada kanvas; daftar antrean perintah; tombol KIRIM MISI (&rarr; DASHBOARD)."],
       ["DASHBOARD", "Terbuka otomatis sesudah misi/perintah dikirim: status &amp; "
        "perintah berjalan, kemajuan antrean + sisa waktu, <b>koordinat sudut MPU "
        "(Roll/Pitch/Yaw)</b> yang dikirim robot, gauge baling-baling (estimasi), "
        "tombol HENTIKAN (STOP) berukuran besar, dan tombol kembali ke BERANDA."],
       ["SETTING &rsaquo; SISTEM",
        "Saklar komponen (NRF, Heartbeat, Motor), indikator monitor, pemilih "
        "<b>MODE KERJA</b> (SIMULASI/REAL), status log &amp; auto-simpan, informasi "
        "layar, dan tombol keluar."],
       ["SETTING &rsaquo; MANUAL",
        "Maju dalam <b>meter</b> + putar kiri/kanan dalam derajat: nilai besar, tombol "
        "&minus;/+, papan angka, penunjuk jumlah paket FW, dan tombol KIRIM per "
        "perintah (&rarr; DASHBOARD)."],
       ["SETTING &rsaquo; LOG",
        "Catatan aktivitas realtime, saklar <b>Auto-simpan TXT</b> &amp; <b>Log MPU</b> "
        "(keduanya menyala sejak aplikasi dibuka), keterangan retensi 3 hari, serta "
        "Export CSV / Export TXT / Clear."]],
      [3.6 * cm, 11.4 * cm])

# ===================================================================== 5
h1("5. Implementasi Prototipe")
h2("5.1 Fitur GUI")
bullets([
    "<b>Halaman BERANDA:</b> layar pembuka bergaya ATM berisi dua tombol besar "
    "&mdash; MISI dan SETTING &mdash; ditambah jalan pintas LIHAT DASHBOARD yang "
    "hanya muncul selagi ada perintah berjalan.",
    "<b>Halaman DASHBOARD:</b> status robot berukuran besar (SIAP / MENGIRIM PERINTAH / "
    "ROBOT BERGERAK / KIRIM ULANG / SELESAI / DIBATALKAN / GAGAL), paket perintah yang "
    "sedang dijalankan, kemajuan antrean, perkiraan sisa waktu, koordinat sudut MPU "
    "(Roll/Pitch/Yaw), gauge baling-baling, dan tombol HENTIKAN berukuran besar. "
    "Terbuka <b>otomatis</b> sesudah KIRIM MISI atau KIRIM perintah manual.",
    "<b>Halaman MISI:</b> input Panjang, Lebar, Lebar lintasan, Kecepatan (m/s), dan "
    "Titik awal; kanvas preview jalur zigzag berpanah + titik START (sentuh peta = pilih "
    "titik awal); daftar <b>antrean perintah kendali</b> yang akan dikirim beserta "
    "ringkasan (jumlah lintasan, jarak, jumlah perintah, estimasi waktu).",
    "<b>SETTING &rsaquo; MANUAL:</b> tiga kartu besar berisi nilai, tombol &minus;/+, papan "
    "angka, dan tombol KIRIM. Kartu <b>MAJU diisi dalam METER</b> (0,1&ndash;50 m, "
    "menerima pecahan seperti 2,5 m) dan di bawah angkanya tertulis menjadi berapa paket "
    "FW jarak itu dipecah &mdash; operator melihat persis apa yang akan dikirim. Kartu "
    "PUTAR KIRI/KANAN tetap derajat (1&ndash;180) sesuai protokol. Rentang sah "
    "ditampilkan dan divalidasi; nilai di luar rentang ditolak sebelum dikirim.",
    "<b>Papan angka layar penuh:</b> tombol 0&ndash;9, titik, backspace, HAPUS, BATAL, "
    "OK &mdash; muncul saat kolom disentuh; memungkinkan operasi <b>tanpa keyboard "
    "fisik</b> pada layar sentuh.",
    "<b>Status Koneksi:</b> chip MODE (REAL/SIMULASI) yang <b>dapat disentuh untuk "
    "berpindah mode</b>, MODUL NRF, dan ROBOT pada bilah atas &mdash; terlihat di semua "
    "halaman.",
    "<b>Tombol STOP permanen</b> pada bilah atas: mengirim <b>STOP:0</b> dan membatalkan "
    "sisa antrean dari halaman mana pun.",
    "<b>SETTING &rsaquo; LOG:</b> catatan realtime seluruh siklus protokol (KIRIM "
    "&rarr; GERAK &rarr; SELESAI), saklar <b>Auto-simpan TXT</b> dan <b>Log MPU</b> yang "
    "keduanya sudah menyala sejak aplikasi dibuka, nama berkas tujuan, keterangan "
    "retensi 3 hari, serta tombol Export CSV / Export TXT / Clear.",
    "<b>SETTING &rsaquo; SISTEM:</b> saklar NRF TX, Heartbeat PING, dan Motor (efek nyata "
    "lewat STOP); indikator monitor Motor Kiri/Kanan &amp; MPU; pemilih <b>MODE KERJA</b> "
    "REAL/SIMULASI dan saklar robot virtual; ringkasan status log MPU &amp; auto-simpan; "
    "informasi resolusi layar &amp; faktor skala.",
])
h2("5.2 Mode Simulasi")
p("Mode SIMULASI kini menjadi <b>keadaan awal aplikasi</b>, bukan sekadar jaring "
  "pengaman ketika pyrf24 tidak ada: RadioLink dimulai memakai <b>MockRadio</b> dan baru "
  "menyentuh perangkat keras setelah operator memilih REAL. MockRadio <b>meniru perilaku Body Robot secara "
  "penuh</b>: menerima [Moves]:[Dist], membalas &quot;ON [Moves]&quot; tiap 1 detik, lalu "
  "&quot;FIN [Moves]:[Dist]&quot; saat gerakan selesai, dan berhenti seketika saat "
  "menerima STOP. Dengan begitu <b>seluruh alur Request-Response</b> dapat diuji dan "
  "didemokan tanpa perangkat keras &mdash; sangat membantu pada fase evaluasi Prototyping.")
h2("5.3 Tampilan Antarmuka")
p("Seluruh tangkapan layar berikut diambil pada ukuran <b>800 &times; 480 piksel</b>, "
  "yaitu resolusi layar sentuh 7 inci yang dipakai Pengendali Utama.")
figure("gui_beranda.png",
       "Gambar 1. Halaman BERANDA: layar pembuka hanya menawarkan MISI dan SETTING; "
       "jalan pintas LIHAT DASHBOARD muncul karena ada misi yang sedang berjalan.")
figure("gui_misi.png",
       "Gambar 2. Halaman MISI: input dimensi tambak di kiri; preview jalur zigzag dan "
       "daftar antrean perintah kendali (FW/CW/CCW) yang akan dikirim di kanan.")
figure(SCREENSHOT,
       "Gambar 3. Halaman DASHBOARD &mdash; terbuka sendiri sesudah KIRIM MISI: status "
       "dan perintah yang sedang dijalankan, kemajuan antrean, koordinat sudut MPU dari "
       "robot, gauge baling-baling (estimasi), serta tombol HENTIKAN berukuran besar.")
figure("gui_manual.png",
       "Gambar 4. SETTING &rsaquo; MANUAL: maju bersatuan meter, putar kiri/kanan dalam "
       "derajat, penunjuk rentang sah, dan tombol KIRIM per perintah.")
figure("gui_keypad.png",
       "Gambar 5. Papan angka layar penuh &mdash; operasi tanpa keyboard fisik, "
       "lengkap dengan penunjuk rentang nilai yang sah.")
figure("gui_log.png",
       "Gambar 6. SETTING &rsaquo; LOG: seluruh siklus protokol terekam beserta sudut "
       "MPU; auto-simpan TXT dan Log MPU sudah menyala sejak aplikasi dibuka.")
figure("gui_sistem.png",
       "Gambar 7. SETTING &rsaquo; SISTEM: saklar komponen, pemilih MODE KERJA, dan "
       "informasi resolusi layar beserta faktor skala tampilan.")

# ===================================================================== 6
h1("6. Pengujian (Black-Box)")
table(["Uji", "Skenario", "Hasil Diharapkan"],
      [["T-1", "Input P=10 L=4, tekan KIRIM MISI",
        "Antrean 29 perintah tersusun &amp; dijalankan berurutan"],
       ["T-2", "Robot online (ACK) di simulasi",
        "Status ROBOT = TERHUBUNG (hijau)"],
       ["T-3", "Robot offline",
        "Status ROBOT = TERPUTUS (merah) &lt; 3 s"],
       ["T-4", "Matikan saklar Motor",
        "STOP:0 terkirim, antrean batal, LED motor merah"],
       ["T-5", "Input non-angka pada dimensi",
        "Muncul dialog error, misi tidak dikirim"],
       ["T-6", "Tekan Export CSV/TXT",
        "Berkas log tersimpan &amp; berisi seluruh event"],
       ["T-7", "Seluruh perintah tereksekusi",
        "Status = SELESAI setelah FIN perintah terakhir diterima"],
       ["T-8", "Nyalakan saklar Log MPU (tanpa mengatur port apa pun)",
        "Roll/Pitch/Yaw tampil realtime dari telemetri radio; satu baris MPU per detik "
        "masuk log, tanpa baris kembar"],
       ["T-9", "Isi dimensi/lebar lintasan/titik awal",
        "Kanvas &amp; antrean perintah berubah realtime"],
       ["T-10", "Sentuh kolom input lalu pakai papan angka",
        "Nilai kolom terisi tanpa keyboard fisik; preview ikut ter-update"],
       ["T-11", "Ganti titik awal (menu / sentuh kanvas)",
        "Jalur &amp; arah belok pertama berubah sesuai sudut awal"],
       ["T-12", "Kirim FW / CW / CCW dari halaman MANUAL",
        "Satu paket terkirim; status ROBOT BERGERAK lalu SELESAI setelah FIN"],
       ["T-13", "Isi CW = 999 pada papan angka",
        "Ditolak dengan pesan &quot;nilai harus 1&ndash;180 derajat&quot;"],
       ["T-14", "Tekan STOP saat antrean berjalan",
        "STOP:0 terkirim, status DIBATALKAN, sisa antrean tidak dikirim"],
       ["T-15", "Robot tidak membalas ON dalam 1 detik",
        "Status KIRIM ULANG; perintah dikirim ulang hingga 5 percobaan"],
       ["T-16", "Jalankan pada layar beresolusi berbeda",
        "Jendela mengikuti ukuran layar; faktor skala tampil di halaman SISTEM"],
       ["T-17", "Buka aplikasi tanpa argumen apa pun",
        "Chip MODE = SIMULASI; tidak ada paket terkirim ke radio nyata"],
       ["T-18", "Sentuh chip MODE di PC tanpa pyrf24",
        "Muncul pesan sebabnya, mode kembali SIMULASI, chip &amp; pemilih SISTEM tetap "
        "sinkron"],
       ["T-19", "Sentuh chip MODE saat antrean berjalan",
        "Perpindahan ditolak dengan pesan &quot;tekan STOP dulu&quot;"],
       ["T-20", "Isi MAJU = 4,5 m lalu KIRIM",
        "Terpecah menjadi 3 paket FW:150 berurutan; jumlah paket sudah tampil di kartu "
        "sebelum dikirim"],
       ["T-21", "Isi MAJU = 0,05 m",
        "Ditolak: di bawah batas 0,1 m (paket FW terkecil 10 cm)"],
       ["T-22", "Nyalakan Auto-simpan TXT lalu jalankan misi",
        "Berkas logs/log_feeder_*.txt terisi baris demi baris selagi misi berjalan"],
       ["T-23", "Tutup aplikasi paksa saat auto-simpan menyala",
        "Berkas TXT tetap berisi seluruh baris hingga kejadian terakhir"],
       ["T-24", "Buka aplikasi, amati layar pembuka",
        "Hanya dua tombol (MISI, SETTING); tidak ada bilah navigasi"],
       ["T-25", "Tekan KIRIM MISI",
        "Aplikasi berpindah SENDIRI ke DASHBOARD; status &amp; koordinat MPU "
        "berjalan realtime"],
       ["T-26", "Tekan HENTIKAN di DASHBOARD",
        "STOP:0 terkirim, status DIBATALKAN, jalan pintas dashboard di BERANDA hilang"],
       ["T-27", "Taruh berkas log bertanggal 5 hari lalu di folder logs/, buka aplikasi",
        "Berkas terhapus &amp; tercatat di log; berkas sesi berjalan tetap ada"]],
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
     "python receiverArduino.py             # GUI layar penuh (layar sentuh 7\")\n"
     "python receiverArduino.py --windowed  # GUI jendela 800x480 (uji di PC)\n"
     "python receiverArduino.py --real      # langsung memakai NRF sungguhan\n"
     "python receiverArduino.py --cli       # mode teks (opsional)")
p("<b>Mode awal selalu SIMULASI.</b> Untuk mengendalikan robot sungguhan, sentuh chip "
  "<b>MODE</b> di bilah atas, pilih REAL pada <b>SISTEM &rarr; MODE KERJA</b>, atau "
  "jalankan dengan <b>--real</b>.")
p("Pada mode layar penuh, tombol <b>Escape</b> atau <b>F11</b> mengembalikan tampilan ke "
  "mode jendela &mdash; berguna saat pengembangan di PC. Tombol yang sama tersedia pada "
  "halaman SISTEM.")
h2("7.3 Berkas Terkait")
table(["Berkas", "Keterangan"],
      [["receiverArduino.py",
        "ENTRY POINT — jalankan ini -&gt; GUI (opsi --windowed / --cli)"],
       ["feeder_gui.py",
        "Aplikasi GUI (CustomTkinter) — halaman bergaya ATM, mengikuti ukuran layar"],
       ["feeder_core.py",
        "Backend: RobotCommand, RadioLink (REAL/SIMULASI), CommandRunner, path planner, "
        "ActivityLogger (+auto-simpan), MPUMonitor"],
       ["capture_gui.py", "Skrip pengambil screenshot tiap halaman GUI untuk dokumentasi"],
       ["build_docs_pdf.py", "Generator dokumen PDF ini"],
       ["Robot/New/Finalnew/Finalnew.ino",
        "Firmware robot (ESP32) — ditulis ulang sebagai eksekutor perintah "
        "FW/CW/CCW/STOP yang membalas ON &amp; FIN"],
       ["Robot/New/Finalnew/Dokumen Spesifikasi Teknis_Skripsi.docx",
        "Acuan perilaku robot &amp; protokol komunikasi"],
       ["logs/", "Berkas auto-simpan TXT &mdash; dibuat sendiri sejak aplikasi "
        "dibuka; isi &gt; 3 hari dihapus otomatis"]],
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
     "chip MODE menolak berpindah ke REAL di Pi, berarti SPI belum aktif / wiring NRF "
     "salah (cek: ls /dev/spidev*) — sebabnya ditampilkan pada dialog dan log.")

# ===================================================================== 8
h1("8. Kesimpulan & Iterasi Berikutnya")
p("Prototipe GUI berhasil memenuhi seluruh kebutuhan fungsional sesuai lingkup "
  "iterasi ini, dengan pemisahan arsitektur yang bersih dan mode simulasi yang "
  "mempermudah evaluasi. <b>Iterasi ini</b> &mdash; menindaklanjuti umpan balik pembimbing "
  "&mdash; menghasilkan perubahan pokok berikut:")
bullets([
    "<b>Tampilan mengikuti ukuran layar perangkat</b> dan dirancang ulang bergaya mesin "
    "ATM untuk layar sentuh 7 inci: enam halaman bertombol besar, tombol STOP permanen, "
    "dan papan angka layar penuh &mdash; <b>tanpa menghilangkan satu pun fitur</b>.",
    "<b>Perilaku robot mengikuti Dokumen Spesifikasi Teknis</b>: protokol Request-Response "
    "&quot;[Moves]:[Dist]&quot; dengan sinyal balik ON dan FIN, lengkap dengan pengiriman "
    "ulang otomatis bila ON tidak diterima dalam 1 detik.",
    "<b>Pola jalur berpindah ke Pengendali Utama.</b> Robot kini menjadi eksekutor satu "
    "perintah; kemajuan misi yang ditampilkan adalah konfirmasi nyata dari robot, bukan "
    "perkiraan berbasis penghitung waktu.",
    "<b>Kendali manual FW / CW / CCW</b> melengkapi STOP yang sudah ada, dengan validasi "
    "rentang sesuai tabel perintah.",
    "<b>Satuan antarmuka mengikuti cara operator berpikir:</b> perintah maju manual diisi "
    "dalam <b>meter</b> dan dipecah otomatis menjadi paket FW 10&ndash;200 cm, sehingga "
    "protokol tetap utuh tanpa membebani operator menghitung sentimeter.",
    "<b>MPU lepas dari port serial:</b> sudutnya ikut telemetri radio dan mengalir di "
    "latar belakang, dengan saklar <b>Log MPU</b> untuk mencatatnya — satu bidang input "
    "beserta satu dependensi (pyserial) berhasil dihapus.",
    "<b>Mode kerja menjadi keputusan operator:</b> REAL/SIMULASI dapat dipindah kapan saja "
    "lewat chip MODE, dengan SIMULASI sebagai keadaan awal yang aman.",
    "<b>Auto-simpan log ke TXT</b> menyala sejak aplikasi dibuka sehingga catatan uji "
    "lapangan tetap utuh tanpa perlu mengingat menekan tombol Export, sementara berkas "
    "berumur lebih dari 3 hari dibuang sendiri agar kartu SD Raspberry Pi tidak penuh.",
    "<b>Navigasi berubah dari menu menjadi alur:</b> beranda menyisakan MISI dan "
    "SETTING, dan DASHBOARD &mdash; berisi status, koordinat MPU, serta tombol berhenti "
    "&mdash; terbuka sendiri begitu misi dikirim.",
])
p("Sebagai efek samping yang menguntungkan, belokan kini <b>ditutup memakai umpan balik "
  "sudut yaw MPU</b> (bukan durasi tetap), sehingga rencana iterasi sebelumnya soal "
  "penghapusan kalibrasi TURN_90_MS sudah terpenuhi. Sesuai Prototyping Model, "
  "keterbatasan yang tersisa menjadi rencana iterasi selanjutnya:")
bullets([
    "Memasang <b>sensor RPM (hall/encoder)</b> untuk mengganti estimasi dengan data ukur.",
    "Menambah <b>odometri</b> agar jarak FW tidak lagi diturunkan dari waktu tempuh, "
    "sehingga tahan terhadap arus air.",
    "Memperluas <b>isi sinyal balik</b> (status komponen, throttle asli, tegangan baterai) "
    "di atas jalur 2 arah yang sudah ada.",
    "Menambah perintah untuk <b>kontrol komponen individual</b> (motor kiri/kanan, MPU).",
    "Mendukung <b>path waypoint bebas</b> (sentuh banyak titik) selain sapuan persegi.",
    "Kalibrasi konstanta (ROBOT_SPEED_MPS, TURN_RATE_DPS, KV) pada pengujian air.",
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
