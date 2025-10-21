; ============================================================
; RePKG-GUI 安装脚本 (installer.iss)
; 作者: YuefChen
; 更新: 2025-10-21
; 功能: 包含 README.md、国际化任务名称、图标、assets 完整资源
; ============================================================

[Setup]
AppId={{8A24C5D1-REPKG-GUI-2025}}
AppName=RePKG-GUI
AppVersion=1.0.0
AppPublisher=YuefChen
AppPublisherURL=https://github.com/
DefaultDirName={autopf}\RePKG-GUI
DefaultGroupName=RePKG-GUI
OutputDir=Output
OutputBaseFilename=RePKG-GUI_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\assets\images\icon.ico
SetupIconFile=assets\images\icon.ico
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; 使用国际化消息引用自定义文本
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenu"; Description: "{cm:CreateStartMenuFolder}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; 主程序与依赖
Source: "RePKG-GUI.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\RePKG.exe"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\repkg_config.json"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\txt\*"; DestDir: "{app}\assets\txt"; Flags: ignoreversion recursesubdirs
Source: "assets\images\*"; DestDir: "{app}\assets\images"; Flags: ignoreversion recursesubdirs

[Icons]
; 桌面快捷方式
Name: "{commondesktop}\RePKG-GUI"; Filename: "{app}\RePKG-GUI.exe"; IconFilename: "{app}\assets\images\icon.ico"; Tasks: desktopicon
; 开始菜单程序入口
Name: "{group}\RePKG-GUI"; Filename: "{app}\RePKG-GUI.exe"; IconFilename: "{app}\assets\images\icon.ico"; Tasks: startmenu
; README 打开快捷方式
Name: "{group}\查看使用说明 (README)"; Filename: "notepad.exe"; Parameters: """{app}\README.md"""; Tasks: startmenu
; 卸载图标
Name: "{group}\卸载 RePKG-GUI"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\RePKG-GUI.exe"; Description: "{cm:LaunchProgram,RePKG-GUI}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\temp"
Type: filesandordirs; Name: "{app}\logs"

; ========================
; 国际化自定义消息定义
; ========================
[CustomMessages]
; --- 中文（简体） ---
chinesesimplified.CreateStartMenuFolder=创建开始菜单文件夹
chinesesimplified.CreateDesktopIcon=创建桌面快捷方式
chinesesimplified.AdditionalIcons=附加图标
chinesesimplified.AppInfo=RePKG-GUI 是一款基于 RePKG 的图形界面工具，由 YuefChen 开发。

; --- 英文 ---
english.CreateStartMenuFolder=Create Start Menu Folder
english.CreateDesktopIcon=Create Desktop Icon
english.AdditionalIcons=Additional Icons
english.AppInfo=RePKG-GUI is a graphical interface for RePKG, developed by YuefChen.

[Code]
procedure InitializeWizard;
begin
  MsgBox(ExpandConstant('{cm:AppInfo}'), mbInformation, MB_OK);
end;
