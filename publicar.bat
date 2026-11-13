@echo off
REM ===== Publica la app: cada push a main se despliega solo en Vercel =====
cd /d "%~dp0"
git push
echo.
echo Vercel publicara la nueva version en 1-2 minutos: https://sayariy-grill.vercel.app
pause
