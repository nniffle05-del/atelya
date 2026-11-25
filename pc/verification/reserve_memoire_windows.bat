@echo off
rem Agrandir la reserve de memoire sur disque de Windows pour les tournages Unreal (accord de NT, 25/11/2026).
rem Double-cliquer, puis repondre OUI a la fenetre "Voulez-vous autoriser cette application...". Redemarrer le PC ensuite.
rem Pour revenir en arriere : reserve_memoire_windows.ps1 -Annuler
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0reserve_memoire_windows.ps1"
echo.
echo Si la ligne ci-dessus commence par FAIT : redemarrez le PC quand vous voulez, le reglage prendra effet.
pause
