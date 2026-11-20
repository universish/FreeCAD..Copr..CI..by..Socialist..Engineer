#!/bin/sh
set -eu

package=${PKG:-${1:-}}
if [ -z "$package" ]; then
    echo "Usage: PKG=freecad-non-native $0" >&2
    exit 2
fi
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
set -- uninstall --package "$package"
if [ "${PURGE_DATA:-0}" = "1" ]; then
    set -- "$@" --purge-data
fi
exec python3 "$script_dir/install_user.py" "$@"
