# Pilih folder sketch berdasarkan environment PlatformIO.
# Dipanggil sebagai 'pre:' extra_script (lihat platformio.ini).
#   -e esp32dev -> Master Code/New/Finalnew  (produksi: radio + MPU + ESC)
#   -e movetest -> Master Code/New/MoveTest   (tes gerak: tanpa radio)
#   -e esctest  -> Test Part/Motor            (tes ESC/motor murni)
Import("env")
import os

SKETCH_DIR_OF_ENV = {
    "esp32dev": ("Master Code", "New", "Finalnew"),
    "movetest": ("Master Code", "New", "MoveTest"),
    "esctest":  ("Test Part", "Motor"),
}

parts = SKETCH_DIR_OF_ENV.get(env["PIOENV"], ("Master Code", "New", "Finalnew"))
src = os.path.join(env["PROJECT_DIR"], *parts)
env.Replace(PROJECT_SRC_DIR=src)
print("[select_sketch] env=%s  ->  PROJECT_SRC_DIR=%s" % (env["PIOENV"], src))
