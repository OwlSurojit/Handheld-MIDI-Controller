#define AppName "Handheld MIDI Controller"
#define AppVersion GetEnv("APP_VERSION")
#if AppVersion == ""
  #define AppVersion "0.0.0-dev"
#endif
#define AppPublisher "Handheld MIDI Controller"
#define AppExeName "HandheldMIDI.exe"

[Setup]
AppId={{65AC3E69-372E-4873-8683-2DFF4FFD75F7}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Handheld MIDI Controller
DefaultGroupName=Handheld MIDI Controller
OutputDir="..\..\dist"
OutputBaseFilename=HandheldMIDI-Windows-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "visualiser"; Description: "Install Visualiser feature (OpenGL, larger install size)"; GroupDescription: "Optional features:"; Flags: unchecked

[Files]
Source: "..\..\dist\HandheldMIDI-core\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: not WizardIsTaskSelected('visualiser')
Source: "..\..\dist\HandheldMIDI-visualiser\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: WizardIsTaskSelected('visualiser')

[Icons]
Name: "{group}\Handheld MIDI Controller"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Handheld MIDI Controller"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch Handheld MIDI Controller"; Flags: nowait postinstall skipifsilent
