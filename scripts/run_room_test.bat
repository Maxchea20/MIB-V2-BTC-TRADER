@echo off
rem One Step 8 variant on one file. Usage: scripts\run_room_test.bat backend\research_binance.db room
rem Variants: room  room-ex  room-block  room-ex-block
setlocal enabledelayedexpansion
cd /d "%~dp0.."
if not exist results\room mkdir results\room
set DB=%1
set V=%2
for %%N in (%DB%) do set NAME=%%~nN
set ARGS=
if "%V%"=="room" set ARGS=room
if "%V%"=="room-ex" set ARGS=room-ex
if "%V%"=="room-block" set ARGS=room room-block
if "%V%"=="room-ex-block" set ARGS=room-ex room-block
set FOLDER=exp-hunt-desktop-cfi-%V%
py scripts\backtest_desktop_cfi.py %DB% %ARGS% > results\room\%NAME%_%V%_hunt.txt
set HUNT=
for /f "delims=" %%F in ('dir /b /ad /o-n results\%FOLDER%') do if not defined HUNT set HUNT=results\%FOLDER%\%%F\trades.csv
py scripts\backtest_hunt_chop.py %DB% !HUNT! > results\room\%NAME%_%V%_switch.txt
echo.
py scripts\summarize_room.py %NAME% %V%
