; OptiForge Inno Setup Script
#define MyAppName "OptiForge"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "Chane0704"
#define MyAppURL "https://github.com/Chane0704/OptiForge"
#define MyAppExeName "OptiForgeApp.exe"

[Setup]
AppId={{A39D9E42-6B44-4F8B-9E39-9B9B3A2C81DF}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=OptiForge-Setup-{#MyAppVersion}
SetupIconFile=..\optiforge.ico
UninstallDisplayIcon={app}\optiforge.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "contextmenu"; Description: "Add 'Analyze with OptiForge' to Windows Explorer right-click menu"; GroupDescription: "Windows Integration:"; Flags: unchecked

[Files]
Source: "..\dist\OptiForgeApp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\optiforge.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\sample_bloated_project\*"; DestDir: "{app}\sample_bloated_project"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\optiforge.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\optiforge.ico"

[Registry]
; Optional Explorer right-click context menu (off by default, cleanly uninstalled)
Root: HKCU; Subkey: "Software\Classes\Directory\shell\OptiForge"; ValueType: string; ValueData: "Analyze with OptiForge"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\OptiForge"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\optiforge.ico"""; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\OptiForge\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: contextmenu

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Strictly cleans application install files, never touches user projects or .optiforge backups
Type: filesandordirs; Name: "{app}"

[Code]
// Helper to detect Microsoft Edge WebView2 Runtime
function IsWebView2Installed(): Boolean;
var
  Installed: Cardinal;
begin
  Result := False;
  if RegQueryDWordValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Installed) or
     RegQueryDWordValue(HKEY_CURRENT_USER, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Installed) or
     RegQueryDWordValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Installed) then
  begin
    Result := True;
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not IsWebView2Installed() then
  begin
    if MsgBox('Microsoft Edge WebView2 Runtime was not detected on this machine.' + #13#10 + #13#10 +
              'OptiForge uses WebView2 to render its desktop interface. If not present, the app will run inside your default web browser.' + #13#10 + #13#10 +
              'Would you like to continue installation anyway?', mbConfirmation, MB_YESNO) = IDNO then
    begin
      Result := False;
    end;
  end;
end;

procedure SHChangeNotify(wEventId: Integer; uFlags: Cardinal; dwItem1, dwItem2: Integer);
external 'SHChangeNotify@shell32.dll stdcall';

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Force Windows Explorer Shell to refresh desktop and taskbar icon cache immediately
    try
      SHChangeNotify($08000000, 0, 0, 0);
    except
      // Ignore if shell notification fails
    end;
  end;
end;
