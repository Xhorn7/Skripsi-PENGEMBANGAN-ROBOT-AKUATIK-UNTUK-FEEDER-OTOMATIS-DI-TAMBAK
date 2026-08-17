"""
build_raspberry_zip.py — Kemas berkas Pengendali Utama jadi raspberry_feeder.zip
================================================================================

Paket ini yang disalin & diekstrak di Raspberry Pi (lihat README_RASPBERRY.md).
Sebelumnya zip dibuat manual sehingga gampang KETINGGALAN saat kode berubah —
Pi masih menjalankan versi lama padahal repo sudah diperbarui. Skrip ini
membuatnya dapat dibangun ulang kapan saja:

    python build_raspberry_zip.py

Jalankan SESUDAH build_docs_pdf.py bila Dokumentasi_GUI_Feeder_SDLC.pdf ikut
berubah, karena PDF itu disertakan apa adanya ke dalam paket.
"""

import hashlib
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "raspberry_feeder.zip"
ROOT_IN_ZIP = "raspberry_feeder"

# Urutan sengaja disamakan dengan paket lama agar diff-nya mudah dibaca.
FILES = [
    "receiverArduino.py",
    "feeder_gui.py",
    "feeder_core.py",
    "requirements.txt",
    "setup_pi.sh",
    "run.sh",
    "README_RASPBERRY.md",
    "Dokumentasi_GUI_Feeder_SDLC.pdf",
]


def main() -> int:
    missing = [n for n in FILES if not (HERE / n).is_file()]
    if missing:
        print("GAGAL — berkas tidak ditemukan: " + ", ".join(missing))
        return 1

    # ZIP_DEFLATED + tanpa metadata waktu sistem supaya hasilnya stabil.
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            z.write(HERE / name, f"{ROOT_IN_ZIP}/{name}")

    total = 0
    print(f"OK -> {OUT}")
    for info in zipfile.ZipFile(OUT).infolist():
        total += info.file_size
        print(f"  {info.file_size:>8d} B  {info.filename}")
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()[:16]
    print(f"  {total:>8d} B  total isi | zip {OUT.stat().st_size} B | sha256 {digest}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
