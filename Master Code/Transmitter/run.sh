#!/usr/bin/env bash
# Launcher GUI Feeder untuk Raspberry Pi.
# Aktifkan virtualenv (bila ada) lalu jalankan entry point.
#   ./run.sh          -> buka GUI
#   ./run.sh --cli    -> mode teks lama

cd "$(dirname "$0")" || exit 1

# aktifkan venv bila tersedia (abaikan bila tidak ada)
if [ -f "$HOME/feeder-venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$HOME/feeder-venv/bin/activate"
fi

python3 receiverArduino.py "$@"
