# freecad-candidate.spec — FreeCAD ÖN-SÜRÜM (Release Candidate / beta) sürümü.
# Upstream önceden derlenmiş Linux sürümünü (rpm > deb > AppImage önceliğiyle)
# yeniden paketler. Kararlı 'freecad' paketiyle YAN YANA kurulabilir:
# ikili adı freecad-can, kurulum dizini /opt/freecad-candidate'dir.
# Bu spec KAYNAKTAN DERLEME YAPMAZ.

# Otomatik Python byte-compile (pyc üretme) işlemini tamamen devredışı bırakır.
%global __brp_python_bytecompile %{nil}
%global __os_install_post %(echo '%{__os_install_post}' | sed -e 's!/usr/lib[^[:space:]]*/brp-python-bytecompile[[:space:]].*$!!g')

# Önceden derlenmiş binary paketlerde debug paketi oluşturulmasını engeller.
%global debug_package %{nil}

# RPM'in binary dosyaları strip ederek (kırparak) bozmasını engeller.
# %global __strip /bin/true

# RPATH denetimi KAPALI: bkz. freecad.spec — upstream conda/pixi yükünde
# hedefsiz mutlak RPATH kayıtları var; yük gömülü kütüphaneleriyle çalışır.
%global __brp_check_rpaths %{nil}

# Shebang denetimi KAPALI: bkz. freecad.spec — payload'taki conda kalıntısı
# shebang'ler brp-mangle-shebangs'i HATA ile düşürür; repackage.sh düzeltir.
%global __brp_mangle_shebangs %{nil}

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
BuildRequires:  patchelf

%description
FreeCAD is an open-source parametric 3D CAD modeler, made primarily to
design real-life objects of any size. This package contains the upstream
pre-release (release candidate / beta) build, repackaged into a native RPM
so it can be installed and updated side by side with the stable 'freecad'
package. The launcher command is 'freecad-can'.

%prep
# Eğer ortam bir Enterprise Linux (EPEL) ise, EPEL reposunu mock/dnf ortamına ekle
%if 0%{?rhel} || 0%{?centos} || 0%{?almalinux}
cat << 'EOF' | sudo tee /etc/yum.repos.d/epel-additional.repo
[epel-additional]
name=Extra Packages for Enterprise Linux %{rhel} - $basearch
baseurl=https://dl.fedoraproject.org/pub/epel/%{rhel}/Everything/$basearch/
enabled=1
gpgcheck=0
EOF
%endif

%autosetup -n %{name}-%{version}

%setup -q

%build
# Yeniden derleme yok: %%{_arch} altındaki normalize edilmiş önceden derlenmiş
# yük doğrudan kullanılır.

%install
install -d %{buildroot}/opt %{buildroot}%{_bindir} \
    %{buildroot}%{_datadir}/applications %{buildroot}%{_datadir}/icons

# Payload seçimi: bkz. freecad.spec — mikro-mimari chroot'ları x86_64
# payload'una yönlendir.
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

# Yan yana kurulum için klasörü ve binary dosyasını yeniden adlandırın
mv %{buildroot}/opt/freecad %{buildroot}/opt/%{name}
mv %{buildroot}%{_bindir}/freecad %{buildroot}%{_bindir}/freecad-can

# Kısayol (Desktop) kopyalama ve düzenleme
cp -a "$PAYLOAD"/usr/share/applications/*.desktop %{buildroot}%{_datadir}/applications/%{name}.desktop
cp -a "$PAYLOAD"/usr/share/icons/* %{buildroot}%{_datadir}/icons/

sed -i 's/^Exec=.*/Exec=freecad-can %F/g' %{buildroot}%{_datadir}/applications/%{name}.desktop

command -v desktop-file-validate >/dev/null 2>&1 && \
    desktop-file-validate %{buildroot}%{_datadir}/applications/%{name}.desktop || true

export QA_RPATHS=0x0002
patchelf --remove-rpath %{buildroot}/opt/%{name}/usr/lib/libtcl8.6.so
patchelf --remove-rpath %{buildroot}/opt/%{name}/usr/lib/libtk8.6.so

# Çalıştırılabilir dosyalara gerekli izinleri zorla
chmod -R +x %{buildroot}/opt/%{name}/usr/bin/
chmod +x %{buildroot}/opt/%{name}/AppRun

# Desktop dosyası içindeki "Exec=freecad" komutunu "Exec=freecad-can" ile değiştir (Masaüstü kısayolu hatasını önler)
sed -i 's/^Exec=.*/Exec=freecad-can %F/g' %{buildroot}%{_datadir}/applications/%{name}.desktop

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
