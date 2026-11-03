<p align="center">
  <img src="https://upload.wikimedia.org/wikipedia/commons/f/f7/FreeCAD-logo.svg" alt="FreeCAD" width="240" />
</p>

<h1 align="center">FreeCAD Copr CI</h1>

<p align="center">
  Upstream FreeCAD'in önceden derlenmiş Linux sürümlerini Fedora, RHEL türevleri ve openSUSE için yerli RPM paketlerine dönüştüren otomatik sürekli entegrasyon hattı; derlemeler Fedora Copr üzerinde yapılır ve barındırılır.
</p>

<p align="center">
  <img src="https://copr.fedorainfracloud.org/coprs/universish/FreeCAD../package/freecad/status_image/last_build.png" alt="Copr derleme durumu" />
  <img src="https://img.shields.io/github/license/universish/FreeCAD..Copr..CI..by..Socialist..Engineer" alt="Lisans" />
  <img src="https://img.shields.io/badge/arch-x86__64%20%7C%20aarch64-blue" alt="Mimariler" />
</p>

---

Bu depo, FreeCAD projesinin yayınladığı önceden derlenmiş Linux paketlerini (.rpm, .deb ve .AppImage dosyalarını) RPM paketlerine dönüştüren gayriresmî bir depodur.

Bu Copr deposu sayesinde FreeCAD'yi Fedora ve ekosisteminde tek bir paket yöneticisi komutuyla kurabilir ve güncel tutabilirsiniz.

