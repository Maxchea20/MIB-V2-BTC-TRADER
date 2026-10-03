@echo off
rem Lock 3 Hunt V3 on every research file. Usage: scripts\run_lock3_all.bat [db ...]
rem Each file gets its own Hunt run first, then the switch on that same Hunt file.
setlocal enabledelayedexpansion
cd /d "%~dp0.."
set DBS=%*
if "%DBS%"=="" set DBS=backend\research_2019_21.db backend\research_2022_25.db backend\research_binance.db
for %%D in (%DBS%) do (
  echo ===== %%D: Hunt =====
  py scripts\backtest_desktop_cfi.py %%D
  set HUNT=
  for /f "delims=" %%F in ('dir /b /ad /o-n results\exp-hunt-desktop-cfi-v1') do if not defined HUNT set HUNT=results\exp-hunt-desktop-cfi-v1\%%F\trades.csv
  echo ===== %%D: Lock 3 switch on !HUNT! =====
  py scripts\backtest_hunt_chop.py %%D !HUNT!
  py scripts\diagnose_hunt_v3.py
)
