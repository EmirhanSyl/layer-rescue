# Builds the Windows installer: PyInstaller (GUI + CLI) and then Inno Setup.
# Usage: powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 [-Version 1.0.0]
param([string]$Version)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

function Assert-LastExitCode([string]$step) {
    if ($LASTEXITCODE -ne 0) { throw "$step failed with exit code $LASTEXITCODE" }
}

if (-not $Version) {
    $Version = python -c "import sys; sys.path.insert(0, 'src'); from layer_rescue._version import __version__; print(__version__)"
    Assert-LastExitCode "Reading the version"
}
Write-Host "Building Layer Rescue $Version"

# Runtime dependencies (pyclipper) must be importable for PyInstaller to bundle them.
python -m pip install .
Assert-LastExitCode "Installing Layer Rescue and its dependencies"

$launcher = Join-Path $root "packaging\launcher.py"
$src = Join-Path $root "src"
$assets = Join-Path $src "layer_rescue\assets"
$icon = Join-Path $assets "icon.ico"
$common = @(
    "--noconfirm", "--clean", "--paths", $src, "--specpath", "build", "--workpath", "build\pyinstaller",
    "--icon", $icon, "--add-data", "$assets;layer_rescue\assets"
)

python -m PyInstaller @common --windowed --name LayerRescue $launcher
Assert-LastExitCode "PyInstaller (GUI)"
python -m PyInstaller @common --console --name layer-rescue-cli $launcher
Assert-LastExitCode "PyInstaller (CLI)"

$iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $iscc)) { throw "Inno Setup 6 was not found. Install it from https://jrsoftware.org/isinfo.php" }

& $iscc "/DMyAppVersion=$Version" "packaging\windows\LayerRescue.iss"
Assert-LastExitCode "Inno Setup"
Write-Host "Installer written to release\LayerRescue-Setup-$Version-win-x64.exe"
