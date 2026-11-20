#!/usr/bin/env python3
"""Submit one SRPM to the configured Copr chroots and wait for every result."""

from __future__ import annotations

import argparse
import json
import os
import sys
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class SubmissionError(RuntimeError):
    pass


ROOT = Path(__file__).resolve().parents[1]
RELEASE_POLICY = json.loads((ROOT / "config" / "release-policy.json").read_text(encoding="utf-8"))


def as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "items"):
        return dict(value.items())
    return dict(vars(value))


def srpm_identity(path: Path) -> tuple[str, str, str]:
    result = subprocess.run(
        ["rpm", "-qp", "--qf", "%{NAME}\n%{VERSION}\n%{RELEASE}\n", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise SubmissionError(f"unable to read SRPM identity: {result.stderr.strip()}")
    fields = result.stdout.splitlines()
    if len(fields) != 3 or not all(fields):
        raise SubmissionError(f"SRPM returned incomplete package identity: {path}")
    return fields[0], fields[1], fields[2]


def response_builds(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return [as_dict(item) for item in response]
    data = as_dict(response)
    for key in ("builds", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return [as_dict(item) for item in value]
    raise SubmissionError("Copr build list response has an unexpected shape")


def find_existing_build(
    client: Any,
    owner: str,
    project: str,
    package: str,
    srpm_name: str,
    version_release: str,
    required_chroots: list[str],
) -> dict[str, Any] | None:
    rows = response_builds(client.build_proxy.get_list(owner, project, packagename=package))
    matches: list[dict[str, Any]] = []
    for row in rows:
        source = as_dict(row.get("source_package") or {})
        if source.get("name") != package:
            continue
        source_url = str(source.get("url") or "")
        source_filename = Path(urllib.parse.urlsplit(source_url).path).name
        same_filename = source_filename == srpm_name
        same_version_release = str(source.get("version") or "") == version_release
        if not (same_filename and same_version_release):
            continue
        target_chroots = row.get("chroots", [])
        if not isinstance(target_chroots, list) or not set(required_chroots).issubset(target_chroots):
            continue
        matches.append(row)
    if not matches:
        return None
    matches.sort(key=lambda row: int(row.get("id") or 0), reverse=True)
    reusable = [row for row in matches if str(row.get("state") or row.get("status") or "").casefold() == "succeeded"]
    if reusable:
        return reusable[0]
    active = [
        row for row in matches
        if str(row.get("state") or row.get("status") or "").casefold()
        not in {"failed", "canceled", "cancelled", "skipped"}
    ]
    return active[0] if active else None


def load_chroots(path: Path) -> list[str]:
    chroots = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.lstrip().startswith("#")]
    if not chroots or len(chroots) != len(set(chroots)):
        raise SubmissionError("chroots.txt is empty or contains duplicates")
    return chroots


def monitor_chroots(
    client: Any,
    build_id: int,
    chroots: list[str],
    timeout_seconds: int,
    poll_seconds: int,
    monotonic=time.monotonic,
    sleep=time.sleep,
) -> tuple[dict[str, dict[str, Any]], bool]:
    terminal = {"succeeded", "failed", "canceled", "cancelled", "skipped"}
    failures = {"failed", "canceled", "cancelled", "skipped"}
    deadline = monotonic() + timeout_seconds
    results: dict[str, dict[str, Any]] = {}
    while True:
        pending = False
        for chroot in chroots:
            result = as_dict(client.build_chroot_proxy.get(build_id, chroot))
            state = str(result.get("status") or result.get("state") or "unknown").casefold()
            results[chroot] = result
            if state not in terminal:
                pending = True
        if any(
            str(result.get("status") or result.get("state") or "unknown").casefold() in failures
            for result in results.values()
        ):
            return results, False
        if not pending:
            return results, False
        remaining = deadline - monotonic()
        if remaining <= 0:
            return results, True
        sleep(min(poll_seconds, remaining))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--srpm", type=Path, required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--project", default=os.getenv("COPR_PROJECT", RELEASE_POLICY["copr_project"]))
    parser.add_argument("--chroots", type=Path, default=Path(__file__).resolve().parents[1] / "chroots.txt")
    parser.add_argument("--output", type=Path, default=Path("copr-build-result.json"))
    parser.add_argument("--timeout-seconds", type=int, default=20_000)
    parser.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()

    try:
        if not args.srpm.is_file() or args.srpm.suffixes[-2:] != [".src", ".rpm"]:
            raise SubmissionError(f"not an SRPM: {args.srpm}")
        if "/" not in args.project or args.project.count("/") != 1:
            raise SubmissionError("Copr project must be OWNER/PROJECT")
        owner, project = args.project.split("/", 1)
        chroots = load_chroots(args.chroots)
        srpm_name, srpm_version, srpm_release = srpm_identity(args.srpm)
        if srpm_name != args.package:
            raise SubmissionError(
                f"SRPM package name {srpm_name!r} does not match requested package {args.package!r}"
            )
        version_release = f"{srpm_version}-{srpm_release}"
        from copr.v3 import Client

        client = Client.create_from_config_file()
        client.project_proxy.get(owner, project)
        existing = find_existing_build(
            client, owner, project, args.package, args.srpm.name, version_release, chroots
        )
        reused_existing_build = existing is not None
        if existing is None:
            check_options = {"chroots": chroots, "progress_callback": None}
            client.build_proxy.check_before_build(owner, project, buildopts=check_options)
            options = {"chroots": chroots}
            submitted = client.build_proxy.create_from_file(owner, project, str(args.srpm), buildopts=options)
            build_id = int(submitted.id)
        else:
            build_id = int(existing["id"])
        chroot_results, timed_out = monitor_chroots(
            client, build_id, chroots, args.timeout_seconds, args.poll_seconds
        )

        final = {
            "package": args.package,
            "project": args.project,
            "srpm": args.srpm.name,
            "reused_existing_build": reused_existing_build,
            "build_id": build_id,
            "build_url": f"https://copr.fedorainfracloud.org/coprs/{owner}/{project}/build/{build_id}/",
            "chroots": chroot_results,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        log_dir = args.output.parent / f"copr-logs-{build_id}"
        log_dir.mkdir(parents=True, exist_ok=True)
        for chroot, row in chroot_results.items():
            for field in ("url_build_log", "url_backend_log", "build_log_url", "backend_log_url"):
                log_url = row.get(field)
                if not isinstance(log_url, str) or not log_url.startswith("https://"):
                    continue
                try:
                    with urllib.request.urlopen(log_url, timeout=60) as response:
                        log_dir.joinpath(f"{chroot}-{field}.txt").write_bytes(response.read())
                except OSError as exc:
                    row[f"{field}_download_error"] = str(exc)
        args.output.write_text(json.dumps(final, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        if timed_out:
            raise SubmissionError(f"Copr build {build_id} timed out; result details saved to {args.output}")
        failed = {
            chroot: str(result.get("status") or result.get("state") or "unknown")
            for chroot, result in chroot_results.items()
            if str(result.get("status") or result.get("state") or "unknown").casefold() != "succeeded"
        }
        if failed or set(chroot_results) != set(chroots):
            raise SubmissionError(f"Copr build {build_id} did not succeed in every target: {failed}")
        print(json.dumps(final, sort_keys=True, default=str))
    except (OSError, ValueError, ImportError, AttributeError, KeyError, SubmissionError) as exc:
        print(f"Copr submission failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
