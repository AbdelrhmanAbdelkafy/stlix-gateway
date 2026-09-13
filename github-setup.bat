@echo off
REM ============================================================
REM  STLIX gateway -> GitHub (private repo)  |  double-click to run
REM  Repo: https://github.com/AbdelrhmanAbdelkafy/stlix-gateway
REM  Rule: secrets never travel (.env / secrets/ are git-ignored)
REM ============================================================
cd /d "%~dp0"
echo.
echo [1/5] git repo
git rev-parse --is-inside-work-tree >nul 2>&1 || git init

echo [2/5] make sure secrets are NOT tracked
git rm --cached -q .env 2>nul
git rm --cached -r -q secrets 2>nul
git rm --cached -q .tmp_hubdata.json 2>nul
git ls-files | findstr /i /c:".env" /c:"secrets/" | findstr /v /i "example" && (
  echo !! a secret file is still tracked - aborting. & pause & exit /b 1
)

echo [3/5] commit
git add -A
git -c user.name="MU" -c user.email="mokafy93@gmail.com" commit -q -m "VPS deploy import (%date%)" 2>nul
git branch -M main

echo [4/5] remote + pull first
git remote remove origin 2>nul
git remote add origin https://github.com/AbdelrhmanAbdelkafy/stlix-gateway.git
REM take anything pushed from elsewhere BEFORE pushing, so the push is never rejected
git pull --rebase origin main

echo [5/5] push  (a GitHub login window may open - sign in as AbdelrhmanAbdelkafy)
git push -u origin main
if errorlevel 1 (
  echo.
  echo !! push failed. Make sure the repo exists (https://github.com/new -> name: stlix-gateway, Private)
  echo    and that you are signed in to GitHub on this PC.
) else (
  echo.
  echo OK - code is on GitHub. Next: run deploy/vps/PASTE-ON-VPS.sh in the Hostinger browser terminal.
)
echo.
pause
