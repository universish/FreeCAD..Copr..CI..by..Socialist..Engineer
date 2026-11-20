#!/bin/sh
set -eu

package=${1:-}
container=${TOOLBOX_CONTAINER:-freecad-rpm}
case "$package" in
    freecad) command_name=freecad; desktop_id=org.freecad.FreeCAD.Native ;;
    freecad-candidate) command_name=freecad-can; desktop_id=org.freecad.FreeCAD.Candidate.Native ;;
    *) echo "Usage: $0 freecad|freecad-candidate" >&2; exit 2 ;;
esac
command -v toolbox >/dev/null 2>&1 || { echo "toolbox is required." >&2; exit 1; }
if toolbox run --container "$container" true >/dev/null 2>&1; then
    toolbox run --container "$container" sudo dnf -y remove "$package"
else
    echo "Toolbox $container is unavailable; removing host launchers only." >&2
fi
rm -f "$HOME/.local/bin/$command_name"
rm -f "$HOME/.local/share/applications/$desktop_id.desktop"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/freecad-native-$package.svg"
keep_path=0
for launcher in freecad freecad-can freecad-non-native freecad-can-non-native; do
    if [ -e "$HOME/.local/bin/$launcher" ]; then
        keep_path=1
    fi
done
if [ "$keep_path" -eq 0 ] && [ -f "$HOME/.profile" ]; then
    profile_tmp=$(mktemp)
    sed '/^# >>> FreeCAD local PATH >>>$/,/^# <<< FreeCAD local PATH <<<$/{d;}' "$HOME/.profile" > "$profile_tmp"
    cat "$profile_tmp" > "$HOME/.profile"
    rm -f "$profile_tmp"
fi
echo "Removed $package from Toolbox $container; the Toolbox itself was kept."
