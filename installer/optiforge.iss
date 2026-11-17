; OptiForge Inno Setup Script
#define MyAppName "OptiForge"
#define MyAppVersion "1.0.0"
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
; Allow per-user install without administrator privileges
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

[Files]
Source: "..\dist\OptiForgeApp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\optiforge.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\optiforge.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\optiforge.ico"

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
  // Check 64-bit and 32-bit registry keys for WebView2
  if RegQueryDWordValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Installed) or
     RegQueryDWordValue(HKEY_CURRENT_USER, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Installed) or
     RegKeyExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}') then
  begin
    Result := True;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // If WebView2 is not detected, inform user that browser fallback is available
    if not IsWebView2Installed() then
    begin
      Log('WebView2 runtime not detected; OptiForge will use default web browser automatically.');
    end;
  end;
end;
