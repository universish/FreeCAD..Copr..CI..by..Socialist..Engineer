#!/usr/bin/env bash
# repackage.sh — indirilen .rpm/.deb/.AppImage dosyasini açar ve Copr RPM'ine
# gömülecek normalize edilmis filesystem agacini üretir:
#
#   payload/$ARCH/opt/$PKG/            (uygulamanin tamamı, gömülü çalisma zamani)
#   payload/$ARCH/opt/$PKG/updates/    (zsync fark-indirme dosyalari)
#   payload/$ARCH/usr/bin/$BIN         (başlatici sarmalayici)
#   payload/$ARCH/usr/share/applications/$PKG.desktop
#   payload/$ARCH/usr/share/icons/hicolor/...
#
# Not: AppImage açimi --appimage-extract ile yapilir ve FUSE GEREKTIRMEZ;
# dogru mimarideki GitHub runner'inda (x86_64 / arm64) çalistigi için
# squashfs offset hesaplamaya gerek kalmaz.
set -euo pipefail
: "${ARCH:?ARCH gerekli}" "${PKG:?PKG gerekli}" "${BIN:?BIN gerekli}" \
  "${FNAME:?FNAME gerekli}" "${ASSET_FMT:?ASSET_FMT gerekli}"

SRC="$(realpath "dist/$ARCH/$FNAME")"
ROOT="payload/$ARCH"
rm -rf work "$ROOT"
mkdir -p work "$ROOT/opt" "$ROOT/usr/bin" "$ROOT/usr/share/applications" "$ROOT/usr/share/icons"

echo "::group::Açma: $FNAME ($ASSET_FMT)"
case "$ASSET_FMT" in
    AppImage)
        chmod +x "$SRC"
        (cd work && "$SRC" --appimage-extract)
        APPROOT="work/squashfs-root"
        ;;
    rpm)
        (cd work && rpm2cpio "$SRC" | cpio -idm --quiet)
        APPROOT="work"
        ;;
    deb)
        (cd work && ar x "$SRC" && tar -xf data.tar.*)
        APPROOT="work"
        ;;
    *)
        echo "::error::Bilinmeyen biçim: $ASSET_FMT"; exit 1 ;;
esac
[ -d "$APPROOT" ] || { echo "::error::Açma başarısız"; exit 1; }
echo "::endgroup::"

# Uygulama kökünü /opt/$PKG altına taşi.
mkdir -p "$ROOT/opt/$PKG"
cp -a "$APPROOT"/. "$ROOT/opt/$PKG/"

# Başlatici: AppRun varsa o (ortam degiskenlerini kendi kurar), yoksa elle sarmala.
if [ -x "$ROOT/opt/$PKG/AppRun" ]; then
    {
        echo '#!/bin/sh'
        echo "# $PKG başlatıcısı — gömülü çalışma zamanını kullanır."
        echo 'exec /opt/'"$PKG"'/AppRun "$@"'
    } > "$ROOT/usr/bin/$BIN"
else
    mainbin=$(find "$ROOT/opt/$PKG/usr/bin" -maxdepth 1 -type f -name 'FreeCAD*' 2>/dev/null | sort | head -n1)
    [ -n "$mainbin" ] || { echo "::error::Ana binary bulunamadı (usr/bin/FreeCAD*)"; exit 1; }
    rel="${mainbin#"$ROOT/opt/$PKG/"}"
    {
        echo '#!/bin/sh'
        echo "# $PKG başlatıcısı — gömülü çalışma zamanını kullanır."
        echo 'HERE=/opt/'"$PKG"
        echo 'export LD_LIBRARY_PATH="$HERE/usr/lib:$HERE/usr/lib64:$HERE/usr/lib/x86_64-linux-gnu:$HERE/usr/lib/aarch64-linux-gnu:$HERE:$LD_LIBRARY_PATH"'
        echo 'export QT_PLUGIN_PATH="$HERE/usr/lib/qt6/plugins:$HERE/usr/lib/x86_64-linux-gnu/qt6/plugins:$HERE/usr/lib/aarch64-linux-gnu/qt6/plugins"'
        echo 'export XDG_DATA_DIRS="$HERE/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"'
        echo 'exec "$HERE/'"$rel"'" "$@"'
    } > "$ROOT/usr/bin/$BIN"
