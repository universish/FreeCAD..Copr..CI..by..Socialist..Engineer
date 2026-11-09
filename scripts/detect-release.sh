#!/usr/bin/env bash
# Select the latest stable or prerelease source tag. Binary release assets are
# intentionally irrelevant: Copr builds from the matching Git source checkout.
set -euo pipefail

STATE_DIR="${STATE_DIR:-state}"
FORCE_VERSION="${FORCE_VERSION:-}"
FORCE_CHANNEL="${FORCE_CHANNEL:-auto}"
API="https://api.github.com/repos/FreeCAD/FreeCAD/releases"

is_candidate_tag() { [[ "$1" =~ (rc[0-9]+|beta|alpha|pre) ]]; }
is_weekly_tag() { [[ "$1" == weekly-* || "$1" == *weekly* ]]; }
classify() {
    local tag="$1" prerelease="$2"
    if [[ "$prerelease" == true ]] || is_candidate_tag "$tag"; then echo candidate; else echo stable; fi
}

if [[ "$FORCE_CHANNEL" != auto && "$FORCE_CHANNEL" != stable && "$FORCE_CHANNEL" != candidate ]]; then
    echo "::error::Invalid channel: $FORCE_CHANNEL"; exit 1
fi

if [[ -n "$FORCE_VERSION" ]]; then
    tag="${FORCE_VERSION#v}"
    is_weekly_tag "$tag" && { echo "::error::Weekly builds are not packaged."; exit 1; }
    release=$(curl -fsSL -H 'Accept: application/vnd.github+json' "$API/tags/$tag") \
        || { echo "::error::Release tag not found: $tag"; exit 1; }
    channel=$(classify "$tag" "$(jq -r '.prerelease' <<<"$release")")
    if [[ "$FORCE_CHANNEL" != auto && "$FORCE_CHANNEL" != "$channel" ]]; then
        echo "::error::Tag $tag belongs to $channel, not $FORCE_CHANNEL"; exit 1
    fi
else
    release=''
    for page in $(seq 1 10); do
        batch=$(curl -fsSL -H 'Accept: application/vnd.github+json' "$API?per_page=100&page=$page")
        [[ $(jq 'length' <<<"$batch") -eq 0 ]] && break
        while IFS= read -r item; do
            tag=$(jq -r '.tag_name' <<<"$item")
            is_weekly_tag "$tag" && continue
            channel=$(classify "$tag" "$(jq -r '.prerelease' <<<"$item")")
            if [[ "$FORCE_CHANNEL" == auto || "$FORCE_CHANNEL" == "$channel" ]]; then
                release="$item"; break 2
            fi
        done < <(jq -c '.[]' <<<"$batch")
    done
    [[ -n "$release" ]] || { echo "::error::No release found for channel $FORCE_CHANNEL"; exit 1; }
    tag=$(jq -r '.tag_name' <<<"$release")
    channel=$(classify "$tag" "$(jq -r '.prerelease' <<<"$release")")
fi

version="${tag#v}"
html_url=$(jq -r '.html_url' <<<"$release")
if [[ "$channel" == stable ]]; then pkg=freecad; else pkg=freecad-candidate; fi

<<<<<<< HEAD
=======
get_appimage_url() {
    local payload="$1"
    jq -r '.assets[]? | select(.browser_download_url|test("\\.AppImage$|\\.appimage$"; "i")) | .browser_download_url' <<<"$payload" | head -n 1
}

>>>>>>> 20e77c9 (feat: add native and non-native AppImage/source Fedora RPM packages and automation)
state_file="$STATE_DIR/$pkg.json"
previous_version=''; previous_release=0
previous_packaging='legacy-binary'
if [[ -f "$state_file" ]]; then
    previous_version=$(jq -r '.version // ""' "$state_file")
    previous_release=$(jq -r '.release // 0' "$state_file")
    previous_packaging=$(jq -r '.packaging_mode // "legacy-binary"' "$state_file")
fi
if [[ "$previous_version" != "$version" ]]; then
    changed=true; release_no=1
elif [[ "$previous_packaging" != native-source ]]; then
    changed=true; release_no=$((previous_release + 1))
elif [[ "${GITHUB_EVENT_NAME:-}" == workflow_dispatch || -n "$FORCE_VERSION" ]]; then
    changed=true; release_no=$((previous_release + 1))
else
    changed=false; release_no=$((previous_release + 1))
fi

<<<<<<< HEAD
=======
appimage_url=$(get_appimage_url "$release")
if [[ -z "$appimage_url" ]]; then
    echo "::warning::No AppImage asset found for tag $tag; non-native SRPM generation will fail unless APPIMAGE_URL is supplied manually." >&2
fi

non_native_pkg="${pkg}-non-native"
if [[ "$pkg" == "freecad-candidate" ]]; then
    non_native_pkg="freecad-candidate-non-native"
fi

>>>>>>> 20e77c9 (feat: add native and non-native AppImage/source Fedora RPM packages and automation)
printf 'Selected %s source tag %s (%s), package %s-%s-%s, changed=%s\n' \
    "$channel" "$tag" "$html_url" "$pkg" "$version" "$release_no" "$changed"
{
    echo "changed=$changed"
    echo "version=$version"
    echo "tag=$tag"
    echo "channel=$channel"
    echo "pkg=$pkg"
<<<<<<< HEAD
    echo "release=$release_no"
    echo "html_url=$html_url"
=======
    echo "non_native_pkg=$non_native_pkg"
    echo "release=$release_no"
    echo "html_url=$html_url"
    echo "appimage_url=$appimage_url"
>>>>>>> 20e77c9 (feat: add native and non-native AppImage/source Fedora RPM packages and automation)
} >> "$GITHUB_OUTPUT"
