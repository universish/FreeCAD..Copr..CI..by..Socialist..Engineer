# Troubleshooting

## Release detection stops before packaging

Check that the upstream release tag is supported, is not weekly, and publishes
an RPM, DEB, or AppImage for both configured architectures. When testing a
release manually, use `workflow_dispatch` and provide `force_tag`; the weekly
exclusion is not bypassed by manual input.

## Artifact verification fails

Check the selected release asset filename, architecture, SHA256 sidecar, and
GitHub asset digest. The detector requires a supported artifact for each
architecture and the downloader refuses mismatched hashes or non-GitHub hosts.

## ClamAV or static scanning fails

Download the `security-report-*` artifact for the package and architecture.
ClamAV database update failures, infected files, ELF architecture mismatches,
escaping symlinks, build-host paths, and privileged file modes block the build.
VirusTotal unavailable results are advisory; a malicious verdict blocks it.

## Copr submission fails

Verify the `COPR_CONFIG` secret, destination project permissions, and that all
names in `chroots.txt` are enabled in the project. Review the uploaded
`copr-result-*` artifact and per-chroot logs. A failed chroot leaves the last
successful state unchanged.

## Release detection cannot read Copr history

The detector reads public build records for each RPM package and uses complete
successful builds to reconcile release counters. Check that the configured
project is public and reachable. If `state/<package>.json` claims a higher
release than Copr reports, inspect the project history before changing either
record; the detector stops rather than risk publishing a reused or skipped
release number.

## State commit fails

The finalizer needs `contents: write` and permission to push to the triggering
branch. Branch protection or repository Actions settings can reject that push;
in that case successful Copr builds exist but state remains unchanged.

## Native build fails in a target

Inspect that chroot's Copr build log. Fedora-oriented BuildRequires are not yet
proven against openEuler or openSUSE; see [native dependencies](native-dependencies.md).
