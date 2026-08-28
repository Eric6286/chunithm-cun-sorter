; 「今天你寸了吗」安装器（Inno Setup 6）
;
; 由 packaging\build.py 调用，版本号通过 /DAppVersion= 传进来——
; 版本的唯一真源是 core\version.py，别在这里再写一份。
;
; 装到用户目录（PrivilegesRequired=lowest），所以不弹 UAC。
;
; 这个文件必须存成 UTF-8 with BOM，否则 ISCC 按 ANSI 读，中文全是乱码。

#define AppName "今天你寸了吗"
#define AppExeName "今天你寸了吗.exe"
; 安装包文件名不带中文和空格，复制到哪儿都不用加引号
#define AppFileBase "chunithm-cun-sorter"
#define AppPublisher "ErikaAlk"
#define AppURL "https://github.com/ErikaAlk/chunithm-cun-sorter"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
; 真源是 coreersion.py 的 APP_USER_MODEL_ID，由 build.py 传进来
#ifndef AppUserModelID
  #define AppUserModelID "JinTianNiCunLeMa.App"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\cun"
#endif

[Setup]
AppId={{7B3C1E2A-9D64-4F51-A0C7-2E8F6B4A15D3}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
VersionInfoVersion={#AppVersion}

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableWelcomePage=no
DisableProgramGroupPage=yes
DisableDirPage=no
AllowNoIcons=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir=..\dist_installer
OutputBaseFilename={#AppFileBase}-{#AppVersion}-安装程序
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}
WizardStyle=modern

Compression=lzma2/normal
SolidCompression=yes

; 升级时如果旧版还开着，让安装器自己关掉
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=no

[Languages]
Name: "cn"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; AppUserModelID 要和程序运行时 set_app_user_model_id 声明的那个一模一样。
; 不写的话，任务栏上跑着的窗口和开始菜单里的快捷方式在 Windows 眼里是两个东西：
; 右键「固定到任务栏」钉出来的是一个点不开的空壳。
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}";     AppUserModelID: "{#AppUserModelID}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}";     AppUserModelID: "{#AppUserModelID}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "现在就打开 {#AppName}"; \
    Flags: nowait postinstall skipifsilent

; install.ini 是 [Code] 写出来的，卸载时要点名删掉
[UninstallDelete]
Type: files; Name: "{app}\install.ini"

[Code]
var
  GamePage: TInputDirWizardPage;

{ 判断一个目录像不像 CHUNITHM 的安装位置。判据和 core\config.py 的
  looks_like_game_root 一致：根下有 bin，且 bin 里有 screenshots /
  chusanApp.exe / option 之一，或者根下直接有 start.bat。 }
function LooksLikeGameRoot(Dir: String): Boolean;
var
  Base: String;
begin
  Result := False;
  if Dir = '' then
    Exit;
  Base := AddBackslash(Dir);
  if not DirExists(Base + 'bin') then
    Exit;
  Result := FileExists(Base + 'start.bat')
         or DirExists(Base + 'bin\screenshots')
         or FileExists(Base + 'bin\chusanApp.exe')
         or DirExists(Base + 'bin\option');
end;

{ 选中 bin 目录也接受，归一成它的上一级。不像游戏目录就返回空串。 }
function NormalizeGameRoot(Dir: String): String;
var
  Parent: String;
begin
  Result := '';
  if Dir = '' then
    Exit;
  if LooksLikeGameRoot(Dir) then
  begin
    Result := RemoveBackslash(Dir);
    Exit;
  end;
  Parent := ExtractFileDir(RemoveBackslash(Dir));
  if (CompareText(ExtractFileName(RemoveBackslash(Dir)), 'bin') = 0)
     and LooksLikeGameRoot(Parent) then
    Result := Parent;
end;

{ 在几个常见位置上碰碰运气。碰不到就留空，让用户自己选——
  真正可靠的自动探测在程序里（读运行中的游戏进程路径），这里只是省事。 }
function DetectGameRoot(): String;
var
  Drives: array[0..5] of String;
  Folders: array[0..4] of String;
  I, J: Integer;
  Candidate: String;
begin
  Result := '';
  Drives[0] := 'C:\'; Drives[1] := 'D:\'; Drives[2] := 'E:\';
  Drives[3] := 'F:\'; Drives[4] := 'G:\'; Drives[5] := 'H:\';
  Folders[0] := 'CHUNITHM';
  Folders[1] := 'Chuni\CHUNITHM';
  Folders[2] := 'Games\CHUNITHM';
  Folders[3] := 'SDHD\CHUNITHM';
  Folders[4] := 'chunithm';
  for I := 0 to GetArrayLength(Drives) - 1 do
    for J := 0 to GetArrayLength(Folders) - 1 do
    begin
      Candidate := Drives[I] + Folders[J];
      if LooksLikeGameRoot(Candidate) then
      begin
        Result := Candidate;
        Exit;
      end;
    end;
end;

procedure InitializeWizard();
begin
  GamePage := CreateInputDirPage(wpSelectDir,
    '选择 CHUNITHM 游戏目录',
    '程序要知道游戏装在哪，才能找到截图文件夹和 start.bat。',
    '选中 CHUNITHM 的根目录，也就是里面有一个 bin 文件夹的那一层。' + #13#10 +
    '现在不确定可以留空，第一次打开程序时还会再问一次。',
    False, '');
  GamePage.Add('');
  GamePage.Values[0] := DetectGameRoot();
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Chosen: String;
begin
  Result := True;
  if CurPageID <> GamePage.ID then
    Exit;
  Chosen := Trim(GamePage.Values[0]);
  if Chosen = '' then
    Exit;                                { 留空＝之后在程序里选，放行 }
  if NormalizeGameRoot(Chosen) = '' then
  begin
    MsgBox('这个目录不像 CHUNITHM 的安装位置：里面应该有一个 bin 文件夹。' + #13#10 +
           '选根目录或者它的 bin 目录都行，也可以留空、之后在程序里再选。',
           mbError, MB_OK);
    Result := False;
  end;
end;

{ 把选中的游戏目录写成 install.ini 放在程序旁边。程序第一次运行时读它，
  填进 %LOCALAPPDATA% 里的配置。这里不直接改 JSON——Pascal 拼 JSON 太容易
  出错，交给 Python 那边做。 }
procedure CurStepChanged(CurStep: TSetupStep);
var
  Root: String;
  Lines: TArrayOfString;
begin
  if CurStep <> ssPostInstall then
    Exit;
  Root := NormalizeGameRoot(Trim(GamePage.Values[0]));
  if Root = '' then
    Exit;
  { Inno 只有复数形式的 SaveStringsToUTF8File，没有 SaveStringToUTF8File。
    写出来带 BOM，Python 那边用 utf-8-sig 读，带不带都认。 }
  SetArrayLength(Lines, 2);
  Lines[0] := '[cun]';
  Lines[1] := 'game_root=' + Root;
  SaveStringsToUTF8File(ExpandConstant('{app}\install.ini'), Lines, False);
end;

[Messages]
; --- 标题与按钮 ---
SetupAppTitle=安装
SetupWindowTitle=安装 - %1
ButtonBack=< 上一步(&B)
ButtonNext=下一步(&N) >
ButtonInstall=安装(&I)
ButtonCancel=取消
ButtonFinish=完成(&F)
ButtonBrowse=浏览(&R)…
ButtonWizardBrowse=浏览(&R)…
ButtonYes=是(&Y)
ButtonNo=否(&N)
ButtonOK=确定
ClickNext=点「下一步」继续，或点「取消」退出安装。
BeveledLabel=

; --- 欢迎页 ---
WelcomeLabel1=欢迎安装 [name]
WelcomeLabel2=即将把 [name/ver] 装到这台电脑上。%n%n它盯着 CHUNITHM 的截图目录，把差一点的成绩挑出来单独归档，顺带按日期 / 评级 / 达成整理全部截图。%n%n继续之前建议先关掉正在运行的旧版本。

; --- 选目录 ---
WizardSelectDir=选择安装位置
SelectDirDesc=把 [name] 装到哪里？
SelectDirLabel3=安装程序会把 [name] 装进下面这个文件夹。它不需要放在游戏目录里。
SelectDirBrowseLabel=点「下一步」继续。想换个地方就点「浏览」。
DiskSpaceGBLabel=至少需要 [gb] GB 可用磁盘空间。
DiskSpaceMBLabel=至少需要 [mb] MB 可用磁盘空间。
CannotInstallToNetworkDrive=不能装到网络驱动器上。
CannotInstallToUNCPath=不能装到 UNC 路径上。
InvalidPath=请填写带盘符的完整路径，例如：%nC:\APP
DirExists=文件夹已经存在：%n%n%1%n%n还是要装到这里吗？
DirDoesntExist=文件夹不存在：%n%n%1%n%n要创建它吗？

; --- 附加任务 ---
WizardSelectTasks=选择附加任务
SelectTasksDesc=还要做点什么？
SelectTasksLabel2=勾上安装时要一并做的事，然后点「下一步」。

; --- 准备安装 ---
WizardReady=准备就绪
ReadyLabel1=一切就绪，可以开始安装了。
ReadyLabel2a=点「安装」开始，或点「上一步」回去改。
ReadyLabel2b=点「安装」开始。
ReadyMemoUserInfo=用户信息：
ReadyMemoDir=安装位置：
ReadyMemoTasks=附加任务：

; --- 安装中与完成 ---
WizardPreparing=正在准备
PreparingDesc=正在准备安装 [name]。
WizardInstalling=正在安装
InstallingLabel=正在把 [name] 装进去。
FinishedHeadingLabel=[name] 装好了
FinishedLabel=[name] 已经装到这台电脑上，桌面或开始菜单里都能找到它。%n%n识别历史截图需要 Tesseract OCR；只用联动和自动截图的话不装也行。
FinishedLabelNoIcons=[name] 已经装到这台电脑上。
FinishedRestartLabel=要装完这一步，需要重启电脑。现在重启吗？
ClickFinish=点「完成」结束安装。
RunEntryExec=运行 %1

; --- 取消与出错 ---
ExitSetupTitle=退出安装
ExitSetupMessage=安装还没完成。现在退出的话，[name] 不会被装上。%n%n真的要退出吗？
AbortRetryIgnoreSelectAction=选一个做法
AbortRetryIgnoreRetry=重试(&T)
AbortRetryIgnoreIgnore=忽略这个错误，继续(&I)
AbortRetryIgnoreCancel=取消安装
ErrorTitle=出错了
SetupAborted=安装没能完成。%n%n请解决问题后重新运行安装程序。
StatusExtractFiles=正在释放文件…
StatusCreateIcons=正在创建快捷方式…
StatusUninstalling=正在卸载 %1…
StatusRollback=正在撤销已做的改动…

; --- 卸载 ---
UninstallAppTitle=卸载
UninstallAppFullTitle=卸载 %1
ConfirmUninstall=确定要把 %1 和它的所有组件都删掉吗？%n%n配置、缓存和统计数据留在 %localappdata%\ChunithmCunSorter，不会被删。
UninstalledAll=%1 已经从这台电脑上卸载干净。
UninstalledMost=%1 已卸载。%n%n有一些内容没能删掉，需要你手动清理。
UninstallStatusLabel=正在把 %1 从这台电脑上删掉，稍等一下。
