# FreeCAD Fedora RPMs

This repository currently provides native FreeCAD RPMs through Copr. Non-native AppImage packaging is being reworked and is not currently built or published by this workflow.

## Package model

- Native packages build from the matching upstream source tag and link against Fedora system libraries.
- Non-native AppImage packages will remain a separate package family, with isolated runtime paths and launchers, when their corrected specs are ready.

## Packages

| Channel | Type | RPM | Command |
|---|---|---|---|
| Stable | Native | `freecad` | `FreeCAD` |
| Prerelease | Native | `freecad-candidate` | `freecad-can` |

## Installation (Fedora)

```bash
sudo dnf copr enable universish/FreeCAD
sudo dnf install freecad
sudo dnf install freecad-candidate
```

## Local build flow

### Native build

```bash
PKG=freecad VERSION=1.1.4 RELEASE=1 \
FREECAD_SOURCE_DIR=/path/to/FreeCAD \
./scripts/build-srpm.sh
```

## Verification

- `bash -n scripts/*.sh` for syntax validation.
- `rpmlint` on each built RPM with the requirement of 0 errors and 0 warnings.
- `ldd` validation for native binaries.

## License

Packaging scripts and spec files are released under the repository license. FreeCAD, its bundled sources, and the upstream AppImage payload retain their upstream licensing terms.
