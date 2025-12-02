@echo off
TITLE FocusFlow Installer

echo ==========================================================
echo  FocusFlow Application Setup
echo ==========================================================
echo This script will install FocusFlow for the current user.
echo It does NOT require administrator privileges.
echo.
pause
echo.

:: Define the installation path in the user's local app data folder
set "INSTALL_PATH=%LOCALAPPDATA%\FocusFlow"
echo Installing to: %INSTALL_PATH%
echo.

:: Create the directory if it doesn't exist, then copy the executable
IF NOT EXIST "%INSTALL_PATH%" MKDIR "%INSTALL_PATH%"
COPY "FocusFlow.exe" "%INSTALL_PATH%\FocusFlow.exe" /Y

:: Add a registry key to the current user's hive to run the stealth monitor on startup
echo Adding stealth monitor to Windows startup...
REG ADD "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /V "FocusFlowMonitor" /t REG_SZ /F /D "%INSTALL_PATH%\stealth_monitor.exe"

:: Create a Desktop shortcut using a temporary VBScript
echo Creating Desktop shortcut...
set SCRIPT="%TEMP%\create_shortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > %SCRIPT%
echo sLinkFile = "%USERPROFILE%\Desktop\FocusFlow.lnk" >> %SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT%
echo oLink.TargetPath = "%INSTALL_PATH%\FocusFlow.exe" >> %SCRIPT%
echo oLink.Save >> %SCRIPT%
cscript /nologo %SCRIPT%
del %SCRIPT%

echo.
echo ==========================================================
echo  Installation Complete!
echo ==========================================================
echo FocusFlow is now installed and will run automatically when you log in.
echo A shortcut has also been placed on your Desktop.
echo.
pause