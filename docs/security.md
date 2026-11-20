# Security pipeline

## Artifact integrity

The detector selects a single upstream RPM, DEB, or AppImage for each
architecture in RPM → DEB → AppImage order. `fetch_asset.py` requires a valid
SHA256 from the matching upstream sidecar or GitHub asset digest. A download
without a trustworthy checksum, a digest mismatch, or an unexpected download
host fails the job.

## Inspection and scanning

- ClamAV databases must update successfully before the scan can pass.
- The original upstream artifact and normalized payload are scanned.
- Native source checkouts, packaging scripts, patches, workflow files, and
  release configuration are scanned before native SRPM generation.
- RPM payloads are inspected and extracted without installation. DEB control
  metadata and maintainer scripts are recorded but never run. AppImages are
  inspected and extracted without launching them.
- Extractors reject traversal paths, escaping symlinks, and special files.
- Payload inspection records hashes and executable files, checks ELF
  architecture and RPATH/RUNPATH, and flags host build paths and setuid/setgid
  files.
- VirusTotal receives only SHA256 identifiers. It never receives binary
  uploads. A malicious hash blocks publication; missing hashes, API failures,
  and rate limits remain advisory and are recorded.

## Reports and publication gate

Every package state update requires clean ClamAV results, no blocking static
findings, complete architecture coverage, and SRPM metadata whose hash matches
the uploaded SRPM artifact. The finalizer also checks that non-native scan
reports match the selected upstream asset hashes and that native scan reports
match the source commit used for the SRPM.

The workflow does not execute upstream application binaries on a GitHub runner.
Copr performs compilation and package installation tests in its target
environment; those builds are monitored before the state update.
