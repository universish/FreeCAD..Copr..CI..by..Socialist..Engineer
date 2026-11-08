#!/usr/bin/env bash
# Build an SRPM from an initialized FreeCAD source checkout (including
# submodules). The resulting Copr build compiles it against distro libraries.
set -euo pipefail
: "${PKG:?PKG is required}" "${VERSION:?VERSION is required}" "${RELEASE:?RELEASE is required}"
: "${FREECAD_SOURCE_DIR:?FREECAD_SOURCE_DIR must point to the FreeCAD checkout}"

[[ -f "$FREECAD_SOURCE_DIR/CMakeLists.txt" ]] || {
    echo "FreeCAD source tree not found at $FREECAD_SOURCE_DIR" >&2
    exit 1
}

rm -rf build SRPMS rpmbuild
mkdir -p build SRPMS
SOURCE_ARCHIVE="$PWD/freecad-sources.tar.gz"

# Archive tracked source files and checked-out submodules, excluding Git
# metadata. -C keeps the source root at archive top level; %setup -c creates
# the versioned build directory from it.
submodules=$(git -C "$FREECAD_SOURCE_DIR" submodule status --recursive)
if grep -Eq '^[+-U]' <<<"$submodules"; then
    echo "Source checkout has uninitialized or mismatched submodules:" >&2
    printf '%s\n' "$submodules" >&2
    exit 1
fi
git -C "$FREECAD_SOURCE_DIR" ls-files --recurse-submodules -z \
    | tar -C "$FREECAD_SOURCE_DIR" --null -T - -czf "$SOURCE_ARCHIVE"

sed -e "s/@VERSION@/${VERSION}/g" \
    -e "s/@RELEASE@/${RELEASE}/g" \
    "$PKG.spec" > "build/$PKG.spec"

rpmbuild -bs "build/$PKG.spec" \
    --define "_topdir $PWD/rpmbuild" \
    --define "_sourcedir $PWD" \
    --define "_srcrpmdir $PWD/SRPMS"

ls -lh SRPMS/*.src.rpm
