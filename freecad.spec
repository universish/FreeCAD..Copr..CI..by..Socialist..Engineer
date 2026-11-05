# freecad.spec — FreeCAD KARARLI sürümü.
# Upstream önceden derlenmiş Linux sürümünü (rpm > deb > AppImage önceliğiyle)
# yeniden paketler. Bu spec KAYNAKTAN DERLEME YAPMAZ; Copr yalnızca src.rpm'i
# her chroot'ta %%{_arch} payload'uyla derler.
#
# Yerelde kullanım:
#   sed -e "s/@VERSION@/26.3/g" -e "s/@RELEASE@/1/g" freecad.spec > /tmp/freecad.spec
#   rpmbuild -bs /tmp/freecad.spec --define "_sourcedir $PWD" --define "_srcrpmdir $PWD"

%global debug_package %{nil}

# RPATH denetimi KAPALI: upstream önceden derlenmiş yükü conda/pixi derleme
# ortamında üretiyor; libtcl8.6/libtk8.6 içine o makinelerin mutlak yolları
# ('/home/runner/work/...', '/home/conda/feedstock_root/...') gömülü kalıyor.
# Fedora check-rpaths bu hedefsiz kayıtları "invalid" sayıp derlemeyi düşürür.
# Yük /opt altında kendi gömülü kütüphaneleriyle çalisir (wrapper
# LD_LIBRARY_PATH ayarlar), bu yüzden denetim güvenle kapatılabilir.
%global __brp_check_rpaths %{nil}

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

%install
install -d %{buildroot}/opt %{buildroot}%{_bindir} \
    %{buildroot}%{_datadir}/applications %{buildroot}%{_datadir}/icons
cp -a %{_arch}/opt/* %{buildroot}/opt/
cp -a %{_arch}/usr/bin/* %{buildroot}%{_bindir}/
cp -a %{_arch}/usr/share/applications/* %{buildroot}%{_datadir}/applications/
cp -a %{_arch}/usr/share/icons/* %{buildroot}%{_datadir}/icons/
command -v desktop-file-validate >/dev/null 2>&1 && \
    desktop-file-validate %{buildroot}%{_datadir}/applications/%{name}.desktop || true

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
