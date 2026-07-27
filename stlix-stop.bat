@echo off
rem Stlix Gateway - stop the server (kills whatever listens on the port).
setlocal
set "PORT=3900"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do taskkill /f /pid %%p >nul 2>&1
echo Stlix Gateway on port %PORT% stopped.
timeout /t 3 >nul
endlocal
