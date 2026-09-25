# Builds the Windows installer: PyInstaller (GUI + CLI) and then Inno Setup.
# Usage: powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 [-Version 0.2.2]
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

$launcher = Join-Path $root "packaging\windows\launcher.py"
$src = Join-Path $root "src"
$common = @("--noconfirm", "--clean", "--paths", $src, "--specpath", "build", "--workpath", "build\pyinstaller")

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
