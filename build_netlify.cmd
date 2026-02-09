@echo off
cd /d "%~dp0"
title Butilding for Netlify...

echo ==========================================
echo        VidGetNow Netlify Builder
echo ==========================================
echo.
echo  1. Installing Dependencies...
cd frontend
call npm install
if errorlevel 1 (
    echo [ERROR] NPM Install failed.
    pause
    exit /b
)

echo.
echo  2. Building React App...
call npm run build
if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b
)

echo.
echo ==========================================
echo        BUILD SUCCESSFUL!
echo ==========================================
echo.
echo  The build is located in:
echo  %~dp0frontend\dist
echo.
echo  HOW TO DEPLOY TO NETLIFY:
echo  1. Go to https://app.netlify.com/drop
echo  2. Drag and drop the 'frontend\dist' folder
echo     into the upload area on that page.
echo.
echo  IMPORTANT:
echo  Once deployed, open the Netlify site settings
echo  in the app (Cog icon) and enter your
echo  Backend URL (e.g., https://xyz.ngrok-free.app)
echo.
pause
explorer "%~dp0frontend"
