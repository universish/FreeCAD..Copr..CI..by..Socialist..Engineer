#!/usr/bin/env bash
# Install a non-native FreeCAD payload for the current user without root.
set -euo pipefail
: "${PKG:?Set PKG to freecad-non-native or freecad-candidate-non-native}"
: "${VERSION:?Set VERSION to the upstream release version}"
: "${PAYLOAD_ARCHIVE:?Set PAYLOAD_ARCHIVE to the verified normalized payload tarball}"

case "$PKG" in
    freecad-non-native) launcher=freecad-non-native; desktop=org.freecad.FreeCAD.NonNative.desktop ;;
    freecad-candidate-non-native) launcher=freecad-can-non-native; desktop=org.freecad.FreeCAD.Candidate.NonNative.desktop ;;
    *) echo "Unsupported package: $PKG" >&2; exit 2 ;;
esac
[[ -f "$PAYLOAD_ARCHIVE" ]] || { echo "Payload archive not found: $PAYLOAD_ARCHIVE" >&2; exit 1; }

prefix="$HOME/.local/opt/$PKG"
mkdir -p "$prefix"
tar -xzf "$PAYLOAD_ARCHIVE" -C "$prefix"
[[ -x "$prefix/AppRun" ]] || { echo "Payload does not contain executable AppRun" >&2; exit 1; }
[[ -s "$prefix/freecad-icon.svg" ]] || { echo "Payload icon is missing" >&2; exit 1; }
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/scalable/apps"
cat > "$HOME/.local/bin/$launcher" <<EOF
#!/bin/sh
exec "$prefix/AppRun" "\$@"
EOF
chmod 0755 "$HOME/.local/bin/$launcher"
install -m 0644 "$prefix/freecad-icon.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/$PKG.svg"
cat > "$HOME/.local/share/applications/$desktop" <<EOF
[Desktop Entry]
Name=$PKG
Comment=FreeCAD installed for this user
Exec=$HOME/.local/bin/$launcher %F
TryExec=$HOME/.local/bin/$launcher
Icon=$PKG
Terminal=false
Type=Application
Categories=Graphics;Science;Engineering;
EOF
printf 'Installed %s %s for this user. Ensure ~/.local/bin is on PATH.\n' "$PKG" "$VERSION"
