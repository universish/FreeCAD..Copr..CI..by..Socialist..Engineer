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