fi
chmod 755 "$ROOT/usr/bin/$BIN"

# Masaüstü kaydi: upstream *.desktop dosyasini bul, Exec/Icon/satirlarini yeniden yaz.
desktop_src=$(find "$APPROOT" -iname '*freecad*.desktop' ! -path '*/opt/*' | head -n1)
if [ -n "$desktop_src" ]; then
    sed -e "s|^Exec=.*|Exec=$BIN %F|" \
        -e "s|^Icon=.*|Icon=$PKG|" \
        -e "s|^TryExec=.*|TryExec=$BIN|" \
        "$desktop_src" > "$ROOT/usr/share/applications/$PKG.desktop"
else
    {
        echo "[Desktop Entry]"
        echo "Type=Application"
        echo "Name=$PKG"
        echo "Exec=$BIN %F"
        echo "Icon=$PKG"
        echo "Terminal=false"
        echo "Categories=Graphics;Engineering;CAD;"
        echo "MimeType=model/step;model/stl;application/x-extension-fcstd;"
    } > "$ROOT/usr/share/applications/$PKG.desktop"
fi

# Simge: mümkün olan en büyük upstream simgesini sistem simge temasina kopyala.
icon_src=$(find "$APPROOT" \( -iname '*freecad*.png' -o -iname 'org.freecad*.svg' \) | sort | tail -n1)
if [ -n "$icon_src" ]; then
    case "$icon_src" in
        *.svg) dest_dir="$ROOT/usr/share/icons/hicolor/scalable/apps"; ext="svg" ;;
        *)     dest_dir="$ROOT/usr/share/icons/hicolor/256x256/apps"; ext="png" ;;
    esac
    mkdir -p "$dest_dir"
    cp "$icon_src" "$dest_dir/$PKG.$ext"
else
    echo "::warning::Upstream simge bulunamadı; simge adımı atlandı."
fi

# --- Shebang temizligi -----------------------------------------------------
# Upstream conda-forge ikilileri, çalistirilabilir betiklere derleme makinesinin
# yollarini shebang olarak gömer ('/home/conda/.../bin/python3.11', yer yer
# '#!/usr/bin/env python' gibi belirsiz kayitlar). Bunlar hedefsizdir
# (runtime'da zaten çalismaz) ve Fedora/Red Hat ailesinin brp-mangle-shebangs
# denetiminde build'i HATA ile düşürür. Python shebang'lerini yükün kendi
# python3'une (varsa) yoksa env python3'e yönlendir. Böylece spec'te denetim
# kapali olsa bile payload temiz olur.
PYBIN="/opt/$PKG/usr/bin/python3"
[ -x "$ROOT$PYBIN" ] || PYBIN="/usr/bin/env python3"
find "$ROOT/opt/$PKG" -type f -perm /111 | while IFS= read -r f; do
    IFS= read -r first < "$f" 2>/dev/null || continue
    case "$first" in
        '#!'*python*) sed -i "1s|.*|#!$PYBIN|" "$f" ;;
    esac
done

# Lisans dosyalarini pakete dahil et.
find "$ROOT/opt/$PKG" -maxdepth 2 -iname 'LICENSE*' -o -maxdepth 2 -iname 'COPYING*' 2>/dev/null | head -5 || true

# zsync fark-indirme dosyasini pakete göm (kullanici update komutu ile kotadan tasarruf eder).
if ls dist/$ARCH/*.zsync 1> /dev/null 2>&1; then
    mkdir -p "$ROOT/opt/$PKG/updates"
    cp dist/$ARCH/*.zsync "$ROOT/opt/$PKG/updates/"
    echo "zsync fark-indirme dosyasi pakete eklendi."
else
    echo "::warning::Paketlenecek zsync dosyasi dist klasöründe bulunamadi."
fi

echo "Payload özeti ($ARCH):"
du -sh "$ROOT/opt/$PKG"
find "$ROOT" -maxdepth 4 -type f | sort | head -30
