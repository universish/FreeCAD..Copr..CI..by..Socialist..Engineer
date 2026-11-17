#!/usr/bin/env bash
# Select the latest stable or prerelease source tag. Binary release assets are
# intentionally irrelevant: Copr builds from the matching Git source checkout.
set -euo pipefail

STATE_DIR="${STATE_DIR:-state}"
FORCE_VERSION="${FORCE_VERSION:-}"
FORCE_CHANNEL="${FORCE_CHANNEL:-auto}"
API="https://api.github.com/repos/FreeCAD/FreeCAD/releases"

is_candidate_tag() { [[ "${1,,}" =~ (rc[0-9]+|beta|alpha|pre) ]]; }
is_weekly_tag() { [[ "${1,,}" == weekly-* || "${1,,}" == *weekly* ]]; }
classify() {
    local tag="$1" prerelease="$2"
    if [[ "$prerelease" == true ]] || is_candidate_tag "$tag"; then echo candidate; else echo stable; fi
}

latest_release_for_channel() {
    local wanted="$1" page batch item tag candidate
    for page in $(seq 1 10); do
        batch=$(curl -fsSL -H 'Accept: application/vnd.github+json' "$API?per_page=100&page=$page")
        [[ $(jq 'length' <<<"$batch") -eq 0 ]] && break
        while IFS= read -r item; do
            tag=$(jq -r '.tag_name' <<<"$item")
            is_weekly_tag "$tag" && continue
            candidate=$(classify "$tag" "$(jq -r '.prerelease' <<<"$item")")
            if [[ "$candidate" == "$wanted" ]]; then
                printf '%s' "$item"
                return 0
            fi
        done < <(jq -c '.[]' <<<"$batch")
    done
    return 1
}

