# FreeCAD Copr RPM Otomasyonu

Bu depo x86_64 ve aarch64 için FreeCAD kararlı ve ön-sürüm paketlerini üretip Copr’da yayınlar. Native aile upstream kaynak kodunu dağıtım kütüphanelerine karşı derler. Non-native aile, upstream Linux dosyalarından ilk bulunanı RPM → DEB → AppImage önceliğiyle yeniden paketler.

## Paketler

| Kanal | Aile | RPM adı | Komut | AppStream kimliği |
| --- | --- | --- | --- |
| Kararlı | Native | `freecad` | `freecad` | `org.freecad.FreeCAD` |
| Candidate | Native | `freecad-candidate` | `freecad-can` | `org.freecad.FreeCAD.Candidate` |
| Kararlı | Non-native | `freecad-non-native` | `freecad-non-native` | `org.freecad.FreeCAD.NonNative` |
| Candidate | Non-native | `freecad-candidate-non-native` | `freecad-can-non-native` | `org.freecad.FreeCAD.Candidate.NonNative` |

Aynı ailede kararlı ve candidate birlikte kurulabilir. Native ve non-native paketlerin başlatıcıları ve kurulum yolları ayrıdır.

## Sisteme kurulum

```bash
sudo dnf copr enable universish/FreeCAD..
sudo dnf install freecad freecad-candidate
sudo dnf install freecad-non-native freecad-candidate-non-native
```

Native paketler sistem paket yerleşimini kullanır; non-native paketlerin bundled runtime’ı `/opt` altındadır. Sistem paketlerini DNF ile güncelleyin veya kaldırın.

## Yalnız kullanıcı hesabına kurulum

Native paketleri Toolbox içine kurup host’a başlatıcı eklemek için:

```bash
./scripts/install-native-toolbox.sh freecad
./scripts/install-native-toolbox.sh freecad-candidate
```

Varsayılan Toolbox adı `freecad-rpm`’dir; gerekirse `TOOLBOX_CONTAINER` ile değiştirin. Toolbox’ı bırakıp tek paketi kaldırmak için:

```bash
./scripts/uninstall-native-toolbox.sh freecad
```

Non-native kullanıcı kurulumu, hedef mimari için doğrulanmış ve normalize edilmiş payload arşivi ister. Yalnızca `~/.local/opt/`, `~/.local/bin/` ve `~/.local/share/` altına yazar:

```bash
PKG=freecad-non-native VERSION=26.3rc2 \
PAYLOAD_ARCHIVE=/path/to/verified-payload.tar.gz \
./scripts/install-user.sh
```

Candidate için `PKG=freecad-candidate-non-native` kullanın. Kurulumu kaldırırken aynı `PKG` değerini verin; örneğin `PKG=freecad-candidate-non-native ./scripts/uninstall-user.sh`.

## Otomatik yayın akışı

GitHub Actions stable ve candidate sürümlerini ayrı tespit eder, weekly tag/asset’lerini dışlar, her mimaride Linux paketlerini seçer, upstream SHA256 sidecar’ı veya GitHub asset digest’ini doğrular. Payload GitHub runner’ında normalize edilip tarandıktan sonra SRPM’ler oluşturulur ve Copr chroot’larına gönderilir. ClamAV zorunlu kapıdır. VirusTotal SHA256 sorguları API erişilemez veya kota doluysa uyarıyla atlanır; zararlı sonucu yayınlamayı durdurur.

Workflow `Europe/Brussels` saatinde 12:30 ve 17:30’da çalışır; elle veya yapılandırılmış repository dispatch olaylarıyla da başlatılabilir. Ortak concurrency grubu eşzamanlı paketleme çalışmalarını önler. Copr gönderimi etkin/tamamlanmış aynı NVR’ı yeniden kullanır ve her paket derlemesinin 14 chroot’un tamamında bitmesini bekler. Bir hedef başarısız olursa workflow başarısız olur ve state güncellenmez.

GitHub Actions için gereken secret: `COPR_CONFIG`; `VT_API_KEY` isteğe bağlı ve ek kontroldür. Yerel kullanım için ignore edilen `.env` placeholder’ı oluşturulur; gerçek anahtarı commit etmeyin.

## Yerel SRPM üretimi

Native kaynak SRPM’si:

```bash
PKG=freecad VERSION=1.1.4 RELEASE=1 \
FREECAD_SOURCE_DIR=/path/to/initialized/FreeCAD \
./scripts/build-srpm.sh
```

Native spec yamaları depoda izlenen `patches/` dizininden alınır. Yok sayılan örnek dizinler build sırasında kullanılmaz.

Doğrulanmış, normalize edilmiş iki mimari payload ile non-native SRPM:

```bash
PKG=freecad-non-native VERSION=1.1.4 RELEASE=1 \
PAYLOAD_ROOT=payload \
./scripts/build-srpm-non-native.sh
```

## Copr hedefleri

Yapılandırılmış hedefler x86_64 ve aarch64 için Fedora 44/45/Rawhide, openEuler 22.03/24.03 ve openSUSE Tumbleweed/Leap 16.0’dır.

## Lisans

Paketleme betikleri ve spec dosyaları depo lisansıyla yayınlanır. FreeCAD ve bundled upstream bileşenleri kendi upstream lisanslarını korur.
