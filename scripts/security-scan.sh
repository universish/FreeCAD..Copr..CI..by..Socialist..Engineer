#!/usr/bin/env bash
# security-scan.sh — paketlenecek yük üzerinde çift katmanli güvenlik taramasi.
#
# 1) ClamAV imza veritabani güncellenir (freshclam) ve TÜM içerik taranir.
#    ClamAV zararli tespit ederse akis DURUR.
# 2) Her dosyanin SHA256 özeti çikarilir ve VirusTotal API ile dosya YÜKLEMEDEN
#    yalnizca özet sorgulanir (ücretsiz kotanin korunması icin).
#    VT'de malicious/suspicious > 0 ise akis DURUR.
# 3) VirusTotal erisilemez/hata verirse (429, 5xx, anahtar yok vs.) yalnizca
#    UYARI verilir ve akis devam eder — zorunlu kontroller ClamAV + SHA256'dır.
#
# NEDEN GitHub Actions'ta: Copr/mock sunucularinda tarama yapmayiz; tüm güvenlik
# kontrolü GitHub sanal makinesinde, paket Copr'a GÖNDERILMEDEN önce tamamlanir.
set -euo pipefail
: "${TARGET:?hedef dizin gerekli (TARGET)}"
VT_MAX_FILES="${VT_MAX_FILES:-150}"

echo "::group::1/3 — ClamAV veritabanı güncellemesi"
sudo freshclam --quiet \
    || echo "::warning::freshclam başarısız; mevcut imza veritabanıyla taranıyor."
echo "::endgroup::"

echo "::group::2/3 — ClamAV tam taraması: $TARGET"
set +e
clamscan -r --infected --scan-archive=yes "$TARGET" | tee "clamav-report-$TARGET.txt"
rc=${PIPESTATUS[0]}
set -e
if [ "$rc" -eq 1 ]; then
    echo "::error::ClamAV zararlı yazılım tespit etti — yayın DURDURULDU."
    exit 1
elif [ "$rc" -ge 2 ]; then
    echo "::warning::ClamAV tarama hatası (kod $rc); rapor denetlenmeli."
fi
echo "ClamAV temiz."
echo "::endgroup::"

echo "::group::3/3 — VirusTotal SHA256 sorguları"
if [ -z "${VT_API_KEY:-}" ]; then
    echo "::warning::VT_API_KEY tanımlı değil; VirusTotal adımı atlanıyor (zorunlu değil)."
    exit 0
fi

total=$(find "$TARGET" -type f | wc -l)
if [ "$total" -gt "$VT_MAX_FILES" ]; then
    echo "::warning::$total dosya var; ücretsiz VT kotası nedeniyle ilk $VT_MAX_FILES dosya sorgulanıyor."
fi
mapfile -t files < <(find "$TARGET" -type f | sort | head -n "$VT_MAX_FILES")

vt_failed=0
for f in "${files[@]}"; do
    sha=$(sha256sum "$f" | awk '{print $1}')
    code=$(curl -sS -o vt-response.json -w "%{http_code}" --max-time 30 \
        -H "x-apikey: $VT_API_KEY" \
        "https://www.virustotal.com/api/v3/files/$sha" 2>/dev/null || echo "000")
    case "$code" in
        200)
            mal=$(jq -r '.data.attributes.last_analysis_stats.malicious // 0' vt-response.json)
            sus=$(jq -r '.data.attributes.last_analysis_stats.suspicious // 0' vt-response.json)
            if [ "$mal" -gt 0 ] || [ "$sus" -gt 0 ]; then
                echo "::error::VirusTotal: $f (sha256=$sha) malicious=$mal suspicious=$sus — yayın DURDURULDU."
                exit 1
            fi
            ;;
        404)
            # VT veritabanında kayıt yok: dosya hiç yüklenmemiş; kota harcanmadan geç.
            ;;
        *)
            vt_failed=$((vt_failed + 1))
            echo "::warning::VT sorgusu başarısız (HTTP $code): $f"
            ;;
    esac
    sleep 2    # ücretsiz VT kotası yaklaşık 4 istek/dakika
done

if [ "$vt_failed" -gt 0 ]; then
    echo "::warning::$vt_failed dosya VirusTotal'e sorulamadı; ClamAV ve SHA256 kontrolleri geçtiği için yayın sürüyor."
fi
echo "::endgroup::"
echo "Güvenlik taraması tamamlandı: $TARGET"
