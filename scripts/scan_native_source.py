#!/usr/bin/env python3
"""Run mandatory ClamAV scans over a checked-out upstream source tree."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def scan(target: Path, report_path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["clamscan", "--infected", "--recursive", f"--log={report_path}", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "target": str(target),
        "status": {0: "clean", 1: "infected"}.get(result.returncode, "error"),
        "exit_code": result.returncode,
        "stderr": result.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--report", type=Path, default=Path("native-security-report.json"))
    parser.add_argument("--report-dir", type=Path, default=Path("native-security-reports"))
    args = parser.parse_args()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"schema_version": 1, "architecture": "source", "package": args.package}
    try:
        source = args.source.resolve(strict=True)
        commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
        if commit.returncode:
            raise RuntimeError(f"unable to identify scanned source commit: {commit.stderr.strip()}")
        report["source_commit"] = commit.stdout.strip()
        update = subprocess.run(["sudo", "freshclam", "--stdout"], capture_output=True, text=True, check=False)
        if update.returncode:
            raise RuntimeError(f"ClamAV database update failed: {update.stderr.strip()}")
        report["clamav_database_update"] = {"exit_code": update.returncode, "output": update.stdout[-2000:]}
        root = Path(__file__).resolve().parents[1]
        targets = [
            source,
            root / "scripts",
            root / "patches",
            root / "packaging",
            root / "config",
            root / ".github" / "workflows",
            root / ".copr" / "Makefile",
            root / "freecad.spec",
        ]
        report["clamav"] = {
            str(target.relative_to(root)) if target.is_relative_to(root) else "upstream-source":
                scan(target, args.report_dir / f"scan-{index}.txt")
            for index, target in enumerate(targets)
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        failed = {name: item for name, item in report["clamav"].items() if item["status"] != "clean"}
        if failed:
            print(f"native source security gate failed: {failed}", file=sys.stderr)
            return 1
        print(f"native source security gate passed; report: {args.report}")
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        report["fatal_error"] = str(exc)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"native source security scan failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
