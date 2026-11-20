import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from io import BytesIO
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import install_user


class UserInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def make_payload(self, package):
        payload = self.root / f"payload-{package}"
        payload.mkdir()
        apprun = payload / "AppRun"
        apprun.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        apprun.chmod(0o755)
        (payload / "freecad-icon.svg").write_text("<svg/>", encoding="utf-8")
        (payload / "payload-manifest.json").write_text(json.dumps({
            "package": package,
            "architecture": "x86_64",
            "source_sha256": "a" * 64,
        }), encoding="utf-8")
        return payload

    def test_stable_and_candidate_install_separately_and_uninstall_independently(self):
        stable = self.make_payload("freecad-non-native")
        candidate = self.make_payload("freecad-candidate-non-native")
        with patch.object(install_user.Path, "home", return_value=self.home):
            install_user.install("freecad-non-native", None, "x86_64", stable)
            install_user.install("freecad-candidate-non-native", None, "x86_64", candidate)

            stable_launcher = self.home / ".local/bin/freecad-non-native"
            candidate_launcher = self.home / ".local/bin/freecad-can-non-native"
            self.assertTrue(stable_launcher.is_file())
            self.assertTrue(candidate_launcher.is_file())
            self.assertIn("freecad-non-native", stable_launcher.read_text(encoding="utf-8"))
            self.assertIn("freecad-candidate-non-native", candidate_launcher.read_text(encoding="utf-8"))

            retained_data = self.home / ".config/freecad-candidate-non-native/user.cfg"
            retained_data.parent.mkdir(parents=True)
            retained_data.write_text("user settings", encoding="utf-8")
            install_user.uninstall("freecad-candidate-non-native")
            self.assertTrue(stable_launcher.is_file())
            self.assertFalse(candidate_launcher.exists())
            self.assertTrue((self.home / ".local/opt/freecad-non-native/AppRun").is_file())
            self.assertTrue(retained_data.is_file())

            install_user.uninstall("freecad-non-native")
            profile = self.home / ".profile"
            self.assertNotIn(install_user.PATH_START, profile.read_text(encoding="utf-8"))

    def test_payload_source_must_match_requested_package(self):
        payload = self.make_payload("freecad-candidate-non-native")
        with patch.object(install_user.Path, "home", return_value=self.home):
            with self.assertRaises(install_user.InstallError):
                install_user.install("freecad-non-native", None, "x86_64", payload)

    def test_tar_member_traversal_is_rejected(self):
        with self.assertRaises(install_user.InstallError):
            install_user.safe_member(self.root, "../../outside")

    def test_tar_member_cannot_traverse_existing_file_parent(self):
        parent = self.root / "usr"
        parent.write_text("not a directory", encoding="utf-8")
        with self.assertRaises(install_user.InstallError):
            install_user.safe_member(self.root, "usr/bin/freecad")

    def test_tar_duplicate_path_is_rejected(self):
        archive_path = self.root / "duplicate.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            for content in (b"first", b"second"):
                member = tarfile.TarInfo("AppRun")
                member.size = len(content)
                archive.addfile(member, BytesIO(content))
        destination = self.root / "extracted"
        destination.mkdir()
        with self.assertRaises(install_user.InstallError):
            install_user.extract_payload(archive_path, destination)

    def test_tar_file_cannot_replace_implicit_parent_directory(self):
        archive_path = self.root / "parent-conflict.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            child = tarfile.TarInfo("usr/bin/freecad")
            child.size = len(b"payload")
            archive.addfile(child, BytesIO(b"payload"))
            parent = tarfile.TarInfo("usr")
            parent.size = len(b"file")
            archive.addfile(parent, BytesIO(b"file"))
        destination = self.root / "extracted"
        destination.mkdir()
        with self.assertRaises(install_user.InstallError):
            install_user.extract_payload(archive_path, destination)


if __name__ == "__main__":
    unittest.main()
