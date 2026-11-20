# -*- rpm-spec -*-
#
# FreeCAD RPM spec
# Версія: @VERSION@
# Встановлення: системний макет (/usr/lib64/freecad, /usr/bin/freecad)
# Стратегія залежностей: максимальне використання системних бібліотек
#   (-devel пакети Fedora), бундлюються лише SMESH, zipios++, lru-cache, 3Dconnexion
#
# Patches:
#   0001 — (за потреби) сумісність із системними версіями бібліотек
#   (boost 1.90, pyside 6.11, coin 4.0.10 тощо)

%{!?fc_package:%global fc_package freecad}
%{!?fc_command:%global fc_command freecad}
%{!?fc_cmd_command:%global fc_cmd_command freecadcmd}
%{!?fc_thumbnail_command:%global fc_thumbnail_command freecad-thumbnailer}
%{!?fc_app_id:%global fc_app_id org.freecad.FreeCAD}
%{!?fc_icon_name:%global fc_icon_name org.freecad.FreeCAD}
%{!?fc_desktop_file:%global fc_desktop_file org.freecad.FreeCAD.desktop}
%{!?fc_metainfo_file:%global fc_metainfo_file org.freecad.FreeCAD.metainfo.xml}
%{!?fc_mime_file:%global fc_mime_file org.freecad.FreeCAD.xml}
%{!?fc_thumbnail_file:%global fc_thumbnail_file FreeCAD.thumbnailer}
%{!?fc_shared_mime_icon_owner:%global fc_shared_mime_icon_owner 1}
Name:           %{fc_package}
Epoch:          1
Version:        @VERSION@
Release:        @RELEASE@%{?dist}
Summary:        A 3D parametric modeler

License:        LGPL-2.1-or-later AND Zlib AND BSD-3-Clause AND Apache-2.0 AND EUPL-1.2 AND BSL-1.0 AND MIT AND GPL-2.0-or-later AND CC-BY-SA-4.0
URL:            https://www.freecad.org/
Source0:        freecad-sources.tar.gz
Source1:        README.md

# Патчі (додаються по мірі необхідності під час збірки)
Patch0:         0001-fix-nlohmann-json-include.patch
Patch1:         0002-find-external-e57format.patch
# Patch2:         0003-boost-1.90-compat.patch
# Patch3:         0004-pyside-6.11-compat.patch

# Тестування та debug-пакунок не збираємо (speed); бінарник не стрипуємо
%global debug_package %{nil}

# Увімкнути/вимкнути тести (зараз вимкнено - деякі тести падають у mock chroot)
%bcond_with tests

# ────────────────────────────────────────────────────────────────────────────
# Build tools
# ────────────────────────────────────────────────────────────────────────────
BuildRequires:  cmake >= 3.22
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  make
BuildRequires:  patch
BuildRequires:  pkgconfig
BuildRequires:  python3-devel
BuildRequires:  swig
BuildRequires:  desktop-file-utils
BuildRequires:  dos2unix
%if 0%{?fedora}
# Upstream's current Fedora package profile needs these additional build tools.
BuildRequires:  doxygen
BuildRequires:  gettext
BuildRequires:  graphviz
BuildRequires:  libappstream-glib
BuildRequires:  strace
BuildRequires:  tbb-devel
%endif

# ── Системні devel-пакети (з них беруться бібліотеки) ──────────────────────
# Coin3D (Coin4 4.0.10 на Fedora 44/45)
BuildRequires:  Coin4-devel
# OpenCASCADE
BuildRequires:  opencascade-devel
# MEDFile
BuildRequires:  med-devel
# VTK
BuildRequires:  vtk-devel
# Boost
BuildRequires:  boost-devel
# Eigen3
BuildRequires:  eigen3-devel
# pybind11
%if 0%{?fedora}
BuildRequires:  python3-pybind11
%else
BuildRequires:  pybind11-devel
%endif
# PyCXX
BuildRequires:  python3-pycxx-devel
# PySide6 / Shiboken6
BuildRequires:  python3-pyside6-devel
BuildRequires:  python3-shiboken6-devel
# Pivy
BuildRequires:  python3-pivy
# Matplotlib
BuildRequires:  python3-matplotlib
# fmt
BuildRequires:  fmt-devel
# yaml-cpp
BuildRequires:  yaml-cpp-devel
# nlohmann_json
BuildRequires:  nlohmann-json-devel
# Microsoft GSL (Guidelines Support Library)
BuildRequires:  guidelines-support-library-devel
# OndselSolver
BuildRequires:  ondselsolver-devel
# libE57Format
BuildRequires:  libE57Format-devel
# libkdtree++
BuildRequires:  libkdtree++-devel
# orocos-kdl
BuildRequires:  orocos-kdl-devel
# GTest / GMock
BuildRequires:  gtest-devel
BuildRequires:  gmock-devel
# HDF5 static
BuildRequires:  hdf5-static
# OpenMPI
BuildRequires:  openmpi-devel
# Xerces-C
BuildRequires:  xerces-c-devel
# ICU
BuildRequires:  libicu-devel
# libspnav
BuildRequires:  libspnav-devel
# OpenGL / GLU
BuildRequires:  mesa-libGL-devel
BuildRequires:  mesa-libGLU-devel
# freetype
BuildRequires:  freetype-devel
# zipios++ (system version too old 0.1.5.9 — bundled)
# BuildRequires:  zipios++-devel
# SMESH (system not available — bundled)
# BuildRequires:  smesh-devel

