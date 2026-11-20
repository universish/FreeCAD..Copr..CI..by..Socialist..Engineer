#!/usr/bin/env python3
"""Scan upstream artifacts and normalized payloads without executing them."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


BLOCKED_PATHS = ("/home/", "/tmp/", "/build/", "/runner/", "/opt/conda/")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_payload(root: Path, architecture: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    root = root.resolve(strict=True)
    expected_machine = {"x86_64": "Advanced Micro Devices X86-64", "aarch64": "AArch64"}[architecture]
    files: list[dict[str, Any]] = []
    links: list[dict[str, str]] = []
    elf_entries: list[dict[str, Any]] = []
    scripts: list[dict[str, str]] = []
    findings: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            target = os.readlink(path)
            resolved = (path.parent / target).resolve(strict=False)
            links.append({"path": rel, "target": target})
            if not resolved.is_relative_to(root):
                findings.append({"severity": "error", "path": rel, "reason": "symlink escapes payload root"})
            continue
        if not stat.S_ISREG(mode):
            findings.append({"severity": "error", "path": rel, "reason": "unsupported special file"})
            continue
        if mode & (stat.S_ISUID | stat.S_ISGID):
            findings.append({"severity": "error", "path": rel, "reason": "setuid/setgid permission"})

        with path.open("rb") as stream:
            header = stream.read(4)
            digest = hashlib.sha256(header)
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
            stream.seek(0)
            shebang = stream.readline(4096).decode("utf-8", errors="replace").strip()
        entry = {"path": rel, "size": path.stat().st_size, "sha256": digest.hexdigest(), "executable": bool(mode & 0o111)}
        files.append(entry)

        if header == b"\x7fELF":
            result = subprocess.run(["readelf", "-h", "-d", str(path)], capture_output=True, text=True, check=False)
            if result.returncode:
                findings.append({"severity": "error", "path": rel, "reason": "readelf inspection failed"})
                continue
            machine = next((line.partition(":")[2].strip() for line in result.stdout.splitlines() if "Machine:" in line), "unknown")
            rpaths = []
            for line in result.stdout.splitlines():
                if "(RPATH)" in line or "(RUNPATH)" in line:
                    rpaths.extend(line.partition("[")[2].partition("]")[0].split(":"))
            elf_entries.append({"path": rel, "machine": machine, "rpath_runpath": rpaths})
            if machine != expected_machine:
                findings.append({"severity": "error", "path": rel, "reason": f"architecture mismatch: {machine}"})
            for rpath in rpaths:
                if any(token in rpath for token in BLOCKED_PATHS):
                    findings.append({"severity": "error", "path": rel, "reason": f"build-host RPATH/RUNPATH: {rpath}"})

        if shebang.startswith("#!"):
            scripts.append({"path": rel, "shebang": shebang})
            if any(token in shebang for token in BLOCKED_PATHS):
                findings.append({"severity": "error", "path": rel, "reason": f"build-host shebang: {shebang}"})
            with path.open("rb") as script_file:
                script_text = script_file.read(256 * 1024).decode("utf-8", errors="replace")
            if re.search(r"(?i)(?:\bcurl\b|\bwget\b|\bnc\b|\bncat\b|\bsocat\b|/dev/tcp|base64\s+-d)", script_text):
                warnings.append({"severity": "warning", "path": rel, "reason": "script contains network or encoded-payload tooling; review before publication"})

    return {
        "files": files,
        "symlinks": links,
        "elf_files": elf_entries,
        "scripts": scripts,
        "findings": findings,
        "warnings": warnings,
    }, findings


def clam_scan(target: Path, report: Path, recursive: bool = True) -> dict[str, Any]:
    command = ["clamscan", "--infected", "--no-summary", f"--log={report}"]
    if recursive:
        command.append("--recursive")
    command.append(str(target))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    status = {0: "clean", 1: "infected"}.get(result.returncode, "error")
    return {"status": status, "exit_code": result.returncode, "report": str(report), "stderr": result.stderr.strip()}


def virustotal(hashes: list[str], api_key: str) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "disabled", "lookups": [], "malicious_hashes": [], "errors": []}
    if not api_key:
        return result
    result["status"] = "complete"
    for digest in sorted(set(hashes)):
        request = urllib.request.Request(
            f"https://www.virustotal.com/api/v3/files/{digest}",
            headers={"x-apikey": api_key, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.load(response)
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            malicious = int(stats.get("malicious", 0))
            suspicious = int(stats.get("suspicious", 0))
            result["lookups"].append({"sha256": digest, "status": "found", "malicious": malicious, "suspicious": suspicious})
            if malicious:
                result["malicious_hashes"].append(digest)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                result["lookups"].append({"sha256": digest, "status": "not_found"})
            elif exc.code in (401, 403, 429) or exc.code >= 500:
                result["status"] = "partial"
                result["errors"].append(f"HTTP {exc.code}")
                result["lookups"].append({"sha256": digest, "status": f"http_{exc.code}"})
                break
            else:
                result["status"] = "partial"
                result["errors"].append(f"HTTP {exc.code}")
        except (OSError, ValueError) as exc:
            result["status"] = "partial"
            result["errors"].append(type(exc).__name__)
            result["lookups"].append({"sha256": digest, "status": "unavailable"})
            break
        time.sleep(max(0.0, float(os.getenv("VT_MIN_INTERVAL_SECONDS", "15"))))
    if result["malicious_hashes"]:
        result["status"] = "malicious"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--architecture", required=True, choices=("x86_64", "aarch64"))
    parser.add_argument("--package", default="")
    parser.add_argument("--report", type=Path, default=Path("security-report.json"))
    parser.add_argument("--clamav-report-dir", type=Path, default=Path("security-reports"))
    args = parser.parse_args()
    report: dict[str, Any] = {"schema_version": 1, "architecture": args.architecture, "package": args.package, "findings": []}
    try:
        if not args.payload.is_dir() or not args.original.is_file():
            raise ValueError("payload directory or original artifact is missing")
        args.clamav_report_dir.mkdir(parents=True, exist_ok=True)
        update = subprocess.run(["sudo", "freshclam", "--stdout"], capture_output=True, text=True, check=False)
        if update.returncode:
            raise ValueError(f"ClamAV database update failed: {update.stderr.strip()}")
        report["clamav_database_update"] = {"exit_code": update.returncode, "output": update.stdout[-2000:]}
        report["clamav"] = {
            "original": clam_scan(args.original, args.clamav_report_dir / "original.txt", recursive=False),
            "payload": clam_scan(args.payload, args.clamav_report_dir / "payload.txt", recursive=True),
        }
        report["original_sha256"] = sha256_file(args.original)
        inspected, findings = inspect_payload(args.payload, args.architecture)
        report["inspection"] = inspected
        report["findings"] = findings
        file_hashes = [item["sha256"] for item in inspected["files"]]
        report["virustotal"] = virustotal(file_hashes, os.getenv("VT_API_KEY", ""))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        clam_failures = [item for item in report["clamav"].values() if item["status"] != "clean"]
        vt_bad = report["virustotal"]["status"] == "malicious"
        if clam_failures or findings or vt_bad:
            print(f"security gate failed; inspect {args.report}", file=sys.stderr)
            return 1
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        report["fatal_error"] = str(exc)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"security scan failed: {exc}", file=sys.stderr)
        return 1
    if report["virustotal"]["status"] in {"disabled", "partial"}:
        print(f"VirusTotal advisory result: {report['virustotal']['status']}", file=sys.stderr)
    print(f"security gate passed; report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
