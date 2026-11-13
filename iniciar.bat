@echo off
REM ===== Inicia el POS en la red local (tablets y PCs del restaurante) =====
cd /d "%~dp0"
set DJANGO_DEBUG=0
if not exist .secret_key (
  .venv\Scripts\python -c "import secrets;print(secrets.token_urlsafe(50))" > .secret_key
)
set /p DJANGO_SECRET_KEY=<.secret_key
.venv\Scripts\python manage.py migrate --noinput
.venv\Scripts\python manage.py collectstatic --noinput >nul
echo.
echo  POS listo. En la tablet abra:  http://IP-DE-ESTA-PC:8000
echo  (vea la IP con el comando ipconfig, "Direccion IPv4")
echo  No cierre esta ventana mientras se use el sistema.
echo.
.venv\Scripts\waitress-serve --listen=0.0.0.0:8000 config.wsgi:application