# ── GUI / Qt6 залежності ────────────────────────────────────────────────────
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtsvg-devel
BuildRequires:  qt6-qttools-devel
%if 0%{?fedora}
# Additional Fedora libraries and tools required by current FreeCAD sources.
BuildRequires:  freeimage-devel
BuildRequires:  libglvnd-devel
BuildRequires:  libXmu-devel
BuildRequires:  mesa-libEGL-devel
BuildRequires:  pyside6-tools
BuildRequires:  python3-lark
BuildRequires:  qt6-qttools-static
%endif

# ── Runtime Requires (головні динамічні залежності; точні обирає rpm auto-deps)
# ────────────────────────────────────────────────────────────────────────────
Requires:       %{name}-data = %{epoch}:%{version}-%{release}
Requires:       python3-pivy
Requires:       python3-matplotlib
Requires:       hicolor-icon-theme
Requires:       shared-mime-info
%if 0%{?fedora}
Requires:       python3-collada
Requires:       python3-defusedxml
Requires:       python3-ply
Requires:       python3-pyside6
Requires:       python3-typing-extensions
Requires:       qt6-assistant
%endif

# Bundled libraries (для rpmlint / transparency)
Provides:       bundled(zipios++) = 0.1.5.9
Provides:       bundled(SMESH) = 7.7.1.0
Provides:       bundled(lru-cache) = 1.0
Provides:       bundled(3Dconnexion) = 1.0

# Architecture exclusions (спадщина від openmpi та libE57Format)
ExcludeArch:    %{ix86}
ExcludeArch:    s390x

# Сховати внутрішні бібліотеки від автозалежностей
%global __provides_exclude_from ^%{_libdir}/%{name}/.*$
%global __requires_exclude ^(lib(Driver(|DAT|STL|UNV)|FreeCAD(App|Base|Gui)|MEFISTO2|SMDS|SMESH|SMESHDS|StdMeshers|area-native)[.]so.*)$

%description
FreeCAD is an open-source, free parametric 3D computer-aided design (CAD)
modeling tool used to create objects ranging from simple designs to complex
projects consisting of extensive assemblies of numerous parts.

%package data
Summary:        Data files for package %{name}
License:        LGPL-2.1-or-later AND GPL-2.0-or-later AND CC-BY-3.0 AND CC-BY-4.0 AND CC-BY-SA-4.0
BuildArch:      noarch

%description data
This package provides data files for package %{name}.

# ────────────────────────────────────────────────────────────────────────────
%prep
%setup -c -q -n FreeCAD-%{version}

