<p align="center">
  <img src="https://upload.wikimedia.org/wikipedia/commons/f/f7/FreeCAD-logo.svg" alt="FreeCAD" width="240" />
</p>

<h1 align="center">FreeCAD Copr CI</h1>

<p align="center">
  Automated continuous integration pipeline that repackages upstream FreeCAD prebuilt Linux releases into native RPM packages for openEuler and other (Fedora, openSUSE, built and hosted on Fedora Copr).
</p>

<p align="center">
  <img src="https://img.shields.io/github/license/universish/FreeCAD..Copr..CI..by..Socialist..Engineer" alt="License" />
  <img src="https://img.shields.io/badge/arch-x86__64%20%7C%20aarch64-blue" alt="Architectures" />
</p>

---

This repository is an unofficial repository that converts the prebuilt Linux packages published by the FreeCAD project (.rpm, .deb and .AppImage artifacts) into RPM packages.

This Copr allows you to install and keep FreeCAD up to date on Fedora and its ecosystem with a single package manager command.

Please report any bugs or package installation issues with this repository in the [issue tracker](https://github.com/universish/FreeCAD..Copr..CI..by..Socialist..Engineer/issues).

FreeCAD official [repository](https://github.com/FreeCAD/FreeCAD) — FreeCAD official [website](https://www.freecad.org/)

## Overview

FreeCAD is a general-purpose parametric 3D CAD modeler. Parametric modeling allows an engineer to revisit the model history and change design parameters at any point, which makes FreeCAD a serious tool for mechanical engineering, product design, architecture and electronics work — from a quick sketch to production-ready drawings and meshes for 3D printing.

Upstream publishes precompiled Linux artifacts on GitHub Releases (x86_64 and aarch64), but not as distribution-native RPM packages for every ecosystem. Our goal is to create native RPM packages for Fedora, openSUSE, and openEuler. In particular, we will continue to contribute to the openEuler project. Building a CAD application of this size from source inside isolated build environments such as Fedora Mock or Copr is slow and fragile: the dependency surface (OpenCASCADE, VTK, Coin, Boost, Qt, PySide) is enormous and moves quickly.

This repository solves that problem with a repackaging pipeline rather than a source build:

1. **Release detection** — the pipeline queries the GitHub Releases API and finds the newest release that is not a weekly development build. Weekly builds are explicitly excluded; stable releases and release candidates (the `yy.XrcY` numbering scheme, e.g. `26.3rc2`) are packaged.
2. **Smart package selection** — if upstream published an `.rpm`, it is used directly; otherwise the `.deb` is unpacked; otherwise the `.AppImage` bundle is extracted (without FUSE). The first available format wins, in that order.
3. **Integrity verification** — every artifact is checked against the upstream `-SHA256.txt` checksum file before anything else happens.
4. **Security scanning** — the extracted payload is scanned in the GitHub Actions runner (never on Copr build servers) with an up-to-date ClamAV database, and every file's SHA-256 is queried against the VirusTotal API. The pipeline halts on any positive detection; a VirusTotal outage only produces a warning.
5. **Payload normalization** — the application is relocated to `/opt/freecad` (stable) or `/opt/freecad-candidate` (release candidate), with a proper launcher, desktop entry, icons and the upstream `.zsync` delta-update file embedded for quota-friendly updates.
6. **SRPM generation** — both architectures are combined into a single source RPM with a Fedora spec file; library dependencies are auto-detected by rpmbuild's dependency generator, while hicolor-icon-theme, xdg-utils, mesa and other system dependencies are declared explicitly.
7. **Copr dispatch** — the SRPM is submitted with `copr-cli` to all configured chroots (openEuler, Fedora 44/45/Rawhide, openSUSE).

The packaging revision (release number) is incremented automatically on every repackaging run (`version-release`), and resets to 1 whenever the upstream version changes, so upgrades always resolve cleanly.

## Packages

| Channel | Package | Command | Description |
|---|---|---|---|
| Stable | `freecad` | `freecad` | Latest stable upstream release |
| Pre-release | `freecad-candidate` | `freecad-can` | Release candidate / beta builds for testing |

The two packages install side by side: the candidate uses its own installation directory (`/opt/freecad-candidate`) and launcher (`freecad-can`). Note that both versions share the same user configuration directory. Only one copy of each package can be installed at a time, and each can be updated independently.

Weekly development snapshots are never packaged.

## Installation

### Fedora (44, 45, Rawhide)

Enable the Copr repository and install the package:

```
sudo dnf copr enable universish/FreeCAD..
sudo dnf install -y freecad
```

For the release candidate:

```
sudo dnf copr enable universish/FreeCAD..
sudo dnf install -y freecad-candidate
```

### **openEuler 24.03**

```
sudo dnf copr enable universish/FreeCAD..
sudo dnf install -y freecad
```

For the release candidate:

```
sudo dnf copr enable universish/FreeCAD..
sudo dnf install -y freecad-candidate
```

### openSUSE Tumbleweed and Leap 16.0

```
sudo zypper addrepo -f https://copr.fedorainfracloud.org/coprs/universish/FreeCAD../repo/opensuse-tumbleweed/universish-FreeCAD..-opensuse-tumbleweed.repo
sudo zypper --gpg-auto-import-keys refresh
sudo zypper install -y freecad
```

For openSUSE Leap 16.0, replace `opensuse-tumbleweed` with `opensuse-leap-16.0` in the repository URL.

## Updating

Regular package manager update picks up new builds:

```
sudo dnf upgrade --refresh -y freecad
```

openSUSE:

```
sudo zypper refresh -f && sudo zypper update -y freecad
```

### Quota-friendly updates with zsync

Each package embeds the upstream `.zsync` file under `/opt/freecad/updates/` (and `/opt/freecad-candidate/updates/` for the candidate). If you keep the original artifact around, you can fetch only the changed blocks of a new release instead of the full download:

```
zsync https://github.com/FreeCAD/FreeCAD/releases/download/<tag>/<file>.AppImage.zsync
```

This typically saves a large portion of the download size on every update.

## Removal

```
sudo dnf remove -y freecad freecad-candidate
```

To temporarily disable the repository:

```
sudo dnf copr disable universish/FreeCAD..
```

To completely remove the repository from the system:

```
sudo dnf copr remove universish/FreeCAD..
```

openSUSE:

```
sudo zypper remove -y freecad freecad-candidate
sudo zypper removerepo copr:copr.fedorainfracloud.org:universish:FreeCAD..
```

## How the automation works

### Triggers

- **Scheduled checks** — twice a day, aligned with the lunch break and end of workday in the timezone of the FreeCAD project headquarters (Europe/Berlin; GitHub cron runs in UTC).
- **Manual dispatch** — `workflow_dispatch` with an optional forced version and channel.
- **Webhook** — `repository_dispatch` events, for immediate reaction to upstream releases and as a fail-safe health check (see below).

All triggers share a concurrency group, so a webhook and a scheduled run can never build the same version twice or race on the packaging revision counter.

### Webhook (optional, recommended)

GitHub scheduled workflows can be delayed or skipped during busy periods. For a strict Europe/Berlin schedule and a health-check ping, create a personal access token with `repo` scope and schedule an external cron service (for example cron-job.org, which supports timezones) to POST every 6 hours:

```
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.github.com/repos/universish/FreeCAD..Copr..CI..by..Socialist..Engineer/dispatches \
  -d '{"event_type":"freecad-healthcheck"}'
```

The pipeline is idempotent: if the release was already processed, the run exits cleanly in seconds.

### Repository structure

```
.
├── .github/
│       └── workflows/
│           └── copr-ci.yml                   # Release detector, scanner, repackager, Copr trigger
├── scripts/
│       ├── detect-release.sh             # Upstream release/channel/revision detection
│       ├── fetch-and-verify.sh           # Download + SHA-256 verification
│       ├── repackage.sh                   # rpm/deb/AppImage extraction and normalization
│       ├── security-scan.sh              # ClamAV + VirusTotal scanning
│       └── build-srpm.sh                  # Source RPM generation
├── freecad.spec                            # Stable package spec
├── freecad-candidate.spec           # Release candidate package spec
├── chroots.txt                               # Target Copr chroots
├── state/                                       # Last processed version per package
│       ├── freecad.json
│       └── freecad-candidate.json
├── LICENSE                                   # MIT License
├── BENİ OKU.md                           # turkish readme
└── README.md
```

### Security model

All artifacts are verified and scanned **before** they reach Copr. ClamAV definitions are refreshed on every run, the full payload is scanned, and SHA-256 hashes are looked up against VirusTotal (hashes only — files themselves are never uploaded, which keeps the free API quota intact). If VirusTotal is unreachable, the run warns and continues once the mandatory ClamAV and checksum checks pass. No scanning ever happens on Copr or mock infrastructure.

## Feedback and issues

This repository is an unofficial packaging pipeline intended to simplify installing and updating FreeCAD on Fedora and related distributions.

Please report RPM packaging or Copr installation issues in our [issue tracker](https://github.com/universish/FreeCAD..Copr..CI..by..Socialist..Engineer/issues).

For upstream application bugs, feature requests or documentation, visit the official [FreeCAD website](https://www.freecad.org/) or the official [GitHub repository](https://github.com/FreeCAD/FreeCAD).


## License

Packaging scripts, GitHub Actions workflows and spec files in this repository are licensed under the [MIT License.](https://raw.githubusercontent.com/universish/FreeCAD..Copr..CI..by..Socialist..Engineer/refs/heads/main/LICENSE)

The underlying FreeCAD application and prebuilt binaries are governed by the upstream FreeCAD licensing terms (LGPL-2.1-or-later, with components under Zlib, BSD-3-Clause, Apache-2.0, MIT and others).

“Kimi AI” was created in fast mode at the ‘High’ thinking level using the necessary plugins, tools, and skills provided by the free “Fast” model. The idea and prompt were written by engineer universish.

Copyrights 2026 (c) universish (S* Y*)

