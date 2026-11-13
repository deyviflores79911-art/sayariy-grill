@echo off
REM ===== Publica en Azure la ultima version guardada en git =====
cd /d "%~dp0"
git push
git archive --format=zip -o "%TEMP%\sayariy-deploy.zip" HEAD
call az webapp deploy -g rg-sayariy-grill -n sayariy-grill --src-path "%TEMP%\sayariy-deploy.zip" --type zip
del "%TEMP%\sayariy-deploy.zip"
echo.
echo Listo: https://sayariy-grill.azurewebsites.net
pause
