#define MyAppName "Layer Rescue"
#define MyAppVersion "0.2.2"
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
var
  BambuCommandLabel: TNewStaticText;
  BambuCommandEdit: TNewEdit;

procedure InitializeWizard;
begin
  BambuCommandLabel := TNewStaticText.Create(WizardForm);
  BambuCommandLabel.Parent := WizardForm.FinishedPage;
  BambuCommandLabel.Left := WizardForm.FinishedLabel.Left;
  BambuCommandLabel.Top :=
    WizardForm.FinishedLabel.Top +
    WizardForm.FinishedLabel.Height +
    ScaleY(16);
  BambuCommandLabel.Width :=
    WizardForm.FinishedPage.ClientWidth -
    BambuCommandLabel.Left -
    ScaleX(8);
  BambuCommandLabel.Height := ScaleY(32);
  BambuCommandLabel.AutoSize := False;
  BambuCommandLabel.WordWrap := True;
  BambuCommandLabel.Caption :=
    'Bambu Studio Post-processing Scripts alanına şu komutu ekleyin:';

  BambuCommandEdit := TNewEdit.Create(WizardForm);
  BambuCommandEdit.Parent := WizardForm.FinishedPage;
  BambuCommandEdit.Left := BambuCommandLabel.Left;
  BambuCommandEdit.Top :=
    BambuCommandLabel.Top +
    BambuCommandLabel.Height +
    ScaleY(4);
  BambuCommandEdit.Width := BambuCommandLabel.Width;
  BambuCommandEdit.ReadOnly := True;
  BambuCommandEdit.AutoSelect := True;
  BambuCommandEdit.HideSelection := False;
end;

procedure CurPageChanged(CurPageID: Integer);
var
  ExePath: String;
begin
  if CurPageID = wpFinished then
  begin
    ExePath := ExpandConstant('{app}\{#MyAppExeName}');

    BambuCommandEdit.Text :=
      Chr(34) + ExePath + Chr(34);

    WizardForm.ActiveControl := BambuCommandEdit;
    BambuCommandEdit.SelectAll;
  end;
end;