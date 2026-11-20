# FreeCAD Copr RPM Automation

This repository is a fork of [MidnightRAT/FreeCAD-rpm](https://github.com/MidnightRAT/FreeCAD-rpm).

This repository builds and publishes stable and prerelease FreeCAD packages for x86_64 and aarch64. The native family compiles the upstream source against distribution libraries. The non-native family repackages the first available upstream Linux artifact in RPM → DEB → AppImage priority order.

## Packages

| Channel | Family | RPM name | Command | AppStream ID |
| --- | --- | --- | --- | --- |
| Stable | Native | `freecad` | `freecad` | `org.freecad.FreeCAD` |
| Candidate | Native | `freecad-candidate` | `freecad-can` | `org.freecad.FreeCAD.Candidate` |
| Stable | Non-native | `freecad-non-native` | `freecad-non-native` | `org.freecad.FreeCAD.NonNative` |
| Candidate | Non-native | `freecad-candidate-non-native` | `freecad-can-non-native` | `org.freecad.FreeCAD.Candidate.NonNative` |

Stable and candidate packages in the same family can be installed together. Native and non-native packages use distinct launchers and installation prefixes.

## Detailed Pipeline Overview

This repository is an unofficial, automated continuous integration pipeline that builds native RPM packages and repackages upstream FreeCAD prebuilt artifacts (`.AppImage`, `.deb`, `.rpm`) into non-native RPM packages. The resulting packages are built and hosted on Fedora Copr for Fedora, openSUSE, and openEuler distributions.

### Why This Repository?
FreeCAD is a powerful, open-source parametric 3D CAD modeler. While upstream provides source code and occasional pre-compiled Linux desktop artifacts, compiling FreeCAD from source across multiple distributions is resource-intensive and prone to dependency shifts. This repository resolves that issue by implementing a dual-family packaging pipeline:

- **Native Family**: Compiles the upstream source directly against distribution libraries for optimal system integration.
- **Non-Native Family**: Repackages verified upstream binaries into standardized RPMs, bypassing complex source compilation while retaining a native package manager experience (installed under `/opt`).

### Key Pipeline Features
- **Smart Release Monitoring**: Tracks upstream GitHub releases for stable and candidate tags, automatically excluding transient weekly builds.
- **Prioritized Artifact Selection**: For non-native builds, the pipeline intelligently selects upstream artifacts in `RPM → DEB → AppImage` priority order.
- **Mandatory Security Gates**: All payloads are normalized and scanned on GitHub runners using ClamAV. Advisory VirusTotal SHA256 lookups are performed; a positive malicious verdict strictly blocks publication.
- **Sanitized SRPM Generation**: Payloads are compressed into architecture-specific source tarballs, and clean Source RPMs (`.src.rpm`) are generated via `rpmbuild -bs`.
- **Automated Copr Dispatch**: Securely submits builds to the `universish/FreeCAD..` Copr project across 14 configured chroots (Fedora 44/45/Rawhide, openEuler 22.03/24.03, openSUSE Tumbleweed/Leap 16.0 for x86_64 and aarch64).

### Repository Structure
```text
.
├── .github/
│   └── workflows/
│       └── copr-ci.yml            # Automated release detector, security scanner, and Copr trigger
├── scripts/
│   ├── build-srpm.sh              # Native SRPM builder
│   ├── build-srpm-non-native.sh   # Non-native SRPM builder
│   ├── install-native-toolbox.sh  # User-space native installer (Toolbox)
│   └── install-user.sh            # User-space non-native installer
├── patches/                       # Native spec patches applied during build
└── README.md                      # This documentation
```

### Component Deep Dive: GitHub Actions Workflow
The workflow operates on a scheduled cron trigger (12:30 and 17:30 `Europe/Brussels` time) and supports manual triggering (`workflow_dispatch`). A shared concurrency group prevents simultaneous packaging runs.

**Operational Sequence:**
1. **Upstream Release Resolution**: Queries the GitHub API for FreeCAD releases, validates tags, and determines the target version.
2. **Artifact Detection & Verification**: Downloads the matching source or prebuilt binary and verifies the upstream SHA256 sidecar or GitHub asset digest.
3. **Security Scanning**: Updates ClamAV signatures and recursively scans the payload. 
4. **Isolated SRPM Generation**: 
   - *Native*: Patches and builds from the `upstream` source directory.
   - *Non-Native*: Extracts and normalizes the payload into `payload/x86_64` or `payload/aarch64`, ensuring `AppRun` is executable and icons are present.
5. **Copr Dispatch**: Injects credentials from the `COPR_CONFIG` secret and triggers builds. The job waits for each package build to finish across all chroots; a failed target fails the job to prevent state advancement.

---

### Installation Instructions (Client-Side)

#### 1. System-wide Installation (Recommended)
Enable the Copr repository and install the desired packages. Stable and candidate packages can be installed side-by-side.

**For Fedora (44, 45, Rawhide):**

* **Add repo:**
```bash
sudo dnf copr enable universish/FreeCAD..
```
* **Install native packages:**
```bash
sudo dnf install -y freecad
```
```bash
sudo dnf install -y freecad-candidate
```

* **Install non-native packages (bundled runtime under /opt):**
```bash
sudo dnf install -y freecad-non-native
```
```bash
sudo dnf install -y freecad-candidate-non-native
```


**For openSUSE (Tumbleweed & Leap 16.0):**

* **Add repository (Replace 'opensuse-tumbleweed' with 'opensuse-leap-16.0' if applicable):**
```bash
sudo zypper addrepo -f https://copr.fedorainfracloud.org/coprs/universish/FreeCAD../repo/opensuse-tumbleweed/universish-FreeCAD..-opensuse-tumbleweed.repo
sudo zypper --gpg-auto-import-keys refresh
```

* **Install packages:**
```bash
sudo zypper install -y freecad
```
```bash
sudo zypper install -y freecad-non-native
```

#### 2. User-only Installation (No Root Required)

**Native via Toolbox (Native packages can be installed inside a Toolbox and exposed on the host):**
Installs inside a Toolbox named `freecad-rpm` by default and exposes it on the host.This uses a Toolbox named `freecad-rpm` by default. Override it with `TOOLBOX_CONTAINER` if needed. To uninstall one package while retaining the Toolbox:
```bash
./scripts/install-native-toolbox.sh freecad
```
```bash
./scripts/install-native-toolbox.sh freecad-candidate
```

This uses a Toolbox named `freecad-rpm` by default. Override it with `TOOLBOX_CONTAINER` if needed. To uninstall one package while retaining the Toolbox (To uninstall): 
```bash
./scripts/uninstall-native-toolbox.sh freecad
```
```bash
./scripts/uninstall-native-toolbox.sh freecad-candidate
```

Native source SRPM:

```bash
PKG=freecad VERSION=1.1.4 RELEASE=1 \
FREECAD_SOURCE_DIR=/path/to/initialized/FreeCAD \
./scripts/build-srpm.sh
```

The native spec patches used by the builder are copied into the tracked `patches/` directory. The ignored reference trees are examples only and are not read by the build.

**Non-Native (via Payload Archive):**
Requires a verified, normalized payload archive for the target architecture. Writes only under `~/.local/opt/`, `~/.local/bin/`, and `~/.local/share/`.
```bash
PKG=freecad-non-native VERSION=1.1.4 \
PAYLOAD_ARCHIVE=/path/to/verified-payload.tar.gz \
./scripts/install-user.sh
```

```bash
PKG=freecad-non-native VERSION=26.3rc2 \
PAYLOAD_ARCHIVE=/path/to/verified-payload.tar.gz \
./scripts/install-user.sh
```

Use `PKG=freecad-candidate-non-native` for the candidate. Remove either user install with its matching `PKG` value, for example `PKG=freecad-candidate-non-native ./scripts/uninstall-user.sh`.

To uninstall: 
```bash
PKG=freecad-non-native ./scripts/uninstall-user.sh
```

Non-native SRPM from verified normalized architecture payloads:

```bash
PKG=freecad-non-native VERSION=1.1.4 RELEASE=1 \
PAYLOAD_ROOT=payload \
./scripts/build-srpm-non-native.sh
```

#### 3. Maintenance Commands
**Update Packages (Bypass Metadata Cache):**
- *Fedora*:
```bash
sudo dnf upgrade --refresh -y freecad
```
```bash
sudo dnf upgrade --refresh -y freecad-non-native
```

- *openSUSE*:
```bash
sudo zypper refresh -f && sudo zypper update -y freecad
```
```bash
sudo zypper refresh -f && sudo zypper update -y freecad-non-native
```

**Remove Packages:**
- *Fedora*: 
```bash
sudo dnf remove -y freecad
```
```bash
sudo dnf remove -y freecad-non-native
```
- *openSUSE*: 
```bash
sudo zypper remove -y freecad
```
```bash
sudo zypper remove -y freecad-non-native
```

**Disable/Remove Repository:**
- *Fedora*: 
```bash
sudo dnf copr disable universish/FreeCAD..
```
```bash
sudo dnf copr remove universish/FreeCAD..
```

- *openSUSE*: 
```bash
sudo zypper removerepo copr:copr.fedorainfracloud.org:universish:FreeCAD..
```

---

### Feedback & Issues
This repository is an unofficial packaging pipeline intended to simplify installing and updating FreeCAD on supported Linux distributions. 

- **Packaging/Copr Issues**: Please report any RPM packaging, CI, or Copr installation issues in this repository's [Issue Tracker](https://github.com/universish/FreeCAD..Copr..CI..by..Socialist..Engineer/issues).
- **Application Issues**: For upstream FreeCAD application bugs, feature requests, or documentation, visit the [official FreeCAD Website](https://www.freecad.org/) or the [official FreeCAD GitHub Repository](https://github.com/FreeCAD/FreeCAD).

## System installation


Native packages use the system package layout; non-native packages keep their bundled runtime under `/opt`. Update or remove system packages with DNF.


## Automated release flow

GitHub Actions checks stable and candidate releases separately, excludes weekly tags/assets, selects Linux artifacts per architecture, verifies the upstream SHA256 sidecar or GitHub asset digest, then normalizes and scans payloads on GitHub runners before creating SRPMs and submitting them to the configured Copr chroots. ClamAV is a required gate. VirusTotal SHA256 lookups are advisory when the API is unavailable or rate-limited; a positive malicious verdict blocks publication.

The workflow runs at 12:30 and 17:30 `Europe/Brussels` time, and can also be started manually or by the configured repository dispatch events. A shared concurrency group prevents simultaneous packaging runs. Copr submission reuses active/succeeded NVRs and waits for each package build to finish across all 14 configured chroots; a failed target fails the job and prevents state advancement.

GitHub Actions secrets required: `COPR_CONFIG`; `VT_API_KEY` is optional/advisory. The project creates a local ignored `.env` placeholder for local VT configuration; never commit a real key.

## NATIVE

Native FreeCAD; RPM packaging for [FreeCAD](https://github.com/FreeCAD/FreeCAD) — open-source parametric 3D CAD modeler, built with **maximum use of system libraries** from Fedora `-devel` packages.

## Dependency strategy

Where possible the package uses **system libraries** from Fedora `-devel` packages:

- Coin4 4.0.10, OpenCASCADE, VTK 9.5+
- Boost 1.90, Eigen3 5.0.1
- PySide6 6.11, Shiboken6, Pivy 0.6.9+
- fmt, yaml-cpp, nlohmann_json, Microsoft GSL (`guidelines-support-library-devel`)
- OndselSolver, libE57Format, libkdtree++, orocos-kdl
- MEDFile, Xerces-C, ICU, OpenMPI, HDF5
- GTest/GMock, libspnav

Only libraries with no compatible version in the distribution (or requiring custom patches) are **bundled**:

- SMESH 7.7.1.0 (custom Salome fork, not in Fedora)
- zipios++ 0.1.5.9 (Fedora version too old, API incompatible)
- lru-cache (header-only, tiny)
- 3Dconnexion (driver SDK, not packaged)

The system-detection logic lives in CMake options (`FREECAD_USE_EXTERNAL_*`) — all enabled where Fedora provides compatible versions.

### Build from Source

```bash
# Install build tools
sudo dnf install -y rpm-build rpmdevtools dnf-plugins-core git wget curl \
  cmake ninja-build gcc gcc-c++ make patch pkgconf dos2unix \
  swig python3-devel desktop-file-utils libappstream-glib \
  Coin4-devel opencascade-devel med-devel vtk-devel \
  boost-devel eigen3-devel pybind11-devel \
  python3-pycxx-devel python3-pyside6-devel python3-shiboken6-devel \
  python3-pivy python3-matplotlib \
  fmt-devel yaml-cpp-devel nlohmann-json-devel guidelines-support-library-devel \
  ondselsolver-devel libE57Format-devel libkdtree++-devel orocos-kdl-devel \
  gtest-devel gmock-devel hdf5-static openmpi-devel xerces-c-devel \
  libicu-devel libspnav-devel \
  mesa-libGL-devel mesa-libGLU-devel freetype-devel \
  qt6-qtbase-devel qt6-qtsvg-devel qt6-qttools-devel

# ...or let dnf resolve them straight from the spec:
# sudo dnf builddep -y freecad.spec

# Determine version and build RPM
VERSION=1.1.4
rpmdev-setuptree
wget -q "https://github.com/FreeCAD/FreeCAD/releases/download/${VERSION}/freecad_source_${VERSION}.tar.gz" \
  -O ~/rpmbuild/SOURCES/freecad_source_${VERSION}.tar.gz
cp README.md ~/rpmbuild/SOURCES/
cp patches/*.patch ~/rpmbuild/SOURCES/ 2>/dev/null || true
sed -e "s/@VERSION@/${VERSION}/g" -e "s/@RELEASE@/1/g" \
  freecad.spec > ~/rpmbuild/SPECS/freecad.spec
rpmbuild -ba ~/rpmbuild/SPECS/freecad.spec
```

> The `%prep`/`%build` uses system libraries resolved at configure time from the `-devel` packages listed above.
> `rpmbuild -ba` produces **both** the SRPM (`~/rpmbuild/SRPMS/*.src.rpm`) and
> the binary RPM (`~/rpmbuild/RPMS/x86_64/*.x86_64.rpm`). Verify the artifacts with:

```bash
rpmlint ~/rpmbuild/RPMS/x86_64/freecad*.rpm   # 0 real errors
rpm -qlp ~/rpmbuild/RPMS/x86_64/freecad*.rpm  # file list
ldd /usr/lib64/freecad/bin/FreeCAD            # no "not found"
/usr/bin/freecad --help                       # smoke test
```

## Local mock build (Fedora 44/45 with RPMFusion)

```bash
# Install mock and RPMFusion
sudo dnf install -y mock
sudo usermod -a -G mock $USER
newgrp mock

# Build SRPM first (spec is a template — substitute the version)
VERSION=1.1.4
sed -e "s/@VERSION@/${VERSION}/g" -e "s/@RELEASE@/1/g" freecad.spec > /tmp/freecad.spec
rpmbuild -bs --define "_sourcedir $PWD" --define "_srcrpmdir $PWD" /tmp/freecad.spec

# Build for Fedora 44 with RPMFusion free
mock -r fedora+rpmfusion_free-44-x86_64 --rebuild freecad-*.src.rpm

# Build for Fedora 45 with RPMFusion free
mock -r fedora+rpmfusion_free-45-x86_64 --rebuild freecad-*.src.rpm
```

Resulting RPMs in `/var/lib/mock/fedora-44-x86_64/result/` (and `fedora-45-x86_64/result/`).

> **Note:** unit tests are off by default (`%bcond_with tests` in the spec — a few
> tests fail under mock chroot). Enable with `rpmbuild --with tests`.

## CI/CD

### GitHub Actions

Automatically:
1. Checks for new FreeCAD releases (weekly schedule)
2. Builds src.rpm and x86_64.rpm in Fedora 44/45 containers
3. Uploads artifacts to GitHub Releases

### COPR

Automatically builds for openEuler 24.03 & Fedora 44/45/rawhide & openSUSE from the latest main branch:
- [COPR Project Page](https://copr.fedorainfracloud.org/coprs/universish/FreeCAD../)

**Note:** Workflows do not trigger on changes to README.md or `.copr/**`.

## License

LGPL-2.1-or-later AND Zlib AND BSD-3-Clause AND Apache-2.0 AND EUPL-1.2 AND BSL-1.0 AND MIT AND GPL-2.0-or-later AND CC-BY-SA-4.0 (same as FreeCAD)

----

## Copr targets

The configured targets cover Fedora 44, Fedora 45, Fedora Rawhide, openEuler 22.03/24.03, and openSUSE Tumbleweed/Leap 16.0 for x86_64 and aarch64.

## License

Packaging scripts, GitHub Actions workflows, and spec files in this repository are released under the repository's primary [MIT License](https://github.com/universish/FreeCAD..Copr..CI..by..Socialist..Engineer/blob/main/LICENSE). 

The underlying FreeCAD application, source code, and bundled upstream components retain their original upstream licenses (primarily [LGPL-2.0-or-later](https://github.com/FreeCAD/FreeCAD/blob/main/LICENSE)).

