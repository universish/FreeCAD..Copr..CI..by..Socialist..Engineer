#!/bin/sh
set -eu

package=${1:-}
container=${TOOLBOX_CONTAINER:-freecad-rpm}
case "$package" in
    freecad) command_name=freecad; icon_id=org.freecad.FreeCAD; display_name='FreeCAD'; desktop_id=org.freecad.FreeCAD.Native ;;
    freecad-candidate) command_name=freecad-can; icon_id=org.freecad.FreeCAD.Candidate; display_name='FreeCAD Candidate'; desktop_id=org.freecad.FreeCAD.Candidate.Native ;;
    *) echo "Usage: $0 freecad|freecad-candidate" >&2; exit 2 ;;
esac
case "$container" in
    *[!a-zA-Z0-9_-]*|'') echo "TOOLBOX_CONTAINER may contain only letters, digits, _ and -." >&2; exit 2 ;;
esac
command -v toolbox >/dev/null 2>&1 || { echo "toolbox is required." >&2; exit 1; }

if ! toolbox run --container "$container" true >/dev/null 2>&1; then
    toolbox create --container "$container"
fi
toolbox run --container "$container" sudo dnf -y install dnf-plugins-core
toolbox run --container "$container" sudo dnf copr enable -y universish/FreeCAD..
toolbox run --container "$container" sudo dnf -y install "$package"
for other_package in freecad freecad-candidate freecad-non-native freecad-candidate-non-native; do
    if [ "$other_package" != "$package" ] && toolbox run --container "$container" rpm -q "$other_package" >/dev/null 2>&1; then
        echo "FreeCAD package $other_package is also installed in the Toolbox; launchers and user settings remain separate." >&2
    fi
done

home=${HOME:?HOME is not set}
bin_dir=$home/.local/bin
apps_dir=$home/.local/share/applications
icons_dir=$home/.local/share/icons/hicolor/scalable/apps
mkdir -p "$bin_dir" "$apps_dir" "$icons_dir"
profile_file=$home/.profile
if ! grep -Fqx '# >>> FreeCAD local PATH >>>' "$profile_file" 2>/dev/null; then
    cat >> "$profile_file" <<'EOF'

# >>> FreeCAD local PATH >>>
case ":$PATH:" in *:"$HOME/.local/bin":*) ;; *) PATH="$HOME/.local/bin:$PATH" ;; esac
export PATH
# <<< FreeCAD local PATH <<<
EOF
fi
launcher=$bin_dir/$command_name
cat > "$launcher" <<EOF
#!/bin/sh
export XDG_CONFIG_HOME="\${XDG_CONFIG_HOME:-\$HOME/.config}/$package"
export XDG_DATA_HOME="\${XDG_DATA_HOME:-\$HOME/.local/share}/$package"
export FREECAD_USER_HOME="\$XDG_DATA_HOME"
mkdir -p "\$FREECAD_USER_HOME"
exec toolbox run --container '$container' env XDG_CONFIG_HOME="\$XDG_CONFIG_HOME" XDG_DATA_HOME="\$XDG_DATA_HOME" FREECAD_USER_HOME="\$FREECAD_USER_HOME" '$command_name' "\$@"
EOF
chmod 0755 "$launcher"
icon_path=$icons_dir/freecad-native-$package.svg
if toolbox run --container "$container" test -f "/usr/share/icons/hicolor/scalable/apps/$icon_id.svg"; then
    toolbox run --container "$container" cat "/usr/share/icons/hicolor/scalable/apps/$icon_id.svg" > "$icon_path"
    icon_name=freecad-native-$package
else
    icon_name=applications-engineering
fi
desktop_file=$apps_dir/$desktop_id.desktop
cat > "$desktop_file" <<EOF
[Desktop Entry]
Name=$display_name (Toolbox)
Comment=FreeCAD installed in the $container Toolbox
GenericName=CAD Application
Exec="$launcher" %F
TryExec="$launcher"
Terminal=false
Type=Application
Icon=$icon_name
Categories=Graphics;Science;Education;Engineering;
StartupNotify=true
MimeType=application/x-extension-fcstd;model/step;model/stl;
EOF
echo "Installed $package in Toolbox $container with host launcher $launcher"
