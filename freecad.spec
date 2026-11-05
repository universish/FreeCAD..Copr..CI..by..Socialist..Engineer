# freecad.spec — FreeCAD KARARLI sürümü.
# Upstream önceden derlenmiş Linux sürümünü (rpm > deb > AppImage önceliğiyle)
# yeniden paketler. Bu spec KAYNAKTAN DERLEME YAPMAZ; Copr yalnızca src.rpm'i
# her chroot'ta payload ile derler.
#
# Yerelde kullanım:
#   sed -e "s/@VERSION@/26.3/g" -e "s/@RELEASE@/1/g" freecad.spec > /tmp/freecad.spec
#   rpmbuild -bs /tmp/freecad.spec --define "_sourcedir $PWD" --define "_srcrpmdir $PWD"

# Otomatik Python byte-compile (pyc üretme) işlemini tamamen devredışı bırakır.
%global __brp_python_bytecompile %{nil}
%global __os_install_post %(echo '%{__os_install_post}' | sed -e 's!/usr/lib[^[:space:]]*/brp-python-bytecompile[[:space:]].*$!!g')

# Önceden derlenmiş binary paketlerde debug paketi oluşturulmasını engeller.
# %global debug_package %{nil}

# RPM'in binary dosyaları strip ederek (kırparak) bozmasını engeller.
# %global __strip /bin/true

# RPATH denetimi KAPALI: upstream önceden derlenmiş yükü conda/pixi derleme
# ortamında üretiyor; libtcl8.6/libtk8.6 içine o makinelerin mutlak yolları
# ('/home/runner/work/...', '/home/conda/feedstock_root/...') gömülü kalıyor.
# Fedora check-rpaths bu hedefsiz kayıtları "invalid" sayıp derlemeyi düşürür.
# Yük /opt altında kendi gömülü kütüphaneleriyle çalisir (wrapper
# LD_LIBRARY_PATH ayarlar), bu yüzden denetim güvenle kapatılabilir.
%global __brp_check_rpaths %{nil}

# Shebang denetimi KAPALI: payload'taki çalistirilabilir betiklerin shebang'i
# upstream conda-forge kalıntısıdır ('/home/conda/.../bin/python3.11' gibi
# hedefsiz mutlak yollar veya '#!/usr/bin/env python' gibi belirsiz yorum
# satırları). Fedora/Red Hat ailesinin brp-mangle-shebangs betiği bunları
# HATA ile düşürür (RHEL9 dokümanı: "generates errors ... ambiguous
# interpreter directive"; ambiguous python shebang'i build'i fail eder).
# openSUSE bu betiği çalistirmadigi için orada derleme başarılıydı. Yük
# kendi python'unu kullanir; repackage.sh shebang'leri zaten düzeltir.
%global __brp_mangle_shebangs %{nil}

Name:           freecad
Version:        @VERSION@
Release:        @RELEASE@%{?dist}
Summary:        General-purpose parametric 3D CAD modeler

License:        LGPL-2.1-or-later
URL:            https://www.freecad.org/
Source0:        %{name}-%{version}.tar.gz

# /opt/freecad altındaki gömülü özel kütüphaneler otomatik Requires/Provides
# ÜRETMESIN (yüzlerce sahte lib*.so provides'ı ve gereksiz bağımlılık
# üretir); gerçek sistem bağımlılıkları aşağıda açıkça bildirilir.
%define __requires_exclude_from ^/opt/%{name}
%define __provides_exclude_from ^/opt/%{name}

# Yalnizca TÜM hedef dağıtımlarda (Fedora, EPEL, Alma, CentOS Stream, Mageia,
# openSUSE, openEuler) ORTAK adlara sahip bağımlılıklar. Qt, OpenGL, fontconfig
# vb. yükün İÇİNDE gömülü olduğu için ayrıca istenmez; Fedora'ya özgü adlar
# (mesa-libGL, qt6-qtbase-gui) openSUSE/Mageia'da ÇÖZÜLEMEZ ve paketi o
# dağıtımlarda kurulamaz kılar.
Requires:       hicolor-icon-theme
Requires:       xdg-utils

%description
FreeCAD is an open-source parametric 3D CAD modeler, made primarily to
design real-life objects of any size. Parametric modeling allows you to
easily modify your design by going back into your model history and
changing its parameters.

This package repackages the upstream prebuilt Linux release into a native
RPM for Fedora, RHEL-compatible distributions and openSUSE, built and
hosted on Fedora Copr.

%prep
%setup -q

%build
# Yeniden derleme yok: %%{_arch} altındaki normalize edilmiş önceden derlenmiş
# yük doğrudan kullanılır.

BuildRequires: patchelf

%install
install -d %{buildroot}/opt %{buildroot}%{_bindir} \
    %{buildroot}%{_datadir}/applications %{buildroot}%{_datadir}/icons

# Payload seçimi: v2/v3/v4 gibi mikro-mimari chroot'larında (örn.
# almalinux-10-x86_64_v2) %%{_arch} "x86_64_v2" olur; kaynak ağaçta bu adlı
# dizin yoktur, x86_64 payload'u kullanılmalı. Önce kendi mimarisi denenir,
# x86_64* türevlerinde x86_64 yedeğine düşülür, diğerlerinde hata verilir.
PAYLOAD="%{_arch}"
if [ ! -d "$PAYLOAD" ]; then
    case "%{_arch}" in
        x86_64*) PAYLOAD="x86_64" ;;
        *) echo "ERROR: %{_arch} için payload yok (yalnızca x86_64/aarch64 var)" >&2; exit 1 ;;
    esac
fi
echo "Seçilen payload: $PAYLOAD"

cp -a "$PAYLOAD"/opt/* %{buildroot}/opt/
cp -a "$PAYLOAD"/usr/bin/* %{buildroot}%{_bindir}/
cp -a "$PAYLOAD"/usr/share/applications/* %{buildroot}%{_datadir}/applications/
cp -a "$PAYLOAD"/usr/share/icons/* %{buildroot}%{_datadir}/icons/
command -v desktop-file-validate >/dev/null 2>&1 && \
    desktop-file-validate %{buildroot}%{_datadir}/applications/%{name}.desktop || true
    
export QA_RPATHS=0x0002
patchelf --remove-rpath %{buildroot}/opt/freecad/usr/lib/libtcl8.6.so
patchelf --remove-rpath %{buildroot}/opt/freecad/usr/lib/libtk8.6.so

%files
/opt/%{name}/
%{_bindir}/%{name}
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/*/apps/%{name}.*

%post
# Yan yana kurulum uyarısı: kararlı sürüm kurulurken candidate kuruluysa bilgilendir.
if [ -x %{_bindir}/freecad-can ]; then
    echo "NOTE: freecad-candidate is also installed; both versions share the same user configuration directory." >&2
fi

%changelog
* Wed Nov 05 2026 universish <universish@tutamail.com> - 1.1.4-1
- Repackage upstream prebuilt FreeCAD 1.1.4
