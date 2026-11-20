#!/usr/bin/env python3
"""Finalize only successful Copr publications into independent package state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "config" / "release-policy.json").read_text(encoding="utf-8"))


class StateError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(args: argparse.Namespace) -> dict[str, Any]:
    if args.manifest:
        return read_json(args.manifest)
    raw = os.getenv("RELEASE_MANIFEST", "")
    if not raw:
        raise StateError("release manifest is missing")
    return json.loads(raw)


def successful_result(path: Path, required_chroots: list[str], package: str) -> dict[str, Any]:
    result = read_json(path)
    if result.get("package") != package:
        raise StateError(f"Copr result package does not match {package}: {path}")
    if not result.get("build_id") or not result.get("build_url"):
        raise StateError(f"Copr result has no build identifier or URL: {path}")
    chroots = result.get("chroots", {})
    if set(chroots) != set(required_chroots):
        raise StateError(f"Copr result does not cover all required chroots: {path}")
    failed = {name: row for name, row in chroots.items() if str(row.get("status", "")).casefold() != "succeeded"}
    if failed:
        raise StateError(f"Copr result includes failed chroots: {path}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--results-dir", type=Path, default=Path("build-results"))
    parser.add_argument("--payload-dir", type=Path, default=Path("payloads"))
    parser.add_argument("--build-metadata-dir", type=Path, default=Path("build-metadata"))
    parser.add_argument("--security-dir", type=Path, default=Path("security-reports"))
    parser.add_argument("--chroots", type=Path, default=ROOT / "chroots.txt")
    parser.add_argument("--state-dir", type=Path, default=ROOT / "state")
    args = parser.parse_args()

    try:
        manifest = load_manifest(args)
        if manifest.get("schema_version") != 1:
            raise StateError("unsupported release manifest schema")
        required_chroots = [line.strip() for line in args.chroots.read_text(encoding="utf-8").splitlines()
                            if line.strip() and not line.lstrip().startswith("#")]
        if not required_chroots or len(required_chroots) != len(set(required_chroots)):
            raise StateError("required Copr chroots are empty or duplicated")
        result_files = {path.stem: path for path in args.results_dir.glob("**/*.json")}
        payload_manifests = {}
        for path in args.payload_dir.glob("payload-*/payload-manifest.json"):
            payload = read_json(path)
            payload_manifests[(payload.get("package"), payload.get("architecture"))] = payload
        build_metadata = {}
        for path in args.build_metadata_dir.glob("**/*.json"):
            metadata = read_json(path)
            if metadata.get("package"):
                build_metadata[metadata["package"]] = metadata
        security_reports = [read_json(path) for path in args.security_dir.glob("**/*security-report.json")]
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        updated: list[dict[str, Any]] = []
        pending_writes: list[tuple[Path, dict[str, Any]]] = []

        for channel, release_data in manifest.get("channels", {}).items():
            if channel not in POLICY["packages"]:
                raise StateError(f"unknown channel in release manifest: {channel}")
            for family in ("native", "non_native"):
                item = release_data[family]
                if not item.get("changed"):
                    continue
                package = item["package"]
                result_path = result_files.get(package)
                if result_path is None:
                    raise StateError(f"successful Copr build result is missing for {package}")
                result = successful_result(result_path, required_chroots, package)
                if int(item.get("release", 0)) < 1:
                    raise StateError(f"invalid RPM release for {package}")
                state = {
                    "schema_version": 1,
                    "package": package,
                    "channel": channel,
                    "family": "native" if family == "native" else "non-native",
                    "version": release_data["version"],
                    "tag": release_data["tag"],
                    "release": int(item["release"]),
                    "packaging_fingerprint": item["packaging_fingerprint"],
                    "assets_fingerprint": item.get("assets_fingerprint", {}),
                    "architectures": POLICY["architectures"],
                    "assets": {},
                    "source_commit": None,
                    "source_archive_sha256": None,
                    "srpm_artifact": None,
                    "copr_builds": [{
                        "id": result["build_id"],
                        "url": result["build_url"],
                        "chroots": result["chroots"],
                    }],
                    "target_chroots": required_chroots,
                    "security_results": {},
                    "published_at": now,
                    "final_status": "succeeded",
                }
                metadata = build_metadata.get(package, {})
                if metadata.get("package") != package:
                    raise StateError(f"SRPM build metadata is missing for {package}")
                if result.get("srpm") != metadata.get("srpm"):
                    raise StateError(f"Copr result SRPM does not match build metadata for {package}")
                srpm_hash = str(metadata.get("srpm_sha256", ""))
                if not metadata.get("srpm") or not re.fullmatch(r"[a-f0-9]{64}", srpm_hash):
                    raise StateError(f"SRPM filename or SHA256 is missing for {package}")
                srpm_paths = list(args.build_metadata_dir.glob(f"**/{metadata['srpm']}"))
                if len(srpm_paths) != 1 or sha256_file(srpm_paths[0]) != srpm_hash:
                    raise StateError(f"SRPM artifact is missing, duplicated, or has a SHA256 mismatch for {package}")
                state["source_commit"] = metadata.get("source_commit")
                state["source_archive_sha256"] = metadata.get("source_archive_sha256")
                state["srpm_artifact"] = {"filename": metadata["srpm"], "sha256": srpm_hash}
                if family == "native":
                    if not re.fullmatch(r"[0-9a-f]{40,64}", str(state["source_commit"] or "")):
                        raise StateError(f"native source commit is missing for {package}")
                    if not re.fullmatch(r"[a-f0-9]{64}", str(state["source_archive_sha256"] or "")):
                        raise StateError(f"native source archive SHA256 is missing for {package}")
                if family == "non_native":
                    for arch in POLICY["architectures"]:
                        payload = payload_manifests.get((package, arch))
                        if payload is None:
                            raise StateError(f"verified payload manifest missing for {package}/{arch}")
                        expected_asset = release_data[family]["assets"][arch]
                        expected_digest = str(expected_asset.get("digest") or "").removeprefix("sha256:").lower()
                        if payload.get("source_filename") != expected_asset.get("name"):
                            raise StateError(f"payload filename does not match selected release asset for {package}/{arch}")
                        if payload.get("format") != expected_asset.get("format"):
                            raise StateError(f"payload format does not match selected release asset for {package}/{arch}")
                        if expected_digest and payload.get("source_sha256") != expected_digest:
                            raise StateError(f"payload SHA256 does not match the selected asset digest for {package}/{arch}")
                        state["assets"][arch] = {
                            "filename": payload["source_filename"],
                            "sha256": payload["source_sha256"],
                            "format": payload["format"],
                        }
                package_reports = {str(report.get("architecture")): report for report in security_reports if report.get("package") == package}
                expected_security_arches = POLICY["architectures"] if family == "non_native" else ["source"]
                if not set(expected_security_arches).issubset(package_reports):
                    raise StateError(f"security reports are incomplete for {package}")
                for architecture in expected_security_arches:
                    report = package_reports[architecture]
                    if report.get("fatal_error"):
                        raise StateError(f"security scan failed for {package}/{architecture}")
                    if report.get("clamav_database_update", {}).get("exit_code") != 0:
                        raise StateError(f"ClamAV database update is not verified for {package}/{architecture}")
                    clamav_rows = report.get("clamav", {})
                    if not clamav_rows or any(item.get("status") != "clean" for item in clamav_rows.values()):
                        raise StateError(f"ClamAV report is not clean for {package}/{architecture}")
                    if report.get("findings"):
                        raise StateError(f"blocking static security findings exist for {package}/{architecture}")
                    if report.get("virustotal", {}).get("status") == "malicious":
                        raise StateError(f"VirusTotal reported malicious hashes for {package}/{architecture}")
                    if report.get("virustotal", {}).get("malicious_hashes"):
                        raise StateError(f"VirusTotal malicious hashes exist for {package}/{architecture}")
                    if family == "native" and report.get("source_commit") != state["source_commit"]:
                        raise StateError(f"native security report does not match the built source commit for {package}")
                    if family == "non_native":
                        expected_hash = state["assets"][architecture]["sha256"]
                        if report.get("original_sha256") != expected_hash:
                            raise StateError(f"security report does not match the verified source asset for {package}/{architecture}")
                state["security_results"] = {
                    str(report.get("architecture", "native")): {
                        "clamav": report.get("clamav", {}),
                        "virustotal": report.get("virustotal", {}),
                        "findings": report.get("findings", []),
                        "warnings": report.get("inspection", {}).get("warnings", []),
                    }
                    for report in security_reports
                    if report.get("package") == package
                }
                final_path = args.state_dir / f"{package}.json"
                pending_writes.append((final_path, state))
                updated.append({"package": package, "version": state["version"], "release": state["release"], "build_id": result["build_id"]})

        args.state_dir.mkdir(parents=True, exist_ok=True)
        for final_path, state in pending_writes:
            temporary_path = final_path.with_suffix(final_path.suffix + ".tmp")
            temporary_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            temporary_path.replace(final_path)
        print(json.dumps({"updated": updated}, sort_keys=True))
    except (OSError, KeyError, ValueError, StateError, json.JSONDecodeError) as exc:
        print(f"release state finalization failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
