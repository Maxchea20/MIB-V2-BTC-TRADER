@echo off
rem Lock 3 Hunt V3 on every research file. Usage: scripts\run_lock3_all.bat [db ...]
rem Full output goes to results\lock3\*.txt. Only a short summary prints.
setlocal enabledelayedexpansion
cd /d "%~dp0.."
if not exist results\lock3 mkdir results\lock3
set DBS=%*
if "%DBS%"=="" set DBS=backend\research_2019_21.db backend\research_2022_25.db backend\research_binance.db
for %%D in (%DBS%) do (
  echo running %%~nD ...
  py scripts\backtest_desktop_cfi.py %%D > results\lock3\%%~nD_hunt.txt
  set HUNT=
  for /f "delims=" %%F in ('dir /b /ad /o-n results\exp-hunt-desktop-cfi-v1') do if not defined HUNT set HUNT=results\exp-hunt-desktop-cfi-v1\%%F\trades.csv
  py scripts\backtest_hunt_chop.py %%D !HUNT! > results\lock3\%%~nD_switch.txt
)
echo.
py scripts\summarize_lock3.py
