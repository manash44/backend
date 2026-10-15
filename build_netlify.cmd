@echo off
setlocal
cd /d "%~dp0"
title Building for Netlify...

echo ==========================================
echo        VidGetNow Netlify Builder
echo ==========================================
echo.

set "FRONTEND_DIR="
if exist "%~dp0..\..\vidgrab_frontend-main\vidgrab_frontend-main\package.json" (
    set "FRONTEND_DIR=%~dp0..\..\vidgrab_frontend-main\vidgrab_frontend-main"
) else if exist "%~dp0frontend\package.json" (
    set "FRONTEND_DIR=%~dp0frontend"
) else if exist "%~dp0..\frontend\package.json" (
    set "FRONTEND_DIR=%~dp0..\frontend"
)

if "%FRONTEND_DIR%"=="" (
    echo [ERROR] Frontend directory not found!
    pause
    exit /b 1
)

echo  1. Installing Dependencies...
pushd "%FRONTEND_DIR%"
call npm install
if errorlevel 1 (
    echo [ERROR] NPM Install failed.
    popd
    pause
    exit /b 1
)

echo.
echo  2. Building React App...
call npm run build
if errorlevel 1 (
    echo [ERROR] Build failed.
    popd
    pause
    exit /b 1
)

popd

echo.
echo ==========================================
echo        BUILD SUCCESSFUL!
echo ==========================================
echo.
echo  The build is located in:
echo  %FRONTEND_DIR%\dist
echo.
echo  HOW TO DEPLOY TO NETLIFY:
echo  1. Go to https://app.netlify.com/drop
echo  2. Drag and drop the '%FRONTEND_DIR%\dist' folder
echo     into the upload area on that page.
echo.
echo  IMPORTANT:
echo  Once deployed, open Settings in the app to verify
echo  or customize your Backend API URL.
echo.
pause
if exist "%FRONTEND_DIR%\dist" (
    explorer "%FRONTEND_DIR%\dist"
)

