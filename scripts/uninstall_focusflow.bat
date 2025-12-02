@echo off
echo ============================================
echo FocusFlow Uninstaller
echo ============================================

echo Stopping services...
sc stop FocusFlowGuard 2>NUL
net stop FocusFlowGuard 2>NUL

echo Creating shutdown signal for graceful shutdown...
if not exist "%APPDATA%\FocusFlow" mkdir "%APPDATA%\FocusFlow" 2>NUL
echo shutdown > "%APPDATA%\FocusFlow\.shutdown_signal" 2>NUL
echo shutdown > "C:\Program Files\FocusFlow\.shutdown_signal" 2>NUL
timeout /t 3 /nobreak >nul

echo Stopping processes...
taskkill /F /IM FocusFlow.exe /T 2>NUL
taskkill /F /IM FocusFlowGuard.exe /T 2>NUL

REM Try using WMIC to kill processes (works better with SYSTEM processes)
wmic process where "name='FocusFlow.exe'" delete 2>NUL
wmic process where "name='FocusFlowGuard.exe'" delete 2>NUL

REM Try using PowerShell as fallback
powershell -Command "Stop-Process -Name 'FocusFlow' -Force -ErrorAction SilentlyContinue" 2>NUL
powershell -Command "Stop-Process -Name 'FocusFlowGuard' -Force -ErrorAction SilentlyContinue" 2>NUL

timeout /t 2 /nobreak >nul

echo Removing scheduled tasks...
schtasks /delete /tn "FocusFlowGuard" /f 2>NUL
schtasks /delete /tn "FocusFlow" /f 2>NUL
schtasks /delete /tn "FocusFlowStartup" /f 2>NUL
schtasks /delete /tn "FocusFlowLaunchNow" /f 2>NUL

echo Removing Windows services...
sc delete FocusFlowGuard 2>NUL

echo Removing Registry Startup keys...
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "FocusFlow" /f 2>NUL
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "FocusFlowGuard" /f 2>NUL
reg delete "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run" /v "FocusFlow" /f 2>NUL
reg delete "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run" /v "FocusFlowGuard" /f 2>NUL
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "FocusFlow" /f 2>NUL
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "FocusFlowGuard" /f 2>NUL

echo Removing Application Registry keys...
reg delete "HKLM\SOFTWARE\FocusFlow" /f 2>NUL
reg delete "HKLM\SOFTWARE\WOW6432Node\FocusFlow" /f 2>NUL

echo Waiting for file locks to release...
timeout /t 3 /nobreak >nul

echo Removing Files...
if exist "C:\Program Files\FocusFlow" (
    rd /S /Q "C:\Program Files\FocusFlow" 2>NUL
    if exist "C:\Program Files\FocusFlow" (
        echo Retrying file removal...
        timeout /t 2 /nobreak >nul
        rd /S /Q "C:\Program Files\FocusFlow" 2>NUL
    )
)
if exist "C:\Program Files (x86)\FocusFlow" (
    rd /S /Q "C:\Program Files (x86)\FocusFlow" 2>NUL
)

echo Cleaning up signal files...
del "%APPDATA%\FocusFlow\.shutdown_signal" 2>NUL

echo.
echo ============================================
echo Done.
echo ============================================
exit /b 0
