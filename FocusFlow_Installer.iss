#define MyAppName "FocusFlow"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "FocusFlow"
#define MyAppURL "https://focusflow.app"
#define MyAppExeName "FocusFlow.exe"
#define MyAppGuardName "FocusFlowGuard.exe"

[Setup]
; Generate unique GUID for your application
AppId={{8B5F5A72-3C4D-4E8F-9A1B-2C3D4E5F6789}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer
OutputBaseFilename=FocusFlow_Setup
SetupIconFile=assets\running.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; TESTING MODE: Interactive installer with uninstaller support
; User-friendly installation with GUI dialogs
; USER-SPACE installation - no admin privileges required
PrivilegesRequired=lowest
; Logging for PDQ Deploy
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\FocusFlow\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\{#MyAppGuardName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\FocusFlow\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; No service-related files needed for user-space testing installation

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Add to Windows startup registry (USER-LEVEL for testing)
Root: HKCU; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "FocusFlowGuard"; ValueData: """{app}\{#MyAppGuardName}"""; Flags: uninsdeletevalue
; Application registry entries (USER-LEVEL for testing)
Root: HKCU; Subkey: "SOFTWARE\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "SOFTWARE\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "SOFTWARE\{#MyAppName}"; ValueType: string; ValueName: "DeploymentMode"; ValueData: "TESTING"; Flags: uninsdeletekey

[Run]
; Start the watchdog directly (user-space, no service)
Filename: "{app}\{#MyAppGuardName}"; StatusMsg: "Starting FocusFlow Guardian..."; Flags: runhidden nowait
; Optional: Launch the main application
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop any running FocusFlow processes before uninstalling
; The watchdog and main app will be terminated by the uninstaller automatically
