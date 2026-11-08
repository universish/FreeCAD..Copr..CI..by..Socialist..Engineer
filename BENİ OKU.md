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
CMake ve dağıtımın geliştirme paketleriyle derleme yapar. Fedora'da bulunan
zipios++, PyCXX ve SMESH paketleri varsayılan olarak kullanılır. OndselSolver,
FreeCAD kaynak ağacının bir upstream bileşeni olarak kaynakla birlikte derlenir.

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
