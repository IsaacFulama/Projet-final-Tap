@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo       TAP Portail Mobile - Demarrage
echo ==============================================
echo.

if not exist "TAP_Mobile_Server.exe" (
  echo ERREUR : TAP_Mobile_Server.exe est introuvable.
  pause
  exit /b 1
)

echo La configuration reseau et les secrets sont generes automatiquement.
echo.
start "TAP Mobile Server" "TAP_Mobile_Server.exe"
echo Serveur demarre. Le programme principal le lance aussi automatiquement.
pause
