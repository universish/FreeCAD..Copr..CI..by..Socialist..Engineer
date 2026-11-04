#!/usr/bin/env bash
# detect-release.sh
# FreeCAD/FreeCAD GitHub releases icindeki istenen KANALA uygun EN GUNCEL sürümü tespit eder.
#
# Copyrights 2026 (c) universish (Saffet Yavuz)
#
# SÜRÜM SINIFLARI:
#   - Kararli (stable) : etikette rc/beta/alpha gecmez, GitHub prerelease bayragi false.
#                      Paket: freecad        (binary: freecad)
#   - Aday (candidate) : <yy.XrcY> gibi ara form (beta gibi düsünülür). NE stable NE
#                      nightly'dir. Paket: freecad-candidate (binary: freecad-can)
#   - Nightly/weekly   : "weekly-" ile baslayan etiketler ve adinda "weekly" gecen
#                      varliklar TAMAMEN dislanir; ASLA paketlenmez.
#
# KANAL (FORCE_CHANNEL) KURALLARI:
#   auto      -> stable+candidate havuzunda EN GUNCEL olani seçer.
#   stable    -> YALNIZCA kararli sürümler arasindan en günceli seçer.
#   candidate -> YALNIZCA aday (rc/beta) sürümler arasindan en günceli seçer.
#
# SÜRÜM ZORLAMA (FORCE_VERSION) KURALLARI:
#   - Kanal=auto + sürüm girildi      : etiket candidate ise candidate, stable ise
#                                       stable kanali otomatik seçilir.
#   - Kanal=stable + candidate etiketi girildi   -> HATA (uyusmazlik).
#   - Kanal=candidate + stable etiketi girildi   -> HATA (uyusmazlik).
#   - Nightly/weekly etiketi girildi             -> HATA (desteklenmez).
#
# Varlik seçim önceliği (her mimari icin): 1) .rpm  2) .deb  3) .AppImage
#
# Paketleme numarasi kurali:
#   - Sürüm degisti -> paketleme numarasi 1
#   - Ayni sürüm tekrar paketleniyor -> copr'daki mevcut numara + 1
#   (Bilgi state/<pkg>.json dosyasinda tutulur; tek yazar oldugumuz icin
#    concurrency kilidi sayesinde iki is akisi ayni sayaci okuyamaz.)
#
# Ciktilar $GITHUB_OUTPUT dosyasina yazilir.
set -euo pipefail

STATE_DIR="${STATE_DIR:-state}"
FORCE_VERSION="${FORCE_VERSION:-}"
FORCE_CHANNEL="${FORCE_CHANNEL:-auto}"    # auto | stable | candidate
API="https://api.github.com/repos/FreeCAD/FreeCAD/releases"

echo "::group::Upstream sürüm tespiti"

# --------------------------------------------------- etiket siniflandirma ----
is_candidate_tag() {
    # <yy.XrcY> ara formu + klasik beta/alpha/pre ibareleri -> candidate
    echo "$1" | grep -qiE '(rc[0-9]+|beta|alpha|pre)'
}

is_weekly_tag() {
    case "$1" in
        weekly-*) return 0 ;;
        *) return 1 ;;
    esac
}

# Tek bir release JSON nesnesinden kanali tespit eder: stable | candidate
classify_release() {
    local tag prerelease
    tag=$(echo "$1" | jq -r '.tag_name')
    prerelease=$(echo "$1" | jq -r '.prerelease')
    if [ "$prerelease" = "true" ] || is_candidate_tag "$tag"; then
        echo "candidate"
    else
        echo "stable"
    fi
}

# ------------------------------------------------------------- sürümü bul ----
if [ -n "$FORCE_VERSION" ]; then
    # Manuel tetik: belirtilen etiket dogrudan alinir.
    tag="${FORCE_VERSION#v}"

    if is_weekly_tag "$tag"; then
        echo "::error::'$tag' bir nightly/weekly sürümüdür; desteklenmez."
        exit 1
    fi

    release=$(curl -fsSL -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "$API/tags/$tag" 2>/dev/null) \
        || { echo "::error::'$tag' etiketli sürüm GitHub'da bulunamadı."; exit 1; }

    detected=$(classify_release "$release")

    # Kanal/sürüm uyusmazlik denetimi
    if [ "$FORCE_CHANNEL" = "auto" ]; then
        channel="$detected"
    elif [ "$FORCE_CHANNEL" = "stable" ] && [ "$detected" = "candidate" ]; then
        echo "::error::'$tag' bir candidate (rc/beta) sürümüdür ama kanal 'stable' seçildi."
        echo "::error::Kanalı 'candidate' seçin ya da 'auto' kullanın."
        exit 1
    elif [ "$FORCE_CHANNEL" = "candidate" ] && [ "$detected" = "stable" ]; then
        echo "::error::'$tag' bir stable sürümüdür ama kanal 'candidate' seçildi."
        echo "::error::Kanalı 'stable' seçin ya da 'auto' kullanın."
        exit 1
    else
        channel="$FORCE_CHANNEL"
    fi
