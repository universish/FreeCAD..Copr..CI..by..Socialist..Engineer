#!/usr/bin/env bash
# Compatibility wrapper for AppImage-derived hybrid packaging.
set -euo pipefail
if [[ -n "${APPIMAGE_URL:-}" ]]; then
  export APPIMAGE_URL
fi
if [[ -z "${APPIMAGE_URL:-}" ]]; then
  echo "APPIMAGE_URL is required; set it to the official FreeCAD AppImage URL" >&2
  exit 1
fi
exec "$(dirname "$0")/build-srpm-non-native.sh" "$@"
