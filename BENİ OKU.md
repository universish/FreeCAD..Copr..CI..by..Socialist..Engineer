# FreeCAD Fedora RPM paketleri

Bu depo şu anda Copr üzerinden native FreeCAD RPM'leri üretir. Non-native AppImage paketlemesi yeniden düzenlenmektedir; bu workflow şu an bu paketleri derlemez veya yayınlamaz.

## Paket modeli

- Native paketler, FreeCAD'in kaynak etiketini alır ve Fedora sistem kütüphanelerine bağlanır.
- Non-native AppImage paketleri, düzeltilmiş spec dosyaları hazır olduğunda ayrı runtime yolları ve başlatıcılarla bağımsız bir paket ailesi olarak eklenecektir.

## Paketler

| Kanal | Tür | RPM | Komut |
|---|---|---|---|
| Kararlı | Native | `freecad` | `FreeCAD` |
| Ön sürüm | Native | `freecad-candidate` | `freecad-can` |

## Fedora kurulumu

```bash
sudo dnf copr enable universish/FreeCAD
sudo dnf install freecad
sudo dnf install freecad-candidate
```

## Yerel derleme akışı

### Native derleme

```bash
PKG=freecad VERSION=1.1.4 RELEASE=1 \
FREECAD_SOURCE_DIR=/path/to/FreeCAD \
./scripts/build-srpm.sh
```

## Doğrulama

- `bash -n scripts/*.sh` ile sözdizimi denetimi.
- Her RPM için `rpmlint` ile 0 hata ve 0 uyarı hedefi.
- Native için `ldd` doğrulaması.

## Lisans

Paketleme betikleri ve spec dosyaları bu depoya ait lisans altında yayınlanır. FreeCAD, kaynak kodu ve AppImage payload'ları kendi upstream lisanslarını korur.
