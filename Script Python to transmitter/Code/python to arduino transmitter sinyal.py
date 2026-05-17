import serial
import time
import sys
import serial.tools.list_ports as list_ports

# ========== KONFIGURASI PORT DAN KOMUNIKASI ==========
PORT = ''  # Port COM (kosong = auto-deteksi). Contoh: 'COM7'
BAUD = 9600  # Kecepatan komunikasi (baud rate) - harus sama dengan Arduino
HANDSHAKE_MSG = 'INIT\n'  # Pesan inisialisasi yang dikirim ke Arduino
HANDSHAKE_RESPONSES = ('READY', 'OK', 'Data terkirim')  # Respons yang diharapkan dari Arduino
HANDSHAKE_TIMEOUT = 3  # Waktu tunggu respons (detik)
HANDSHAKE_RETRIES = 2  # Jumlah percobaan handshake jika gagal
AUTO_DETECT = True  # Jika True, cari port Arduino otomatis jika PORT kosong


def find_arduino_ports():
    """
    MENCARI PORT ARDUINO YANG TERSEDIA
    
    Fungsi ini:
    - Membaca daftar semua port COM yang terhubung
    - Filter port berdasarkan nama/deskripsi hardware (CH340, FT232, Arduino, dll)
    - Mengembalikan list port yang kemungkinan adalah Arduino
    
    Return:
      list - Daftar port COM yang terdeteksi sebagai Arduino (contoh: ['COM7'])
    """
    arduino_keywords = ('CH340', 'FT232', 'Arduino', 'Atmega', 'USB-SERIAL', 'Silicon Labs')
    ports = list(list_ports.comports())
    candidates = []
    for p in ports:
        desc = p.description.upper() if p.description else ''
        if any(kw in desc for kw in arduino_keywords):
            candidates.append(p.device)
    return candidates


def autodetect_port(baud=BAUD):
    """
    AUTO-DETEKSI PORT ARDUINO DAN KONEKSI
    
    Fungsi ini:
    - Mencari semua port Arduino yang tersedia
    - Mencoba terbuka setiap port
    - Mengirim pesan INIT dan menunggu respons (handshake)
    - Mengembalikan port pertama yang berhasil handshake
    
    Args:
      baud - Kecepatan komunikasi (default: BAUD)
    
    Return:
      tuple (port_name, serial_object) jika sukses, atau (None, None) jika gagal
      Contoh: ('COM7', <Serial object>)
    """
    print('Auto-detecting Arduino port...')
    candidates = find_arduino_ports()
    if not candidates:
        print('No Arduino ports found. Trying all available ports.')
        candidates = [p.device for p in list(list_ports.comports())]
    
    for port in candidates:
        print(f'Trying {port}...')
        ser = open_serial(port=port, baud=baud, timeout=1)
        if not ser:
            continue
        if handshake(ser, timeout=HANDSHAKE_TIMEOUT):
            print(f'Found Arduino on {port}')
            return port, ser
        ser.close()
    
    print('Auto-detect failed: no responding Arduino found.')
    return None, None


def open_serial(port=PORT, baud=BAUD, timeout=1):
    """
    MEMBUKA KONEKSI PORT SERIAL KE ARDUINO
    
    Fungsi ini:
    - Membuka port COM dengan kecepatan dan timeout yang ditentukan
    - Menunggu 2 detik (untuk Arduino auto-reset)
    - Membersihkan buffer input/output
    - Menangani error (PermissionError, SerialException)
    
    Args:
      port - Nama port COM (contoh: 'COM7')
      baud - Kecepatan komunikasi (default: 9600)
      timeout - Waktu tunggu baca data (detik, default: 1)
    
    Return:
      serial.Serial object jika sukses, atau None jika gagal
    """
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=timeout, write_timeout=1)
        # Tunggu Arduino selesai reset setelah membuka port (untuk bootloader)
        time.sleep(2)
        try:
            # Bersihkan sisa data lama di buffer input dan output
            ser.reset_input_buffer()
            ser.reset_output_buffer()
        except Exception:
            pass
        return ser
    except serial.SerialException as e:
        print('Could not open port:', e)
        return None
    except PermissionError as e:
        print('Permission error opening port:', e)
        return None


