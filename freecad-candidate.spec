# Native Fedora package built from the matching FreeCAD source tag.
# Source archives include initialized Git submodules; no AppImage/conda runtime
# or prebuilt third-party shared libraries are installed.

%bcond_without tests
%bcond_without bundled_zipios
%bcond_with bundled_pycxx
%bcond_without bundled_smesh
%bcond_with bundled_gtest

Name:           freecad-candidate
Version:        @VERSION@
Release:        @RELEASE@%{?dist}
Summary:        General purpose parametric 3D CAD modeler
License:        LGPL-2.0-or-later
URL:            https://www.freecad.org/
Source0:        freecad-sources.tar.gz

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
Conflicts:      freecad

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
ln -s ../%{_lib}/%{name}/bin/FreeCAD %{buildroot}%{_bindir}/freecad-can
ln -s ../%{_lib}/%{name}/bin/FreeCADCmd %{buildroot}%{_bindir}/freecadcmd-can
rm -rf %{buildroot}%{_libdir}/%{name}/include/E57Format
rm -rf %{buildroot}%{_includedir}/gmock %{buildroot}%{_includedir}/gtest
rm -rf %{buildroot}%{_libdir}/%{name}/%{_lib}/cmake %{buildroot}%{_libdir}/%{name}/%{_lib}/pkgconfig
mv %{buildroot}%{_libdir}/%{name}/share/applications %{buildroot}%{_datadir}/
sed -i 's/^Exec=.*/Exec=freecad-can %F/; s/^TryExec=.*/TryExec=freecad-can/' %{buildroot}%{_datadir}/applications/org.freecad.FreeCAD.desktop
mv %{buildroot}%{_datadir}/applications/org.freecad.FreeCAD.desktop %{buildroot}%{_datadir}/applications/freecad-candidate.desktop
mv %{buildroot}%{_libdir}/%{name}/share/metainfo/* %{buildroot}%{_metainfodir}/
mv %{buildroot}%{_libdir}/%{name}/share/icons %{buildroot}%{_datadir}/
mv %{buildroot}%{_libdir}/%{name}/share/pixmaps %{buildroot}%{_datadir}/
mv %{buildroot}%{_libdir}/%{name}/share/mime %{buildroot}%{_datadir}/
mv %{buildroot}%{_libdir}/%{name}/share/thumbnailers %{buildroot}%{_datadir}/
mv %{buildroot}%{_libdir}/%{name}/share/pkgconfig %{buildroot}%{_datadir}/

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/freecad-candidate.desktop
%{?fedora:appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/*.metainfo.xml}

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
%{_metainfodir}/*
%dir %{_libdir}/%{name}
%{_libdir}/%{name}/bin/
%{_libdir}/%{name}/%{_lib}/
%{_libdir}/%{name}/Ext/
%{_libdir}/%{name}/Mod/
%{_libdir}/%{name}/share/
%{_datadir}/applications/freecad-candidate.desktop
%{_datadir}/icons/hicolor/*
%{_datadir}/pixmaps/*
%{_datadir}/mime/packages/*
%{_datadir}/thumbnailers/*
%{python3_sitelib}/freecad/*

%changelog
* Sun Nov 08 2026 universish <universish@tutamail.com> - @VERSION@-@RELEASE@
- Build FreeCAD candidate natively against Fedora libraries and Python modules
