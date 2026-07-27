@echo off
rem =====================================================
rem  Stlix Gateway - one double-click starts everything:
rem    1) stops any older copy holding the port
rem    2) starts the server MINIMIZED (its own window)
rem    3) waits for /health, then opens the platform
rem
rem  ASCII only on purpose: cmd reads the OEM codepage,
rem  Arabic in a .bat shows as mojibake.
rem  Python is launched DIRECTLY (no nested powershell -
rem  security software on this machine kills those).
rem  Port 3900, not 8000: another process owns
rem  127.0.0.1:8000 on this machine and 8080 is in a
rem  Windows excluded range. See RELEASE.md.
rem =====================================================
setlocal
set "ROOT=D:\Nama Code project\stlix-gateway"
set "PORT=3900"

if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo Could not find %ROOT%\.venv\Scripts\python.exe
  echo Edit ROOT at the top of this file if the project moved.
  pause
  exit /b 1
)

rem --- 1) free the port ---------------------------------
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do taskkill /f /pid %%p >nul 2>&1

rem --- 2) start the server, minimized -------------------
start "Stlix Gateway :%PORT%" /min /d "%ROOT%" "%ROOT%\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%

rem --- 3) wait until it answers, then open Chrome -------
echo Starting Stlix Gateway on port %PORT% ...
set /a tries=0
:wait
set /a tries+=1
curl -s -o NUL --max-time 2 http://127.0.0.1:%PORT%/health >nul 2>&1 && goto up
if %tries% geq 30 goto up
timeout /t 1 /nobreak >nul
goto wait
:up
start "" http://127.0.0.1:%PORT%/tools/platform
echo.
echo Server is running in its own minimized window.
echo To stop it: double-click stlix-stop.bat
timeout /t 4 >nul
endlocal
