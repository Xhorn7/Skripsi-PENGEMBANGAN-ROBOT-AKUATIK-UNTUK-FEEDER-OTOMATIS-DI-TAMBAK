@echo off
REM ============================================================
REM  Serial Monitor helper (pakai arduino-cli bawaan Arduino IDE)
REM  Pemakaian:
REM     monitor.bat            -> COM11 @ 115200 (default)
REM     monitor.bat COM7       -> COM7  @ 115200
REM     monitor.bat COM7 9600  -> COM7  @ 9600
REM  Tekan Ctrl+C untuk keluar.
REM ============================================================

set "CLI=C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"

set "PORT=%~1"
if "%PORT%"=="" set "PORT=COM11"

set "BAUD=%~2"
if "%BAUD%"=="" set "BAUD=115200"

echo.
echo === Serial Monitor : %PORT% @ %BAUD% baud ===
echo (Ctrl+C untuk keluar)
echo.

"%CLI%" monitor -p %PORT% -c baudrate=%BAUD%
