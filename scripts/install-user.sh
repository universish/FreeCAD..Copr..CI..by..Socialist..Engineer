#!/bin/sh
set -eu

package=${PKG:-${1:-}}
if [ -z "$package" ]; then
    echo "Usage: PKG=freecad-non-native PAYLOAD_DIR=/path/to/normalized/payload $0" >&2
    exit 2
fi
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
set -- install --package "$package"
if [ -n "${ARCH:-}" ]; then
    set -- "$@" --architecture "$ARCH"
fi
if [ -n "${PAYLOAD_ARCHIVE:-}" ]; then
    set -- "$@" --archive "$PAYLOAD_ARCHIVE"
fi
if [ -n "${PAYLOAD_DIR:-}" ]; then
    set -- "$@" --payload-dir "$PAYLOAD_DIR"
fi
exec python3 "$script_dir/install_user.py" "$@"
