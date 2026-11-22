@echo off
rem Starts asvz-enroll and writes everything it prints to %USERPROFILE%\asvz.log.
rem Meant to be run by Windows Task Scheduler, see SETUP-GUIDE.md.
rem
rem Usage:  enrol-weekly.bat --lesson-id 777113
rem Any options are passed on to asvz-enroll unchanged.

cd /d "%~dp0.."
set "LOG_FILE=%USERPROFILE%\asvz.log"

rem Where the uv installer puts uv; otherwise rely on PATH.
set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not exist "%UV%" set "UV=uv"

echo ===== %date% %time% =====>>"%LOG_FILE%"
"%UV%" run asvz-enroll %* >>"%LOG_FILE%" 2>&1
