@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo       TAP Gestion des Loyers - Demarrage
echo ==============================================
echo.

if not exist "TAP_Gestion_Loyers.exe" (
  echo ERREUR : TAP_Gestion_Loyers.exe est introuvable.
  pause
  exit /b 1
)

if exist "config.json" (
  echo Configuration trouvee.
) else (
  echo AVERTISSEMENT : config.json est introuvable.
)

echo Lancement de l'application...
start "TAP Gestion des Loyers" /wait "TAP_Gestion_Loyers.exe"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo L'application s'est fermee avec le code %EXIT_CODE%.
  echo Consultez error_reports ou contactez l'administrateur.
  pause
)
exit /b %EXIT_CODE%
