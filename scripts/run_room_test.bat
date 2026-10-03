@echo off
rem Step 8 room-to-run test. Usage: scripts\run_room_test.bat backend\research_2022_25.db
rem Four variants, each with the Lock 3 switch on its own Hunt file. Short summary prints at the end.
setlocal enabledelayedexpansion
cd /d "%~dp0.."
if not exist results\room mkdir results\room
set DB=%1
for %%N in (%DB%) do set NAME=%%~nN
for %%V in (room room-ex room-block room-ex-block) do (
  echo running %NAME% %%V ...
  set ARGS=
  set FOLDER=exp-hunt-desktop-cfi-%%V
  if "%%V"=="room" set ARGS=room
  if "%%V"=="room-ex" set ARGS=room-ex
  if "%%V"=="room-block" set ARGS=room room-block
  if "%%V"=="room-ex-block" set ARGS=room-ex room-block
  py scripts\backtest_desktop_cfi.py %DB% !ARGS! > results\room\%NAME%_%%V_hunt.txt
  set HUNT=
  for /f "delims=" %%F in ('dir /b /ad /o-n results\!FOLDER!') do if not defined HUNT set HUNT=results\!FOLDER!\%%F\trades.csv
  py scripts\backtest_hunt_chop.py %DB% !HUNT! > results\room\%NAME%_%%V_switch.txt
)
echo.
py scripts\summarize_room.py %NAME%
