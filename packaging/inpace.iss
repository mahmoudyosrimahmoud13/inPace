; The Windows installer: inPace-setup.exe (built by packaging/build.py with Inno Setup 6).
; Installs for the current user (no admin password), adds inPace to the Start menu and to
; "Installed apps" with an uninstaller, and opens inpace:// links. Your courses and progress live
; in Documents\inPace, so installing, updating or uninstalling never touches them.

#define AppVersion GetEnv("INPACE_VERSION")
#if AppVersion == ""
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{5B1E3C2A-7F4D-4E8B-9A61-3C2D7E8F9A10}
AppName=inPace
AppVersion={#AppVersion}
AppVerName=inPace {#AppVersion}
AppPublisher=Mahmoud Yosri
AppPublisherURL=https://mahmoudyosrimahmoud13.github.io/inPace/
AppSupportURL=https://github.com/mahmoudyosrimahmoud13/inpace/issues
AppUpdatesURL=https://github.com/mahmoudyosrimahmoud13/inpace/releases
AppCopyright=Copyright (c) 2026 Mahmoud Yosri. MIT license.
DefaultDirName={autopf}\inPace
DefaultGroupName=inPace
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=inPace-setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\inPace.exe
UninstallDisplayName=inPace
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
CloseApplications=force
RestartApplications=no
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany=Mahmoud Yosri
VersionInfoDescription=inPace setup
VersionInfoProductName=inPace
VersionInfoProductVersion={#AppVersion}
VersionInfoCopyright=Copyright (c) 2026 Mahmoud Yosri

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; An update replaces the whole program folder, so nothing from an older version is left behind.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\inPace\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\inPace"; Filename: "{app}\inPace.exe"; Comment: "Finish the courses you start"
Name: "{autodesktop}\inPace"; Filename: "{app}\inPace.exe"; Tasks: desktopicon

[Registry]
; inpace:// links (from chats, emails and the website) open inPace.
Root: HKA; Subkey: "Software\Classes\inpace"; ValueType: string; ValueName: ""; ValueData: "URL:inPace link"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\inpace"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\inpace\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\inPace.exe"",0"
Root: HKA; Subkey: "Software\Classes\inpace\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\inPace.exe"" ""%1"""

[Run]
Filename: "{app}\inPace.exe"; Description: "{cm:LaunchProgram,inPace}"; Flags: nowait postinstall skipifsilent
; An update from inside the app runs this installer silently with /RELAUNCH=1: open inPace again after.
Filename: "{app}\inPace.exe"; Flags: nowait; Check: Relaunch

[Code]
function Relaunch: Boolean;
begin
  Result := ExpandConstant('{param:RELAUNCH|0}') = '1';
end;
