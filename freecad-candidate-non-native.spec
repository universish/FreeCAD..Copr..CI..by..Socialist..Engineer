# freecad-candidate.spec — FreeCAD ÖN-SÜRÜM (Release Candidate / beta) sürümü.
# Upstream önceden derlenmiş Linux sürümünü (rpm > deb > AppImage önceliğiyle)
# yeniden paketler. Kararlı 'freecad' paketiyle YAN YANA kurulabilir:
# ikili adı freecad-can, kurulum dizini /opt/freecad-candidate'dir.
# Bu spec KAYNAKTAN DERLEME YAPMAZ.

# Otomatik Python byte-compile (pyc üretme) işlemini tamamen devredışı bırakır.
%global __brp_python_bytecompile %{nil}
# RPATH denetimi KAPALI: bkz. freecad.spec — upstream conda/pixi yükünde
# hedefsiz mutlak RPATH kayıtları var; yük gömülü kütüphaneleriyle çalışır.
%global __brp_check_rpaths %{nil}

%global __os_install_post %(echo '%{__os_install_post}' | sed -e 's!/usr/lib[^[:space:]]*/brp-python-bytecompile[[:space:]].*$!!g')

# Önceden derlenmiş binary paketlerde debug paketi oluşturulmasını engeller.
%global debug_package %{nil}

# RPM'in binary dosyaları strip ederek bozmasını ve hardlinkleri kırmasını engeller.
%global __strip /bin/true

# Fedora'nın gereksiz .build-id sembolik bağları ve debug klasörleri üretmesini engeller.
%global _build_id_links none

# Shebang denetimi KAPALI: bkz. freecad.spec — payload'taki conda kalıntısı
# shebang'ler brp-mangle-shebangs'i HATA ile düşürür; repackage.sh düzeltir.
%global __brp_mangle_shebangs %{nil}

Name:           freecad-candidate-non-native
Version:        @VERSION@
Release:        @RELEASE@%{?dist}
Summary:        General-purpose parametric 3D CAD modeler (release candidate)
Group:          Productivity/Graphics/CAD
License:        LGPL-2.1-or-later
URL:            https://www.freecad.org/
Source0:        freecad-payload-x86_64.tar.gz
Source1:        freecad-payload-aarch64.tar.gz
ExclusiveArch:  x86_64 aarch64

# Gömülü kütüphaneler Requires/Provides üretmesin (bkz. freecad.spec).
%define __requires_exclude_from ^/opt/%{name}
%define __provides_exclude_from ^/opt/%{name}

# Yalnızca tüm hedef dağıtımlarda ortak adlar (bkz. freecad.spec).
Requires:       hicolor-icon-theme shared-mime-info
Requires(post,postun): desktop-file-utils shared-mime-info
BuildRequires:  desktop-file-utils

%description
FreeCAD candidate is packaged with the upstream runtime under a separate
non-native package identity and /opt prefix. It is co-installable with native
FreeCAD packages.

%prep
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
# Yeniden derleme yok: %%{_arch} altındaki normalize edilmiş önceden derlenmiş
# yük doğrudan kullanılır.

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
cat > %{buildroot}%{_bindir}/freecad-can-non-native <<'EOF'
#!/bin/sh
exec /opt/%{name}/AppRun "$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/freecad-can-non-native
install -m 0644 %{buildroot}/opt/%{name}/freecad-icon.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg
cat <<EOF > %{buildroot}%{_datadir}/applications/org.freecad.FreeCAD.Candidate.NonNative.desktop
[Desktop Entry]
Name=FreeCAD Candidate (Non-Native)
Comment=FreeCAD candidate with bundled upstream runtime
GenericName=CAD Application
Exec=freecad-can-non-native %F
TryExec=freecad-can-non-native
Icon=%{name}
Terminal=false
Type=Application
Categories=Graphics;Science;Education;Engineering;
StartupNotify=true
StartupWMClass=FreeCAD
MimeType=application/x-extension-fcstd;model/step;model/stl;
EOF
desktop-file-validate %{buildroot}%{_datadir}/applications/org.freecad.FreeCAD.Candidate.NonNative.desktop
cat > %{buildroot}%{_metainfodir}/org.freecad.FreeCAD.Candidate.NonNative.metainfo.xml <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>org.freecad.FreeCAD.Candidate.NonNative</id>
  <name>FreeCAD Candidate (Non-Native)</name>
  <summary>FreeCAD candidate with the bundled upstream runtime</summary>
  <description><p>FreeCAD release candidate installed with its bundled upstream Linux runtime.</p></description>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>LGPL-2.1-or-later</project_license>
  <launchable type="desktop-id">org.freecad.FreeCAD.Candidate.NonNative.desktop</launchable>
  <provides>
    <binary>freecad-can-non-native</binary>
  </provides>
</component>
EOF

%files
/opt/%{name}/
%{_bindir}/freecad-can-non-native
%{_datadir}/applications/org.freecad.FreeCAD.Candidate.NonNative.desktop
%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg
%{_metainfodir}/org.freecad.FreeCAD.Candidate.NonNative.metainfo.xml

%post
# Yan yana kurulum uyarısı.
if [ -x %{_bindir}/freecad ]; then
    echo "NOTE: native stable FreeCAD is also installed; package launchers and runtime paths remain separate." >&2
fi
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
