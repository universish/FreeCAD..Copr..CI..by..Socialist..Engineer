# Non-native AppImage-derived candidate Fedora package
# Uses extracted AppImage payload under /opt/freecad-candidate-non-native

%bcond_with tests

Name:           freecad-candidate-non-native
Version:        @VERSION@
Release:        @RELEASE@%{?dist}
Summary:        General purpose parametric 3D CAD modeler candidate (AppImage non-native build)
License:        LGPL-2.0-or-later
URL:            https://www.freecad.org/
Source0:        freecad-appimage-payload.tar.gz

BuildRequires:  desktop-file-utils
Requires:       hicolor-icon-theme shared-mime-info
Requires(post,postun): desktop-file-utils shared-mime-info
Conflicts:      freecad-non-native

%description
FreeCAD candidate non-native package bundled with its own runtime extracted from the official AppImage.

%prep
%setup -T -a 0 -q -c -n FreeCAD-CandidateNonNative-%{version}

%build
# Pre-extracted AppImage bundle; no compilation needed.

%install
mkdir -p %{buildroot}%{_optdir}/freecad-candidate-non-native
cp -rp * %{buildroot}%{_optdir}/freecad-candidate-non-native/

mkdir -p %{buildroot}%{_bindir}
cat << 'EOF' > %{buildroot}%{_bindir}/freecad-can-non-native
#!/bin/sh
exec /opt/freecad-candidate-non-native/AppRun "$@"
EOF
chmod +x %{buildroot}%{_bindir}/freecad-can-non-native

mkdir -p %{buildroot}%{_datadir}/applications
cat << 'EOF' > %{buildroot}%{_datadir}/applications/org.freecad.FreeCADCandidateNonNative.desktop
[Desktop Entry]
Name=FreeCAD Candidate (Non-Native)
Comment=Parametric 3D modeler candidate (AppImage runtime)
Exec=freecad-can-non-native %F
Icon=freecad
Terminal=false
Type=Application
Categories=Graphics;Engineering;3DGraphics;
MimeType=application/x-extension-fcstd;
EOF

%post
/usr/bin/update-desktop-database &>/dev/null || :
/usr/bin/update-mime-database %{_datadir}/mime &>/dev/null || :

%postun
/usr/bin/update-desktop-database &>/dev/null || :
/usr/bin/update-mime-database %{_datadir}/mime &>/dev/null || :

%files
%{_bindir}/freecad-can-non-native
%{_optdir}/freecad-candidate-non-native/
%{_datadir}/applications/org.freecad.FreeCADCandidateNonNative.desktop

%changelog
* Sun Nov 08 2026 universish <universish@tutamail.com> - @VERSION@-@RELEASE@
- Non-native FreeCAD candidate package using AppImage runtime layout under /opt
