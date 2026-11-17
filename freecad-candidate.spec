# Native Fedora package built from the matching FreeCAD source tag.
# Source archives include initialized Git submodules; no AppImage/conda runtime
# or prebuilt third-party shared libraries are installed.

%bcond_with tests
%bcond_without bundled_zipios
%bcond_with bundled_pycxx
%bcond_without bundled_smesh
%bcond_with bundled_gtest

Name:           freecad-candidate
Version:        @VERSION@
Release:        @RELEASE@%{?dist}
Summary:        General purpose parametric 3D CAD modeler (release candidate)
License:        LGPL-2.1-or-later AND Zlib AND BSD-3-Clause AND Apache-2.0 AND EUPL-1.2 AND BSL-1.0 AND MIT AND GPL-2.0-or-later AND CC-BY-SA-4.0
URL:            https://www.freecad.org/
Source0:        freecad-sources.tar.gz
Patch0:         0001-fix-nlohmann-json-include.patch
Patch1:         0002-find-external-e57format.patch

%global plugins AssemblyApp AssemblyGui CAMSimulator DraftUtils Fem FreeCAD Import Inspection MatGui Materials Measure Mesh MeshPart Part PartDesignGui Path PathApp PathSimulator Points QtUnitGui ReverseEngineering Robot Sketcher Spreadsheet Start Surface TechDraw Web _PartDesign area flatmesh libDriver libDriverDAT libDriverSTL libDriverUNV libE57Format libMEFISTO2 libSMDS libSMESH libSMESHDS libStdMeshers libarea-native tsp_solver
%global exported_libs libOndselSolver
%global bundled_ondsel_solver_version 1.0.1

BuildRequires:  cmake gcc-c++ gettext doxygen swig graphviz gcc-gfortran desktop-file-utils tbb-devel ninja-build
BuildRequires:  boost-devel Coin4-devel eigen3-devel fmt-devel freeimage-devel libglvnd-devel libicu-devel libspnav-devel libXmu-devel med-devel mesa-libEGL-devel mesa-libGLU-devel netgen-mesher-devel netgen-mesher-devel-private opencascade-devel openmpi-devel python3 python3-devel python3-lark python3-matplotlib python3-pivy python3-pybind11 python3-pyside6-devel python3-shiboken6-devel pyside6-tools qt6-qttools-static qt6-qtsvg-devel vtk-devel xerces-c-devel yaml-cpp-devel
BuildRequires:  libappstream-glib
%if %{without bundled_smesh}
BuildRequires:  smesh-devel
%endif
%if %{without bundled_zipios}
BuildRequires:  zipios++-devel
%endif
%if %{without bundled_pycxx}
BuildRequires:  python3-pycxx-devel
%endif
%if %{with tests}
BuildRequires:  python3-typing-extensions xwayland-run weston
%if %{without bundled_gtest}
BuildRequires:  gtest-devel gmock-devel
%endif
%endif
Requires:       hicolor-icon-theme fmt python3-matplotlib python3-pivy python3-collada python3-pyside6 qt6-assistant python3-typing-extensions python3-defusedxml python3-ply
Requires(post,postun): desktop-file-utils shared-mime-info
Provides:       bundled(libondselsolver) = %{bundled_ondsel_solver_version}
Recommends:     python3-pysolar IfcOpenShell-python3

%global plugin_exclude %( for i in %{plugins}; do echo -n "\\|$i\\(Gui\\)\\?"; done )
%global lib_exclude %( for i in %{exported_libs}; do echo -n "\\|$i"; done )
%global __requires_exclude_from ^%{_libdir}/%{name}/(lib|Mod)/.*
%global __provides_exclude_from ^%{_libdir}/%{name}/Mod/.*
%global __provides_exclude ^(libFreeCAD.*%{plugin_exclude})\\.so.*
%global __requires_exclude ^(libFreeCAD.*%{plugin_exclude}%{lib_exclude})\\.so.*

%description
FreeCAD is an open-source parametric 3D CAD modeler for mechanical
engineering, product design, architecture and other engineering fields.

%prep
%setup -T -a 0 -q -c -n FreeCAD-%{version}
%patch -P0 -p1
%patch -P1 -p1

%build
LDFLAGS='-Wl,--as-needed -Wl,--no-undefined'; export LDFLAGS
%cmake \
    -DCMAKE_INSTALL_PREFIX=%{_libdir}/%{name} \
    -DCMAKE_INSTALL_DOCDIR=%{_docdir}/%{name} \
    -DCMAKE_INSTALL_INCLUDEDIR=%{_includedir} \
    -DRESOURCEDIR=%{_datadir}/%{name} \
    -DFREECAD_QT_VERSION:STRING=6 \
    -DFREECAD_USE_EXTERNAL_PIVY=TRUE \
    -DFREECAD_USE_EXTERNAL_FMT=TRUE \
    -DFREECAD_USE_PCL:BOOL=OFF \
    -DOpenGL_GL_PREFERENCE=GLVND \
    -DUSE_OCC=TRUE \
%if %{without bundled_pycxx}
    -DFREECAD_USE_EXTERNAL_PYCXX=TRUE \
%endif
%if %{without bundled_smesh}
    -DFREECAD_USE_EXTERNAL_SMESH=TRUE \
%endif
%if %{without bundled_zipios}
    -DFREECAD_USE_EXTERNAL_ZIPIOS=TRUE \
%endif
%if %{with tests}
%if %{without bundled_gtest}
    -DFREECAD_USE_EXTERNAL_GTEST=TRUE \
%endif
    -DENABLE_DEVELOPER_TESTS=TRUE \
%else
    -DENABLE_DEVELOPER_TESTS=FALSE \
