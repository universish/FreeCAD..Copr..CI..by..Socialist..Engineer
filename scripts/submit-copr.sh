#!/usr/bin/env bash
# Submit SRPMs to Copr without duplicating an active or completed package NVR.
set -euo pipefail
: "${COPR_PROJECT:?COPR_PROJECT is required}"

owner=${COPR_PROJECT%%/*}
project=${COPR_PROJECT#*/}
[[ "$owner" != "$project" && -n "$owner" && -n "$project" ]] || {
    echo "COPR_PROJECT must be owner/project" >&2
    exit 1
}
[[ "$#" -gt 0 ]] || { echo "Pass one or more SRPM paths" >&2; exit 1; }

mapfile -t wanted < <(grep -Ev '^[[:space:]]*(#|$)' "${CHROOTS_FILE:-chroots.txt}")
(( ${#wanted[@]} > 0 )) || { echo "No Copr chroots configured" >&2; exit 1; }
copr-cli list-chroots > "${RUNNER_TEMP:-/tmp}/valid-chroots.txt"
args=()
for chroot in "${wanted[@]}"; do
    grep -Fqx "$chroot" "${RUNNER_TEMP:-/tmp}/valid-chroots.txt" || {
        echo "Configured Copr chroot is unavailable: $chroot" >&2
        exit 1
    }
    args+=(-r "$chroot")
done

WAIT_SECONDS="${COPR_BUILD_WAIT_SECONDS:-20700}"
POLL_SECONDS="${COPR_BUILD_POLL_SECONDS:-60}"
[[ "$WAIT_SECONDS" =~ ^[0-9]+$ && "$POLL_SECONDS" =~ ^[0-9]+$ ]] || {
    echo "Copr wait and poll intervals must be integer seconds" >&2
    exit 1
}
(( WAIT_SECONDS > 0 && POLL_SECONDS > 0 )) || {
    echo "Copr wait and poll intervals must be positive" >&2
    exit 1
}

fetch_builds() {
    local name="$1" response
    response=$(curl --fail --silent --show-error --retry 3 \
        --get "https://copr.fedorainfracloud.org/api_3/build/list" \
        --data-urlencode "ownername=$owner" \
        --data-urlencode "projectname=$project" \
        --data-urlencode "packagename=$name" \
        --data-urlencode 'limit=100')
    jq -e '.items | type == "array"' >/dev/null <<<"$response" || {
        echo "Copr build list response has an unexpected format" >&2
        return 1
    }
    printf '%s' "$response"
}

nvr_state() {
    local builds="$1" name="$2" nvr="$3"
    jq -r --arg name "$name" --arg nvr "$nvr" '
        [.items[]?
         | select((.source_package.name // .pkg_name // "") == $name)
         | select((.source_package.version // .pkg_version // "") == $nvr)]
        | sort_by(.id // 0) | last // empty | .state // empty
    ' <<<"$builds"
}

wait_for_nvr() {
    local name="$1" nvr="$2" deadline=$((SECONDS + WAIT_SECONDS)) builds state
    while :; do
        builds=$(fetch_builds "$name") || return 1
        state=$(nvr_state "$builds" "$name" "$nvr")
        case "$state" in
            succeeded)
                echo "Copr build passed: $name-$nvr in all configured chroots."
                return 0
                ;;
            failed|canceled|forked)
                echo "Copr build failed: $name-$nvr (state=$state)" >&2
                return 1
                ;;
            '')
                printf 'Waiting for Copr to register %s-%s\n' "$name" "$nvr"
                ;;
            *)
                printf 'Copr build in progress: %s-%s (state=%s)\n' "$name" "$nvr" "$state"
                ;;
        esac
        if (( SECONDS >= deadline )); then
            echo "Timed out waiting for Copr build: $name-$nvr" >&2
            return 1
        fi
        sleep "$POLL_SECONDS"
    done
}

for srpm in "$@"; do
    [[ -f "$srpm" ]] || { echo "SRPM not found: $srpm" >&2; exit 1; }
    read -r name version release < <(rpm -qp --qf '%{NAME} %{VERSION} %{RELEASE}\n' "$srpm")
    nvr="${version}-${release}"
    builds=$(fetch_builds "$name")
    existing=$(nvr_state "$builds" "$name" "$nvr")
    if [[ "$existing" == succeeded || "$existing" == starting || "$existing" == pending || "$existing" == running || "$existing" == importing ]]; then
        echo "Reusing existing Copr NVR $name-$nvr (state=$existing)."
    else
        copr-cli build --nowait --timeout "$WAIT_SECONDS" "${args[@]}" "$COPR_PROJECT" "$srpm"
    fi
    wait_for_nvr "$name" "$nvr"
done