# Convert CRLF to LF (upstream tarball has Windows line endings)
find . -type f \( -name "*.h" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.c" -o -name "*.cxx" \) -exec dos2unix {} + 2>/dev/null || true

# Apply patches manually after line ending conversion
%patch -P0 -p1
%patch -P1 -p1

# Видаляємо бандлі, які замінюємо системними пакетами
rm -rf \
  src/3rdParty/json \
  src/3rdParty/libkdtree \
  src/3rdParty/PyCXX \
  src/3rdParty/OndselSolver \
  src/3rdParty/libE57Format \
  tests/lib \
  src/3rdParty/GSL

# SMESH та zipios++ залишаємо (системні версії несумісні / відсутні)

# ────────────────────────────────────────────────────────────────────────────
%build
# Обмеження паралелізму (FreeCAD потребує багато RAM)
export CMAKE_BUILD_PARALLEL_LEVEL=%{?_smp_mflags:2}%{!?_smp_mflags:2}
export CMAKE_POLICY_VERSION_MINIMUM=3.5

%cmake \
  -DCMAKE_INSTALL_PREFIX=%{_libdir}/%{name} \
  -DCMAKE_INSTALL_BINDIR=%{_libdir}/%{name}/bin \
  -DCMAKE_INSTALL_LIBDIR=%{_libdir}/%{name} \
  -DCMAKE_INSTALL_DATAROOTDIR=%{_datadir} \
  -DCMAKE_INSTALL_DATADIR=../../share/%{name} \
  -DFREECAD_USE_EXTERNAL_ZIPIOS=OFF \
  -DFREECAD_USE_EXTERNAL_SMESH=OFF \
  -DFREECAD_USE_EXTERNAL_KDL=ON \
  -DFREECAD_USE_EXTERNAL_ONDSELSOLVER=ON \
  -DFREECAD_USE_EXTERNAL_E57FORMAT=ON \
  -DFREECAD_USE_EXTERNAL_PYCXX=ON \
  -DFREECAD_USE_EXTERNAL_KDTREE=ON \
  -DFREECAD_USE_EXTERNAL_JSON=ON \
  -DFREECAD_USE_EXTERNAL_COIN_PIVY=ON \
  -DFREECAD_CHECK_PIVY=ON \
  -DFREECAD_VERSION_INCLUDE_GIT=OFF \
  -DBUILD_GUI=ON \
  -DBUILD_FEM_NETGEN=OFF \
  -Wno-dev

%cmake_build

# ────────────────────────────────────────────────────────────────────────────
%install
%cmake_install

# Keep Python modules under this package's private prefix so stable and
# candidate installations can coexist.
mkdir -p %{buildroot}%{_libdir}/%{name}/python
if [ -d %{buildroot}%{python3_sitelib}/freecad ]; then
  mv %{buildroot}%{python3_sitelib}/freecad %{buildroot}%{_libdir}/%{name}/python/
fi

# Прибираємо лишню документацію
rm -f %{buildroot}%{_docdir}/FreeCAD/LICENSE.html
rm -f %{buildroot}%{_docdir}/FreeCAD/ThirdPartyLibraries.html
rmdir %{buildroot}%{_docdir}/FreeCAD 2>/dev/null || true

# Package-specific launchers avoid file collisions between release channels.
mkdir -p %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/%{fc_command} <<EOF
#!/bin/sh
export PYTHONPATH="%{_libdir}/%{name}/python\${PYTHONPATH:+:\$PYTHONPATH}"
export XDG_CONFIG_HOME="\${XDG_CONFIG_HOME:-\$HOME/.config}/%{name}"
export XDG_DATA_HOME="\${XDG_DATA_HOME:-\$HOME/.local/share}/%{name}"
export FREECAD_USER_HOME="\$XDG_DATA_HOME"
mkdir -p "\$FREECAD_USER_HOME"
exec %{_libdir}/%{name}/bin/FreeCAD "\$@"
EOF
cat > %{buildroot}%{_bindir}/%{fc_cmd_command} <<EOF
#!/bin/sh
export PYTHONPATH="%{_libdir}/%{name}/python\${PYTHONPATH:+:\$PYTHONPATH}"
export XDG_CONFIG_HOME="\${XDG_CONFIG_HOME:-\$HOME/.config}/%{name}"
export XDG_DATA_HOME="\${XDG_DATA_HOME:-\$HOME/.local/share}/%{name}"
export FREECAD_USER_HOME="\$XDG_DATA_HOME"
mkdir -p "\$FREECAD_USER_HOME"
exec %{_libdir}/%{name}/bin/FreeCADCmd "\$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/%{fc_command} %{buildroot}%{_bindir}/%{fc_cmd_command}
ln -sr %{buildroot}%{_libdir}/%{name}/bin/freecad-thumbnailer %{buildroot}%{_bindir}/%{fc_thumbnail_command}

# Python byte-compile
%py_byte_compile %{python3} %{buildroot}%{_libdir}/%{name}/

# Give shared desktop and MIME files this package's own IDs and launcher.
desktop_file=$(find %{buildroot}%{_datadir}/applications -maxdepth 1 -type f -name 'org.freecad.FreeCAD.desktop' -print -quit)
test -n "$desktop_file"
mv "$desktop_file" "%{buildroot}%{_datadir}/applications/%{fc_desktop_file}"
sed -i \
  -e 's/^Exec=.*/Exec=%{fc_command} %F/' \
  -e 's/^TryExec=.*/TryExec=%{fc_command}/' \
  -e 's/^Icon=.*/Icon=%{fc_icon_name}/' \
  -e 's/^Name=.*/Name=%{name}/' \
  "%{buildroot}%{_datadir}/applications/%{fc_desktop_file}"
desktop-file-validate "%{buildroot}%{_datadir}/applications/%{fc_desktop_file}"

metainfo_file=$(find %{buildroot}%{_metainfodir} -maxdepth 1 -type f -name 'org.freecad.FreeCAD.metainfo.xml' -print -quit)
test -n "$metainfo_file"
mv "$metainfo_file" "%{buildroot}%{_metainfodir}/%{fc_metainfo_file}"
sed -i 's/org\.freecad\.FreeCAD/%{fc_app_id}/g' "%{buildroot}%{_metainfodir}/%{fc_metainfo_file}"

icon_list=$(mktemp)
find %{buildroot}%{_datadir}/icons/hicolor -type f -name 'org.freecad.FreeCAD*' -print > "$icon_list"
test -s "$icon_list"
while IFS= read -r icon_file; do
  icon_dir=$(dirname "$icon_file")
  icon_base=$(basename "$icon_file")
  icon_new=$(printf '%s' "$icon_base" | sed 's/org\.freecad\.FreeCAD/%{fc_icon_name}/g')
  mv "$icon_file" "$icon_dir/$icon_new"
done < "$icon_list"
rm -f "$icon_list"

mime_file=$(find %{buildroot}%{_datadir}/mime/packages -maxdepth 1 -type f -name 'org.freecad.FreeCAD.xml' -print -quit)
if [ -n "$mime_file" ]; then
  mv "$mime_file" "%{buildroot}%{_datadir}/mime/packages/%{fc_mime_file}"
  sed -i 's/org\.freecad\.FreeCAD/%{fc_app_id}/g' "%{buildroot}%{_datadir}/mime/packages/%{fc_mime_file}"
fi

thumbnailer_file=$(find %{buildroot}%{_datadir}/thumbnailers -maxdepth 1 -type f -name 'FreeCAD.thumbnailer' -print -quit)
if [ -n "$thumbnailer_file" ]; then
  mv "$thumbnailer_file" "%{buildroot}%{_datadir}/thumbnailers/%{fc_thumbnail_file}"
  sed -i 's/^Exec=.*/Exec=%{fc_thumbnail_command} %i %o/' "%{buildroot}%{_datadir}/thumbnailers/%{fc_thumbnail_file}"
fi

pixmap_file=%{buildroot}%{_datadir}/pixmaps/freecad.svg
if [ -f "$pixmap_file" ]; then
  mv "$pixmap_file" "%{buildroot}%{_datadir}/pixmaps/freecad-%{name}.svg"
fi

# ────────────────────────────────────────────────────────────────────────────
%check
%if %{with tests}
export QT_QPA_PLATFORM=offscreen
%ctest
%endif
desktop-file-validate %{buildroot}%{_datadir}/applications/%{fc_desktop_file}
%if 0%{?fedora}
appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/%{fc_metainfo_file}
%endif

# ────────────────────────────────────────────────────────────────────────────
%post
for other_package in freecad freecad-candidate freecad-non-native freecad-candidate-non-native; do
  if [ "$other_package" != "%{name}" ] && rpm -q "$other_package" >/dev/null 2>&1; then
    echo "FreeCAD package $other_package is also installed; this package keeps a separate launcher and user configuration." >&2
  fi
done
/usr/bin/update-desktop-database %{_datadir}/applications &>/dev/null ||:
/usr/bin/gtk-update-icon-cache -f -t %{_datadir}/icons/hicolor &>/dev/null ||:

%postun
/usr/bin/update-desktop-database %{_datadir}/applications &>/dev/null ||:
/usr/bin/gtk-update-icon-cache -f -t %{_datadir}/icons/hicolor &>/dev/null ||:

# ────────────────────────────────────────────────────────────────────────────
%files
%license LICENSE
%doc README.md
%{_bindir}/%{fc_command}
%{_bindir}/%{fc_cmd_command}
%{_bindir}/%{fc_thumbnail_command}
%{_libdir}/%{name}/
%{_datadir}/applications/%{fc_desktop_file}
%{_datadir}/icons/hicolor/*/apps/%{fc_icon_name}.*
%if %{fc_shared_mime_icon_owner}
%{_datadir}/icons/hicolor/scalable/mimetypes/application-x-extension-fcstd.svg
%endif
%{_metainfodir}/%{fc_metainfo_file}
%{_datadir}/mime/packages/%{fc_mime_file}
%{_datadir}/pixmaps/freecad-%{name}.svg
%{_datadir}/thumbnailers/%{fc_thumbnail_file}
%dir %{_datadir}/thumbnailers

%files data
%license LICENSE
%{_datadir}/%{name}/

# ────────────────────────────────────────────────────────────────────────────
%changelog
* Sat Oct 17 2026 FreeCAD RPM Packager <freecad@copr.fedorainfracloud.org> - @VERSION@-@RELEASE@
- Initial packaging of FreeCAD 1.1.4 for Fedora 44/45 (COPR)
- System libraries: Coin4, OpenCASCADE, VTK, Boost, Eigen3, PySide6, Pivy, fmt, yaml-cpp, nlohmann_json, GSL, OndselSolver, libE57Format, libkdtree++, orocos-kdl, MEDFile, Xerces-C, ICU, OpenMPI, HDF5, gtest/gmock
- Bundled: SMESH, zipios++, lru-cache, 3Dconnexion
- System layout: %{_libdir}/freecad + symlinks in %{_bindir}
- Subpackage: freecad-data (noarch)
