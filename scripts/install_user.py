#!/usr/bin/env python3
"""Install a verified normalized FreeCAD payload under the current user's home."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "config" / "release-policy.json").read_text(encoding="utf-8"))
PATH_START = "# >>> FreeCAD local PATH >>>"
PATH_END = "# <<< FreeCAD local PATH <<<"


class InstallError(RuntimeError):
    pass


def package_profile(package: str) -> tuple[str, dict[str, Any]]:
    for channel, profile in POLICY["packages"].items():
        if profile["non_native"] == package:
            return channel, profile
    raise InstallError(f"unsupported non-native package: {package}")


def safe_member(root: Path, name: str) -> Path:
    if name.startswith("/") or "\\" in name or "\x00" in name:
        raise InstallError(f"unsafe archive path: {name!r}")
    parts = [part for part in name.split("/") if part not in {"", "."}]
    if any(part == ".." for part in parts):
        raise InstallError(f"archive path escapes extraction root: {name!r}")
    destination = root.joinpath(*parts)
    parent = destination.parent
    if not parent.resolve().is_relative_to(root.resolve()):
        raise InstallError(f"archive path escapes extraction root: {name!r}")
    current = root
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise InstallError(f"archive path traverses symlink: {name!r}")
        if current.exists() and not current.is_dir():
            raise InstallError(f"archive path traverses a non-directory entry: {name!r}")
    return destination


def extract_payload(archive_path: Path, destination: Path) -> None:
    links: list[tuple[Path, str, bool]] = []
    seen_entries: dict[Path, str] = {}

    def register_entry(path: Path, kind: str, name: str) -> None:
        previous = seen_entries.get(path)
        if previous is not None:
            if kind == previous == "directory":
                return
            raise InstallError(f"duplicate archive path: {name}")
        relative = path.relative_to(destination)
        for parent in relative.parents:
            if parent == Path("."):
                continue
            parent_kind = seen_entries.get(destination / parent)
            if parent_kind is not None and parent_kind != "directory":
                raise InstallError(f"archive path traverses a non-directory entry: {name}")
        if kind != "directory":
            for previous_path, previous_kind in seen_entries.items():
                if path in previous_path.parents:
                    raise InstallError(f"archive entry conflicts with a parent path: {name}")
        seen_entries[path] = kind

    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in archive:
            target = safe_member(destination, member.name)
            if target == destination:
                continue
            if member.isdir():
                register_entry(target, "directory", member.name)
                target.mkdir(parents=True, exist_ok=True)
                target.chmod(0o755)
            elif member.isreg():
                register_entry(target, "regular", member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise InstallError(f"archive file data is missing: {member.name}")
                with source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
            elif member.issym():
                register_entry(target, "symlink", member.name)
                links.append((target, member.linkname, False))
            elif member.islnk():
                register_entry(target, "hardlink", member.name)
                links.append((target, member.linkname, True))
            else:
                raise InstallError(f"unsupported archive entry: {member.name}")
    for path, link_target, is_hardlink in links:
        if is_hardlink:
            target = safe_member(destination, link_target)
            if target.is_symlink() or not target.is_file():
                raise InstallError(f"invalid hardlink target: {link_target}")
            path.parent.mkdir(parents=True, exist_ok=True)
            os.link(target, path)
            continue
        if link_target.startswith("/") or "\\" in link_target:
            raise InstallError(f"absolute symlink target: {path.relative_to(destination)}")
        resolved = (path.parent / link_target).resolve(strict=False)
        if not resolved.is_relative_to(destination.resolve()):
            raise InstallError(f"symlink escapes payload root: {path.relative_to(destination)} -> {link_target}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(link_target)


def verify_payload(root: Path, package: str, architecture: str) -> dict[str, Any]:
    manifest = json.loads((root / "payload-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("package") != package or manifest.get("architecture") != architecture:
        raise InstallError("payload manifest package or architecture does not match this installation")
    digest = str(manifest.get("source_sha256", ""))
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise InstallError("payload manifest is missing its verified upstream SHA256")
    apprun = root / "AppRun"
    icon = root / "freecad-icon.svg"
    if not apprun.is_file() or not apprun.stat().st_mode & 0o111:
        raise InstallError("normalized payload has no executable AppRun")
    if not icon.is_file():
        raise InstallError("normalized payload has no FreeCAD SVG icon")
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            target = (path.parent / os.readlink(path)).resolve(strict=False)
            if not target.is_relative_to(root.resolve()):
                raise InstallError(f"payload symlink escapes installation root: {path.relative_to(root)}")
        elif not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise InstallError(f"payload contains a special file: {path.relative_to(root)}")
    return manifest


def desktop_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def ensure_local_bin_path(home: Path) -> None:
    profile = home / ".profile"
    current = profile.read_text(encoding="utf-8") if profile.exists() else ""
    if PATH_START in current:
        return
    block = (
        f"\n{PATH_START}\n"
        'case ":$PATH:" in *:"$HOME/.local/bin":*) ;; *) PATH="$HOME/.local/bin:$PATH" ;; esac\n'
        "export PATH\n"
        f"{PATH_END}\n"
    )
    profile.write_text(current.rstrip("\n") + block, encoding="utf-8")


def remove_local_bin_path_if_unused(home: Path) -> None:
    bin_dir = home / ".local" / "bin"
    retained = [
        profile["non_native_command"]
        for profile in POLICY["packages"].values()
    ] + ["freecad", "freecad-can"]
    if any((bin_dir / command).exists() for command in retained):
        return
    profile = home / ".profile"
    if not profile.exists():
        return
    lines = profile.read_text(encoding="utf-8").splitlines(keepends=True)
    output = []
    skipping = False
    for line in lines:
        if line.rstrip("\n") == PATH_START:
            skipping = True
            continue
        if skipping:
            if line.rstrip("\n") == PATH_END:
                skipping = False
            continue
        output.append(line)
    profile.write_text("".join(output), encoding="utf-8")


def install(package: str, archive_path: Path | None, architecture: str, payload_dir: Path | None = None) -> None:
    _channel, profile = package_profile(package)
    if architecture not in POLICY["architectures"]:
        raise InstallError(f"unsupported architecture: {architecture}")
    home = Path.home()
    opt_root = home / ".local" / "opt"
    target = opt_root / package
    opt_root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{package}-", dir=opt_root))
    backup = opt_root / f".{package}-previous"
    try:
        if (archive_path is None) == (payload_dir is None):
            raise InstallError("provide exactly one normalized payload directory or tar.gz archive")
        if payload_dir is not None:
            payload_source = payload_dir.resolve(strict=True)
            if not payload_source.is_dir():
                raise InstallError("normalized payload path is not a directory")
            verify_payload(payload_source, package, architecture)
            shutil.copytree(payload_source, stage, symlinks=True, dirs_exist_ok=True)
        else:
            assert archive_path is not None
            extract_payload(archive_path.resolve(strict=True), stage)
        verify_payload(stage, package, architecture)
        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            os.replace(target, backup)
        try:
            os.replace(stage, target)
        except Exception:
            if backup.exists() and not target.exists():
                os.replace(backup, target)
            raise
        if backup.exists():
            shutil.rmtree(backup)

        bin_dir = home / ".local" / "bin"
        apps_dir = home / ".local" / "share" / "applications"
        icons_dir = home / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps"
        for directory in (bin_dir, apps_dir, icons_dir):
            directory.mkdir(parents=True, exist_ok=True)
        ensure_local_bin_path(home)
        command = profile["non_native_command"]
        icon_name = package
        launcher = bin_dir / command
        appdir = str(target)
        launcher.write_text(
            "#!/bin/sh\n"
            f"APPDIR={shlex_quote(appdir)}\n"
            f"export XDG_CONFIG_HOME=\"${{XDG_CONFIG_HOME:-$HOME/.config}}/{package}\"\n"
            f"export XDG_DATA_HOME=\"${{XDG_DATA_HOME:-$HOME/.local/share}}/{package}\"\n"
            'export FREECAD_USER_HOME="$XDG_DATA_HOME"\n'
            'mkdir -p "$FREECAD_USER_HOME"\n'
            "exec \"$APPDIR/AppRun\" \"$@\"\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        icon_path = icons_dir / f"{icon_name}.svg"
        shutil.copy2(target / "freecad-icon.svg", icon_path)
        desktop_id = profile["non_native_desktop_id"]
        desktop = apps_dir / f"{desktop_id}.desktop"
        executable = desktop_escape(str(launcher))
        desktop.write_text(
            "[Desktop Entry]\n"
            f"Name={profile['non_native_display_name']}\n"
            "Comment=FreeCAD with the upstream bundled runtime\n"
            "GenericName=CAD Application\n"
            f'Exec="{executable}" %F\n'
            f'TryExec="{executable}"\n'
            "Terminal=false\nType=Application\n"
            f"Icon={icon_name}\n"
            "Categories=Graphics;Science;Education;Engineering;\n"
            "StartupNotify=true\nMimeType=application/x-extension-fcstd;model/step;model/stl;\n",
            encoding="utf-8",
        )
        print(f"Installed {package} ({architecture}) under {target}")
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def shlex_quote(value: str) -> str:
    import shlex
    return shlex.quote(value)


def uninstall(package: str, purge_data: bool = False) -> None:
    _channel, profile = package_profile(package)
    home = Path.home()
    paths = [
        home / ".local" / "opt" / package,
        home / ".local" / "bin" / profile["non_native_command"],
        home / ".local" / "share" / "applications" / f"{profile['non_native_desktop_id']}.desktop",
        home / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps" / f"{package}.svg",
    ]
    if purge_data:
        paths.extend((home / ".config" / package, home / ".local" / "share" / package))
    for path in paths:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    remove_local_bin_path_if_unused(home)
    print(f"Removed user installation {package}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--package", required=True)
    parser.add_argument("--archive", type=Path, default=Path(os.getenv("PAYLOAD_ARCHIVE", "")) if os.getenv("PAYLOAD_ARCHIVE") else None)
    parser.add_argument("--payload-dir", type=Path, default=Path(os.getenv("PAYLOAD_DIR", "")) if os.getenv("PAYLOAD_DIR") else None)
    parser.add_argument("--architecture", default=os.getenv("ARCH", ""))
    parser.add_argument("--purge-data", action="store_true", help="also remove this package's user settings and data")
    args = parser.parse_args()
    try:
        if args.action == "install":
            architecture = args.architecture or {"x86_64": "x86_64", "aarch64": "aarch64"}.get(os.uname().machine, "")
            install(args.package, args.archive, architecture, args.payload_dir)
        else:
            uninstall(args.package, purge_data=args.purge_data)
    except (OSError, ValueError, KeyError, tarfile.TarError, InstallError) as exc:
        print(f"user installation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
