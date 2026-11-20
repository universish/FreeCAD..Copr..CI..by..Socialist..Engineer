# Native dependency profiles

Native SRPMs compile the exact upstream source tag and use the system libraries
enabled by the spec's CMake profile. Bundled SMESH and zipios++ remain enabled;
Coin/Pivy, KDL, OndselSolver, E57Format, PyCXX, libkdtree++, and nlohmann-json
are selected as external dependencies where the current Fedora profile
provides them.

The SRPM builder reads the CMake option declarations from the exact upstream
checkout and fails if the spec passes an undefined project option. This guards
against silently ignored CMake settings when upstream changes its options.

## Distribution status

`freecad.spec` currently contains Fedora package names and Fedora-oriented
runtime dependencies. The Copr matrix requests all twelve targets, but separate
validated BuildRequires/CMake profiles for openEuler and openSUSE have not yet
been established. A submitted SRPM can therefore fail dependency resolution in
those chroots. Do not treat the configured target list as proof that the native
matrix is supported until Copr reports successful builds for all targets.

The target builds are also the evidence needed to determine whether optional
system dependencies should be disabled and retained from upstream source on a
specific distribution. Do not remove bundled sources for a dependency unless
that target's package and CMake discovery path have been verified.
