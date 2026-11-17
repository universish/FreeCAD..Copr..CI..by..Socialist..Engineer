#!/usr/bin/env bash
# Build a two-architecture non-native SRPM from verified normalized payloads.
set -euo pipefail
: "${PKG:?PKG is required}" "${VERSION:?VERSION is required}" "${RELEASE:?RELEASE is required}"
: "${PAYLOAD_ROOT:=${PWD}/payload}"
: "${SPEC_FILE:=${PKG}.spec}"

[[ -f "$SPEC_FILE" ]] || { echo "Spec not found: $SPEC_FILE" >&2; exit 1; }
rm -rf build SRPMS rpmbuild
mkdir -p build SRPMS

for arch in x86_64 aarch64; do
    payload="$PAYLOAD_ROOT/$arch"
    [[ -d "$payload" ]] || { echo "Normalized payload missing: $payload" >&2; exit 1; }
    [[ -x "$payload/AppRun" && -s "$payload/freecad-icon.svg" ]] || {
        echo "Payload $payload must contain executable AppRun and freecad-icon.svg" >&2
        exit 1
    }
    tar -C "$payload" -czf "freecad-payload-$arch.tar.gz" .
done

sed -e "s/@VERSION@/${VERSION}/g" \
    -e "s/@RELEASE@/${RELEASE}/g" \
    "$SPEC_FILE" > "build/$PKG.spec"

rpmbuild -bs "build/$PKG.spec" \
    --define "_topdir $PWD/rpmbuild" \
    --define "_sourcedir $PWD" \
    --define "_srcrpmdir $PWD/SRPMS"

ls -lh SRPMS/*.src.rpm