else
    # Otomatik: istenen kanala uygun EN GUNCEL sürümü bul.
    # GitHub releases API'si en yeniden eskiye siralar; sayfalari geziyoruz.
    release=""
    for page in 1 2 3 4 5 6 8 10; do
        batch=$(curl -fsSL -H "Accept: application/vnd.github+json" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            "$API?per_page=25&page=$page")
        [ "$(echo "$batch" | jq 'length')" -eq 0 ] && break

        while IFS= read -r rel; do
            [ -z "$rel" ] && continue
            rtag=$(echo "$rel" | jq -r '.tag_name')
            is_weekly_tag "$rtag" && continue
            rch=$(classify_release "$rel")
            if [ "$FORCE_CHANNEL" = "auto" ] || [ "$FORCE_CHANNEL" = "$rch" ]; then
                release="$rel"
                break 2
            fi
        done < <(echo "$batch" | jq -c '.[]')
    done

    if [ -z "$release" ]; then
        echo "::error::Kanal '$FORCE_CHANNEL' için uygun upstream sürümü bulunamadı."
        exit 1
    fi
    tag=$(echo "$release" | jq -r '.tag_name')
    channel=$(classify_release "$release")
fi

version="${tag#v}"
title=$(echo "$release" | jq -r '.name')
html_url=$(echo "$release" | jq -r '.html_url')
assets=$(echo "$release" | jq -c '[.assets[] | {name, url: .browser_download_url}]')

echo "Etiket   : $tag"
echo "Sürüm    : $version"
echo "Başlık   : $title"
echo "Sayfa    : $html_url"

if [ "$channel" = "stable" ]; then
    pkg="freecad"; bin="freecad"
else
    pkg="freecad-candidate"; bin="freecad-can"
fi
echo "Kanal    : $channel  ->  paket: $pkg  (binary: $bin)"

# ------------------------------------------------------ varlik seçimi --------
# $1=mimari  $2=uzanti (rpm|deb|AppImage)
pick_asset() {
    echo "$assets" | jq -r --arg a "$1" --arg e "$2" '
        map(select(.name | contains("weekly") | not)
            | select(.name | test("Linux-" + $a + "(-py[0-9]+)?\\." + $e + "$")))
        | sort_by(.name)
        | .[0].url // empty'
}

# $1=varlik dosya adi  $2=ek (örn. "-SHA256.txt" veya ".zsync")
find_aux() {
    echo "$assets" | jq -r --arg n "$1" '
        .[] | select(.name == $n) | .url // empty'
}

for arch in x86_64 aarch64; do
    url=""; fmt=""
    for ext in rpm deb AppImage; do
        url=$(pick_asset "$arch" "$ext")
        if [ -n "$url" ]; then fmt="$ext"; break; fi
    done
    if [ -z "$url" ]; then
        echo "::error::${arch} için .rpm/.deb/.AppImage varlığı bulunamadı (tag: $tag)"
        exit 1
    fi
    fname=$(basename "$url")
    sha_url=$(find_aux "${fname}-SHA256.txt")
    zsync_url=$(find_aux "${fname}.zsync")
    echo "$arch -> $fmt : $fname"
    eval "${arch}_url='$url'"
    eval "${arch}_fmt='$fmt'"
    eval "${arch}_sha='$sha_url'"
    eval "${arch}_zsync='$zsync_url'"
done

# --------------------------------------------- degisim + paketleme numarasi --
state_file="$STATE_DIR/$pkg.json"
prev_version=""; prev_release=0
if [ -f "$state_file" ]; then
    prev_version=$(jq -r '.version // ""' "$state_file")
    prev_release=$(jq -r '.release // 0' "$state_file")
fi

if [ -n "$FORCE_VERSION" ] || [ "$prev_version" != "$version" ]; then
    changed="true"; release_no=1
else
    changed="false"; release_no=$((prev_release + 1))
fi
echo "Önceki : $prev_version-$prev_release  ->  Yeni: $version-$release_no (changed=$changed)"
echo "::endgroup::"

# ------------------------------------------------------------- çiktilar ------
{
    echo "changed=$changed"
    echo "version=$version"
    echo "tag=$tag"
    echo "channel=$channel"
    echo "pkg=$pkg"
    echo "bin=$bin"
    echo "release=$release_no"
    echo "html_url=$html_url"
    echo "x86_64_url=$x86_64_url"
    echo "x86_64_fmt=$x86_64_fmt"
    echo "x86_64_sha=$x86_64_sha"
    echo "x86_64_zsync=$x86_64_zsync"
    echo "aarch64_url=$aarch64_url"
    echo "aarch64_fmt=$aarch64_fmt"
    echo "aarch64_sha=$aarch64_sha"
    echo "aarch64_zsync=$aarch64_zsync"
} >> "$GITHUB_OUTPUT"
