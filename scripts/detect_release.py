#!/usr/bin/env python3
"""Resolve eligible FreeCAD releases and artifact metadata for CI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "release-policy.json"
STATE_DIR = ROOT / "state"
COPR_API = "https://copr.fedorainfracloud.org/api_3"
COPR_PAGE_SIZE = 100


class DetectionError(RuntimeError):
    pass


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_weekly(release: dict[str, Any], policy: dict[str, Any]) -> bool:
    tag_and_assets = [release.get("tag_name", "")]
    for asset in release.get("assets", []):
        tag_and_assets.extend((asset.get("name", ""), asset.get("browser_download_url", "")))
    marker = policy["weekly_marker"].casefold()
    if any(marker in str(value).casefold() for value in tag_and_assets):
        return True
    # Release notes can discuss weekly builds generically. A dated weekly
    # identity in the title/body is the unambiguous signal to exclude.
    dated_marker = re.compile(r"\bweekly[-_ ]?\d{4}[._-]\d{2}[._-]\d{2}\b", re.IGNORECASE)
    return any(dated_marker.search(str(release.get(field, ""))) for field in ("name", "body"))


def classify_release(release: dict[str, Any], policy: dict[str, Any]) -> str:
    tag = str(release.get("tag_name", ""))
    if is_weekly(release, policy):
        return "EXCLUDED_WEEKLY"
    if re.fullmatch(policy["candidate_tag_pattern"], tag, flags=re.IGNORECASE):
        return "CANDIDATE"
    if any(re.fullmatch(pattern, tag) for pattern in policy["stable_tag_patterns"]):
        return "CANDIDATE" if release.get("prerelease") else "STABLE"
    return "UNSUPPORTED"


def architecture_matches(name: str, architecture: str) -> bool:
    folded = name.casefold().replace("-", "_")
    aliases = {
        "x86_64": (r"(?<![a-z0-9])x86_64(?![a-z0-9])", r"(?<![a-z0-9])amd64(?![a-z0-9])"),
        "aarch64": (r"(?<![a-z0-9])aarch64(?![a-z0-9])", r"(?<![a-z0-9])arm64(?![a-z0-9])"),
    }
    return any(re.search(pattern, folded) for pattern in aliases[architecture])


def select_asset(release: dict[str, Any], architecture: str, policy: dict[str, Any]) -> dict[str, Any]:
    tag = str(release.get("tag_name", ""))
    for fmt in policy["artifact_priority"]:
        suffix = ".appimage" if fmt == "AppImage" else f".{fmt}"
        candidates = []
        for asset in release.get("assets", []):
            name = str(asset.get("name", ""))
            url = str(asset.get("browser_download_url", ""))
            if not name.casefold().startswith("freecad") or not name.casefold().endswith(suffix.casefold()):
                continue
            if tag.lstrip("vV").casefold() not in name.casefold():
                continue
            if not architecture_matches(name, architecture):
                continue
            if policy["weekly_marker"].casefold() in f"{name} {url}".casefold():
                continue
            candidates.append(asset)
        if candidates:
            candidates.sort(key=lambda item: str(item.get("name", "")).casefold())
            selected = candidates[0]
            filename = str(selected["name"])
            checksum_name = f"{filename}-SHA256.txt"
            checksum_asset = next(
                (item for item in release.get("assets", []) if item.get("name") == checksum_name), None
            )
            return {
                "name": filename,
                "format": fmt,
                "architecture": architecture,
                "url": selected["browser_download_url"],
                "digest": selected.get("digest"),
                "size": selected.get("size"),
                "updated_at": selected.get("updated_at"),
                "checksum_url": checksum_asset.get("browser_download_url") if checksum_asset else None,
            }
    raise DetectionError(f"No supported non-weekly {architecture} artifact for {tag}")


def choose_latest(releases: list[dict[str, Any]], channel: str, policy: dict[str, Any], forced_tag: str = "") -> dict[str, Any] | None:
    eligible = [release for release in releases if classify_release(release, policy) == channel.upper()]
    if forced_tag:
        eligible = [release for release in eligible if release.get("tag_name", "").casefold() == forced_tag.casefold()]
        if not eligible:
            raise DetectionError(f"Requested tag is not an eligible {channel} release: {forced_tag}")
        return eligible[0]
    eligible.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
    return eligible[0] if eligible else None


def load_releases(token: str = "") -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{load_policy()['upstream']}/releases?per_page=100"
    releases: list[dict[str, Any]] = []
    for page in range(1, 11):
        request = urllib.request.Request(url + f"&page={page}", headers={"Accept": "application/vnd.github+json"})
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                batch = json.load(response)
        except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            raise DetectionError(f"GitHub releases request failed: {exc}") from exc
        if not batch:
            break
        releases.extend(batch)
    return releases


def package_state(package: str) -> dict[str, Any]:
    path = STATE_DIR / f"{package}.json"
    if not path.exists():
        return {"version": None, "release": 0, "tag": None, "assets": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _copr_response_builds(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        rows = response
    elif isinstance(response, dict):
        rows = response.get("builds", response.get("items"))
    else:
        rows = None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise DetectionError("Copr build-list response has an unexpected shape")
    return rows


def load_copr_builds(package: str, project: str, timeout: int = 45) -> list[dict[str, Any]]:
    """Load the complete public Copr build history for one RPM package."""
    if project.count("/") != 1:
        raise DetectionError("Copr project must be OWNER/PROJECT")
    owner, project_name = project.split("/", 1)
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for offset in range(0, COPR_PAGE_SIZE * 100, COPR_PAGE_SIZE):
        query = urllib.parse.urlencode({
            "ownername": owner,
            "projectname": project_name,
            "packagename": package,
            "limit": COPR_PAGE_SIZE,
            "offset": offset,
            "order": "id",
            "order_type": "DESC",
        })
        request = urllib.request.Request(
            f"{COPR_API}/build/list/?{query}",
            headers={"Accept": "application/json", "User-Agent": "FreeCAD-Copr-release-detector"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
        except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            raise DetectionError(f"Copr build history request failed for {package}: {exc}") from exc
        batch = _copr_response_builds(payload)
        if not batch:
            return rows
        for row in batch:
            build_id = str(row.get("id") or "")
            if build_id and build_id in seen_ids:
                raise DetectionError(f"Copr build history pagination repeated build {build_id} for {package}")
            if build_id:
                seen_ids.add(build_id)
        rows.extend(batch)
        if len(batch) < COPR_PAGE_SIZE:
            return rows
    raise DetectionError(f"Copr build history exceeds the safe 10,000-record limit for {package}")


def successful_copr_release(
    builds: list[dict[str, Any]], package: str, version: str, required_chroots: list[str]
) -> int:
    """Return the greatest fully successful Copr RPM release for this version."""
    release_pattern = re.compile(re.escape(version) + r"-([1-9][0-9]*)")
    highest = 0
    for build in builds:
        source = build.get("source_package") or {}
        if not isinstance(source, dict):
            continue
        if str(source.get("name") or build.get("packagename") or "") != package:
            continue
        if str(build.get("state") or build.get("status") or "").casefold() != "succeeded":
            continue
        chroots = build.get("chroots")
        if not isinstance(chroots, list) or not set(required_chroots).issubset(chroots):
            continue
        source_version = str(source.get("version") or "")
        if not source_version:
            filename = Path(urllib.parse.urlsplit(str(source.get("url") or "")).path).name
            prefix = f"{package}-{version}-"
            if filename.startswith(prefix) and filename.endswith(".src.rpm"):
                source_version = f"{version}-{filename[len(prefix):-len('.src.rpm')]}"
        match = release_pattern.fullmatch(source_version)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest


def resolve_channel(
    release: dict[str, Any],
    channel: str,
    policy: dict[str, Any],
    copr_builds_by_package: dict[str, list[dict[str, Any]]] | None = None,
    required_chroots: list[str] | None = None,
) -> dict[str, Any]:
    tag = str(release["tag_name"])
    version = re.sub(r"^[vV]", "", tag)
    package_names = policy["packages"][channel]
    selected_assets = {
        arch: select_asset(release, arch, policy) for arch in policy["architectures"]
    }
    output: dict[str, Any] = {
        "channel": channel,
        "tag": tag,
        "version": version,
        "prerelease": bool(release.get("prerelease")),
        "release_url": release.get("html_url"),
        "published_at": release.get("published_at"),
        "native": {"package": package_names["native"]},
        "non_native": {"package": package_names["non_native"], "assets": selected_assets},
    }
    for family in ("native", "non_native"):
        package = package_names[family]
        shared_fingerprint_files = [
            ROOT / "README.md",
            ROOT / "config" / "release-policy.json",
            ROOT / "scripts" / "detect_release.py",
            ROOT / "scripts" / "security_scan.py",
            ROOT / ".github" / "workflows" / "build-rpm.yml",
            ROOT / "chroots.txt",
        ]
        fingerprint_files = (
            [
                *shared_fingerprint_files,
                ROOT / "freecad.spec",
                ROOT / "scripts" / "build_native_srpm.py",
                ROOT / "scripts" / "scan_native_source.py",
                *sorted((ROOT / "patches").glob("*.patch")),
            ]
            if family == "native"
            else [
                *shared_fingerprint_files,
                ROOT / "packaging" / "non-native" / "non-native.spec.in",
                ROOT / "scripts" / "build_non_native_srpm.py",
                ROOT / "scripts" / "fetch_asset.py",
                ROOT / "scripts" / "normalize_payload.py",
            ]
        )
        packaging_hash = hashlib.sha256()
        for input_path in fingerprint_files:
            packaging_hash.update(input_path.name.encode("utf-8"))
            packaging_hash.update(input_path.read_bytes())
        packaging_fingerprint = packaging_hash.hexdigest()
        old = package_state(package)
        old_release = int(old.get("release", 0)) if old.get("version") == version else 0
        fingerprints = {
            arch: {
                "name": asset.get("name"),
                "digest": asset.get("digest"),
                "url": asset.get("url"),
                "size": asset.get("size"),
                "updated_at": asset.get("updated_at"),
                "checksum_url": asset.get("checksum_url"),
            }
            for arch, asset in selected_assets.items()
        } if family == "non_native" else {}
        same_assets = old.get("assets", {}) == fingerprints
        state_changed = (
            old.get("version") != version
            or old.get("tag") != tag
            or old.get("packaging_fingerprint") != packaging_fingerprint
        )
        if family == "non_native":
            state_changed = state_changed or not same_assets
        if copr_builds_by_package is None:
            # Pure detector use (fixtures/local tests) can omit network records.
            copr_release = old_release
        else:
            copr_release = successful_copr_release(
                copr_builds_by_package.get(package, []),
                package,
                version,
                required_chroots or [],
            )
            if old_release > copr_release:
                raise DetectionError(
                    f"state for {package}/{version} claims release {old_release}, "
                    f"but Copr has no matching successful build record"
                )
        changed = state_changed or copr_release > old_release
        if copr_release > old_release and not state_changed:
            # Recover a successful Copr publication whose Git state commit was
            # interrupted. Rebuilding the same NEVR lets submission reuse it.
            rpm_release = copr_release
        else:
            rpm_release = max(old_release, copr_release) + (1 if state_changed else 0)
        if rpm_release < 1:
            rpm_release = 1
        output[family].update({
            "changed": changed,
            "release": rpm_release,
            "packaging_fingerprint": packaging_fingerprint,
            "assets_fingerprint": fingerprints,
        })
    return output


def detect(
    releases: list[dict[str, Any]],
    policy: dict[str, Any],
    forced_tag: str = "",
    forced_channel: str = "auto",
    copr_builds_by_package: dict[str, list[dict[str, Any]]] | None = None,
    required_chroots: list[str] | None = None,
) -> dict[str, Any]:
    channels: dict[str, Any] = {}
    selected_channels = (forced_channel,) if forced_channel != "auto" else ("stable", "candidate")
    if forced_tag and forced_channel == "auto":
        requested = next((item for item in releases if item.get("tag_name", "").casefold() == forced_tag.casefold()), None)
        if requested is None:
            raise DetectionError(f"Requested release tag was not found: {forced_tag}")
        classification = classify_release(requested, policy)
        if classification not in {"STABLE", "CANDIDATE"}:
            raise DetectionError(f"Requested release is not eligible: {forced_tag} ({classification})")
        selected_channels = (classification.lower(),)
    for channel in selected_channels:
        release = choose_latest(releases, channel, policy, forced_tag)
        if release is None:
            continue
        channels[channel] = resolve_channel(
            release, channel, policy, copr_builds_by_package, required_chroots
        )
    if not channels:
        raise DetectionError("No eligible stable or candidate release was found")
    return {"schema_version": 1, "channels": channels}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-tag", default="")
    parser.add_argument("--force-channel", choices=("auto", "stable", "candidate"), default="auto")
    parser.add_argument("--input-json", type=Path, help="Use a fixture instead of the GitHub API")
    parser.add_argument("--copr-builds-json", type=Path, help="Use a package-to-build-list fixture instead of the Copr API")
    parser.add_argument("--output", type=Path, help="Write manifest to a file")
    args = parser.parse_args()
    try:
        policy = load_policy()
        releases = json.loads(args.input_json.read_text(encoding="utf-8")) if args.input_json else load_releases(os.getenv("GITHUB_TOKEN", ""))
        if args.copr_builds_json:
            copr_builds = json.loads(args.copr_builds_json.read_text(encoding="utf-8"))
            if not isinstance(copr_builds, dict):
                raise DetectionError("Copr build fixture must map package names to build lists")
        else:
            project = str(policy.get("copr_project", ""))
            copr_builds = {
                package: load_copr_builds(package, project)
                for channel_packages in policy["packages"].values()
                for package in (channel_packages["native"], channel_packages["non_native"])
            }
        required_chroots = [
            line.strip() for line in (ROOT / "chroots.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not required_chroots or len(required_chroots) != len(set(required_chroots)):
            raise DetectionError("required Copr chroots are empty or duplicated")
        manifest = detect(
            releases, policy, args.force_tag, args.force_channel, copr_builds, required_chroots
        )
    except (DetectionError, OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"release detection failed: {exc}", file=sys.stderr)
        return 1
    rendered = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    native_matrix = []
    non_native_matrix = []
    native_package_matrix = []
    non_native_package_matrix = []
    for channel, item in manifest["channels"].items():
        native = item["native"]
        if native["changed"]:
            native_row = {
                "channel": channel,
                "package": native["package"],
                "tag": item["tag"],
                "version": item["version"],
                "release": str(native["release"]),
                "prerelease": item["prerelease"],
            }
            native_matrix.append(native_row)
            native_package_matrix.append(native_row)
        non_native = item["non_native"]
        if non_native["changed"]:
            non_native_package_matrix.append({
                "channel": channel,
                "package": non_native["package"],
                "tag": item["tag"],
                "version": item["version"],
                "release": str(non_native["release"]),
            })
            for architecture, asset in non_native["assets"].items():
                non_native_matrix.append({
                    "channel": channel,
                    "package": non_native["package"],
                    "tag": item["tag"],
                    "version": item["version"],
                    "release": str(non_native["release"]),
                    **asset,
                })
    if args.output:
        args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"manifest={rendered}\n")
            output.write(f"native_matrix={json.dumps(native_matrix, separators=(',', ':'))}\n")
            output.write(f"native_package_matrix={json.dumps(native_package_matrix or [{'skip': True}], separators=(',', ':'))}\n")
            output.write(f"non_native_matrix={json.dumps(non_native_matrix, separators=(',', ':'))}\n")
            output.write(f"non_native_package_matrix={json.dumps(non_native_package_matrix or [{'skip': True}], separators=(',', ':'))}\n")
            output.write(f"has_native={str(bool(native_matrix)).lower()}\n")
            output.write(f"has_non_native={str(bool(non_native_matrix)).lower()}\n")
            output.write(f"has_changes={str(bool(native_matrix or non_native_matrix)).lower()}\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
