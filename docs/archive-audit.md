# Historical non-native packaging audit

## Scope

The historical directory is named `archives/`. This review opened only files
whose names and contents identify them as non-native payload, build, scan, or
user-installation implementations. No archived native spec, native build or
Toolbox installer, native patch, or mixed native/non-native workflow was read.
No archived file was executed, imported, or copied into the maintained tree.

## Reviewed files and disposition

| Historical file | Finding | Current disposition |
| --- | --- | --- |
| `archives/freecad-non-native.spec` | Stable package used `/opt`, a distinct command and desktop entry. It disabled RPM's RPATH and shebang checks and excluded dependency generation for all files under `/opt`, which can hide invalid build paths and real host requirements. Its license metadata described only LGPL. | Replaced by the parameterized [`../packaging/non-native/non-native.spec.in`](../packaging/non-native/non-native.spec.in) and release-policy identities. The maintained spec keeps RPM runtime dependency generation enabled and declares the combined FreeCAD license expression. |
| `archives/freecad-candidate-non-native.spec` | Candidate identity had a separate `/opt` prefix and launcher, but duplicated the stable spec and likewise disabled RPATH/shebang checks and automatic dependencies. | Candidate values are supplied by [`../config/release-policy.json`](../config/release-policy.json); no second spec is maintained. |
| `archives/scripts/fetch-and-verify.sh` | Required a checksum sidecar or GitHub digest and rejected a mismatch. It accepted the artifact URL without independently restricting its host. | The maintained [`../scripts/fetch_asset.py`](../scripts/fetch_asset.py) retains checksum enforcement and validates the download source and selected asset metadata. |
| `archives/scripts/repackage.sh` | Ran an AppImage with `--appimage-extract`; extracted RPM and DEB archives with general-purpose tools without path/symlink checks; did not emit a provenance manifest. | Not migrated. [`../scripts/normalize_payload.py`](../scripts/normalize_payload.py) inspects AppImages and extracts them without launching their code, rejects unsafe paths and special files, validates architecture, and writes a payload manifest. |
| `archives/scripts/security-scan.sh` | Required ClamAV and checked symlinks. VirusTotal treated both malicious and suspicious detections as blockers, stopped without a structured report, and only checked the normalized tree. | [`../scripts/security_scan.py`](../scripts/security_scan.py) scans the original artifact and normalized payload, records a machine-readable report, checks ELF architecture and RPATH/RUNPATH, and blocks on malicious VirusTotal results while recording suspicious results. |
| `archives/scripts/build-srpm-non-native.sh` | Used `rm -rf` on fixed working-directory names, trusted payload directories without provenance validation, and created non-deterministic archives. | [`../scripts/build_non_native_srpm.py`](../scripts/build_non_native_srpm.py) validates both architecture manifests, builds in a temporary directory, creates normalized source archives, and records SRPM metadata and its SHA256. |
| `archives/scripts/install-user.sh` | Extracted a tarball directly into the final install prefix without traversal checks or a manifest check; wrote launchers and desktop files directly. | [`../scripts/install_user.py`](../scripts/install_user.py) validates package/architecture identity, checks links and special files, supports safe extraction or a normalized payload directory, and stages runtime replacement. Its uninstall preserves settings unless purge is explicitly requested. |
| `archives/scripts/uninstall-user.sh` | Removed only the runtime, launcher, desktop file, and icon; did not clean managed PATH integration because the installer did not add it. | The maintained uninstaller removes only the selected package integration and removes its managed `.profile` block when no supported user launcher remains. |
| `archives/state/freecad-non-native.json` and `archives/state/freecad-candidate-non-native.json` | Both contained empty version/release placeholders and only a `packaging_mode` field. | The maintained `state/` files identify each package/channel/family and initialize its independent counter at zero. The finalizer adds fingerprints, build, security, and publication data after a successful build. |

## Legacy files deliberately not reviewed

The archive also contains `archives/.github/workflows/copr-ci.yml` and shared
release/submission scripts. They mix native and non-native behavior, so they
were excluded to respect the instruction not to use archived native files.
The native specs, native build scripts, and patch files were not opened. This
report therefore documents the non-native-only audit, not a full audit of all
historical archive contents.

## Migration decision

No archived implementation was copied. The maintained non-native pipeline is
implemented from the current repository baseline; the historical findings
above are recorded only to explain why the safer extraction, provenance,
scanning, and installation boundaries are required.
