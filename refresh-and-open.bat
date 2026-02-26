@echo off
cd /d "%~dp0"
echo Refreshing prices...
python finance_manager.py
if %ERRORLEVEL% EQU 0 (
    echo Opening dashboard...
    start "" "%~dp0dashboard.html"
) else (
    echo Update failed. Check the message above.
    pause
)
