#!/usr/bin/env python3
"""Build a native FreeCAD SRPM from the exact upstream tag checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "freecad.spec"
PATCHES = (ROOT / "patches" / "0001-fix-nlohmann-json-include.patch", ROOT / "patches" / "0002-find-external-e57format.patch")
POLICY = json.loads((ROOT / "config" / "release-policy.json").read_text(encoding="utf-8"))


class BuildError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(source: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(source), *args], capture_output=True, check=False)
    if result.returncode:
        raise BuildError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout.decode("utf-8", errors="surrogateescape")


def validate_version(version: str, release: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+~-]*", version):
        raise BuildError(f"invalid RPM version: {version!r}")
    if not re.fullmatch(r"[1-9][0-9]*", release):
        raise BuildError(f"RPM release must be a positive integer: {release!r}")
    if "weekly" in version.casefold():
        raise BuildError("weekly FreeCAD builds are excluded from native SRPM generation")


def validate_checkout(source: Path, version: str, package: str = "freecad", prerelease: bool = False) -> None:
    source = source.resolve(strict=True)
    if not (source / "CMakeLists.txt").is_file():
        raise BuildError(f"not a FreeCAD source checkout: {source}")
    origin = git(source, "remote", "get-url", "origin").strip().lower().removesuffix(".git")
    if origin not in {"https://github.com/freecad/freecad", "git@github.com:freecad/freecad", "ssh://git@github.com/freecad/freecad"}:
        raise BuildError(f"unexpected upstream origin: {origin}")
    tags = git(source, "tag", "--points-at", "HEAD").splitlines()
    expected = {version.casefold(), f"v{version}".casefold()}
    matched_tag = next((tag for tag in tags if tag.casefold() in expected), None)
    if matched_tag is None:
        raise BuildError(f"HEAD is not tagged with the requested release {version}")
    from detect_release import classify_release, load_policy

    classification = classify_release({"tag_name": matched_tag, "prerelease": prerelease}, load_policy())
    if classification == "EXCLUDED_WEEKLY":
        raise BuildError("weekly FreeCAD tags are excluded from native SRPM generation")
    package_channel = next((channel for channel, values in POLICY["packages"].items() if values["native"] == package), None)
    if package_channel is None:
        raise BuildError(f"unknown native package identity: {package}")
    expected_classification = "STABLE" if package_channel == "stable" else "CANDIDATE"
    if classification != expected_classification:
        raise BuildError(f"tag {matched_tag} classifies as {classification}, not {expected_classification}")
    changes = git(source, "status", "--porcelain", "--untracked-files=all")
    if changes.strip():
        raise BuildError(f"upstream checkout contains local changes:\n{changes}")
    submodules = git(source, "submodule", "status", "--recursive")
    if any(line.startswith(("-", "+", "U")) for line in submodules.splitlines()):
        raise BuildError(f"source submodules are missing, modified, or conflicted:\n{submodules}")


def validate_native_profile(source: Path, spec_text: str) -> None:
    """Reject custom CMake definitions that the selected upstream tag does not declare."""
    declared: set[str] = set()
    declaration_patterns = (
        re.compile(r"(?m)^\s*option\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE),
        re.compile(r"(?m)^\s*cmake_dependent_option\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE),
        re.compile(r"(?m)^\s*set\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE),
    )
    cmake_inputs = list(source.rglob("*.cmake")) + list(source.rglob("CMakeLists.txt"))
    for path in cmake_inputs:
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in declaration_patterns:
            declared.update(match.group(1) for match in pattern.finditer(text))
    project_definitions = {
        name
        for name in re.findall(r"(?m)^\s*-D([A-Za-z_][A-Za-z0-9_]*)=", spec_text)
        if not name.startswith("CMAKE_")
    }
    unknown = sorted(project_definitions - declared)
    if unknown:
        raise BuildError("native CMake profile contains options not declared by this upstream tag: " + ", ".join(unknown))


def make_source_archive(source: Path, destination: Path) -> None:
    names = git(source, "ls-files", "--recurse-submodules", "-z").encode("utf-8", errors="surrogateescape")
    if not names.strip(b"\0"):
        raise BuildError("upstream checkout contains no tracked files")
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "tar", "--directory", str(source), "--create", "--gzip", "--file", str(destination),
            "--sort=name", "--mtime=@0", "--owner=0", "--group=0", "--numeric-owner",
            "--no-recursion", "--null", "--verbatim-files-from", "--files-from=-",
        ],
        input=names,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise BuildError(f"source archive creation failed: {result.stderr.decode(errors='replace')}")


def spec_for(package: str, version: str, release: str, template: str | None = None) -> str:
    channel = next((name for name, values in POLICY["packages"].items() if values["native"] == package), None)
    if channel is None:
        raise BuildError(f"package is not in release policy: {package}")
    validate_version(version, release)
    profile = POLICY["packages"][channel]
    macros = {
        "fc_package": profile["native"],
        "fc_command": profile["native_command"],
        "fc_cmd_command": profile["native_cmd_command"],
        "fc_thumbnail_command": profile["native_thumbnail_command"],
        "fc_app_id": profile["native_app_id"],
        "fc_icon_name": profile["native_icon_name"],
        "fc_desktop_file": profile["native_desktop_file"],
        "fc_metainfo_file": profile["native_metainfo_file"],
        "fc_mime_file": profile["native_mime_file"],
        "fc_thumbnail_file": profile["native_thumbnail_file"],
        "fc_shared_mime_icon_owner": "1" if channel == "stable" else "0",
    }
    spec = template if template is not None else SPEC.read_text(encoding="utf-8")
    spec = spec.replace("@VERSION@", version).replace("@RELEASE@", release)
    rendered = "\n".join(f"%global {key} {value}" for key, value in macros.items()) + "\n" + spec
    if "@VERSION@" in rendered or "@RELEASE@" in rendered:
        raise BuildError("spec contains unresolved version placeholders")
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--prerelease", action="store_true")
    parser.add_argument("--package", choices=tuple(values["native"] for values in POLICY["packages"].values()), default="freecad")
    parser.add_argument("--spec", type=Path, default=SPEC)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "SRPMS")
    args = parser.parse_args()
    try:
        validate_version(args.version, args.release)
        source = args.source.resolve(strict=True)
        validate_checkout(source, args.version, args.package, args.prerelease)
        for patch in PATCHES:
            if not patch.is_file() or not patch.stat().st_size:
                raise BuildError(f"required packaging patch missing: {patch}")
        spec_template = args.spec.resolve(strict=True).read_text(encoding="utf-8")
        validate_native_profile(source, spec_template)
        with tempfile.TemporaryDirectory(prefix="freecad-native-srpm-") as temporary:
            work = Path(temporary)
            sources = work / "SOURCES"
            spec_dir = work / "SPECS"
            topdir = work / "rpmbuild"
            srpm_dir = work / "srpms"
            sources.mkdir()
            spec_dir.mkdir()
            topdir.mkdir()
            srpm_dir.mkdir()
            source_archive = sources / "freecad-sources.tar.gz"
            make_source_archive(source, source_archive)
            shutil.copy2(ROOT / "README.md", sources / "README.md")
            for patch in PATCHES:
                shutil.copy2(patch, sources / patch.name)
            spec_text = spec_for(args.package, args.version, args.release, spec_template)
            spec_path = spec_dir / "freecad.spec"
            spec_path.write_text(spec_text, encoding="utf-8")
            command = [
                "rpmbuild", "-bs", str(spec_path),
                "--define", f"_topdir {topdir}",
                "--define", f"_sourcedir {sources}",
                "--define", f"_srcrpmdir {srpm_dir}",
            ]
            result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
            if result.returncode:
                raise BuildError(f"rpmbuild failed:\n{result.stdout}\n{result.stderr}")
            srpms = list(srpm_dir.glob("*.src.rpm"))
            if len(srpms) != 1:
                raise BuildError(f"expected one SRPM, found {len(srpms)}")
            args.output_dir.mkdir(parents=True, exist_ok=True)
            output = args.output_dir.resolve() / srpms[0].name
            shutil.copy2(srpms[0], output)
            manifest = {
                "package": args.package,
                "version": args.version,
                "release": int(args.release),
                "source_commit": git(source, "rev-parse", "HEAD").strip(),
                "source_tag": git(source, "describe", "--tags", "--exact-match", "HEAD").strip(),
                "srpm": output.name,
                "srpm_sha256": sha256_file(output),
                "source_archive_sha256": sha256_file(source_archive),
            }
            (args.output_dir / f"{args.package}-native-srpm.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(manifest, sort_keys=True))
    except (OSError, BuildError, subprocess.SubprocessError) as exc:
        print(f"native SRPM build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
