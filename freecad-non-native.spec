# Non-native AppImage-derived Fedora package
# Uses extracted AppImage payload under /opt/freecad-non-native

%bcond_with tests

Name:           freecad-non-native
Version:        @VERSION@
Release:        @RELEASE@%{?dist}
Summary:        General purpose parametric 3D CAD modeler (AppImage non-native build)
License:        LGPL-2.0-or-later
URL:            https://www.freecad.org/
Source0:        freecad-appimage-payload.tar.gz

BuildRequires:  desktop-file-utils
Requires:       hicolor-icon-theme shared-mime-info
Requires(post,postun): desktop-file-utils shared-mime-info

%description
FreeCAD non-native package bundled with its own runtime extracted from the official AppImage.

%prep
%setup -T -a 0 -q -c -n FreeCAD-NonNative-%{version}

%build
# Pre-extracted AppImage bundle; no compilation needed.

%install
mkdir -p %{buildroot}%{_optdir}/freecad-non-native
cp -rp * %{buildroot}%{_optdir}/freecad-non-native/

mkdir -p %{buildroot}%{_bindir}
cat << 'EOF' > %{buildroot}%{_bindir}/freecad-non-native
#!/bin/sh
exec /opt/freecad-non-native/AppRun "$@"
EOF
chmod +x %{buildroot}%{_bindir}/freecad-non-native

mkdir -p %{buildroot}%{_datadir}/applications
cat << 'EOF' > %{buildroot}%{_datadir}/applications/org.freecad.FreeCADNonNative.desktop
[Desktop Entry]
Name=FreeCAD (Non-Native)
Comment=Parametric 3D modeler (AppImage runtime)
Exec=freecad-non-native %F
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
%{_bindir}/freecad-non-native
%{_optdir}/freecad-non-native/
%{_datadir}/applications/org.freecad.FreeCADNonNative.desktop

%changelog
* Sun Nov 08 2026 universish <universish@tutamail.com> - @VERSION@-@RELEASE@
- Non-native FreeCAD package using AppImage runtime layout under /opt
