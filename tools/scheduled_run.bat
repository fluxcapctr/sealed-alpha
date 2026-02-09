@echo off
REM Pokemon Scraper - Scheduled Daily Run
REM Called by Windows Task Scheduler at midnight

set PROJECT_DIR=c:\Users\Eric\Desktop\ADMIN\CODE-PROJECTS\Mega_Pokemon_Scraper
set VENV_PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe
set LOG_DIR=%PROJECT_DIR%\.tmp

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo [%date% %time%] Starting daily scraper run >> "%LOG_DIR%\scheduled_run.log"

"%VENV_PYTHON%" "%PROJECT_DIR%\tools\run_daily.py" >> "%LOG_DIR%\scheduled_run.log" 2>&1

echo [%date% %time%] Daily scraper run finished (exit code: %ERRORLEVEL%) >> "%LOG_DIR%\scheduled_run.log"
echo. >> "%LOG_DIR%\scheduled_run.log"
