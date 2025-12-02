@echo off
REM FocusFlow Service Installation Script for PDQ Deployment
REM Starts app in user session with visible tray icon

setlocal EnableDelayedExpansion

set "INSTALL_PATH=%~1"
if "%INSTALL_PATH%"=="" set "INSTALL_PATH=%~dp0.."

set "MAIN_EXE=%INSTALL_PATH%\FocusFlow.exe"
set "GUARD_EXE=%INSTALL_PATH%\FocusFlowGuard.exe"

echo ============================================
echo Installing FocusFlow...
echo Install Path: %INSTALL_PATH%
echo ============================================

REM Create logs directory
if not exist "%INSTALL_PATH%\logs" mkdir "%INSTALL_PATH%\logs"

REM Check if executables exist
if not exist "%MAIN_EXE%" (
    echo ERROR: Main executable not found: %MAIN_EXE%
    exit /b 1
)

REM ============================================
REM STEP 1: Clean up any existing tasks
REM ============================================
echo Removing existing scheduled tasks...
schtasks /delete /tn "FocusFlowGuard" /f 2>nul
schtasks /delete /tn "FocusFlow" /f 2>nul
schtasks /delete /tn "FocusFlowStartup" /f 2>nul
schtasks /delete /tn "FocusFlowLaunchNow" /f 2>nul

REM ============================================
REM STEP 2: Add to registry Run key for future logons
REM ============================================
echo Adding registry startup entries...
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "FocusFlow" /t REG_SZ /d "\"%MAIN_EXE%\"" /f >nul

if exist "%GUARD_EXE%" (
    reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "FocusFlowGuard" /t REG_SZ /d "\"%GUARD_EXE%\"" /f >nul
)

REM ============================================
REM STEP 3: Create scheduled task for logon (backup)
REM ============================================
echo Creating startup task for future logons...
schtasks /create /tn "FocusFlowStartup" /tr "\"%MAIN_EXE%\"" /sc onlogon /rl HIGHEST /f 2>nul

REM ============================================
REM STEP 4: Launch app in EACH logged-in user's session
REM Uses PowerShell to find all explorer.exe processes and launch as those users
REM ============================================
echo Launching FocusFlow in user sessions...

REM Kill any existing Session 0 instance first
taskkill /F /IM FocusFlow.exe 2>nul
timeout /t 1 /nobreak >nul

REM Use PowerShell to launch in each user's session via their explorer.exe
powershell -ExecutionPolicy Bypass -Command ^
  "$users = Get-WmiObject Win32_Process -Filter \"Name='explorer.exe'\" | ForEach-Object { $_.GetOwner().User } | Select-Object -Unique; ^
   foreach ($user in $users) { ^
     Write-Host \"Launching for user: $user\"; ^
     $taskName = 'FocusFlowLaunch_' + $user; ^
     schtasks /create /tn $taskName /tr '\"%MAIN_EXE%\"' /sc once /st 00:00 /f /ru $user 2>$null; ^
     schtasks /run /tn $taskName 2>$null; ^
     Start-Sleep -Seconds 2; ^
     schtasks /delete /tn $taskName /f 2>$null; ^
   }"

REM ============================================
REM STEP 5: Store install info in registry
REM ============================================
reg add "HKLM\SOFTWARE\FocusFlow" /v "InstallPath" /t REG_SZ /d "%INSTALL_PATH%" /f >nul
reg add "HKLM\SOFTWARE\FocusFlow" /v "MainExe" /t REG_SZ /d "%MAIN_EXE%" /f >nul
reg add "HKLM\SOFTWARE\FocusFlow" /v "Version" /t REG_SZ /d "1.0.1" /f >nul

echo.
echo ============================================
echo Installation completed successfully.
echo ============================================
exit /b 0
