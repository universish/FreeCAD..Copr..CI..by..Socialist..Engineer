#!/usr/bin/env bash
# build-srpm.sh — iki mimarinin payload'unu TEK kaynak ağacinda birleştirir
# ve Fedora spec ile Source RPM (.src.rpm) üretir.
#
# Copyrights 2026 (c) universish (Saffet Yavuz)
# 
# Kaynak ağaci yapisi:
#   $PKG-$VERSION/
#     x86_64/opt/... usr/...
#     aarch64/opt/... usr/...
#
# Spec dosyasi %install adiminda %{_arch} makrosu ile kendi mimarisinin
# payload'unu seçer; böylece tek bir SRPM Copr'da hem x86_64 hem aarch64
# chrootlarinda dogru binary üretir.
set -euo pipefail
: "${PKG:?PKG gerekli}" "${VERSION:?VERSION gerekli}" "${RELEASE:?RELEASE gerekli}"

TDIR="$PKG-$VERSION"
rm -rf build SRPMS
mkdir -p "build/$TDIR" SRPMS

for arch in x86_64 aarch64; do
    [ -d "payload/$arch" ] || { echo "::error::payload/$arch eksik"; exit 1; }
    cp -a "payload/$arch" "build/$TDIR/$arch"
done

tar -czf "$TDIR.tar.gz" -C build "$TDIR"

sed -e "s/@VERSION@/${VERSION}/g" \
    -e "s/@RELEASE@/${RELEASE}/g" \
    "$PKG.spec" > "build/$PKG.spec"

rpmbuild -bs "build/$PKG.spec" \
    --define "_topdir $PWD/rpmbuild" \
    --define "_sourcedir $PWD" \
    --define "_srcrpmdir $PWD/SRPMS"

echo "Üretilen SRPM:"
ls -lh SRPMS/
