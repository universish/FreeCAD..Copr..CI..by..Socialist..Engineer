#!/usr/bin/env python3
"""Create one two-architecture non-native SRPM from inspected payloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "config" / "release-policy.json").read_text(encoding="utf-8"))
TEMPLATE = ROOT / "packaging" / "non-native" / "non-native.spec.in"


class BuildError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def spec_for(package: str, version: str, release: str) -> str:
    channel = next((name for name, packages in POLICY["packages"].items() if packages["non_native"] == package), None)
    if channel is None:
        raise BuildError(f"package is not in release policy: {package}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+~-]*", version) or not re.fullmatch(r"[1-9][0-9]*", release):
        raise BuildError("invalid RPM version or release number")
    if "weekly" in version.casefold():
        raise BuildError("weekly FreeCAD builds are excluded from non-native SRPM generation")
    from detect_release import classify_release, load_policy

    classification = classify_release(
        {"tag_name": version, "prerelease": channel == "candidate"}, load_policy()
    )
    expected = "STABLE" if channel == "stable" else "CANDIDATE"
    if classification != expected:
        raise BuildError(f"version {version} classifies as {classification}, not {expected}")
    metadata = POLICY["packages"][channel]
    replacements = {
        "@PACKAGE@": package,
        "@VERSION@": version,
        "@RELEASE@": release,
        "@COMMAND@": metadata["non_native_command"],
        "@DESKTOP_ID@": metadata["non_native_desktop_id"],
        "@DISPLAY_NAME@": metadata["non_native_display_name"],
    }
    rendered = TEMPLATE.read_text(encoding="utf-8")
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    if re.search(r"@[A-Z_]+@", rendered):
        raise BuildError("non-native spec has unresolved template tokens")
    return rendered


def verify_payload(path: Path, package: str, architecture: str) -> None:
    manifest_path = path / "payload-manifest.json"
    if not (path / "AppRun").is_file() or not (path / "AppRun").stat().st_mode & 0o111:
        raise BuildError(f"missing executable AppRun for {package}/{architecture}")
    if not (path / "freecad-icon.svg").is_file():
        raise BuildError(f"missing FreeCAD icon for {package}/{architecture}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"payload manifest is missing or invalid: {manifest_path}") from exc
    if manifest.get("package") != package or manifest.get("architecture") != architecture:
        raise BuildError(f"payload manifest identity mismatch: {manifest_path}")
    if not re.fullmatch(r"[a-f0-9]{64}", str(manifest.get("source_sha256", ""))):
        raise BuildError(f"payload manifest has no verified artifact hash: {manifest_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--payload-root", type=Path, default=ROOT / "payload")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "SRPMS")
    args = parser.parse_args()
    try:
        spec = spec_for(args.package, args.version, args.release)
        payload_root = args.payload_root.resolve(strict=True)
        with tempfile.TemporaryDirectory(prefix="freecad-nonnative-srpm-") as temporary:
            work = Path(temporary)
            sources, specs, topdir, srpms = (work / name for name in ("SOURCES", "SPECS", "rpmbuild", "srpms"))
            for directory in (sources, specs, topdir, srpms):
                directory.mkdir()
            for architecture in POLICY["architectures"]:
                payload = payload_root / args.package / architecture
                verify_payload(payload, args.package, architecture)
                archive_path = sources / f"freecad-payload-{architecture}.tar.gz"
                result = subprocess.run(
                    ["tar", "--directory", str(payload), "--create", "--gzip", "--file", str(archive_path),
                     "--sort=name", "--mtime=@0", "--owner=0", "--group=0", "--numeric-owner", "."],
                    capture_output=True, check=False,
                )
                if result.returncode:
                    raise BuildError(f"payload archive creation failed: {result.stderr.decode(errors='replace')}")
            spec_path = specs / f"{args.package}.spec"
            spec_path.write_text(spec, encoding="utf-8")
            expanded = subprocess.run(["rpmspec", "-P", str(spec_path)], cwd=ROOT, capture_output=True, check=False)
            if expanded.returncode:
                raise BuildError(f"RPM spec expansion failed:\n{expanded.stderr.decode(errors='replace')}")
            result = subprocess.run(
                ["rpmbuild", "-bs", str(spec_path), "--define", f"_topdir {topdir}",
                 "--define", f"_sourcedir {sources}", "--define", f"_srcrpmdir {srpms}"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            if result.returncode:
                raise BuildError(f"rpmbuild failed:\n{result.stdout}\n{result.stderr}")
            built = list(srpms.glob("*.src.rpm"))
            if len(built) != 1:
                raise BuildError(f"expected one SRPM, found {len(built)}")
            args.output_dir.mkdir(parents=True, exist_ok=True)
            final = args.output_dir.resolve() / built[0].name
            shutil.copy2(built[0], final)
            manifest = {
                "package": args.package,
                "version": args.version,
                "release": int(args.release),
                "srpm": final.name,
                "srpm_sha256": sha256_file(final),
            }
            (args.output_dir / f"{args.package}-srpm.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(manifest, sort_keys=True))
    except (OSError, BuildError, subprocess.SubprocessError) as exc:
        print(f"non-native SRPM build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
