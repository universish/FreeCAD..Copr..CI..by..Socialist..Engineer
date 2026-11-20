#!/usr/bin/env python3
"""Download one release asset and require an upstream SHA256 match."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def validate_https_url(value: str) -> None:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}:
        raise ValueError(f"refusing unexpected download URL: {value}")


def parse_sha256_sidecar(contents: str, filename: str) -> str | None:
    matched: set[str] = set()
    bare: set[str] = set()
    for line in contents.splitlines():
        fields = line.strip().split()
        hashes = [field for field in fields if re.fullmatch(r"[A-Fa-f0-9]{64}", field)]
        if not hashes:
            continue
        digest = hashes[0].lower()
        if len(fields) == 1:
            bare.add(digest)
        elif fields[-1].lstrip("*") == filename:
            matched.add(digest)
    if len(matched) == 1:
        return next(iter(matched))
    if len(matched) > 1:
        raise ValueError(f"checksum file contains duplicate entries for {filename}")
    if len(bare) == 1:
        return next(iter(bare))
    if len(bare) > 1:
        raise ValueError("checksum file contains multiple unlabelled hashes")
    return None


def request_bytes(url: str, token: str = "") -> bytes:
    validate_https_url(url)
    headers = {"Accept": "application/octet-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=90) as response:
        validate_https_url(response.geturl())
        return response.read()


def download_asset(url: str, destination: Path, token: str = "") -> str:
    validate_https_url(url)
    headers = {"Accept": "application/octet-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    digest = hashlib.sha256()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as stream:
            validate_https_url(response.geturl())
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                stream.write(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return digest.hexdigest()


def fetch_checksum(url: str, token: str = "") -> str:
    contents = request_bytes(url, token).decode("utf-8", errors="replace")
    return contents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--filename", required=True)
    parser.add_argument("--architecture", required=True, choices=("x86_64", "aarch64"))
    parser.add_argument("--format", required=True, choices=("rpm", "deb", "AppImage"))
    parser.add_argument("--digest", default="")
    parser.add_argument("--checksum-url", default="")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if Path(args.filename).name != args.filename or args.filename in {"", ".", ".."}:
        print("invalid artifact filename", file=sys.stderr)
        return 2
    output_dir = args.output_dir or Path("dist") / args.architecture
    destination = output_dir / args.filename
    token = os.getenv("GITHUB_TOKEN", "")

    verified_by = "github_asset_digest"
    try:
        actual = download_asset(args.url, destination, token)
        expected = ""
        if args.checksum_url:
            try:
                expected = parse_sha256_sidecar(fetch_checksum(args.checksum_url, token), args.filename) or ""
            except (OSError, urllib.error.URLError, UnicodeError) as exc:
                if not args.digest:
                    raise ValueError(f"unable to retrieve required checksum sidecar: {exc}") from exc
                print(f"warning: checksum sidecar unavailable; using GitHub asset digest: {exc}", file=sys.stderr)
        if not expected and args.digest:
            expected = args.digest.removeprefix("sha256:").lower()
        elif expected:
            verified_by = "sidecar"
        if not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ValueError("no trustworthy SHA256 checksum is available")
        if actual != expected:
            raise ValueError(f"SHA256 mismatch: expected {expected}, got {actual}")
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, ValueError, UnicodeError) as exc:
        destination.unlink(missing_ok=True)
        print(f"asset verification failed: {exc}", file=sys.stderr)
        return 1

    result = {
        "filename": args.filename,
        "path": str(destination),
        "architecture": args.architecture,
        "format": args.format,
        "sha256": actual,
        "verified_by": verified_by,
    }
    manifest_path = output_dir / "verified-asset.json"
    manifest_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            for key in ("filename", "path", "sha256"):
                output.write(f"{key}={result[key]}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
