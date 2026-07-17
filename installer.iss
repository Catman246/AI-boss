#define MyAppName "招聘助手"
#define MyAppVersion "0.1.0"
#define MyAppExeName "RecruitingAssistant.exe"

[Setup]
AppId={{7E862B58-6327-4F28-AC56-A7853C9E8CF0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Recruiting Console
DefaultDirName={localappdata}\Programs\RecruitingAssistant
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=release
OutputBaseFilename=招聘助手-安装包
SetupIconFile=assets\app-icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: checkedonce

[Files]
Source: "dist\RecruitingAssistant\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
