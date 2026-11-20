#!/usr/bin/env python3
"""Safely extract and normalize a verified RPM, DEB, or AppImage payload."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


class PayloadError(RuntimeError):
    pass


def safe_parts(name: str) -> tuple[str, ...]:
    if name.startswith("/") or "\\" in name or "\x00" in name:
        raise PayloadError(f"unsafe archive path: {name!r}")
    parts = tuple(part for part in name.split("/") if part not in {"", "."})
    if any(part == ".." for part in parts):
        raise PayloadError(f"archive path escapes its root: {name!r}")
    return parts


def safe_destination(root: Path, name: str) -> Path:
    parts = safe_parts(name)
    destination = root.joinpath(*parts)
    parent = destination.parent
    if not parent.resolve().is_relative_to(root.resolve()):
        raise PayloadError(f"archive path escapes extraction root: {name!r}")
    current = root
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise PayloadError(f"archive path traverses an earlier symlink: {name!r}")
        if current.exists() and not current.is_dir():
            raise PayloadError(f"archive path traverses a non-directory entry: {name!r}")
    return destination


def extract_tar_stream(stream: io.BufferedIOBase, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    links: list[tuple[Path, str, bool]] = []
    with tarfile.open(fileobj=stream, mode="r|*") as archive:
        for member in archive:
            path = safe_destination(destination, member.name)
            if path == destination:
                continue
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
                path.chmod(0o755)
            elif member.isreg():
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists() or path.is_symlink():
                    raise PayloadError(f"duplicate archive path: {member.name}")
                source = archive.extractfile(member)
                if source is None:
                    raise PayloadError(f"missing file data for {member.name}")
                with source, path.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                path.chmod(0o755 if member.mode & 0o111 else 0o644)
            elif member.issym():
                links.append((path, member.linkname, False))
            elif member.islnk():
                links.append((path, member.linkname, True))
            else:
                raise PayloadError(f"unsupported special tar entry: {member.name}")
    for path, target, hardlink in links:
        if hardlink:
            target_path = safe_destination(destination, target)
            if target_path.is_symlink() or not target_path.is_file():
                raise PayloadError(f"invalid hardlink target: {target!r}")
        else:
            if target.startswith("/") or "\\" in target:
                raise PayloadError(f"absolute symlink target: {path.relative_to(destination)} -> {target}")
            resolved = (path.parent / target).resolve(strict=False)
            if not resolved.is_relative_to(destination.resolve()):
                raise PayloadError(f"symlink escapes extraction root: {path.relative_to(destination)} -> {target}")
            target_path = None
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() or path.is_symlink():
            raise PayloadError(f"duplicate archive link: {path.relative_to(destination)}")
        if hardlink:
            os.link(target_path, path)
        else:
            path.symlink_to(target)


def extract_newc(stream: io.BufferedReader, destination: Path) -> None:
    """Extract cpio newc with path checks; file ownership and special files are ignored."""
    destination.mkdir(parents=True, exist_ok=True)
    links: list[tuple[Path, str]] = []
    inode_paths: dict[tuple[int, int, int], Path] = {}
    pending_hardlinks: dict[tuple[int, int, int], list[Path]] = {}
    hardlink_expected: dict[tuple[int, int, int], int] = {}
    hardlink_entry_counts: dict[tuple[int, int, int], int] = {}
    seen_entries: dict[Path, str] = {}
    offset = 0

    def register_entry(path: Path, kind: str, name: str) -> None:
        if path in seen_entries:
            raise PayloadError(f"duplicate RPM payload path: {name}")
        relative = path.relative_to(destination)
        for parent in relative.parents:
            if parent == Path("."):
                continue
            parent_path = destination / parent
            parent_kind = seen_entries.get(parent_path)
            if parent_kind is not None and parent_kind != "directory":
                raise PayloadError(f"RPM payload path traverses a non-directory entry: {name}")
        if kind != "directory":
            for previous_path, previous_kind in seen_entries.items():
                if previous_kind == "directory":
                    continue
                if previous_path in path.parents:
                    raise PayloadError(f"RPM payload entry conflicts with a parent path: {name}")
        seen_entries[path] = kind

    def read_exact(size: int) -> bytes:
        nonlocal offset
        data = stream.read(size)
        if len(data) != size:
            raise PayloadError("truncated RPM cpio payload")
        offset += size
        return data

    def align4() -> None:
        nonlocal offset
        padding = (-offset) % 4
        if padding:
            read_exact(padding)

    while True:
        header = read_exact(110)
        magic = header[:6]
        if magic not in {b"070701", b"070702"}:
            raise PayloadError("RPM payload is not a supported newc cpio archive")
        fields = [int(header[6 + i * 8 : 14 + i * 8], 16) for i in range(13)]
        ino, mode, _uid, _gid, nlink, _mtime, filesize, devmajor, devminor = fields[:9]
        namesize = fields[11]
        if namesize < 1 or namesize > 4096 or filesize > (1 << 40):
            raise PayloadError("invalid RPM cpio entry size")
        raw_name = read_exact(namesize)
        align4()
        if not raw_name.endswith(b"\0") or b"\0" in raw_name[:-1]:
            raise PayloadError("invalid RPM cpio pathname")
        name = raw_name[:-1].decode("utf-8", errors="surrogateescape")
        if name == "TRAILER!!!":
            break
        path = safe_destination(destination, name)
        file_type = stat.S_IFMT(mode)
        if path != destination:
            kind = "directory" if file_type == stat.S_IFDIR else "symlink" if file_type == stat.S_IFLNK else "regular" if file_type == stat.S_IFREG else "special"
            register_entry(path, kind, name)
        inode_key = (devmajor, devminor, ino)
        if path == destination and file_type == stat.S_IFDIR:
            if filesize:
                raise PayloadError("directory entry contains file data")
        elif file_type == stat.S_IFDIR:
            if filesize:
                raise PayloadError(f"directory entry contains data: {name}")
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(0o755)
        elif file_type == stat.S_IFREG:
            path.parent.mkdir(parents=True, exist_ok=True)
            if nlink < 1:
                raise PayloadError(f"invalid RPM hardlink count: {name}")
            if nlink > 1:
                expected = hardlink_expected.setdefault(inode_key, nlink)
                if expected != nlink:
                    raise PayloadError(f"inconsistent RPM hardlink count: {name}")
                hardlink_entry_counts[inode_key] = hardlink_entry_counts.get(inode_key, 0) + 1
            if filesize == 0 and nlink > 1 and inode_key in inode_paths:
                if path.exists() or path.is_symlink():
                    raise PayloadError(f"duplicate RPM payload path: {name}")
                os.link(inode_paths[inode_key], path)
            elif filesize == 0 and nlink > 1 and inode_key not in inode_paths:
                if path.exists() or path.is_symlink() or path in pending_hardlinks.get(inode_key, []):
                    raise PayloadError(f"duplicate RPM payload path: {name}")
                pending_hardlinks.setdefault(inode_key, []).append(path)
            else:
                if nlink > 1 and inode_key in inode_paths:
                    raise PayloadError(f"RPM hardlink group contains multiple data entries: {name}")
                if path.exists() or path.is_symlink():
                    raise PayloadError(f"duplicate RPM payload path: {name}")
                with path.open("xb") as output:
                    remaining = filesize
                    while remaining:
                        chunk = read_exact(min(1024 * 1024, remaining))
                        output.write(chunk)
                        remaining -= len(chunk)
                path.chmod(0o755 if mode & 0o111 else 0o644)
                if nlink > 1:
                    inode_paths[inode_key] = path
                    for pending in pending_hardlinks.pop(inode_key, []):
                        pending.parent.mkdir(parents=True, exist_ok=True)
                        os.link(path, pending)
        elif file_type == stat.S_IFLNK:
            target = read_exact(filesize).decode("utf-8", errors="surrogateescape")
            links.append((path, target))
        else:
            raise PayloadError(f"unsupported special RPM payload entry: {name}")
        if file_type != stat.S_IFREG and file_type != stat.S_IFLNK:
            if filesize:
                read_exact(filesize)
        align4()

    for inode_key, expected in hardlink_expected.items():
        if hardlink_entry_counts[inode_key] != expected:
            raise PayloadError(f"incomplete RPM hardlink group: expected {expected}, saw {hardlink_entry_counts[inode_key]}")
        if inode_key in inode_paths:
            continue
        paths = pending_hardlinks.get(inode_key, [])
        if len(paths) != expected:
            raise PayloadError(f"RPM hardlink group has no data entry and an incomplete member list: {inode_key}")
        first, *rest = paths
        first.parent.mkdir(parents=True, exist_ok=True)
        first.touch(mode=0o644, exist_ok=False)
        for path in rest:
            path.parent.mkdir(parents=True, exist_ok=True)
            os.link(first, path)
    for path, target in links:
        if target.startswith("/") or "\\" in target:
            raise PayloadError(f"absolute RPM symlink target: {path.relative_to(destination)} -> {target}")
        if not (path.parent / target).resolve(strict=False).is_relative_to(destination.resolve()):
            raise PayloadError(f"RPM symlink escapes extraction root: {path.relative_to(destination)} -> {target}")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() or path.is_symlink():
            raise PayloadError(f"duplicate RPM symlink path: {path.relative_to(destination)}")
        path.symlink_to(target)


def extract_deb(source: Path, destination: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="freecad-deb-") as temporary:
        members_dir = Path(temporary)
        data_member: tuple[str, Path] | None = None
        control_member: tuple[str, Path] | None = None
        with source.open("rb") as archive:
            if archive.read(8) != b"!<arch>\n":
                raise PayloadError("invalid DEB ar header")
            while header := archive.read(60):
                if len(header) != 60 or header[58:60] != b"`\n":
                    raise PayloadError("invalid DEB archive member header")
                name = header[:16].decode("ascii", errors="replace").strip().rstrip("/")
                try:
                    size = int(header[48:58].decode("ascii").strip())
                except ValueError as exc:
                    raise PayloadError("invalid DEB archive member size") from exc
                if size < 0 or size > source.stat().st_size:
                    raise PayloadError("invalid DEB archive member size")
                selected = name.startswith("data.tar") or name.startswith("control.tar")
                member_path = members_dir / name if selected else None
                if member_path is not None:
                    if member_path.exists():
                        raise PayloadError(f"duplicate DEB archive member: {name}")
                    remaining = size
                    with member_path.open("wb") as member_file:
                        while remaining:
                            chunk = archive.read(min(1024 * 1024, remaining))
                            if not chunk:
                                raise PayloadError("truncated DEB archive member")
                            member_file.write(chunk)
                            remaining -= len(chunk)
                else:
                    archive.seek(size, os.SEEK_CUR)
                    if archive.tell() > source.stat().st_size:
                        raise PayloadError("truncated DEB archive member")
                if selected and member_path is not None:
                    if name.startswith("data.tar"):
                        data_member = (name, member_path)
                    else:
                        control_member = (name, member_path)
                if size % 2:
                    if len(archive.read(1)) != 1:
                        raise PayloadError("truncated DEB archive padding")
        if data_member is None:
            raise PayloadError("DEB contains no data.tar payload")
        if control_member is None:
            raise PayloadError("DEB contains no control.tar metadata archive")

        def unpack_ar_tar(name: str, path: Path, target: Path) -> None:
            try:
                if name.endswith(".zst"):
                    with tempfile.TemporaryFile() as decompressed:
                        result = subprocess.run(["zstd", "-d", "-q", "-c", str(path)], stdout=decompressed, stderr=subprocess.PIPE, check=False)
                        if result.returncode:
                            raise PayloadError(f"unable to decompress DEB {name}: {result.stderr.decode(errors='replace')}")
                        decompressed.seek(0)
                        extract_tar_stream(decompressed, target)
                else:
                    with path.open("rb") as stream:
                        extract_tar_stream(stream, target)
            except tarfile.TarError as exc:
                raise PayloadError(f"invalid DEB {name} archive: {exc}") from exc

        unpack_ar_tar(*data_member, destination)
        control_root = destination / "metadata" / "upstream-deb-control"
        unpack_ar_tar(*control_member, control_root)
        control_file = control_root / "control"
        if not control_file.is_file():
            raise PayloadError("DEB control archive has no control metadata file")
        control_text = control_file.read_text(encoding="utf-8", errors="replace")
        scripts = [path.name for path in sorted(control_root.iterdir()) if path.is_file() and path.name in {"preinst", "postinst", "prerm", "postrm", "config", "triggers"}]
        (destination / "metadata" / "upstream-deb-metadata.json").write_text(
            json.dumps({"control_archive": control_member[0], "data_archive": data_member[0], "control": control_text, "maintainer_scripts": scripts}, indent=2) + "\n",
            encoding="utf-8",
        )


def inspect_upstream_rpm(source: Path, destination: Path) -> None:
    details = {}
    for name, options in (("info", ["--info"]), ("scripts", ["--scripts"]), ("requirements", ["--requires"])):
        result = subprocess.run(["rpm", "-qp", *options, str(source)], capture_output=True, text=True, check=False)
        if result.returncode:
            raise PayloadError(f"unable to inspect upstream RPM {name}: {result.stderr.strip()}")
        details[name] = result.stdout
    metadata = destination / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "upstream-rpm-metadata.json").write_text(json.dumps(details, indent=2) + "\n", encoding="utf-8")


def inspect_appimage(source: Path, destination: Path) -> None:
    result = subprocess.run(["file", "--brief", str(source)], capture_output=True, text=True, check=False)
    if result.returncode:
        raise PayloadError(f"unable to inspect AppImage file type: {result.stderr.strip()}")
    metadata = destination / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as stream:
        magic = stream.read(16)
    (metadata / "upstream-appimage-metadata.json").write_text(
        json.dumps({"file_type": result.stdout.strip(), "magic_hex": magic.hex()}, indent=2) + "\n",
        encoding="utf-8",
    )


def verify_tree(root: Path) -> None:
    resolved_root = root.resolve()
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            target = (path.parent / os.readlink(path)).resolve(strict=False)
            if not target.is_relative_to(resolved_root):
                raise PayloadError(f"symlink escapes payload root: {path.relative_to(root)}")
        elif not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise PayloadError(f"unexpected special file in payload: {path.relative_to(root)}")


def sanitize_modes(root: Path) -> None:
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            path.chmod(0o755)
        elif stat.S_ISREG(mode):
            path.chmod(0o755 if mode & 0o111 else 0o644)


def find_file(root: Path, pattern: str, executable: bool = False) -> Path | None:
    matches = []
    for path in root.rglob("*"):
        if path.is_file() and re.fullmatch(pattern, path.name, flags=re.IGNORECASE):
            if not executable or os.access(path, os.X_OK):
                matches.append(path)
    return sorted(matches, key=lambda item: (len(item.parts), str(item).casefold()))[0] if matches else None


def verify_elf_architecture(binary: Path, architecture: str) -> None:
    result = subprocess.run(["readelf", "-h", str(binary)], text=True, capture_output=True, check=False)
    if result.returncode:
        raise PayloadError(f"unable to inspect FreeCAD executable: {binary}")
    machine = next((line.partition(":")[2].strip() for line in result.stdout.splitlines() if "Machine:" in line), "")
    wanted = "X86-64" if architecture == "x86_64" else "AArch64"
    if machine != wanted:
        raise PayloadError(f"expected {architecture} payload but FreeCAD executable is {machine or 'unknown'}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", required=True, type=Path)
    parser.add_argument("--package", required=True, choices=("freecad-non-native", "freecad-candidate-non-native"))
    parser.add_argument("--architecture", required=True, choices=("x86_64", "aarch64"))
    parser.add_argument("--output-root", type=Path, default=Path("payload"))
    args = parser.parse_args()
    try:
        asset = json.loads(args.asset_manifest.read_text(encoding="utf-8"))
        if asset["architecture"] != args.architecture:
            raise PayloadError("verified artifact architecture does not match requested architecture")
        source = Path(asset["path"]).resolve(strict=True)
        source_hash = hashlib.sha256()
        with source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                source_hash.update(chunk)
        if source_hash.hexdigest() != asset["sha256"]:
            raise PayloadError("verified source artifact changed after checksum verification")
        output_candidate = args.output_root / args.package / args.architecture
        if output_candidate.is_symlink():
            raise PayloadError("payload output path must not be a symlink")
        output = output_candidate.resolve()
        if not output.is_relative_to(args.output_root.resolve()):
            raise PayloadError("payload output path escapes the configured output root")
        if output.exists():
            shutil.rmtree(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="freecad-extract-") as temporary:
            temp_root = Path(temporary)
            extracted = temp_root / "extracted"
            extracted.mkdir()
            fmt = asset["format"]
            if fmt == "AppImage":
                inspect_appimage(source, temp_root)
                extracted.rmdir()
                result = subprocess.run(["unsquashfs", "-no-progress", "-d", str(extracted), str(source)], capture_output=True, text=True, check=False)
                if result.returncode:
                    raise PayloadError(f"unsquashfs failed: {result.stderr.strip()}")
            elif fmt == "deb":
                extract_deb(source, extracted)
            elif fmt == "rpm":
                inspect_upstream_rpm(source, extracted)
                proc = subprocess.Popen(["rpm2cpio", str(source)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                assert proc.stdout is not None
                try:
                    extract_newc(proc.stdout, extracted)
                finally:
                    proc.stdout.close()
                stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
                if proc.wait() != 0:
                    raise PayloadError(f"rpm2cpio failed: {stderr.strip()}")
            else:
                raise PayloadError(f"unsupported artifact format: {fmt}")
            verify_tree(extracted)
            sanitize_modes(extracted)

            upstream_apprun = find_file(extracted, r"AppRun", executable=True)
            if upstream_apprun:
                payload_source = upstream_apprun.parent
                shutil.copytree(payload_source, output, symlinks=True, dirs_exist_ok=True)
            else:
                shutil.copytree(extracted, output, symlinks=True, dirs_exist_ok=True)
                binary = find_file(output, r"FreeCAD", executable=True) or find_file(output, r"freecad", executable=True)
                if binary is None:
                    raise PayloadError("no executable AppRun or FreeCAD binary was found")
                verify_elf_architecture(binary, args.architecture)
                relative = binary.relative_to(output).as_posix()
                wrapper = """#!/bin/sh
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PRIVATE_LIB_DIRS=""
for path in "$HERE"/usr/lib "$HERE"/usr/lib64 "$HERE"/lib "$HERE"/lib64 "$HERE"/opt/*/usr/lib "$HERE"/opt/*/usr/lib64; do
    [ -d "$path" ] && PRIVATE_LIB_DIRS="${PRIVATE_LIB_DIRS:+$PRIVATE_LIB_DIRS:}$path"
