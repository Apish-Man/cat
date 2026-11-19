#!/bin/bash
# Prepare an arm64 export from the official universal Godot template.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"
godot_bin=${GODOT_BIN:-godot}
template=${GODOT_MAC_TEMPLATE:-"$HOME/Library/Application Support/Godot/export_templates/4.7.2.stable/macos.zip"}
staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT
mkdir -p build/godot-templates dist/mac
unzip -q "$template" -d "$staging"
binaries="$staging/macos_template.app/Contents/MacOS"
for kind in debug release; do
    src="$binaries/godot_macos_${kind}.universal"
    dst="$binaries/godot_macos_${kind}.arm64"
    lipo "$src" -thin arm64 -output "$dst"
    chmod +x "$dst"
    rm "$src"
done
(cd "$staging" && zip -qry macos-arm64.zip macos_template.app)
mv "$staging/macos-arm64.zip" build/godot-templates/macos-arm64.zip
"$godot_bin" --headless --path mac --import
"$godot_bin" --headless --path mac --export-release "macOS arm64" ../dist/mac/CatMate.app
codesign --verify --deep --strict dist/mac/CatMate.app
