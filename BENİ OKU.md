# FreeCAD Fedora RPM paketleri (Native ve Non-Native)

Bu depo, FreeCAD için hem native kaynak tabanlı RPM'leri hem de non-native AppImage tabanlı RPM'leri üretir.

## Paket modeli

- Native paketler, FreeCAD'in kaynak etiketini alır ve Fedora sistem kütüphanelerine bağlanır.
- Non-native paketler, resmi upstream AppImage içindeki çalıştırılabilir runtime'ı `--appimage-extract` ile çıkarır ve bunu ayrı bir `/opt` düzeni altında paketler.
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
