# FreeCAD Copr RPM Automation

This repository builds and publishes stable and prerelease FreeCAD packages for x86_64 and aarch64. The native family compiles the upstream source against distribution libraries. The non-native family repackages the first available upstream Linux artifact in RPM → DEB → AppImage priority order.

## Packages

| Channel | Family | RPM name | Command | AppStream ID |
| --- | --- | --- | --- | --- |
| Stable | Native | `freecad` | `freecad` | `org.freecad.FreeCAD` |
| Candidate | Native | `freecad-candidate` | `freecad-can` | `org.freecad.FreeCAD.Candidate` |
| Stable | Non-native | `freecad-non-native` | `freecad-non-native` | `org.freecad.FreeCAD.NonNative` |
| Candidate | Non-native | `freecad-candidate-non-native` | `freecad-can-non-native` | `org.freecad.FreeCAD.Candidate.NonNative` |

Stable and candidate packages in the same family can be installed together. Native and non-native packages use distinct launchers and installation prefixes.

## System installation

```bash
sudo dnf copr enable universish/FreeCAD..
sudo dnf install freecad freecad-candidate
sudo dnf install freecad-non-native freecad-candidate-non-native
```

Native packages use the system package layout; non-native packages keep their bundled runtime under `/opt`. Update or remove system packages with DNF.

## User-only installation

Native packages can be installed inside a Toolbox and exposed on the host:

```bash
./scripts/install-native-toolbox.sh freecad
./scripts/install-native-toolbox.sh freecad-candidate
```

This uses a Toolbox named `freecad-rpm` by default. Override it with `TOOLBOX_CONTAINER` if needed. To uninstall one package while retaining the Toolbox:

```bash
./scripts/uninstall-native-toolbox.sh freecad
```

For a non-native user install, provide a verified, normalized payload archive for the target architecture. The installer writes only under `~/.local/opt/`, `~/.local/bin/`, and `~/.local/share/`:

```bash
PKG=freecad-non-native VERSION=26.3rc2 \
PAYLOAD_ARCHIVE=/path/to/verified-payload.tar.gz \
./scripts/install-user.sh
```

Use `PKG=freecad-candidate-non-native` for the candidate. Remove either user install with its matching `PKG` value, for example `PKG=freecad-candidate-non-native ./scripts/uninstall-user.sh`.

## Automated release flow

GitHub Actions checks stable and candidate releases separately, excludes weekly tags/assets, selects Linux artifacts per architecture, verifies the upstream SHA256 sidecar or GitHub asset digest, then normalizes and scans payloads on GitHub runners before creating SRPMs and submitting them to the configured Copr chroots. ClamAV is a required gate. VirusTotal SHA256 lookups are advisory when the API is unavailable or rate-limited; a positive malicious verdict blocks publication.

The workflow runs at 12:30 and 17:30 `Europe/Brussels` time, and can also be started manually or by the configured repository dispatch events. A shared concurrency group prevents simultaneous packaging runs. Copr submission reuses active/succeeded NVRs and waits for each package build to finish across all 14 configured chroots; a failed target fails the job and prevents state advancement.

GitHub Actions secrets required: `COPR_CONFIG`; `VT_API_KEY` is optional/advisory. The project creates a local ignored `.env` placeholder for local VT configuration; never commit a real key.

## Local SRPM creation

Native source SRPM:

```bash
PKG=freecad VERSION=1.1.4 RELEASE=1 \
FREECAD_SOURCE_DIR=/path/to/initialized/FreeCAD \
./scripts/build-srpm.sh
```

The native spec patches used by the builder are copied into the tracked `patches/` directory. The ignored reference trees are examples only and are not read by the build.

Non-native SRPM from verified normalized architecture payloads:

```bash
PKG=freecad-non-native VERSION=1.1.4 RELEASE=1 \
PAYLOAD_ROOT=payload \
./scripts/build-srpm-non-native.sh
```

## Copr targets

The configured targets cover Fedora 44, Fedora 45, Fedora Rawhide, openEuler 22.03/24.03, and openSUSE Tumbleweed/Leap 16.0 for x86_64 and aarch64.

## License

Packaging scripts and spec files are released under the repository license. FreeCAD and bundled upstream components retain their upstream licenses.
