@echo off
cd /d "%~dp0"
echo Starting Nickel&Dime server...
start "Nickel&Dime" cmd /k "python server.py"
echo Waiting for server on http://localhost:5000 ...
powershell -NoProfile -Command "for($i=0;$i -lt 30;$i++){ if (Test-NetConnection localhost -Port 5000 -InformationLevel Quiet){ exit 0 } Start-Sleep -Seconds 1 } exit 1"
if %ERRORLEVEL% EQU 0 (
    start "" "http://localhost:5000/"
) else (
    echo.
    echo Server did not start. Check the 'Nickel&Dime' window for errors.
    pause
)
