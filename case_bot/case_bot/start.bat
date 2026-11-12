@echo off
cd /d "%~dp0"
title case bot

where python >nul 2>&1
if errorlevel 1 (
  echo Python not found. Install it from python.org and check "Add python.exe to PATH".
  pause
  exit /b
)

if exist token.txt goto havetoken
set /p TOKEN=Paste bot token from BotFather and press Enter: 
>token.txt echo %TOKEN%
:havetoken
set /p BOT_TOKEN=<token.txt

echo Installing dependencies...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo Install failed. If you use Python 3.14 or newer, install Python 3.12 or 3.13 and try again.
  pause
  exit /b
)

:run
echo Starting bot...
python bot.py
echo Bot stopped. Restarting in 5 seconds. Close this window to quit.
timeout /t 5 >nul
goto run
