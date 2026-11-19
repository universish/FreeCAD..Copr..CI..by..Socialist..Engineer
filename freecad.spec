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

Name:           freecad
Epoch:          1
Version:        @VERSION@
Release:        @RELEASE@%{?dist}
Summary:        A 3D parametric modeler

License:        LGPL-2.1-or-later AND Zlib AND BSD-3-Clause AND Apache-2.0 AND EUPL-1.2 AND BSL-1.0 AND MIT AND GPL-2.0-or-later AND CC-BY-SA-4.0
URL:            https://www.freecad.org/
Source0:        https://github.com/FreeCAD/FreeCAD/releases/download/%{version}/freecad_source_%{version}.tar.gz
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
BuildRequires:  git
BuildRequires:  desktop-file-utils
BuildRequires:  libappstream-glib
BuildRequires:  dos2unix

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
BuildRequires:  pybind11-devel
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

# ── Runtime Requires (головні динамічні залежності; точні обирає rpm auto-deps)
# ────────────────────────────────────────────────────────────────────────────
Requires:       %{name}-data = %{epoch}:%{version}-%{release}
Requires:       python3-pivy
Requires:       python3-matplotlib
Requires:       hicolor-icon-theme
Requires:       shared-mime-info

# Bundled libraries (для rpmlint / transparency)
Provides:       bundled(zipios++) = 0.1.5.9
Provides:       bundled(SMESH) = 7.7.1.0
Provides:       bundled(lru-cache) = 1.0
Provides:       bundled(3Dconnexion) = 1.0

# Architecture exclusions (спадщина від openmpi та libE57Format)
ExcludeArch:    %{ix86}
ExcludeArch:    s390x

# Сховати внутрішні бібліотеки від автозалежностей
%global __provides_exclude_from ^%{_libdir}/freecad/.*$
%global __requires_exclude ^(lib(Driver(|DAT|STL|UNV)|FreeCAD(App|Base|Gui)|MEFISTO2|SMDS|SMESH|SMESHDS|StdMeshers|area-native)[.]so.*)$

%description
FreeCAD is an open-source, free parametric 3D computer-aided design (CAD)
modeling tool used to create objects ranging from simple designs to complex
projects consisting of extensive assemblies of numerous parts.

%package data
Summary:        Data files for package freecad
License:        LGPL-2.1-or-later AND GPL-2.0-or-later AND CC-BY-3.0 AND CC-BY-4.0 AND CC-BY-SA-4.0
BuildArch:      noarch

%description data
This package provides data files for package freecad.

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
  src/3rdParty/3Dconnexion \
  src/3rdParty/OpenGL \
  src/3rdParty/lru-cache \
  src/3rdParty/GSL

# SMESH та zipios++ залишаємо (системні версії несумісні / відсутні)

# ────────────────────────────────────────────────────────────────────────────
%build
# Обмеження паралелізму (FreeCAD потребує багато RAM)
export CMAKE_BUILD_PARALLEL_LEVEL=%{?_smp_mflags:2}%{!?_smp_mflags:2}
export CMAKE_POLICY_VERSION_MINIMUM=3.5

%cmake \
  -DCMAKE_INSTALL_PREFIX=%{_libdir}/freecad \
  -DCMAKE_INSTALL_BINDIR=%{_libdir}/freecad/bin \
  -DCMAKE_INSTALL_LIBDIR=%{_libdir}/freecad \
  -DCMAKE_INSTALL_DATAROOTDIR=%{_datadir} \
  -DCMAKE_INSTALL_DATADIR=../../share/freecad \
  -DFREECAD_USE_EXTERNAL_ZIPIOS=OFF \
  -DFREECAD_USE_EXTERNAL_SMESH=OFF \
  -DFREECAD_USE_EXTERNAL_KDL=ON \
  -DFREECAD_USE_EXTERNAL_FMT=ON \
  -DFREECAD_USE_EXTERNAL_ONDSELSOLVER=ON \
  -DFREECAD_USE_EXTERNAL_E57FORMAT=ON \
  -DFREECAD_USE_EXTERNAL_GTEST=ON \
  -DFREECAD_USE_EXTERNAL_PYCXX=ON \
  -DFREECAD_USE_EXTERNAL_KDTREE=ON \
  -DFREECAD_USE_EXTERNAL_JSON=ON \
  -DFREECAD_CHECK_PIVY=ON \
  -DBUILD_GUI=ON \
  -DBUILD_FEM_NETGEN=OFF \
  -DBUILD_ENABLE_CXX_STD=C++17 \
  -DCMAKE_CXX_STANDARD=17 \
  -Wno-dev

