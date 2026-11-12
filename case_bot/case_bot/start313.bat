@echo off
cd /d "%~dp0"
title case bot (python 3.13)

py -3.13 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.13 not found. Install it from python.org and check "Add python.exe to PATH".
  pause
  exit /b
)

if exist token.txt goto havetoken
set /p TOKEN=Paste bot token from BotFather and press Enter: 
>token.txt echo %TOKEN%
:havetoken
set /p BOT_TOKEN=<token.txt
if exist webapp.txt set /p WEBAPP_URL=<webapp.txt

echo Installing dependencies...
py -3.13 -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo Install failed. Check your internet connection and run this file again.
  pause
  exit /b
)

:run
echo Starting bot...
py -3.13 bot.py
echo Bot stopped. Restarting in 5 seconds. Close this window to quit.
timeout /t 5 >nul
goto run
