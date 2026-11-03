freecad-copr/
├── .github/workflows/copr-ci.yml   # Ana hat: gate → build (matrix) → srpm → copr → finalize
├── scripts/
│   ├── detect-release.sh           # Sürüm/kanal/paketleme-no tespiti (weekly filtresi burada)
│   ├── fetch-and-verify.sh         # İndirme + zorunlu SHA256 doğrulama + zsync alımı
│   ├── repackage.sh                # rpm/deb/AppImage açma, /opt altına normalize, .desktop+simge+wrapper
│   ├── security-scan.sh            # freshclam + clamscan + VirusTotal SHA256 sorgusu
│   └── build-srpm.sh               # İki mimariyi tek SRPM'de birleştirme
├── freecad.spec                    # Kararlı paket (freecad, /opt/freecad, binary: freecad)
├── freecad-candidate.spec          # Ön-sürüm (freecad-candidate, /opt/freecad-candidate, binary: freecad-can)
├── chroots.txt                     # Hedef Copr chroot listesi (düzenlenebilir)
├── state/freecad.json              # Paketleme sayacı (kararlı)
├── state/freecad-candidate.json    # Paketleme sayacı (aday)
├── README.md                       # Kurumsal, İngilizce, emoji yok
└── BENİ OKU.md                     # README'nin Türkçesi
