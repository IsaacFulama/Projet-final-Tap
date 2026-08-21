@echo off
setlocal
cd /d "%~dp0"

if not exist "TAP_Gestion_Loyers.exe" (
  echo ERREUR : TAP_Gestion_Loyers.exe est introuvable.
  pause
  exit /b 1
)

if not exist "config.json" (
  echo AVERTISSEMENT : config.json est introuvable.
)

start "TAP Gestion des Loyers" /wait "TAP_Gestion_Loyers.exe"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo L'application s'est fermee avec le code %EXIT_CODE%.
  pause
)
exit /b %EXIT_CODE%
