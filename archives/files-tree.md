# files tree

freecad-copr/
├── .github/workflows/copr-ci.yml       # Release gate → payload scan → SRPM → Copr → state
├── scripts/
│   ├── detect-release.sh               # Stable/candidate + per-arch artifact/state selection
│   ├── fetch-and-verify.sh             # Download and mandatory SHA256 verification
│   ├── repackage.sh                    # RPM/DEB/AppImage extraction and payload normalization
│   ├── security-scan.sh                # Required ClamAV and advisory VirusTotal checks
│   ├── submit-copr.sh                  # Chroot validation and Copr NVR idempotency
│   ├── build-srpm.sh                   # Native source + submodules → SRPM
│   ├── build-srpm-non-native.sh        # Two architecture payloads → non-native SRPM
│   ├── install-user.sh                 # Non-native user-local install under ~/.local/opt
│   ├── uninstall-user.sh               # Remove non-native user-local files
│   ├── install-native-toolbox.sh       # Install native RPM in Toolbox and export host launchers
│   └── uninstall-native-toolbox.sh     # Remove a Toolbox native package and host launchers
├── freecad.spec                        # Native stable source-built RPM spec
├── freecad-candidate.spec              # Native candidate derived from stable spec
├── freecad-non-native.spec             # Stable upstream binary runtime RPM spec
├── freecad-candidate-non-native.spec   # Candidate upstream binary runtime RPM spec
├── patches/                            # Tracked patches needed by native stable/candidate SRPMs
├── chroots.txt                         # Copr targets for 3 distro families × 2 architectures
├── state/                              # Per-package version/revision and asset state
├── README.md                           # English documentation
└── BENİ OKU.md                         # Turkish documentation
