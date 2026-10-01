#!/usr/bin/env bash
# Builds LayerRescue.app with PyInstaller and zips it into release/.
# Usage: packaging/macos/build.sh [version]
set -euo pipefail

cd "$(dirname "$0")/../.."
root="$PWD"
version="${1:-$(python3 -c 'import sys; sys.path.insert(0, "src"); from layer_rescue._version import __version__; print(__version__)')}"
arch="$(uname -m)"
echo "Building Layer Rescue $version for macOS $arch"

# Runtime dependencies (pyclipper) must be importable for PyInstaller to bundle them.
python3 -m pip install .

python3 -m PyInstaller --noconfirm --clean --windowed \
  --name LayerRescue \
  --osx-bundle-identifier io.github.emirhansyl.layerrescue \
  --icon "$root/packaging/macos/LayerRescue.icns" \
  --add-data "$root/src/layer_rescue/assets:layer_rescue/assets" \
  --paths "$root/src" \
  --specpath build --workpath build/pyinstaller --distpath dist \
  "$root/packaging/launcher.py"

app="dist/LayerRescue.app"
plist="$app/Contents/Info.plist"
plutil -replace CFBundleShortVersionString -string "$version" "$plist"
plutil -replace CFBundleVersion -string "$version" "$plist"

# Editing Info.plist invalidates PyInstaller's ad-hoc signature. Apple Silicon
# refuses to run unsigned code, so sign again (ad-hoc until Developer ID signing is added).
codesign --force --deep --sign - "$app"
codesign --verify --deep --strict "$app"

mkdir -p release
zip="release/LayerRescue-$version-macos-$arch.zip"
rm -f "$zip"
ditto -c -k --keepParent "$app" "$zip"
echo "Wrote $zip"
