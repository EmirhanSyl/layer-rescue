#define MyAppName "Layer Rescue"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Layer Rescue contributors"
#define MyAppExeName "LayerRescue.exe"

[Setup]
AppId={{4D98FC7C-38D4-49E4-98FB-793F8F1EB6A9}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={localappdata}\Programs\LayerRescue
DefaultGroupName=Layer Rescue
PrivilegesRequired=lowest

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir=..\..\release
OutputBaseFilename=LayerRescue-Setup-{#MyAppVersion}-win-x64

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes

[Files]
Source: "..\..\dist\LayerRescue\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

Source: "..\..\dist\layer-rescue-cli\*"; \
    DestDir: "{app}\cli"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

Source: "..\..\README.md"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

Source: "..\..\README.tr.md"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

Source: "..\..\LICENSE"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

[Icons]
Name: "{group}\Layer Rescue Documentation"; \
    Filename: "{app}\README.tr.md"

Name: "{group}\Uninstall Layer Rescue"; \
    Filename: "{uninstallexe}"

[Registry]
Root: HKCU; \
    Subkey: "Software\LayerRescue"; \
    ValueType: string; \
    ValueName: "InstallPath"; \
    ValueData: "{app}"; \
    Flags: uninsdeletekey

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ExePath: String;
  BambuCommand: String;
  MessageText: String;
begin
  if CurStep = ssPostInstall then
  begin
    ExePath := ExpandConstant('{app}\LayerRescue.exe');
    BambuCommand := Chr(34) + ExePath + Chr(34);

    MessageText :=
      'Bambu Studio Post-processing Scripts alanına şu komutu ekleyin:' +
      Chr(13) + Chr(10) +
      Chr(13) + Chr(10) +
      BambuCommand;

    MsgBox(
      MessageText,
      mbInformation,
      MB_OK
    );
  end;
end;