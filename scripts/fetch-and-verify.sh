#!/usr/bin/env bash
# fetch-and-verify.sh — seçilen upstream varligini indirir ve SHA256 ile
# bütünlük dogrular; varsa .zsync fark-indirme dosyasini da alir
# (sonradan RPM paketine gömülüp kullaniciya kota tasarrufu saglanir).
#
# Copyrights 2026 (c) universish (Saffet Yavuz)
# 
# Gerekli çevre degiskenleri: ARCH, ASSET_URL, ASSET_FMT, VERSION
# Opsiyonel: SHA_URL, ZSYNC_URL
set -euo pipefail
: "${ARCH:?ARCH gerekli}" "${ASSET_URL:?ASSET_URL gerekli}" \
  "${ASSET_FMT:?ASSET_FMT gerekli}" "${VERSION:?VERSION gerekli}"

fname=$(basename "$ASSET_URL")
mkdir -p "dist/$ARCH"

echo "::group::İndirme: $fname"
curl -fL --retry 3 --retry-delay 5 -o "dist/$ARCH/$fname" "$ASSET_URL"
ls -lh "dist/$ARCH/$fname"

# --- SHA256 bütünlük kontrolü (zorunlu adim) ---
if [ -n "${SHA_URL:-}" ]; then
    curl -fsSL -o "dist/$ARCH/SHA256SUMS" "$SHA_URL"
    echo "Upstream SHA256 listesi:"
    cat "dist/$ARCH/SHA256SUMS"
    expected=$(awk -v f="$fname" 'index($0, f) {print $1; exit}' "dist/$ARCH/SHA256SUMS")
    if [ -z "$expected" ]; then
        # Dosya adi satirda geçmiyorsa tek satirlik özet dosyasi varsay.
        expected=$(awk 'NF {print $1; exit}' "dist/$ARCH/SHA256SUMS")
    fi
    echo "$expected  dist/$ARCH/$fname" | sha256sum -c - \
        || { echo "::error::SHA256 doğrulaması başarısız: $fname"; exit 1; }
    echo "SHA256 doğrulandı: $expected"
else
    echo "::warning::Upstream SHA256 dosyası bulunamadı; yalnızca TLS bütünlüğüne güvenildi."
fi

# --- zsync (opsiyonel; RPM içine gömülecek ve veri tasarrufu sağlayacak) ---
if [ -n "${ZSYNC_URL:-}" ]; then
    # Zsync sunucuda yoksa veya 404 dönerse hata vermeden atlansın.
    curl -fL --retry 3 --retry-delay 2 -o "dist/$ARCH/$fname.zsync" "$ZSYNC_URL" \
        || echo "::warning::zsync dosyası Github Release'de bulunamadı (atlaniyor)."
else
    # Eğer doğrudan url verilmediyse dosya adından türetmeyi dene
    curl -fL --retry 2 -o "dist/$ARCH/$fname.zsync" "${ASSET_URL}.zsync" \
        || echo "::warning::varsayilan zsync dosyasi da bulunamadi."
fi
echo "::endgroup::"

{
    echo "fname=$fname"
    echo "size=$(stat -c%s "dist/$ARCH/$fname")"
} >> "$GITHUB_OUTPUT"
