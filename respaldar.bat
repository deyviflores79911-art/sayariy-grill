@echo off
REM ===== Copia de seguridad de la base de datos y las fotos =====
cd /d "%~dp0"
if not exist respaldos mkdir respaldos
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set FECHA=%%i
copy db.sqlite3 "respaldos\db_%FECHA%.sqlite3" >nul
powershell -NoProfile -Command "if (Test-Path media) { Compress-Archive -Path media -DestinationPath 'respaldos\fotos_%FECHA%.zip' -Force }"
echo Respaldo guardado en la carpeta respaldos (%FECHA%). Copielo tambien a un USB o Google Drive.
pause
