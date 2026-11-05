# freecad-candidate.spec — FreeCAD ÖN-SÜRÜM (Release Candidate / beta) sürümü.
# Upstream önceden derlenmiş Linux sürümünü (rpm > deb > AppImage önceliğiyle)
# yeniden paketler. Kararlı 'freecad' paketiyle YAN YANA kurulabilir:
# ikili adı freecad-can, kurulum dizini /opt/freecad-candidate'dir.
# Bu spec KAYNAKTAN DERLEME YAPMAZ.

%global debug_package %{nil}

# RPATH denetimi KAPALI: bkz. freecad.spec — upstream conda/pixi yükünde
# hedefsiz mutlak RPATH kayıtları var; yük gömülü kütüphaneleriyle çalışır.
%global __brp_check_rpaths %{nil}

Name:           freecad-candidate
Version:        @VERSION@
Release:        @RELEASE@%{?dist}
Summary:        General-purpose parametric 3D CAD modeler (release candidate)

License:        LGPL-2.1-or-later
URL:            https://www.freecad.org/
Source0:        %{name}-%{version}.tar.gz

# Gömülü kütüphaneler Requires/Provides üretmesin (bkz. freecad.spec).
%define __requires_exclude_from ^/opt/%{name}
%define __provides_exclude_from ^/opt/%{name}

# Yalnızca tüm hedef dağıtımlarda ortak adlar (bkz. freecad.spec).
Requires:       hicolor-icon-theme
Requires:       xdg-utils

%description
FreeCAD is an open-source parametric 3D CAD modeler, made primarily to
design real-life objects of any size. This package contains the upstream
pre-release (release candidate / beta) build, repackaged into a native RPM
so it can be installed and updated side by side with the stable 'freecad'
package. The launcher command is 'freecad-can'.

%prep
%setup -q

%build
# Yeniden derleme yok: %%{_arch} altındaki normalize edilmiş önceden derlenmiş
# yük doğrudan kullanılır.

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

%files
/opt/%{name}/
%{_bindir}/%{name}
%{_bindir}/freecad-can
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/*/apps/%{name}.*

%post
# Yan yana kurulum uyarısı.
if [ -x %{_bindir}/freecad ]; then
    echo "NOTE: stable 'freecad' is also installed; both versions share the same user configuration directory." >&2
fi

%changelog
* Wed Nov 05 2026 universish <universish@tutamail.com> - 1.1.4-1
- Repackage upstream prebuilt FreeCAD 1.1.4
