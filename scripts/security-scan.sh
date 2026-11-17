#!/usr/bin/env bash
# Required ClamAV scan and static payload checks; VirusTotal SHA256 lookups are
# advisory on quota/network failures, but known malicious reports block publish.
set -euo pipefail
: "${TARGET:?TARGET payload directory is required}"
[[ -d "$TARGET" ]] || { echo "Payload directory not found: $TARGET" >&2; exit 1; }
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

if [[ -z "${VT_API_KEY:-}" && -f "${ENV_FILE:-.env}" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${ENV_FILE:-.env}"
    set +a
fi

command -v freshclam >/dev/null && command -v clamscan >/dev/null || {
    echo "ClamAV is required for the mandatory scan" >&2; exit 1;
}
if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl stop clamav-freshclam.service 2>/dev/null || true
fi
sudo freshclam --stdout
set +e
clamscan --recursive --infected --no-summary "$TARGET"
clam_status=$?
set -e
case "$clam_status" in
    0) ;;
    1) echo "ClamAV detected malware in $TARGET" >&2; exit 1 ;;
    *) echo "ClamAV scan failed (exit $clam_status)" >&2; exit "$clam_status" ;;
esac

[[ -x "$TARGET/AppRun" ]] || { echo "Normalized AppRun is missing or not executable" >&2; exit 1; }
[[ -s "$TARGET/freecad-icon.svg" ]] || { echo "Normalized FreeCAD icon is missing" >&2; exit 1; }
target_root=$(realpath "$TARGET")
links_file="$work_dir/links"

if ! find "$target_root" -type l -print0 > "$links_file"; then
    echo "Static payload symlink enumeration failed" >&2
    exit 1
fi

while IFS= read -r -d '' link; do
    resolved=$(realpath -m "$link")
    case "$resolved" in
        "$target_root"/*) ;;
        *)
            echo "Payload symlink escapes package root: $link -> $resolved" >&2
            exit 1
            ;;
    esac
done < "$links_file"

if [[ -z "${VT_API_KEY:-}" ]]; then
    echo "::warning::VT_API_KEY is unset; skipping advisory VirusTotal hash lookups."
    exit 0
fi
command -v curl >/dev/null || { echo "::warning::curl unavailable; skipping VirusTotal"; exit 0; }

seen="$work_dir/seen"
report="$work_dir/report"
file_list="$work_dir/files"

: > "$seen"

if ! find "$target_root" -type f -print0 > "$file_list"; then
    echo "::error::Unable to enumerate payload files for VirusTotal checks." >&2
    exit 1
fi

while IFS= read -r -d '' file; do
    hash=$(sha256sum "$file" | awk '{print $1}')
    grep -qx "$hash" "$seen" && continue
    echo "$hash" >> "$seen"

    code=$(curl --silent --show-error --connect-timeout 15 --max-time 45 \
        -H "x-apikey: $VT_API_KEY" -o "$report" -w '%{http_code}' \
        "https://www.virustotal.com/api/v3/files/$hash" || true)

    if [[ "$code" == 200 ]]; then
        verdict=$(jq -r '.data.attributes.last_analysis_stats // {} | (.malicious // 0) + (.suspicious // 0)' "$report" 2>/dev/null || echo 0)

        if [[ "$verdict" =~ ^[0-9]+$ && "$verdict" -gt 0 ]]; then
            echo "VirusTotal reports $verdict malicious/suspicious detections for $hash ($file)" >&2
            exit 1
        fi

    elif [[ "$code" == 404 ]]; then
        : # Hash not present in VirusTotal; this is not a scan failure.

    elif [[ "$code" == 429 || "$code" == 401 || "$code" == 403 || "$code" =~ ^5 ]]; then
        echo "::warning::VirusTotal returned HTTP $code; advisory hash checks stop here."
        exit 0

    else
        echo "::warning::VirusTotal returned HTTP ${code:-network-error}; skipping this lookup."
    fi
done < "$file_list"
