@echo off
REM FocusFlow Service Uninstallation Script

setlocal EnableDelayedExpansion

set "INSTALL_PATH=%~1"
if "%INSTALL_PATH%"=="" set "INSTALL_PATH=%~dp0.."

set "NSSM_PATH=%INSTALL_PATH%\tools\nssm.exe"
set "SERVICE_NAME=FocusFlowGuard"

echo ============================================
echo Stopping and removing FocusFlow Guardian...
echo ============================================

REM Stop any running processes first
taskkill /F /IM FocusFlow.exe 2>nul
taskkill /F /IM FocusFlowGuard.exe 2>nul

REM Try NSSM method first
if exist "%NSSM_PATH%" (
    echo Using NSSM for service removal...
    "%NSSM_PATH%" stop "%SERVICE_NAME%" 2>nul
    timeout /t 3 /nobreak >nul
    "%NSSM_PATH%" remove "%SERVICE_NAME%" confirm 2>nul
)

REM Also try native sc command
sc stop "%SERVICE_NAME%" 2>nul
timeout /t 2 /nobreak >nul
sc delete "%SERVICE_NAME%" 2>nul

REM Remove scheduled task if it exists
schtasks /delete /tn "FocusFlowGuard" /f 2>nul

REM Remove from Windows startup registry (both HKLM and HKCU)
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "FocusFlowGuard" /f 2>nul
reg delete "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "FocusFlowGuard" /f 2>nul
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "FocusFlow" /f 2>nul
reg delete "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "FocusFlow" /f 2>nul

echo.
echo ============================================
echo Service uninstallation completed.
echo ============================================
exit /b 0
