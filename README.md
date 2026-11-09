<<<<<<< HEAD
# FreeCAD native Fedora RPMs

This repository builds FreeCAD from its matching upstream source tag and
packages it for Fedora through Copr. It does not wrap upstream AppImages,
Debian packages, or prebuilt RPM payloads. FreeCAD uses Fedora's system Qt 6,
Python, OpenCascade, VTK, and other packaged libraries; RPM's ELF dependency
generators record shared library requirements.

## Packages

| Channel | RPM | Command |
|---|---|---|
| Stable | `freecad` | `FreeCAD` |
| Prerelease | `freecad-candidate` | `freecad-can` |

The candidate RPM conflicts with the stable package because upstream installs
shared desktop metadata and resource paths. Install one channel at a time.

## Build flow

GitHub Actions selects an upstream stable or prerelease source tag, checks out
its recursive Git submodules, creates an SRPM, then submits that SRPM to the
Fedora 44, Fedora 45, and Fedora Rawhide Copr chroots for x86_64 and aarch64.
The Fedora spec files use CMake and distro development packages. PyCXX and
test tooling use Fedora RPMs. Fedora does not currently provide the SMESH and
zipios++ development packages required by this FreeCAD release, so those two
components are built from the upstream source tree; no prebuilt shared objects
are copied into the RPM. FreeCAD's OndselSolver is also built from source.

Run the SRPM generation step locally from this repository with an initialized
FreeCAD checkout available as `FREECAD_SOURCE_DIR`:

```sh
PKG=freecad VERSION=1.1.4 RELEASE=1 \
FREECAD_SOURCE_DIR=/path/to/FreeCAD \
./scripts/build-srpm.sh
```

Full binary builds require a Fedora buildroot with the `BuildRequires` listed
in the spec. Copr provides those isolated buildroots for the configured Fedora
chroots. `rpmlint` and `mock` checks should be run against the resulting binary
RPMs before publishing.

## License

Packaging scripts and spec files are MIT licensed. FreeCAD source and bundled
project components retain their upstream licenses.
=======
# FreeCAD Fedora RPMs (Native and Non-Native)

This repository provides both **native** source-built RPMs and **non-native** AppImage-bundled RPMs for FreeCAD through Copr.

## Package model

- **Native** packages build from the matching upstream source tag and link against Fedora system libraries.
- **Non-native** packages use the official AppImage payload extracted with `--appimage-extract` and keep that runtime inside a dedicated `/opt` prefix.
- These are intentionally separate families, with different binary names, desktop launchers, and package ownership.

## Packages

| Channel | Type | RPM | Command |
|---|---|---|---|
| Stable | Native | `freecad` | `FreeCAD` |
| Prerelease | Native | `freecad-candidate` | `freecad-can` |
| Stable | Non-Native | `freecad-non-native` | `freecad-non-native` |
| Prerelease | Non-Native | `freecad-candidate-non-native` | `freecad-can-non-native` |

## Installation (Fedora)

```bash
sudo dnf copr enable universish/FreeCAD
sudo dnf install freecad
sudo dnf install freecad-candidate
sudo dnf install freecad-non-native
sudo dnf install freecad-candidate-non-native
```

## Local build flow

### Native build

```bash
PKG=freecad VERSION=1.1.4 RELEASE=1 \
FREECAD_SOURCE_DIR=/path/to/FreeCAD \
./scripts/build-srpm.sh
```

### Non-native AppImage build

```bash
PKG=freecad-non-native VERSION=1.1.4 RELEASE=1 \
APPIMAGE_URL=https://github.com/FreeCAD/FreeCAD/releases/download/1.1.4/FreeCAD-1.1.4-Linux-x86_64.AppImage \
./scripts/build-srpm-non-native.sh
```

The non-native builder downloads the AppImage, extracts it with `--appimage-extract`, and packages the extracted payload while keeping the runtime isolated from the native Fedora library path.

## Verification

- `bash -n scripts/*.sh` for syntax validation.
- `rpmlint` on each built RPM with the requirement of 0 errors and 0 warnings.
- `ldd` validation for native binaries and AppImage runtime tracing for the non-native family.

## License

Packaging scripts and spec files are released under the repository license. FreeCAD, its bundled sources, and the upstream AppImage payload retain their upstream licensing terms.
>>>>>>> 20e77c9 (feat: add native and non-native AppImage/source Fedora RPM packages and automation)
