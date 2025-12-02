#define MyAppName "FocusFlow"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "FocusFlow"
#define MyAppURL "https://onfocusflow.com"
#define MyAppExeName "FocusFlow.exe"
#define MyAppGuardName "FocusFlowGuard.exe"

[Setup]
; Unique GUID for your application - DO NOT CHANGE for updates to work
AppId={{8B5F5A72-3C4D-4E8F-9A1B-2C3D4E5F6789}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer
OutputBaseFilename=FocusFlow_Setup_PDQ
SetupIconFile=assets\running.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

; PDQ DEPLOYMENT: Full silent installation
DisableWelcomePage=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
DisableFinishedPage=yes
CreateAppDir=yes
UsePreviousAppDir=yes

; Admin privileges required for service installation
PrivilegesRequired=admin

; Logging for PDQ Deploy troubleshooting
SetupLogging=yes

; PRODUCTION MODE: No uninstaller visible to users
CreateUninstallRegKey=no
Uninstallable=no

; CRITICAL: Close running applications before install
CloseApplications=force
CloseApplicationsFilter=*.exe
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Main application files
Source: "dist\FocusFlow\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\FocusFlow\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Watchdog/Guard executable
Source: "dist\{#MyAppGuardName}"; DestDir: "{app}"; Flags: ignoreversion
; NSSM for service management (optional - install scripts work without it)
Source: "tools\nssm.exe"; DestDir: "{app}\tools"; Flags: ignoreversion skipifsourcedoesntexist
; Scripts
Source: "scripts\install_service.bat"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "scripts\uninstall_service.bat"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "scripts\stop_focusflow.bat"; DestDir: "{app}\scripts"; Flags: ignoreversion

[Dirs]
; Create logs directory
Name: "{app}\logs"; Permissions: everyone-full

[Registry]
; Windows startup registry (SYSTEM-WIDE) - Main app for tray icon visibility
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "FocusFlow"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue
; Watchdog as backup
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "FocusFlowGuard"; ValueData: """{app}\{#MyAppGuardName}"""; Flags: uninsdeletevalue
; Application registry entries
Root: HKLM; Subkey: "SOFTWARE\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"
Root: HKLM; Subkey: "SOFTWARE\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"
Root: HKLM; Subkey: "SOFTWARE\{#MyAppName}"; ValueType: string; ValueName: "DeploymentMode"; ValueData: "PRODUCTION"

[Code]
var
  WasRunning: Boolean;

function InitializeSetup(): Boolean;
begin
  Result := True;
  WasRunning := False;
end;

procedure StopFocusFlowProcesses();
var
  ResultCode: Integer;
begin
  Log('Stopping FocusFlow processes before installation...');
  
  // Stop Windows service first
  Exec('sc.exe', 'stop FocusFlowGuard', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('net.exe', 'stop FocusFlowGuard', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('sc.exe', 'delete FocusFlowGuard', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  // Remove scheduled tasks
  Exec('schtasks.exe', '/delete /tn "FocusFlowGuard" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('schtasks.exe', '/delete /tn "FocusFlow" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('schtasks.exe', '/delete /tn "FocusFlowStartup" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  // Create shutdown signal files for graceful shutdown
  ForceDirectories(ExpandConstant('{%APPDATA}\FocusFlow'));
  SaveStringToFile(ExpandConstant('{%APPDATA}\FocusFlow\.shutdown_signal'), 'shutdown', False);
  SaveStringToFile(ExpandConstant('{pf}\FocusFlow\.shutdown_signal'), 'shutdown', False);
  
  // Wait for graceful shutdown
  Sleep(3000);
  
  // Force kill using multiple methods
  Exec('taskkill.exe', '/F /IM FocusFlow.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill.exe', '/F /IM FocusFlowGuard.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  // Use WMIC as fallback (better for SYSTEM processes)
  Exec('wmic.exe', 'process where "name=''FocusFlow.exe''" delete', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('wmic.exe', 'process where "name=''FocusFlowGuard.exe''" delete', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  // Use PowerShell as final fallback
  Exec('powershell.exe', '-Command "Stop-Process -Name FocusFlow -Force -ErrorAction SilentlyContinue"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('powershell.exe', '-Command "Stop-Process -Name FocusFlowGuard -Force -ErrorAction SilentlyContinue"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  // Wait for processes to fully terminate and release file locks
  Sleep(3000);
  
  // Clean up signal files
  DeleteFile(ExpandConstant('{%APPDATA}\FocusFlow\.shutdown_signal'));
  DeleteFile(ExpandConstant('{pf}\FocusFlow\.shutdown_signal'));
  
  WasRunning := True;
  Log('FocusFlow processes stopped.');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  NeedsRestart := False;
  StopFocusFlowProcesses();
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  AppPath: String;
begin
  if CurStep = ssPostInstall then
  begin
    Log('Post-installation: Setting up FocusFlow...');
    
    // Install the startup registry entries using the batch script
    Exec(ExpandConstant('{app}\scripts\install_service.bat'), 
         ExpandConstant('"{app}"'), 
         ExpandConstant('{app}'), 
         SW_HIDE, ewWaitUntilTerminated, ResultCode);
    
    // Start the main application in USER session using explorer.exe as launcher
    // This trick runs the app in the logged-in user's context, not SYSTEM
    AppPath := ExpandConstant('{app}\{#MyAppExeName}');
    Exec('explorer.exe', AppPath, '', SW_HIDE, ewNoWait, ResultCode);
    
    Log('FocusFlow installation completed. App launched in user session.');
  end;
end;

[Run]
; Run the app in the user's session after install using runasoriginaluser
; This is the KEY for PDQ deployment - runs in user session even when installer runs as SYSTEM
Filename: "{app}\{#MyAppExeName}"; Flags: runasoriginaluser nowait