%endif
    -DONDSELSOLVER_BUILD_EXE=TRUE \
    -DBUILD_GUI=TRUE \
    -G Ninja
%cmake_build

%install
%cmake_install
mkdir -p %{buildroot}%{_bindir} %{buildroot}%{_datadir} %{buildroot}%{_metainfodir}
mkdir -p %{buildroot}%{_libdir}/%{name}/python
if [ -d %{buildroot}%{python3_sitelib}/freecad ]; then
    mv %{buildroot}%{python3_sitelib}/freecad %{buildroot}%{_libdir}/%{name}/python/
fi
cat > %{buildroot}%{_bindir}/freecad-can <<EOF
#!/bin/sh
export PYTHONPATH="%{_libdir}/%{name}/python\${PYTHONPATH:+:\$PYTHONPATH}"
exec %{_libdir}/%{name}/bin/FreeCAD "\$@"
EOF
cat > %{buildroot}%{_bindir}/freecadcmd-can <<EOF
#!/bin/sh
export PYTHONPATH="%{_libdir}/%{name}/python\${PYTHONPATH:+:\$PYTHONPATH}"
exec %{_libdir}/%{name}/bin/FreeCADCmd "\$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/freecad-can %{buildroot}%{_bindir}/freecadcmd-can
rm -rf %{buildroot}%{_libdir}/%{name}/include/E57Format
rm -rf %{buildroot}%{_includedir}/gmock %{buildroot}%{_includedir}/gtest
rm -rf %{buildroot}%{_libdir}/%{name}/%{_lib}/cmake %{buildroot}%{_libdir}/%{name}/%{_lib}/pkgconfig
mv %{buildroot}%{_libdir}/%{name}/share/applications %{buildroot}%{_datadir}/
sed -i 's/^Exec=.*/Exec=freecad-can %F/; s/^TryExec=.*/TryExec=freecad-can/; s/^Icon=.*/Icon=org.freecad.FreeCAD.Candidate/' %{buildroot}%{_datadir}/applications/org.freecad.FreeCAD.desktop
mv %{buildroot}%{_datadir}/applications/org.freecad.FreeCAD.desktop %{buildroot}%{_datadir}/applications/org.freecad.FreeCAD.Candidate.desktop
mv %{buildroot}%{_libdir}/%{name}/share/metainfo/* %{buildroot}%{_metainfodir}/
if [ -f %{buildroot}%{_metainfodir}/org.freecad.FreeCAD.metainfo.xml ]; then
    sed -i 's/org\.freecad\.FreeCAD/org.freecad.FreeCAD.Candidate/g' \
        %{buildroot}%{_metainfodir}/org.freecad.FreeCAD.metainfo.xml
    mv %{buildroot}%{_metainfodir}/org.freecad.FreeCAD.metainfo.xml \
        %{buildroot}%{_metainfodir}/org.freecad.FreeCAD.Candidate.metainfo.xml
fi
mv %{buildroot}%{_libdir}/%{name}/share/icons %{buildroot}%{_datadir}/
icon_src=$(find %{buildroot}%{_datadir}/icons/hicolor -type f -iname '*FreeCAD*.svg' -print -quit)
if [ -z "$icon_src" ]; then
    echo "Candidate FreeCAD SVG icon was not installed" >&2
    exit 1
fi
install -D -m 0644 "$icon_src" \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/org.freecad.FreeCAD.Candidate.svg
find %{buildroot}%{_datadir}/icons/hicolor -type f \
    ! -name org.freecad.FreeCAD.Candidate.svg -delete
mv %{buildroot}%{_libdir}/%{name}/share/mime %{buildroot}%{_datadir}/
for mime_file in %{buildroot}%{_datadir}/mime/packages/*.xml; do
    [ -f "$mime_file" ] || continue
    mv "$mime_file" "${mime_file%.xml}-candidate.xml"
done
mv %{buildroot}%{_libdir}/%{name}/share/pixmaps %{buildroot}%{_datadir}/
mv %{buildroot}%{_libdir}/%{name}/share/thumbnailers %{buildroot}%{_datadir}/
mv %{buildroot}%{_libdir}/%{name}/share/pkgconfig %{buildroot}%{_datadir}/
rm -rf %{buildroot}%{_datadir}/pixmaps %{buildroot}%{_datadir}/thumbnailers

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/org.freecad.FreeCAD.Candidate.desktop
%{?fedora:appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/org.freecad.FreeCAD.Candidate.metainfo.xml}

%post
/usr/bin/update-desktop-database &>/dev/null || :
/usr/bin/update-mime-database %{_datadir}/mime &>/dev/null || :

%postun
/usr/bin/update-desktop-database &>/dev/null || :
/usr/bin/update-mime-database %{_datadir}/mime &>/dev/null || :

%files
%license %{_docdir}/%{name}/LICENSE.html
%doc %{_docdir}/%{name}/ThirdPartyLibraries.html
%{_bindir}/freecad-can
%{_bindir}/freecadcmd-can
%{_metainfodir}/org.freecad.FreeCAD.Candidate.metainfo.xml
%dir %{_libdir}/%{name}
%{_libdir}/%{name}/bin/
%{_libdir}/%{name}/%{_lib}/
%{_libdir}/%{name}/Ext/
%{_libdir}/%{name}/Mod/
%{_libdir}/%{name}/share/
%{_datadir}/applications/org.freecad.FreeCAD.Candidate.desktop
%{_datadir}/icons/hicolor/scalable/apps/org.freecad.FreeCAD.Candidate.svg
%{_datadir}/mime/packages/*-candidate.xml
%{_libdir}/%{name}/python/

%changelog
* Sun Nov 08 2026 universish <universish@tutamail.com> - @VERSION@-@RELEASE@
- Build FreeCAD candidate natively against Fedora libraries and Python modules
