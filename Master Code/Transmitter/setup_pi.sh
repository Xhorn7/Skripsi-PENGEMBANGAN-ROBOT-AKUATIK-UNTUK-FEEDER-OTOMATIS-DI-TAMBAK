#!/usr/bin/env bash
# =====================================================================
# setup_pi.sh — Instalasi otomatis GUI Feeder di Raspberry Pi (jalankan 1x)
# Pemakaian:  chmod +x setup_pi.sh && ./setup_pi.sh
# =====================================================================
set -e
cd "$(dirname "$0")"

VENV="$HOME/feeder-venv"

echo "==============================================="
echo "  Setup GUI Feeder Robot Akuatik — Raspberry Pi"
echo "==============================================="

echo "[1/5] Mengaktifkan SPI (untuk NRF24)..."
sudo raspi-config nonint do_spi 0 || echo "  (lewati — set SPI manual bila perlu)"

echo "[2/5] Memasang paket sistem (python3-venv, python3-tk)..."
sudo apt update
sudo apt install -y python3-venv python3-tk

echo "[3/5] Menambahkan user ke grup spi, gpio, dialout..."
sudo usermod -aG spi,gpio,dialout "$USER"

echo "[4/5] Membuat virtualenv (--system-site-packages) di $VENV ..."
if [ ! -d "$VENV" ]; then
    python3 -m venv --system-site-packages "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "[5/5] Memasang dependensi Python..."
pip install --upgrade pip
pip install -r requirements.txt

chmod +x run.sh 2>/dev/null || true

echo ""
echo "==============================================="
echo "  SELESAI."
echo "  PENTING: logout-login sekali agar grup aktif."
echo "  Jalankan GUI:   ./run.sh"
echo "  Mode teks   :   ./run.sh --cli"
echo "==============================================="
