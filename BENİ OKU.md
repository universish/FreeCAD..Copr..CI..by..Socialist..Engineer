<<<<<<< HEAD
# Native Fedora RPM paketleri

Bu depo, FreeCAD'yi ilgili upstream kaynak etiketi ve Git alt modülleriyle
derleyerek Fedora için Copr RPM'leri üretir. AppImage, Debian paketi veya
önceden derlenmiş RPM yükü paketlenmez. FreeCAD; Fedora'nın Qt 6, Python,
OpenCascade, VTK ve diğer sistem kütüphanelerini kullanır. Paylaşımlı
kütüphane bağımlılıkları RPM'in ELF bağımlılık üreticileriyle belirlenir.

## Paketler

| Kanal | RPM | Komut |
|---|---|---|
| Kararlı | `freecad` | `FreeCAD` |
| Ön sürüm | `freecad-candidate` | `freecad-can` |

Candidate RPM, upstream'in ortak masaüstü ve kaynak yollarını kullanması
nedeniyle kararlı paketle çakışır. Aynı anda yalnızca bir kanal kurulabilir.

## Derleme akışı

GitHub Actions upstream kararlı veya ön sürüm kaynak etiketini seçer, tüm Git
alt modüllerini indirir, SRPM oluşturur ve SRPM'i Fedora 44, Fedora 45 ve
Fedora Rawhide Copr chroot'larına (x86_64 ve aarch64) gönderir. Spec dosyaları
CMake ve dağıtımın geliştirme paketleriyle derleme yapar. PyCXX ve test
araçları Fedora RPM'lerinden kurulur. Bu FreeCAD sürümünün ihtiyaç duyduğu
SMESH ve zipios++ geliştirme paketleri Fedora'da bulunmadığı için bu iki
bileşen upstream kaynak ağacından derlenir; hazır `.so` dosyaları RPM'e
kopyalanmaz. OndselSolver da kaynak koddan derlenir.

Yerelde SRPM üretmek için Git alt modülleri hazırlanmış bir FreeCAD checkout'u
gerekir:

```sh
PKG=freecad VERSION=1.1.4 RELEASE=1 \
FREECAD_SOURCE_DIR=/path/to/FreeCAD \
./scripts/build-srpm.sh
```

İkili RPM derlemesi spec dosyasındaki `BuildRequires` paketleriyle Fedora
buildroot'unda yapılmalıdır. Copr yapılandırılmış Fedora chroot'ları sağlar.
Yayın öncesi oluşan ikili RPM'ler `rpmlint` ve `mock` ile denetlenmelidir.

## Lisans

Paketleme betikleri ve spec dosyaları MIT lisanslıdır. FreeCAD kaynak kodu ve
kaynak ağacında bulunan bileşenler kendi upstream lisanslarını korur.
=======
# FreeCAD Fedora RPM paketleri (Native ve Non-Native)

Bu depo, FreeCAD için hem **native** kaynak tabanlı RPM'leri hem de **non-native** AppImage tabanlı RPM'leri üretir.

## Paket modeli

- **Native** paketler, FreeCAD'in kaynak etiketini alır ve Fedora sistem kütüphanelerine bağlanır.
- **Non-native** paketler, resmi upstream AppImage içindeki çalıştırılabilir runtime'ı `--appimage-extract` ile çıkarır ve bunu ayrı bir `/opt` düzeni altında paketler.
- Bunlar kasıtlı olarak ayrı ailelerdir; farklı ikili adları, masaüstü başlatıcıları ve paket sahipliği vardır.

## Paketler

| Kanal | Tür | RPM | Komut |
|---|---|---|---|
| Kararlı | Native | `freecad` | `FreeCAD` |
| Ön sürüm | Native | `freecad-candidate` | `freecad-can` |
| Kararlı | Non-Native | `freecad-non-native` | `freecad-non-native` |
| Ön sürüm | Non-Native | `freecad-candidate-non-native` | `freecad-can-non-native` |

## Fedora kurulumu

```bash
sudo dnf copr enable universish/FreeCAD
sudo dnf install freecad
sudo dnf install freecad-candidate
sudo dnf install freecad-non-native
sudo dnf install freecad-candidate-non-native
```

## Yerel derleme akışı

### Native derleme

```bash
PKG=freecad VERSION=1.1.4 RELEASE=1 \
FREECAD_SOURCE_DIR=/path/to/FreeCAD \
./scripts/build-srpm.sh
```

### Non-native AppImage derleme

```bash
PKG=freecad-non-native VERSION=1.1.4 RELEASE=1 \
APPIMAGE_URL=https://github.com/FreeCAD/FreeCAD/releases/download/1.1.4/FreeCAD-1.1.4-Linux-x86_64.AppImage \
./scripts/build-srpm-non-native.sh
```

Non-native oluşturucu, AppImage'i indirir, `--appimage-extract` ile açar ve paket içindeki runtime'ı native Fedora kütüphane yolu ile karışmayacak şekilde ayırır.

## Doğrulama

- `bash -n scripts/*.sh` ile sözdizimi denetimi.
- Her RPM için `rpmlint` ile 0 hata ve 0 uyarı hedefi.
- Native için `ldd` doğrulaması, non-native için AppImage runtime izleme.

## Lisans

Paketleme betikleri ve spec dosyaları bu depoya ait lisans altında yayınlanır. FreeCAD, kaynak kodu ve AppImage payload'ları kendi upstream lisanslarını korur.
>>>>>>> 20e77c9 (feat: add native and non-native AppImage/source Fedora RPM packages and automation)
