#!/usr/bin/env bash
# Fetch a selected upstream Linux artifact and verify it against the release
# checksum sidecar, falling back only to GitHub's SHA256 asset digest.
set -euo pipefail
: "${ARCH:?ARCH is required}" "${ASSET_URL:?ASSET_URL is required}" "${ASSET_FORMAT:?ASSET_FORMAT is required}"
ASSET_DIR="${ASSET_DIR:-dist/$ARCH}"
CHECKSUM_URL="${CHECKSUM_URL:-}"
API_DIGEST="${API_DIGEST:-}"

case "$ARCH" in x86_64|aarch64) ;; *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;; esac
case "$ASSET_FORMAT" in rpm|deb|AppImage) ;; *) echo "Unsupported artifact format: $ASSET_FORMAT" >&2; exit 1 ;; esac

mkdir -p "$ASSET_DIR"
filename=$(basename "${ASSET_URL%%\?*}")
[[ -n "$filename" && "$filename" != . && "$filename" != / ]] || {
    echo "Could not determine artifact filename" >&2; exit 1;
}
artifact="$ASSET_DIR/$filename"
curl --fail --location --retry 4 --retry-all-errors --connect-timeout 30 \
    "$ASSET_URL" --output "$artifact"

expected=''
if [[ -n "$CHECKSUM_URL" ]]; then
    checksum_file="$ASSET_DIR/${filename}-SHA256.txt"
    curl --fail --location --retry 3 --connect-timeout 30 \
        "$CHECKSUM_URL" --output "$checksum_file"
    expected=$(awk -v target="$filename" '
        {
            hash = ""
            for (i = 1; i <= NF; i++) {
                if (length($i) == 64 && $i ~ /^[[:xdigit:]]+$/) hash = $i
            }
            if (hash == "") next
            if ($NF == target || $NF == "*" target) { matched = hash; matches++ }
            else if (NF == 1) bare = hash
        }
        END {
            if (matches == 1) print matched
            else if (matches == 0) print bare
        }
    ' "$checksum_file")
    [[ -n "$expected" ]] || { echo "No SHA256 value in checksum sidecar: $CHECKSUM_URL" >&2; exit 1; }
elif [[ -n "$API_DIGEST" ]]; then
    expected="${API_DIGEST#sha256:}"
else
    echo "No upstream checksum sidecar or GitHub SHA256 digest; refusing unverified artifact" >&2
    exit 1
fi

[[ "$expected" =~ ^[[:xdigit:]]{64}$ ]] || {
    echo "Invalid SHA256 value for $filename" >&2
    exit 1
}

actual=$(sha256sum "$artifact" | awk '{print $1}')
if [[ "${actual,,}" != "${expected,,}" ]]; then
    echo "SHA256 mismatch for $filename" >&2
    echo "expected: $expected" >&2
    echo "actual:   $actual" >&2
    exit 1
fi
printf 'Verified %s (%s) SHA256=%s\n' "$filename" "$ARCH" "$actual"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    {
        echo "filename=$filename"
        echo "path=$artifact"
        echo "sha256=$actual"
    } >> "$GITHUB_OUTPUT"
fi