done
export LD_LIBRARY_PATH="${PRIVATE_LIB_DIRS}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export QT_PLUGIN_PATH="$HERE/usr/lib/qt6/plugins:$HERE/usr/lib64/qt6/plugins${QT_PLUGIN_PATH:+:$QT_PLUGIN_PATH}"
exec "$HERE"/""" + shlex.quote(relative) + " \"$@\"\n"
                (output / "AppRun").write_text(wrapper, encoding="utf-8")
                (output / "AppRun").chmod(0o755)
            for metadata_root in (extracted / "metadata", temp_root / "metadata"):
                if metadata_root.is_dir():
                    shutil.copytree(metadata_root, output / "metadata", symlinks=True, dirs_exist_ok=True)
            icon = find_file(output, r"org\.freecad\.FreeCAD\.svg") or find_file(output, r".*freecad.*\.svg")
            if icon is None:
                raise PayloadError("no FreeCAD SVG icon was found")
            shutil.copy2(icon, output / "freecad-icon.svg")
            (output / "AppRun").chmod(0o755)
            verify_tree(output)
        manifest = {
            "schema_version": 1,
            "package": args.package,
            "architecture": args.architecture,
            "source_filename": asset["filename"],
            "source_sha256": asset["sha256"],
            "format": asset["format"],
            "payload": str(output),
        }
        (output / "payload-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(manifest, sort_keys=True))
    except (OSError, KeyError, ValueError, PayloadError, json.JSONDecodeError) as exc:
        print(f"payload normalization failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
