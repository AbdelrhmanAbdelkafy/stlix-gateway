@echo off
rem STLIX Gateway - deploy wrapper.
rem Windows blocks .ps1 files by default (execution policy). A .bat is not
rem blocked, and Bypass below is scoped to this single process - it changes
rem no setting on the machine. All arguments pass through to deploy.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy.ps1" %*
