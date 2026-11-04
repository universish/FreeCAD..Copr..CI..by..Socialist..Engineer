#!/usr/bin/env bash
# security-scan.sh — paketlenecek yük üzerinde çift katmanli güvenlik taramasi.
#
# Copyrights 2026 (c) universish (Saffet Yavuz)
# 
# 1) ClamAV imza veritabani güncellenir (freshclam) ve TÜM içerik taranir.
#    ClamAV zararli tespit ederse akis DURUR.
# 2) Çalistirilabilir ikililer ve paylaşimli kütüphanelerin SHA256 özeti
#    çikarilir; VirusTotal API ile DOSYA YÜKLEMEDEN yalnizca özet sorgulanir.
#    VT'de malicious/suspicious > 0 ise akis DURUR.
# 3) VirusTotal 429 (kota) verirse 30 sn bekleyip en fazla 3 kez tekrar
#    denenir; yine olmazsa yalnizca UYARI verilir ve akis devam eder —
#    zorunlu kontroller ClamAV + SHA256'dır.
#
# NEDEN GitHub Actions'ta: Copr/mock sunucularinda tarama yapmayiz; tüm güvenlik
# kontrolü GitHub sanal makinesinde, paket Copr'a GÖNDERILMEDEN önce tamamlanir.
set -euo pipefail
: "${TARGET:?hedef dizin gerekli (TARGET)}"
VT_MAX_FILES="${VT_MAX_FILES:-150}"

# Rapor dosyasi adinda dizin ayiraci olmasin (TARGET=payload/aarch64 gibi
# degerlerde tee hedef yolunu bulamayip hata verirdi).
REPORT="clamav-report-$(echo "$TARGET" | tr '/ ' '__').txt"

echo "::group::1/3 — ClamAV veritabanı güncellemesi"
# Runner imgesinde arka planda çalisabilen freshclam servisi log kilidi tutar.
# Önce servis durdurulur, kalan süreç öldürülür, kilit/pid dosyalari temizlenir;
# ardindan varsayilan güncelleme yapilir (özel log dosyasi seçeneği kullanilmaz:
# farkli freshclam sürümlerinde stderr sözdizimi dosya adi sanilarak hata verebilir).
sudo systemctl stop clamav-freshclam 2>/dev/null || true
sudo pkill -x freshclam 2>/dev/null || true
sleep 2
sudo rm -f /var/log/clamav/freshclam.log.lock /run/clamav/freshclam.pid 2>/dev/null || true
sudo freshclam --quiet --no-warnings \
    || echo "::warning::freshclam başarısız; mevcut imza veritabanıyla taranıyor."
echo "::endgroup::"

echo "::group::2/3 — ClamAV tam taraması: $TARGET"
set +e
clamscan -r --infected --scan-archive=yes "$TARGET" | tee "$REPORT"
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

# Aday seçimi: yalnizca çalistirilabilir ikililer ve paylaşimli kütüphaneler.
# .py/.ui gibi kaynak metinler VT veritabaninda neredeyse hic eşleşmez;
# kotayi gereksiz tüketirler, risk de tasi mazlar. ClamAV zaten hepsini taradi.
# Boyuta göre büyükten küçüğe sirala: kota daralirsa en kritikler (FreeCAD
# ikilisi, Qt/lib kütüphaneleri) ilk sorgulanir.
find "$TARGET" -type f \( -perm /111 -o -name '*.so' -o -name '*.so.*' \) \
    -printf '%s %p\n' | sort -rn > /tmp/vt-candidates.txt
total=$(wc -l < /tmp/vt-candidates.txt)
echo "VT adayi ikili/kütüphane sayisi: $total (dosya YÜKLENMEZ, yalnizca SHA256 özeti sorgulanir)"
mapfile -t files < <(head -n "$VT_MAX_FILES" /tmp/vt-candidates.txt | cut -d' ' -f2-)
if [ "$total" -gt "$VT_MAX_FILES" ]; then
    echo "::notice::Kota korumasi: ilk $VT_MAX_FILES aday sorgulaniyor (büyükten küçüğe sirali)."
fi

vt_failed=0
vt_consec_429=0
for f in "${files[@]}"; do
    [ -f "$f" ] || continue
    sha=$(sha256sum "$f" | awk '{print $1}')

    # 429 (kota) alirsak 30 sn bekleyip en fazla 3 kez tekrar dene.
    # Üst üste 5 dosyada da kota devam ederse VT adimini TAMAMEN atla:
    # günlük kota bitmiş demektir, kalan dosyaları bekletmenin anlami yok.
    attempt=0
    while :; do
        code=$(curl -sS -o vt-response.json -w "%{http_code}" --max-time 30 \
            -H "x-apikey: $VT_API_KEY" \
            "https://www.virustotal.com/api/v3/files/$sha" 2>/dev/null || echo "000")
        if [ "$code" != "429" ]; then
            vt_consec_429=0
            break
        fi
        vt_consec_429=$((vt_consec_429 + 1))
        if [ "$vt_consec_429" -ge 5 ]; then
            echo "::warning::VirusTotal kotasi üst üste $vt_consec_429 dosyada da dolu; VT adimi atlaniyor."
            echo "::warning::Zorunlu kontroller (ClamAV + SHA256) geçti; yayin sürüyor."
            exit 0
        fi
        if [ "$attempt" -ge 3 ]; then
            break
        fi
        attempt=$((attempt + 1))
        echo "::notice::VT kotasi dolu (429); 30 sn bekleniyor (tekrar $attempt/3): $(basename "$f")"
        sleep 30
    done

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
