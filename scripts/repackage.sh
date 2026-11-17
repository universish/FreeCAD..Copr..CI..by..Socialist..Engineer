#!/usr/bin/env bash
# Extract a verified upstream RPM/DEB/AppImage and normalize its runtime for
# the non-native RPM spec: AppRun, freecad-icon.svg, and architecture payload.
set -euo pipefail
: "${ARCH:?ARCH is required}" "${PKG:?PKG is required}" "${ASSET_FORMAT:?ASSET_FORMAT is required}" "${FILENAME:?FILENAME is required}"

case "$ARCH" in x86_64|aarch64) ;; *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;; esac
case "$ASSET_FORMAT" in rpm|deb|AppImage) ;; *) echo "Unsupported artifact format: $ASSET_FORMAT" >&2; exit 1 ;; esac

source_file=$(realpath "dist/$ARCH/$FILENAME")
root="payload/$ARCH"
work="work/$ARCH"
[[ -f "$source_file" ]] || { echo "Verified artifact not found: $source_file" >&2; exit 1; }
rm -rf "$work" "$root"
mkdir -p "$work/extracted" "$root"

case "$ASSET_FORMAT" in
    AppImage)
        chmod +x "$source_file"
        (cd "$work" && "$source_file" --appimage-extract >/dev/null)
        app_root="$work/squashfs-root"
        ;;
    rpm)
        command -v rpm2cpio >/dev/null && command -v cpio >/dev/null || {
            echo "rpm2cpio and cpio are required to extract upstream RPMs" >&2; exit 1;
        }
        (cd "$work/extracted" && rpm2cpio "$source_file" | cpio -idm --quiet)
        app_root="$work/extracted"
        ;;
    deb)
        command -v ar >/dev/null || { echo "ar is required to extract upstream DEBs" >&2; exit 1; }
        data_member=$(ar t "$source_file" | grep -E '^data\.tar\.(zst|xz|gz|bz2)$' | head -n 1 || true)
        [[ -n "$data_member" ]] || { echo "DEB has no supported data.tar member" >&2; exit 1; }
        case "$data_member" in
            data.tar.gz) data_tar_flags=(-zxf -) ;;
            data.tar.xz) data_tar_flags=(-Jxf -) ;;
            data.tar.bz2) data_tar_flags=(-jxf -) ;;
            data.tar.zst) data_tar_flags=(--zstd -xf -) ;;
        esac
        ar p "$source_file" "$data_member" | tar "${data_tar_flags[@]}" -C "$work/extracted"
        app_root="$work/extracted"
        ;;
esac
[[ -d "$app_root" ]] || { echo "Artifact extraction failed: $app_root" >&2; exit 1; }

app_run=$(find "$app_root" -type f -name AppRun -perm /111 -print -quit)
if [[ -n "$app_run" ]]; then
    app_dir=$(dirname "$app_run")
    cp -a "$app_dir"/. "$root"/
else
    cp -a "$app_root"/. "$root"/
    main_bin=$(find "$root" -type f \( -name FreeCAD -o -name freecad \) -perm /111 -print -quit)
    [[ -n "$main_bin" ]] || { echo "Could not locate an executable FreeCAD binary in $FILENAME" >&2; exit 1; }
    relative_bin="${main_bin#"$root"/}"
    cat > "$root/AppRun" <<'EOF'
#!/bin/sh
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PRIVATE_LIB_DIRS=""
for path in "$HERE"/usr/lib "$HERE"/usr/lib64 "$HERE"/usr/lib/* "$HERE"/opt/*/usr/lib "$HERE"/opt/*/usr/lib64; do
    [ -d "$path" ] && PRIVATE_LIB_DIRS="${PRIVATE_LIB_DIRS:+$PRIVATE_LIB_DIRS:}$path"
done
PRIVATE_QT_PLUGIN_DIRS=""
for path in "$HERE"/usr/lib/qt6/plugins "$HERE"/usr/lib64/qt6/plugins "$HERE"/opt/*/usr/lib/qt6/plugins "$HERE"/opt/*/usr/lib64/qt6/plugins; do
    [ -d "$path" ] && PRIVATE_QT_PLUGIN_DIRS="${PRIVATE_QT_PLUGIN_DIRS:+$PRIVATE_QT_PLUGIN_DIRS:}$path"
done
export LD_LIBRARY_PATH="${PRIVATE_LIB_DIRS}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export QT_PLUGIN_PATH="${PRIVATE_QT_PLUGIN_DIRS}${QT_PLUGIN_PATH:+:$QT_PLUGIN_PATH}"
export XDG_DATA_DIRS="$HERE/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
exec "$HERE/@MAIN_BIN@" "$@"
EOF
    sed -i -e "s|@MAIN_BIN@|$relative_bin|g" "$root/AppRun"
    chmod 0755 "$root/AppRun"
fi

icon=$(find "$root" -type f \( -iname 'org.freecad.FreeCAD.svg' -o -iname '*freecad*.svg' \) -print -quit)
[[ -n "$icon" ]] || { echo "No FreeCAD SVG icon found in normalized payload" >&2; exit 1; }
cp -f "$icon" "$root/freecad-icon.svg"
chmod 0755 "$root/AppRun"

main_bin=$(find "$root" -type f \( -name FreeCAD -o -name freecad \) -perm /111 -print -quit)
if [[ -n "$main_bin" ]] && command -v readelf >/dev/null; then
    machine=$(LC_ALL=C readelf -h "$main_bin" | awk -F: '/Machine:/ {gsub(/^[[:space:]]+/, "", $2); print $2}')
    case "$ARCH:$machine" in
        x86_64:*X86-64*|aarch64:*AArch64*) ;;
        *) echo "Architecture mismatch: $ARCH payload contains '$machine' binary" >&2; exit 1 ;;
    esac
fi
printf 'Normalized %s payload: ' "$ARCH"
du -sh "$root"
