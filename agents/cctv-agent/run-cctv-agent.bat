@echo off
rem STLIX CCTV agent — double-click on the factory PC. Keeps running; close the window to stop.
cd /d "%~dp0"
if not exist config.json (
  echo config.json مش موجود — انسخ config.example.json لـ config.json وحط IP وباسورد كل DVR
  pause & exit /b 1
)
python -c "import requests" 2>nul || pip install requests
:loop
python agent.py config.json
echo agent stopped — restarting in 15s
timeout /t 15 >nul
goto loop
