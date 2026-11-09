#!/usr/bin/env bash
# Download and extract official FreeCAD AppImage to build a non-native SRPM.
set -euo pipefail
: "${PKG:?PKG is required}" "${VERSION:?VERSION is required}" "${RELEASE:?RELEASE is required}"
: "${APPIMAGE_URL:?APPIMAGE_URL is required}"

rm -rf build SRPMS rpmbuild squashfs-root
mkdir -p build SRPMS

echo "=== Downloading AppImage ==="
wget -q "$APPIMAGE_URL" -O freecad.AppImage
chmod +x freecad.AppImage

echo "=== Extracting AppImage ==="
./freecad.AppImage --appimage-extract >/dev/null

echo "=== Creating payload tarball ==="
tar -C squashfs-root -czf freecad-appimage-payload.tar.gz .

sed -e "s/@VERSION@/${VERSION}/g" \
    -e "s/@RELEASE@/${RELEASE}/g" \
    "$PKG.spec" > "build/$PKG.spec"

rpmbuild -bs "build/$PKG.spec" \
    --define "_topdir $PWD/rpmbuild" \
    --define "_sourcedir $PWD" \
    --define "_srcrpmdir $PWD/SRPMS"

ls -lh SRPMS/*.src.rpm
