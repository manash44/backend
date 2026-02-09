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
echo  2. Run App (Internet Access / ngrok)
echo     - Generates a public URL accessible from anywhere
echo     - Requires ngrok authtoken
echo.
echo  3. Development Mode
echo     - Starts Backend + Frontend Dev Server (Vite)
echo     - Use this for coding changes
echo.
echo  4. Rebuild Frontend
echo     - Compiles the React app into static files 
echo     - Run this if you changed frontend code and want to run Option 1/2
echo.
echo  5. Fix/Update Dependencies
echo     - Re-installs yt-dlp and other requirements
echo     - Run this if you see import errors
echo.
echo  0. Exit
echo.
set /p choice="Select an option [0-5]: "

if "%choice%"=="1" goto RUN_LOCAL
if "%choice%"=="2" goto RUN_INTERNET
if "%choice%"=="3" goto RUN_DEV
if "%choice%"=="4" goto BUILD_FRONTEND
if "%choice%"=="5" goto FIX_DEPS
if "%choice%"=="0" exit
goto MENU

:RUN_LOCAL
cls
echo Starting Local Server...
echo Use Ctrl+C to stop.
echo.
py -3.13 app.py
pause
goto MENU

:RUN_INTERNET
cls
echo Starting Server with Internet Access...
echo Use Ctrl+C to stop.
echo.
py -3.13 app.py --ngrok
pause
goto MENU

:RUN_DEV
cls
echo Starting Development Services...
echo.
echo [1/2] Starting Backend (New Window)...
start "VidGetNow Backend" cmd /c "cd /d "%~dp0" && py -3.13 app.py"
echo.
echo [2/2] Starting Frontend Dev Server...
cd frontend
call npm run dev
cd ..
goto MENU

:BUILD_FRONTEND
cls
echo Building Frontend...
cd frontend
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
cd ..
goto MENU

:FIX_DEPS
cls
echo Updating Dependencies...
echo.
echo [1/3] Uploading Pip...
py -3.13 -m pip install --upgrade pip
echo.
echo [2/3] Installing/Updating core requirements...
py -3.13 -m pip install -U flask flask-cors pyngrok curl-cffi
echo.
echo [3/3] Installing latest yt-dlp (Master Branch)...
py -3.13 -m pip install -U --force-reinstall https://github.com/yt-dlp/yt-dlp/archive/master.zip
echo.
echo [SUCCESS] Dependencies updated!
pause
goto MENU
