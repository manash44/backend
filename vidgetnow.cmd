@echo off
cd /d "%~dp0"
title VidGetNow Launcher

:MENU
cls
echo ==========================================
echo        VidGetNow - Video Downloader
echo ==========================================
echo.
echo  1. Run App (Local Network Only)
echo     - Runs standard production server
echo     - Access via http://localhost:5000
echo.
echo  2. Development Mode
echo     - Starts Backend + Frontend Dev Server (Vite)
echo     - Use this for coding changes
echo.
echo  3. Rebuild Frontend
echo     - Compiles the React app into static files 
echo     - Run this if you changed frontend code and want to run Option 1
echo.
echo  4. Fix/Update Dependencies
echo     - Re-installs yt-dlp and other requirements
echo     - Run this if you see import errors
echo.
echo  0. Exit
echo.
set /p choice="Select an option [0-4]: "

if "%choice%"=="1" goto RUN_LOCAL
if "%choice%"=="2" goto RUN_DEV
if "%choice%"=="3" goto BUILD_FRONTEND
if "%choice%"=="4" goto FIX_DEPS
if "%choice%"=="0" exit
goto MENU

:RUN_LOCAL
cls
echo Starting Local Server...
echo Use Ctrl+C to stop.
echo.
py app.py
pause
goto MENU


:RUN_DEV
cls
echo Starting Development Services...
echo.
echo [1/2] Starting Backend (New Window)...
start "VidGetNow Backend" cmd /c "cd /d "%~dp0" && py app.py"
echo.
echo [2/2] Starting Frontend Dev Server...
cd ..\..\vidgrab_frontend-main\vidgrab_frontend-main
call npm run dev
cd "%~dp0"
goto MENU

:BUILD_FRONTEND
cls
echo Building Frontend...
cd ..\..\vidgrab_frontend-main\vidgrab_frontend-main
call npm install
call npm run build
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
) else (
    echo.
    echo [SUCCESS] Frontend built successfully!
    timeout /t 3 >nul
)
cd "%~dp0"
goto MENU

:FIX_DEPS
cls
echo Updating Dependencies...
echo.
echo [1/3] Uploading Pip...
py -m pip install --upgrade pip
echo.
echo [2/3] Installing/Updating core requirements...
py -m pip install -r requirements.txt
echo.
echo [3/3] Installing latest yt-dlp (Master Branch)...
py -m pip install -U --force-reinstall https://github.com/yt-dlp/yt-dlp/archive/master.zip
echo.
echo [SUCCESS] Dependencies updated!
pause
goto MENU