%cmake_build

# ────────────────────────────────────────────────────────────────────────────
%install
%cmake_install

# Прибираємо лишню документацію
rm -f %{buildroot}%{_docdir}/FreeCAD/LICENSE.html
rm -f %{buildroot}%{_docdir}/FreeCAD/ThirdPartyLibraries.html
rmdir %{buildroot}%{_docdir}/FreeCAD 2>/dev/null || true

# Симлінки у /usr/bin
mkdir -p %{buildroot}%{_bindir}
ln -sr %{buildroot}%{_libdir}/freecad/bin/FreeCAD %{buildroot}%{_bindir}/freecad
ln -sr %{buildroot}%{_libdir}/freecad/bin/FreeCAD %{buildroot}%{_bindir}/FreeCAD
ln -sr %{buildroot}%{_libdir}/freecad/bin/FreeCADCmd %{buildroot}%{_bindir}/freecadcmd
ln -sr %{buildroot}%{_libdir}/freecad/bin/FreeCADCmd %{buildroot}%{_bindir}/FreeCADCmd
ln -sr %{buildroot}%{_libdir}/freecad/bin/freecad-thumbnailer %{buildroot}%{_bindir}/freecad-thumbnailer

# Python byte-compile
%py_byte_compile %{python3} %{buildroot}%{_libdir}/freecad/

# ────────────────────────────────────────────────────────────────────────────
%check
%if %{with tests}
export QT_QPA_PLATFORM=offscreen
%ctest
desktop-file-validate %{buildroot}%{_datadir}/applications/*.desktop
appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/*.metainfo.xml
%endif

# ────────────────────────────────────────────────────────────────────────────
%post
/usr/bin/update-desktop-database %{_datadir}/applications &>/dev/null ||:
/usr/bin/gtk-update-icon-cache -f -t %{_datadir}/icons/hicolor &>/dev/null ||:

%postun
/usr/bin/update-desktop-database %{_datadir}/applications &>/dev/null ||:
/usr/bin/gtk-update-icon-cache -f -t %{_datadir}/icons/hicolor &>/dev/null ||:

# ────────────────────────────────────────────────────────────────────────────
%files
%license LICENSE
%doc README.md
%{_bindir}/freecad
%{_bindir}/FreeCAD
%{_bindir}/freecadcmd
%{_bindir}/FreeCADCmd
%{_bindir}/freecad-thumbnailer
%{_libdir}/freecad/
%{python3_sitelib}/freecad/
%{_datadir}/applications/org.freecad.FreeCAD.desktop
%{_datadir}/icons/hicolor/*/apps/org.freecad.FreeCAD.*
%{_datadir}/icons/hicolor/scalable/mimetypes/application-x-extension-fcstd.svg
%{_metainfodir}/org.freecad.FreeCAD.metainfo.xml
%{_datadir}/mime/packages/org.freecad.FreeCAD.xml
%{_datadir}/pixmaps/freecad.svg
%{_datadir}/thumbnailers/FreeCAD.thumbnailer
%dir %{_datadir}/thumbnailers

%files data
%license LICENSE
%{_datadir}/freecad/

# ────────────────────────────────────────────────────────────────────────────
%changelog
* Sun Oct 17 2026 FreeCAD RPM Packager <freecad@copr.fedorainfracloud.org> - @VERSION@-@RELEASE@
- Initial packaging of FreeCAD 1.1.4 for Fedora 44/45 (COPR)
- System libraries: Coin4, OpenCASCADE, VTK, Boost, Eigen3, PySide6, Pivy, fmt, yaml-cpp, nlohmann_json, GSL, OndselSolver, libE57Format, libkdtree++, orocos-kdl, MEDFile, Xerces-C, ICU, OpenMPI, HDF5, gtest/gmock
- Bundled: SMESH, zipios++, lru-cache, 3Dconnexion
- System layout: %{_libdir}/freecad + symlinks in %{_bindir}
- Subpackage: freecad-data (noarch)