def handshake(ser, test_msg=HANDSHAKE_MSG, timeout=HANDSHAKE_TIMEOUT):
    """
    HANDSHAKE DENGAN ARDUINO (VERIFIKASI KONEKSI)
    
    Fungsi ini:
    - Mengirim pesan INIT ke Arduino
    - Menunggu respons dari Arduino (READY, OK, Data terkirim, dll)
    - Menggunakan partial match (cocok jika respons mengandung keyword)
    - Timeout jika tidak ada respons dalam waktu yang ditentukan
    
    Args:
      ser - Serial object (hasil dari open_serial)
      test_msg - Pesan handshake yang dikirim (default: 'INIT\n')
      timeout - Waktu tunggu respons (detik, default: 3)
    
    Return:
      bool - True jika handshake sukses, False jika timeout/gagal
    """
    try:
        ser.write(test_msg.encode())
    except Exception as e:
        print('Failed to write handshake:', e)
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            line = ser.readline().decode(errors='ignore').strip()
        except Exception:
            line = ''
        if line:
            print('RX:', line)  # Tampilkan data yang diterima dari Arduino
            # Cek jika respons mengandung salah satu keyword dari HANDSHAKE_RESPONSES
            if any(resp in line for resp in HANDSHAKE_RESPONSES):
                return True
    return False


def main():
    """
    FUNGSI UTAMA - ALUR KOMUNIKASI PYTHON KE ARDUINO
    
    Alur:
    1. Cari/buka port Arduino (PORT spesifik atau auto-deteksi)
    2. Lakukan handshake dengan Arduino (verifikasi koneksi)
    3. Loop: tunggu input pengguna → kirim ke Arduino → tampilkan status
    4. Graceful shutdown saat user tekan Ctrl+C
    """
    # ========== PEMBUKAAN PORT ==========
    if PORT and PORT.strip():
        # Jika PORT sudah ditentukan, coba buka port itu
        print(f'Connecting to {PORT}...')
        ser = open_serial()
        if not ser and AUTO_DETECT:
            # Jika gagal membuka PORT tetapi auto-detect enabled, coba cari Arduino
            print('Fallback: attempting auto-detection.')
            port, ser = autodetect_port()
            if not ser:
                sys.exit(1)
        elif not ser:
            print('Failed to open port and auto-detect is disabled.')
            sys.exit(1)
    else:
        # Jika PORT kosong, langsung auto-deteksi
        print('No PORT specified; auto-detecting...')
        port, ser = autodetect_port()
        if not ser:
            sys.exit(1)

    # ========== HANDSHAKE / VERIFIKASI KONEKSI ==========
    for attempt in range(1, HANDSHAKE_RETRIES + 1):
        print(f'Handshake attempt {attempt}/{HANDSHAKE_RETRIES}...')
        if handshake(ser):
            print('Handshake successful.')
            break
        else:
            print('Handshake failed.')
            if attempt < HANDSHAKE_RETRIES:
                time.sleep(1)
    else:
        # Jika semua percobaan handshake gagal, tutup port dan keluar
        print('Handshake failed after retries. Closing port.')
        ser.close()
        sys.exit(1)

    # ========== LOOP PENGIRIMAN PESAN ==========
    try:
        while True:
            msg = input("Input pesan: ")
            try:
                # Encode input menjadi bytes dan tambah newline
                ser.write((msg + "\n").encode())
                # Flush buffer untuk memastikan data langsung terkirim
                ser.flush()
                print("Terkirim:", msg)
            except Exception as e:
                print('Write error:', e)
    except KeyboardInterrupt:
        # User tekan Ctrl+C untuk keluar
        print('\nExiting.')
    finally:
        # Selalu tutup port saat keluar, error atau tidak
        ser.close()


# ========== ENTRY POINT / TITIK AWAL PROGRAM ==========
if __name__ == '__main__':
    """
    Jalankan main() hanya jika script ini dieksekusi langsung,
    bukan ketika diimpor sebagai modul dari script lain.
    """
    main()