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
%global debug_package %{nil}

# RPM'in binary dosyaları strip ederek bozmasını ve hardlinkleri kırmasını engeller.
%global __strip /bin/true

# Fedora'nın gereksiz .build-id sembolik bağları ve debug klasörleri üretmesini engeller.
%global _build_id_links none

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

Name:           freecad-non-native
Version:        @VERSION@
Release:        @RELEASE@%{?dist}
Summary:        General-purpose parametric 3D CAD modeler
Group:          Productivity/Graphics/CAD
License:        LGPL-2.1-or-later
URL:            https://www.freecad.org/
Source0:        freecad-payload-x86_64.tar.gz
Source1:        freecad-payload-aarch64.tar.gz
ExclusiveArch:  x86_64 aarch64

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
Requires:       shared-mime-info
Requires(post,postun): desktop-file-utils shared-mime-info
BuildRequires:  desktop-file-utils
BuildRequires:  patchelf
BuildRequires:  coreutils
BuildRequires:  rpm-build
BuildRequires:  bash
BuildRequires:  sed
BuildRequires:  hardlink

%description
FreeCAD is an open-source parametric 3D CAD modeler, made primarily to
design real-life objects of any size. Parametric modeling allows you to
easily modify your design by going back into your model history and
changing its parameters.

This package installs the upstream prebuilt FreeCAD runtime under /opt,
separate from the native source-built FreeCAD package.

%prep
gpgcheck=0
%setup -q -c -n %{name}-%{version} -T
%ifarch x86_64
tar -xzf %{SOURCE0} -C .
%elifarch aarch64
tar -xzf %{SOURCE1} -C .
%else
echo "Unsupported architecture: %{_arch}" >&2
exit 1
%endif

%build
# The upstream runtime is prebuilt; no compilation is performed.

%install
install -d %{buildroot}/opt/%{name} %{buildroot}%{_bindir} \
    %{buildroot}%{_datadir}/applications \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps \
    %{buildroot}%{_metainfodir}
cp -a . %{buildroot}/opt/%{name}/
test -x %{buildroot}/opt/%{name}/AppRun || {
    echo "Normalized payload must contain executable AppRun" >&2
    exit 1
}
cat > %{buildroot}%{_bindir}/%{name} <<'EOF'
#!/bin/sh
exec /opt/%{name}/AppRun "$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/%{name}
install -m 0644 %{buildroot}/opt/%{name}/freecad-icon.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg
cat <<EOF > %{buildroot}%{_datadir}/applications/org.freecad.FreeCAD.NonNative.desktop
[Desktop Entry]
Name=FreeCAD (Non-Native)
Comment=FreeCAD with bundled upstream runtime
GenericName=CAD Application
Exec=%{name} %F
TryExec=%{name}
Terminal=false
Type=Application
Icon=%{name}
Categories=Graphics;Science;Education;Engineering;
StartupNotify=true
StartupWMClass=FreeCAD
MimeType=application/x-extension-fcstd;model/step;model/stl;
EOF
desktop-file-validate %{buildroot}%{_datadir}/applications/org.freecad.FreeCAD.NonNative.desktop
cat > %{buildroot}%{_metainfodir}/org.freecad.FreeCAD.NonNative.metainfo.xml <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>org.freecad.FreeCAD.NonNative</id>
  <name>FreeCAD (Non-Native)</name>
  <summary>FreeCAD with the bundled upstream runtime</summary>
  <description><p>FreeCAD installed with its bundled upstream Linux runtime.</p></description>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>LGPL-2.1-or-later</project_license>
  <launchable type="desktop-id">org.freecad.FreeCAD.NonNative.desktop</launchable>
  <provides>
    <binary>freecad-non-native</binary>
  </provides>
</component>
EOF

%files
/opt/%{name}/
%{_bindir}/%{name}
%{_datadir}/applications/org.freecad.FreeCAD.NonNative.desktop
%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg
%{_metainfodir}/org.freecad.FreeCAD.NonNative.metainfo.xml

%post
# Native and non-native launchers/prefixes are intentionally distinct.
if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database -q /usr/share/applications/ || true
fi
if [ -x /usr/bin/update-mime-database ]; then
    /usr/bin/update-mime-database %{_datadir}/mime || true
fi

%postun
if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database -q /usr/share/applications/ || true
fi
if [ -x /usr/bin/update-mime-database ]; then
    /usr/bin/update-mime-database %{_datadir}/mime || true
fi

%changelog
* Thu Nov 05 2026 universish <universish@tutamail.com> - 1.1.4-1
- Repackage upstream prebuilt FreeCAD 1.1.4
