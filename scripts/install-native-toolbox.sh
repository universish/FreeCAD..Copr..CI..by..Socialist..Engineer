#!/usr/bin/env bash
# Install a native FreeCAD RPM into a user's Toolbox and expose host launchers.
set -euo pipefail

package="${1:?Usage: install-native-toolbox.sh freecad|freecad-candidate}"
container="${TOOLBOX_CONTAINER:-freecad-rpm}"
case "$package" in
    freecad)
        launcher=freecad
        binary=FreeCAD
        label='FreeCAD (Toolbox)'
        desktop_id=org.freecad.FreeCAD.Toolbox.desktop
        icon_name=org.freecad.FreeCAD
        ;;
    freecad-candidate)
        launcher=freecad-can
        binary=freecad-can
        label='FreeCAD Candidate (Toolbox)'
        desktop_id=org.freecad.FreeCAD.Candidate.Toolbox.desktop
        icon_name=org.freecad.FreeCAD.Candidate
        ;;
    *) echo "Unsupported native package: $package" >&2; exit 2 ;;
esac
[[ "$container" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Invalid toolbox name" >&2; exit 2; }
command -v toolbox >/dev/null || { echo "Install Fedora Toolbox first (dnf install toolbox)." >&2; exit 1; }

if ! toolbox run --container "$container" true >/dev/null 2>&1; then
    toolbox create --container "$container"
fi
toolbox run --container "$container" sudo dnf -y copr enable universish/FreeCAD..
toolbox run --container "$container" sudo dnf -y install "$package"

mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications" \
    "$HOME/.local/share/icons/hicolor/scalable/apps"
cat > "$HOME/.local/bin/$launcher" <<EOF
#!/bin/sh
exec toolbox run --container '$container' '$binary' "\$@"
EOF
chmod 0755 "$HOME/.local/bin/$launcher"

icon_source=$(toolbox run --container "$container" sh -lc \
    "find /usr/share/icons/hicolor -type f -name '${icon_name}.*' -print -quit" || true)
icon_file="$HOME/.local/share/icons/hicolor/scalable/apps/${icon_name}.svg"
if [[ "$icon_source" == *.svg ]]; then
    toolbox run --container "$container" cat "$icon_source" > "$icon_file"
fi

printf '[Desktop Entry]\nName=%s\nType=Application\nExec="%s" %%F\nTryExec=%s\nIcon=%s\nTerminal=false\nCategories=Graphics;Science;Engineering;\n' \
    "$label" "$HOME/.local/bin/$launcher" "$HOME/.local/bin/$launcher" "$icon_name" \
    > "$HOME/.local/share/applications/$desktop_id"
command -v desktop-file-validate >/dev/null && desktop-file-validate "$HOME/.local/share/applications/$desktop_id"
printf 'Installed %s in Toolbox %s; host launcher: %s\n' "$package" "$container" "$HOME/.local/bin/$launcher"
