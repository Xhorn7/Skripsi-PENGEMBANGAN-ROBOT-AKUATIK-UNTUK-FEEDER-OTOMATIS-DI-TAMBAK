# Pilih folder sketch berdasarkan environment PlatformIO.
# Dipanggil sebagai 'pre:' extra_script (lihat platformio.ini).
#   -e esp32dev  -> Master Code/New/Finalnew  (produksi: radio + MPU + ESC)
#   -e movetest  -> Master Code/New/MoveTest   (tes gerak: tanpa radio)
Import("env")
import os

SKETCH_OF_ENV = {
    "esp32dev": "Finalnew",
    "movetest": "MoveTest",
    "esctest":  "EscTest",
}

name = SKETCH_OF_ENV.get(env["PIOENV"], "Finalnew")
src = os.path.join(env["PROJECT_DIR"], "Master Code", "New", name)
env.Replace(PROJECT_SRC_DIR=src)
print("[select_sketch] env=%s  ->  PROJECT_SRC_DIR=%s" % (env["PIOENV"], src))
