#!/usr/bin/env bash
# Remove a non-native per-user FreeCAD installation created by install-user.sh.
set -euo pipefail
: "${PKG:?Set PKG to freecad-non-native or freecad-candidate-non-native}"
case "$PKG" in
    freecad-non-native) launcher=freecad-non-native; desktop=org.freecad.FreeCAD.NonNative.desktop ;;
    freecad-candidate-non-native) launcher=freecad-can-non-native; desktop=org.freecad.FreeCAD.Candidate.NonNative.desktop ;;
    *) echo "Unsupported package: $PKG" >&2; exit 2 ;;
esac
rm -rf "$HOME/.local/opt/$PKG"
rm -f "$HOME/.local/bin/$launcher" \
    "$HOME/.local/share/applications/$desktop" \
    "$HOME/.local/share/icons/hicolor/scalable/apps/$PKG.svg"
printf 'Removed %s user installation.\n' "$PKG"
