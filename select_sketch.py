# Pilih folder sketch berdasarkan environment PlatformIO.
# Dipanggil sebagai 'pre:' extra_script (lihat platformio.ini).
#   -e esp32dev -> Master Code/Robot/New/Finalnew  (produksi: radio + MPU + ESC)
#   -e movetest -> Test Part/MoveTest              (tes gerak: tanpa radio)
#   -e esctest  -> Test Part/EscTest               (tes ESC/motor murni)
#   -e mputest  -> Test Part/MPU Test/mpu          (kalibrasi & cek bus MPU)
#   -e mpudiag  -> Test Part/MpuDiag               (diagnosa I2C tanpa pustaka)
#   -e nrfdiag  -> Test Part/NrfDiag               (diagnosa SPI tanpa pustaka RF24)
#   -e nanotest -> Test Part/MPU Test/mpu          (sketch MPU yg sama, di Nano)
Import("env")
import os

SKETCH_DIR_OF_ENV = {
    "esp32dev": ("Master Code", "Robot", "New", "Finalnew"),
    "movetest": ("Test Part", "MoveTest"),
    "esctest":  ("Test Part", "EscTest"),
    "mputest":  ("Test Part", "MPU Test", "mpu"),
    "mpudiag":  ("Test Part", "MpuDiag"),
    "nrfdiag":  ("Test Part", "NrfDiag"),
    "nanotest": ("Test Part", "MPU Test", "mpu"),
}

parts = SKETCH_DIR_OF_ENV.get(env["PIOENV"], ("Master Code", "Robot", "New", "Finalnew"))
src = os.path.join(env["PROJECT_DIR"], *parts)
env.Replace(PROJECT_SRC_DIR=src)
print("[select_sketch] env=%s  ->  PROJECT_SRC_DIR=%s" % (env["PIOENV"], src))
