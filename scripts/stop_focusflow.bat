@echo off
REM FocusFlow Pre-Update Stop Script for PDQ Deployment
REM This script gracefully stops FocusFlow before an update

setlocal EnableDelayedExpansion

echo ============================================
echo FocusFlow Pre-Update Stop Script
echo ============================================

REM Get install path from registry or use default
set "INSTALL_PATH="
for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\FocusFlow" /v InstallPath 2^>nul') do set "INSTALL_PATH=%%b"
if "%INSTALL_PATH%"=="" set "INSTALL_PATH=%ProgramFiles%\FocusFlow"

set "APPDATA_PATH=%APPDATA%\FocusFlow"
set "SIGNAL_FILE=%INSTALL_PATH%\.shutdown_signal"
set "SIGNAL_FILE_APPDATA=%APPDATA_PATH%\.shutdown_signal"

echo Install path: %INSTALL_PATH%
echo AppData path: %APPDATA_PATH%

REM Step 1: Stop the Windows service first
echo.
echo Step 1: Stopping FocusFlowGuard service...
sc stop FocusFlowGuard 2>nul
net stop FocusFlowGuard 2>nul

REM Step 2: Create shutdown signal file (graceful shutdown)
echo.
echo Step 2: Creating shutdown signal for graceful app shutdown...
if not exist "%APPDATA_PATH%" mkdir "%APPDATA_PATH%" 2>nul
echo shutdown > "%SIGNAL_FILE_APPDATA%" 2>nul
if exist "%INSTALL_PATH%" (
    echo shutdown > "%SIGNAL_FILE%" 2>nul
)

REM Step 3: Wait for graceful shutdown (max 15 seconds)
echo.
echo Step 3: Waiting for graceful shutdown...
set /a WAIT_COUNT=0
:WAIT_LOOP
tasklist /FI "IMAGENAME eq FocusFlow.exe" 2>NUL | find /I "FocusFlow.exe" >NUL
if errorlevel 1 (
    echo Application shut down gracefully.
    goto :CLEANUP
)
set /a WAIT_COUNT+=1
if %WAIT_COUNT% GEQ 15 (
    echo Graceful shutdown timeout - forcing termination...
    goto :FORCE_KILL
)
timeout /t 1 /nobreak >nul
goto :WAIT_LOOP

:FORCE_KILL
REM Step 4: Force kill if graceful shutdown failed
echo.
echo Step 4: Force terminating any remaining processes...
taskkill /F /IM FocusFlow.exe 2>nul
taskkill /F /IM FocusFlowGuard.exe 2>nul

REM Wait a moment for processes to fully terminate
timeout /t 2 /nobreak >nul

:CLEANUP
REM Step 5: Clean up signal files
echo.
echo Step 5: Cleaning up signal files...
del "%SIGNAL_FILE%" 2>nul
del "%SIGNAL_FILE_APPDATA%" 2>nul

REM Step 6: Release any file locks by waiting
echo.
echo Step 6: Waiting for file locks to release...
timeout /t 2 /nobreak >nul

echo.
echo ============================================
echo FocusFlow stopped successfully.
echo Ready for update installation.
echo ============================================

exit /b 0
