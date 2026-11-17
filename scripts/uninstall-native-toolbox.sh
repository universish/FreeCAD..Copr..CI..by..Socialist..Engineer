#!/usr/bin/env bash
# Remove one native FreeCAD RPM from the user's Toolbox and remove its host launchers.
set -euo pipefail

package="${1:?Usage: uninstall-native-toolbox.sh freecad|freecad-candidate}"
container="${TOOLBOX_CONTAINER:-freecad-rpm}"
case "$package" in
    freecad)
        launcher=freecad
        desktop_id=org.freecad.FreeCAD.Toolbox.desktop
        icon_name=org.freecad.FreeCAD
        ;;
    freecad-candidate)
        launcher=freecad-can
        desktop_id=org.freecad.FreeCAD.Candidate.Toolbox.desktop
        icon_name=org.freecad.FreeCAD.Candidate
        ;;
    *) echo "Unsupported native package: $package" >&2; exit 2 ;;
esac
command -v toolbox >/dev/null || { echo "Toolbox is not installed." >&2; exit 1; }
toolbox run --container "$container" sudo dnf -y remove "$package"
rm -f "$HOME/.local/bin/$launcher" \
    "$HOME/.local/share/applications/$desktop_id" \
    "$HOME/.local/share/icons/hicolor/scalable/apps/${icon_name}.svg"
printf 'Removed %s from Toolbox %s. The Toolbox itself was left intact.\n' "$package" "$container"