Bu depoyla ilgili hataları veya paket kurulum sorunlarını [hata takipçisinde](https://github.com/universish/FreeCAD..Copr..CI..by..Socialist..Engineer/issues) bildirin.

FreeCAD resmî [depo](https://github.com/FreeCAD/FreeCAD) — FreeCAD resmî [web sitesi](https://www.freecad.org/)

## Genel bakış

FreeCAD, genel amaçlı parametrik 3B CAD modelleme yazılımıdır. Parametrik modelleme, mühendisin model geçmişine dönüp tasarım parametrelerini istediği an değiştirebilmesini sağlar; bu da FreeCAD'yi mekanik mühendisliği, ürün tasarımı, mimarlık ve elektronik işlerinde — hızlı bir esketirden üretime hazır teknik resimlere ve 3B baskı mesh'lerine kadar — ciddi bir araç haline getirir.

Upstream, GitHub Releases sayfasında önceden derlenmiş Linux dosyalarını (x86_64 ve aarch64) yayınlar; ancak bunları her ekosistem için dağıtım yerli RPM paketi olarak sunmaz. Bu boyuttaki bir CAD uygulamasını Fedora Mock veya Copr gibi izole derleme ortamlarında kaynaktan derlemek yavaş ve kırılgandır: bağımlılık yüzeyi (OpenCASCADE, VTK, Coin, Boost, Qt, PySide) çok geniştir ve hızla değişir.

Bu depo sorunu kaynak derleme yerine yeniden paketleme hattıyla çözer:

1. **Sürüm tespiti** — Hat, GitHub Releases API'sini sorgular ve haftalık geliştirme derlemesi OLMAYAN en yeni sürümü bulur. Haftalık (weekly) derlemeler açıkça dışlanır; kararlı sürümler ve sürüm adayları (`yy.XrcY` numaralandırması, örn. `26.3rc2`) paketlenir.
2. **Akıllı paket seçimi** — Upstream `.rpm` yayınladıysa doğrudan o kullanılır; değilse `.deb` açılır; o da yoksa `.AppImage` paketi çıkarılır (FUSE gerektirmez). İlk bulunan biçim bu sırayla kazanır.
3. **Bütünlük doğrulaması** — Her dosya, başka hiçbir işlem yapılmadan ÖNCE upstream `-SHA256.txt` sağlama dosyasına karşı denetlenir.
4. **Güvenlik taraması** — Çıkarılan paket içeriği GitHub Actions sanal makinesinde (Copr derleme sunucularında asla) güncel ClamAV veritabanıyla taranır ve her dosyanın SHA-256 özeti VirusTotal API'sine sorgulanır. Herhangi bir olumlu tespitte hat DURUR; VirusTotal'e erişilemezse yalnızca uyarı verilir.
5. **İçerik normalize etme** — Uygulama `/opt/freecad` (kararlı) veya `/opt/freecad-candidate` (sürüm adayı) altına taşınır; uygun başlatıcı, masaüstü kaydı, simgeler ve kota dostu güncelleme için upstream `.zsync` dosyası pakete gömülür.
6. **SRPM üretimi** — Her iki mimari tek bir kaynak RPM'de Fedora spec dosyasıyla birleştirilir; kütüphane bağımlılıkları rpmbuild'in bağımlılık üreteciyle otomatik tespit edilir, hicolor-icon-theme, xdg-utils, mesa ve diğer sistem bağımlılıkları açıkça bildirilir.
7. **Copr gönderimi** — SRPM, yapılandırılmış tüm chroot'lara (Fedora 44/45/Rawhide/ELN, EPEL 9/10, AlmaLinux, CentOS Stream, Mageia, openSUSE) `copr-cli` ile gönderilir.

Paketleme numarası (release) her yeniden paketlemede otomatik olarak bir artar (`sürüm-paketleme_numarası` biçiminde) ve upstream sürümü değiştiğinde 1'e sıfırlanır; böylece yükseltmeler her zaman sorunsuz çözülür.

## Paketler

| Kanal | Paket | Komut | Açıklama |
|---|---|---|---|
| Kararlı | `freecad` | `freecad` | En yeni kararlı upstream sürümü |
| Ön-sürüm | `freecad-candidate` | `freecad-can` | Test için sürüm adayı / beta derlemeleri |

İki paket yan yana kurulabilir: aday sürüm kendi kurulum dizinini (`/opt/freecad-candidate`) ve başlatıcısını (`freecad-can`) kullanır. Her iki sürümün aynı kullanıcı yapılandırma dizinini paylaştığını unutmayın. Her paketin yalnızca bir kopyası kurulu olabilir ve her biri bağımsız güncellenebilir.

Haftalık geliştirme derlemeleri asla paketlenmez.

## Kurulum

### Fedora (44, 45, Rawhide, ELN)

Copr deposunu etkinleştirip paketi kurun:

```
sudo dnf copr enable universish/FreeCAD..
sudo dnf install -y freecad
```

Sürüm adayı için:

```
sudo dnf copr enable universish/FreeCAD..
sudo dnf install -y freecad-candidate
```

### RHEL, AlmaLinux, CentOS Stream, EPEL

```
sudo dnf copr enable universish/FreeCAD..
sudo dnf install -y freecad
```

(RHEL türevi sistemlerde önce EPEL'i etkinleştirin.)

### openSUSE Tumbleweed ve Leap 16.0

```
sudo zypper addrepo -f https://copr.fedorainfracloud.org/coprs/universish/FreeCAD../repo/opensuse-tumbleweed/universish-FreeCAD..-opensuse-tumbleweed.repo
sudo zypper --gpg-auto-import-keys refresh
sudo zypper install -y freecad
```

openSUSE Leap 16.0 için depo URL'sindeki `opensuse-tumbleweed` kısmını `opensuse-leap-16.0` ile değiştirin.

## Güncelleme

Sıradan paket yöneticisi güncellemesi yeni derlemeleri alır:

```
sudo dnf upgrade --refresh -y freecad
```

openSUSE:

```
sudo zypper refresh -f && sudo zypper update -y freecad
```

### zsync ile kota dostu güncelleme

Her paket, upstream `.zsync` dosyasını `/opt/freecad/updates/` (aday sürüm için `/opt/freecad-candidate/updates/`) altına gömer. Orijinal dosyayı sakladıysanız yeni sürümün yalnızca değişen bloklarını indirerek tam indirme yerine kota tasarrufu yapabilirsiniz:

```
zsync https://github.com/FreeCAD/FreeCAD/releases/download/<etiket>/<dosya>.AppImage.zsync
```

Bu, her güncellemede indirme boyutunun büyük bir bölümünden tasarruf sağlar.

## Kaldırma

```
sudo dnf remove -y freecad freecad-candidate
```

Depoyu geçici olarak devre dışı bırakmak için:

```
sudo dnf copr disable universish/FreeCAD..
```

Depoyu sistemden tamamen kaldırmak için:

```
sudo dnf copr remove universish/FreeCAD..
```

openSUSE:

```
sudo zypper remove -y freecad freecad-candidate
sudo zypper removerepo copr:copr.fedorainfracloud.org:universish:FreeCAD..
```

## Otomasyon nasıl çalışır

### Tetikleyiciler

- **Zamanlanmış denetimler** — Günde iki kez, FreeCAD projesi merkezinin bulunduğu saat dilimindeki (Avrupa/Berlin; GitHub cron'u UTC'de çalışır) öğle arası ve iş çıkışına hizalanır.
- **Manuel tetik** — İsteğe bağlı sürüm ve kanal zorlamalı `workflow_dispatch`.
- **Webhook** — `repository_dispatch` olayları; upstream yayın ping'ine anında tepki ve sağlık kontrolü için (aşağıya bakın).

Tüm tetikleyiciler ortak bir concurrency grubunu paylaşır; böylece webhook ve zamanlanmış çalışma aynı sürümü asla iki kez derleyemez ve paketleme numarası sayacında yarışma oluşmaz.

### Webhook (isteğe bağlı, önerilir)

GitHub zamanlanmış iş akışları yoğun dönemlerde gecikebilir veya atlanabilir. Kesin bir Avrupa/Berlin takvimi ve sağlık kontrolü ping'i için `repo` yetkili bir kişisel erişim anahtarı oluşturun ve harici bir zamanlayıcı (örn. saat dilimi destekli cron-job.org) 6 saatte bir POST yollayacak şekilde ayarlayın:

```
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ERISIM_ANAHTARINIZ" \
  https://api.github.com/repos/universish/FreeCAD..Copr..CI..by..Socialist..Engineer/dispatches \
  -d '{"event_type":"freecad-healthcheck"}'
```

Hat idempotenttir (kendini tekrarlamaz): sürüm daha önce işlendiyse çalıştırma saniyeler içinde temiz şekilde sonlanır.

### Depo yapısı

```
.
├── .github/
│   └── workflows/
│       └── copr-ci.yml        # Sürüm dedektörü, tarayıcı, yeniden paketleyici, Copr tetikleyici
├── scripts/
│   ├── detect-release.sh      # Upstream sürüm/kanal/revizyon tespiti
│   ├── fetch-and-verify.sh    # İndirme + SHA-256 doğrulama
│   ├── repackage.sh           # rpm/deb/AppImage açma ve normalize etme
│   ├── security-scan.sh       # ClamAV + VirusTotal taraması
│   └── build-srpm.sh          # Kaynak RPM üretimi
├── freecad.spec               # Kararlı paket spec dosyası
├── freecad-candidate.spec     # Sürüm adayı paket spec dosyası
├── chroots.txt                # Hedef Copr chroot'ları
├── state/                     # Paket başına son işlenen sürüm
└── README.md
```

### Güvenlik modeli

Tüm dosyalar Copr'a ulaşmadan ÖNCE doğrulanır ve taranır. ClamAV tanımları her çalıştırmada yenilenir, tüm paket içeriği taranır ve SHA-256 özeti VirusTotal'e sorgulanır (yalnızca özet — dosyaların kendisi asla yüklenmez, böylece ücretsiz API kotası korunur). VirusTotal'e ulaşılamazsa, zorunlu ClamAV ve sağlama kontrolleri geçildiğinde çalıştırma uyarı vererek sürer. Tarama Copr veya mock altyapısında asla yapılmaz.

## Geri bildirim ve sorunlar

Bu depo, FreeCAD'yi Fedora ve türevi dağıtımlarda kurmayı ve güncellemeyi kolaylaştırmayı amaçlayan gayriresmî bir paketleme hattıdır.

RPM paketleme veya Copr kurulum sorunlarını lütfen [hata takipçimize](https://github.com/universish/FreeCAD..Copr..CI..by..Socialist..Engineer/issues) bildirin.

Upstream uygulama hataları, özellik istekleri veya belgeleme için resmî [FreeCAD web sitesine](https://www.freecad.org/) veya resmî [GitHub deposuna](https://github.com/FreeCAD/FreeCAD) başvurun.

## Lisans

Bu depodaki paketleme betikleri, GitHub Actions iş akışları ve spec dosyaları MIT Lisansı altındadır.

FreeCAD uygulamasının kendisi ve önceden derlenmiş dosyaları upstream FreeCAD lisans koşullarına (LGPL-2.1-or-later; Zlib, BSD-3-Clause, Apache-2.0, MIT vb. altında bileşenlerle) tabidir.