asset_for_arch() {
    local release_json="$1" arch="$2" version ext item asset_name checksum_url
    version=$(jq -r '.tag_name' <<<"$release_json")
    version="${version#v}"
    version="${version#V}"
    for ext in rpm deb AppImage; do
        item=$(jq -c --arg arch "$arch" --arg ext "$ext" --arg version "$version" '
            [ .assets[]?
              | select(.name | startswith("FreeCAD_" + $version + "-Linux-" + $arch))
              | select(.name | test("(?i)^FreeCAD_.*-Linux-" + $arch + "(-py[0-9]+)?\\." + $ext + "$"))
              | select(.name | test("weekly"; "i") | not)
            ] | sort_by([if (.name | test("(?i)-py[0-9]+\\.")) then 1 else 0 end, .name]) | .[0] // empty
        ' <<<"$release_json")
        if [[ -n "$item" ]]; then
            asset_name=$(jq -r '.name' <<<"$item")
            checksum_url=$(jq -r --arg checksum "${asset_name}-SHA256.txt" \
                '.assets[]? | select(.name == $checksum) | .browser_download_url' \
                <<<"$release_json" | head -n 1)
            jq -c --arg checksum_url "$checksum_url" --arg format "$ext" \
                '. + {format:$format, checksum_url:$checksum_url}' <<<"$item"
            return 0
        fi
    done
    return 1
}

state_for_package() {
    local package="$1" mode="$2" version="$3" release_json="$4" digest_x86="${5:-}" digest_arm="${6:-}"
    local file="$STATE_DIR/$package.json" old_version='' old_release=0 old_mode="$mode"
    local old_digest_x86='' old_digest_arm='' changed=false next_release=1
    if [[ -f "$file" ]]; then
        old_version=$(jq -r '.version // ""' "$file")
        old_release=$(jq -r '.release // 0' "$file")
        old_mode=$(jq -r --arg mode "$mode" '.packaging_mode // $mode' "$file")
        old_digest_x86=$(jq -r '.x86_64_digest // .assets.x86_64.digest // ""' "$file")
        old_digest_arm=$(jq -r '.aarch64_digest // .assets.aarch64.digest // ""' "$file")
    fi
    if [[ "$old_version" != "$version" ]]; then
        changed=true; next_release=1
    elif [[ "$old_mode" != "$mode" || "${GITHUB_EVENT_NAME:-}" == workflow_dispatch || -n "$FORCE_VERSION" ]]; then
        changed=true; next_release=$((old_release + 1))
    elif [[ "$mode" == non-native && ( "$old_digest_x86" != "$digest_x86" || "$old_digest_arm" != "$digest_arm" ) ]]; then
        changed=true; next_release=$((old_release + 1))
    else
        next_release=$old_release
    fi
    printf '%s %s\n' "$changed" "$next_release"
}

if [[ "$FORCE_CHANNEL" != auto && "$FORCE_CHANNEL" != stable && "$FORCE_CHANNEL" != candidate ]]; then
    echo "::error::Invalid channel: $FORCE_CHANNEL"; exit 1
fi

stable_release=''
candidate_release=''
if [[ -n "$FORCE_VERSION" ]]; then
    requested_tag="${FORCE_VERSION#refs/tags/}"
    [[ "$requested_tag" =~ ^[vV]?[A-Za-z0-9][A-Za-z0-9._+-]*$ ]] || {
        echo "::error::Invalid release tag: $FORCE_VERSION"; exit 1;
    }
    if [[ "${requested_tag,,}" == weekly-* || "${requested_tag,,}" == *weekly* ]]; then
        echo "::error::Weekly builds are not packaged."; exit 1
    fi
    alternate_tag="$requested_tag"
    if [[ "$requested_tag" == [vV]* ]]; then alternate_tag="${requested_tag:1}"; else alternate_tag="v$requested_tag"; fi
    forced_release=''
    for lookup_tag in "$requested_tag" "$alternate_tag"; do
        forced_release=$(curl -fsSL -H 'Accept: application/vnd.github+json' "$API/tags/$lookup_tag" 2>/dev/null) || true
        [[ -n "$forced_release" ]] && break
    done
    [[ -n "$forced_release" ]] || { echo "::error::Release tag not found: $requested_tag (or $alternate_tag)"; exit 1; }
    tag=$(jq -r '.tag_name' <<<"$forced_release")
    forced_channel=$(classify "$tag" "$(jq -r '.prerelease' <<<"$forced_release")")
    if [[ "$FORCE_CHANNEL" != auto && "$FORCE_CHANNEL" != "$forced_channel" ]]; then
        echo "::error::Tag $tag belongs to $forced_channel, not $FORCE_CHANNEL"; exit 1
    fi
    if [[ "$forced_channel" == stable ]]; then stable_release="$forced_release"; else candidate_release="$forced_release"; fi
else
    if [[ "$FORCE_CHANNEL" == auto || "$FORCE_CHANNEL" == stable ]]; then
        stable_release=$(latest_release_for_channel stable) || true
    fi
    if [[ "$FORCE_CHANNEL" == auto || "$FORCE_CHANNEL" == candidate ]]; then
        candidate_release=$(latest_release_for_channel candidate) || true
    fi
fi

process_channel() {
    local channel_name="$1" release_json="$2" native_package="$3" non_native_package="$4"
    local tag version html_url x86_json arm_json native_changed native_release non_native_changed non_native_release
    local arch asset_var field value asset_digest
    [[ -n "$release_json" ]] || {
        printf -v "${channel_name}_enabled" '%s' false
        printf -v "${channel_name}_native_changed" '%s' false
        printf -v "${channel_name}_non_native_changed" '%s' false
        return 0
    }

    tag=$(jq -r '.tag_name' <<<"$release_json")
    version="${tag#v}"
    html_url=$(jq -r '.html_url' <<<"$release_json")
    x86_json=$(asset_for_arch "$release_json" x86_64) || {
        echo "::error::No supported RPM/DEB/AppImage for x86_64 at $tag"; return 1;
    }
    arm_json=$(asset_for_arch "$release_json" aarch64) || {
        echo "::error::No supported RPM/DEB/AppImage for aarch64 at $tag"; return 1;
    }
    local x86_digest arm_digest
    x86_digest=$(jq -r '.digest // "" | sub("^sha256:"; "")' <<<"$x86_json")
    arm_digest=$(jq -r '.digest // "" | sub("^sha256:"; "")' <<<"$arm_json")
    read -r native_changed native_release < <(state_for_package "$native_package" native-source "$version" "$release_json")
    read -r non_native_changed non_native_release < <(state_for_package "$non_native_package" non-native "$version" "$release_json" "$x86_digest" "$arm_digest")

    printf -v "${channel_name}_enabled" '%s' true
    printf -v "${channel_name}_tag" '%s' "$tag"
    printf -v "${channel_name}_version" '%s' "$version"
    printf -v "${channel_name}_html_url" '%s' "$html_url"
    printf -v "${channel_name}_native_pkg" '%s' "$native_package"
    printf -v "${channel_name}_non_native_pkg" '%s' "$non_native_package"
    printf -v "${channel_name}_native_changed" '%s' "$native_changed"
    printf -v "${channel_name}_native_release" '%s' "$native_release"
    printf -v "${channel_name}_non_native_changed" '%s' "$non_native_changed"
    printf -v "${channel_name}_non_native_release" '%s' "$non_native_release"
    for arch in x86_64 aarch64; do
        if [[ "$arch" == x86_64 ]]; then asset_var="$x86_json"; else asset_var="$arm_json"; fi
        printf -v "${channel_name}_${arch}_url" '%s' "$(jq -r '.browser_download_url' <<<"$asset_var")"
        printf -v "${channel_name}_${arch}_digest" '%s' "$(jq -r '.digest // "" | sub("^sha256:"; "")' <<<"$asset_var")"
        printf -v "${channel_name}_${arch}_checksum_url" '%s' "$(jq -r '.checksum_url' <<<"$asset_var")"
        printf -v "${channel_name}_${arch}_format" '%s' "$(jq -r '.format' <<<"$asset_var")"
    done
}

process_channel stable "$stable_release" freecad freecad-non-native
process_channel candidate "$candidate_release" freecad-candidate freecad-candidate-non-native
if [[ "$stable_enabled" != true && "$candidate_enabled" != true ]]; then
    echo "::error::No supported stable or candidate release was found."; exit 1
fi

changed=false
native_items='[]'
non_native_items='[]'
payload_items='[]'
for status in "$stable_native_changed" "$stable_non_native_changed" "$candidate_native_changed" "$candidate_non_native_changed"; do
    [[ "${status:-false}" == true ]] && changed=true
done

for channel_name in stable candidate; do
    enabled_var="${channel_name}_enabled"
    native_changed_var="${channel_name}_native_changed"
    non_native_changed_var="${channel_name}_non_native_changed"
    native_pkg_var="${channel_name}_native_pkg"
    non_native_pkg_var="${channel_name}_non_native_pkg"
    version_var="${channel_name}_version"
    tag_var="${channel_name}_tag"
    html_url_var="${channel_name}_html_url"
    native_release_var="${channel_name}_native_release"
    non_native_release_var="${channel_name}_non_native_release"
    [[ "${!enabled_var:-false}" == true ]] || continue
    if [[ "${!native_changed_var:-false}" == true ]]; then
        item=$(jq -cn \
            --arg channel "$channel_name" \
            --arg pkg "${!native_pkg_var}" \
            --arg version "${!version_var}" \
            --arg tag "${!tag_var}" \
            --arg release "${!native_release_var}" \
            --arg html_url "${!html_url_var}" \
            '{channel:$channel,pkg:$pkg,version:$version,tag:$tag,release:$release,html_url:$html_url}')
        native_items=$(jq -cn --argjson items "$native_items" --argjson item "$item" '$items + [$item]')
    fi
    if [[ "${!non_native_changed_var:-false}" == true ]]; then
        x86_url_var="${channel_name}_x86_64_url"
        x86_format_var="${channel_name}_x86_64_format"
        x86_digest_var="${channel_name}_x86_64_digest"
        arm_url_var="${channel_name}_aarch64_url"
        arm_format_var="${channel_name}_aarch64_format"
        arm_digest_var="${channel_name}_aarch64_digest"
        item=$(jq -cn \
            --arg channel "$channel_name" \
            --arg pkg "${!non_native_pkg_var}" \
            --arg version "${!version_var}" \
            --arg tag "${!tag_var}" \
            --arg release "${!non_native_release_var}" \
            --arg html_url "${!html_url_var}" \
            --arg x86_url "${!x86_url_var}" \
            --arg x86_format "${!x86_format_var}" \
            --arg x86_digest "${!x86_digest_var}" \
            --arg arm_url "${!arm_url_var}" \
            --arg arm_format "${!arm_format_var}" \
            --arg arm_digest "${!arm_digest_var}" \
            '{channel:$channel,pkg:$pkg,version:$version,tag:$tag,release:$release,html_url:$html_url,x86_64_url:$x86_url,x86_64_format:$x86_format,x86_64_digest:$x86_digest,aarch64_url:$arm_url,aarch64_format:$arm_format,aarch64_digest:$arm_digest}')
        non_native_items=$(jq -cn --argjson items "$non_native_items" --argjson item "$item" '$items + [$item]')
        for arch in x86_64 aarch64; do
            url_var="${channel_name}_${arch}_url"
            format_var="${channel_name}_${arch}_format"
            checksum_var="${channel_name}_${arch}_checksum_url"
            digest_var="${channel_name}_${arch}_digest"
            if [[ "$arch" == aarch64 ]]; then runner=ubuntu-24.04-arm; else runner=ubuntu-latest; fi
            item=$(jq -cn \
                --arg channel "$channel_name" \
                --arg arch "$arch" \
                --arg runner "$runner" \
                --arg pkg "${!non_native_pkg_var}" \
                --arg version "${!version_var}" \
                --arg url "${!url_var}" \
                --arg format "${!format_var}" \
                --arg checksum "${!checksum_var}" \
                --arg digest "${!digest_var}" \
                '{channel:$channel,arch:$arch,runner:$runner,pkg:$pkg,version:$version,url:$url,format:$format,checksum_url:$checksum,digest:$digest}')
            payload_items=$(jq -cn --argjson items "$payload_items" --argjson item "$item" '$items + [$item]')
        done
    fi
done

native_matrix=$(jq -cn --argjson include "$native_items" '{include:$include}')
non_native_matrix=$(jq -cn --argjson include "$non_native_items" '{include:$include}')
payload_matrix=$(jq -cn --argjson include "$payload_items" '{include:$include}')
native_changed=$(jq -r 'length > 0' <<<"$native_items")
non_native_changed=$(jq -r 'length > 0' <<<"$non_native_items")

# Keep generic outputs temporarily for compatibility with callers during rollout.
selected_channel=stable
if [[ "$FORCE_CHANNEL" == candidate || ( -n "$FORCE_VERSION" && "$candidate_enabled" == true ) || "$stable_enabled" != true ]]; then
    selected_channel=candidate
fi
eval "tag=\${${selected_channel}_tag:-}"
eval "version=\${${selected_channel}_version:-}"
eval "html_url=\${${selected_channel}_html_url:-}"
eval "pkg=\${${selected_channel}_native_pkg:-}"
eval "release_no=\${${selected_channel}_native_release:-}"
non_native_pkg="${pkg}-non-native"
[[ "$selected_channel" == candidate ]] && non_native_pkg=freecad-candidate-non-native

printf 'Stable: %s (%s); candidate: %s (%s); any_changed=%s\n' \
    "${stable_tag:-none}" "${stable_native_release:-0}" \
    "${candidate_tag:-none}" "${candidate_native_release:-0}" "$changed"
{
    echo "changed=$changed"
    echo "native_changed=$native_changed"
    echo "non_native_changed=$non_native_changed"
    echo "native_matrix=$native_matrix"
    echo "non_native_matrix=$non_native_matrix"
    echo "payload_matrix=$payload_matrix"
    echo "channel=$selected_channel"
    echo "tag=$tag"
    echo "version=$version"
    echo "pkg=$pkg"
    echo "non_native_pkg=$non_native_pkg"
    echo "release=$release_no"
    echo "html_url=$html_url"
    for channel_name in stable candidate; do
        for field in enabled tag version html_url native_pkg non_native_pkg native_changed native_release non_native_changed non_native_release x86_64_url x86_64_digest x86_64_checksum_url x86_64_format aarch64_url aarch64_digest aarch64_checksum_url aarch64_format; do
            var="${channel_name}_${field}"
            echo "${var}=${!var:-}"
        done
    done
} >> "$GITHUB_OUTPUT"
