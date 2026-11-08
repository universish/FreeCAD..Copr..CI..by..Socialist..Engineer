freecad-copr/
├── .github/workflows/copr-ci.yml   # Source checkout → SRPM → Fedora Copr builds
├── scripts/
│   ├── detect-release.sh           # Upstream source tag/channel/revision
│   └── build-srpm.sh               # Archive source + submodules, create SRPM
├── freecad.spec                    # Native stable Fedora RPM spec
├── freecad-candidate.spec          # Native prerelease Fedora RPM spec
├── chroots.txt                     # Fedora Copr chroots only
├── state/                          # Last processed release per channel
├── README.md                       # English documentation
└── BENİ OKU.md                     # Turkish documentation
