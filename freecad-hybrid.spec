# Hybrid AppImage-derived RPM template for FreeCAD
# This is a compatibility package model for extracted AppImage payloads. It keeps
# the runtime in a dedicated prefix and avoids placing the bundle into /opt as a
# monolithic fallback for the native FreeCAD package.

%bcond_with tests

Name:           freecad-hybrid
Version:        @VERSION@
Release:        @RELEASE@%{?dist}
Summary:        FreeCAD AppImage-derived hybrid runtime package
License:        LGPL-2.0-or-later
URL:            https://www.freecad.org/
Source0:        freecad-appimage-payload.tar.gz

BuildRequires:  desktop-file-utils
Requires:       hicolor-icon-theme shared-mime-info
Requires(post,postun): desktop-file-utils shared-mime-info

%description
FreeCAD hybrid package that reuses an extracted AppImage payload while keeping
its bundled runtime isolated from the native Fedora package layout.

%prep
%setup -T -a 0 -q -c -n freecad-hybrid-%{version}

%build
# No source compilation; this package is intended for AppImage extraction.

%install
mkdir -p %{buildroot}%{_optdir}/freecad-hybrid
cp -rp * %{buildroot}%{_optdir}/freecad-hybrid/

mkdir -p %{buildroot}%{_bindir}
cat <<'EOF' > %{buildroot}%{_bindir}/freecad-hybrid
#!/bin/sh
exec /opt/freecad-hybrid/AppRun "$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/freecad-hybrid

mkdir -p %{buildroot}%{_datadir}/applications
cat <<'EOF' > %{buildroot}%{_datadir}/applications/org.freecad.FreeCADHybrid.desktop
[Desktop Entry]
Name=FreeCAD Hybrid
Comment=FreeCAD runtime extracted from the upstream AppImage
Exec=freecad-hybrid %F
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
%{_bindir}/freecad-hybrid
%{_optdir}/freecad-hybrid/
%{_datadir}/applications/org.freecad.FreeCADHybrid.desktop

%changelog
* Sun Nov 10 2026 universish <universish@tutamail.com> - @VERSION@-@RELEASE@
- Hybrid AppImage-based FreeCAD packaging template
