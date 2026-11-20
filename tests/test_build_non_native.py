import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_non_native_srpm
import install_user


class NonNativeBuildTests(unittest.TestCase):
    def test_spec_profiles_are_independent_and_expand(self):
        profiles = {
            "freecad-non-native": ("freecad-non-native", "org.freecad.FreeCAD.NonNative", "1.1.4"),
            "freecad-candidate-non-native": ("freecad-can-non-native", "org.freecad.FreeCAD.Candidate.NonNative", "26.3rc2"),
        }
        with tempfile.TemporaryDirectory() as temporary:
            for package, (command, desktop_id, version) in profiles.items():
                with self.subTest(package=package):
                    spec = build_non_native_srpm.spec_for(package, version, "1")
                    self.assertIn(f"Name:           {package}", spec)
                    self.assertIn(f"Exec={command} %F", spec)
                    self.assertIn(f"<id>{desktop_id}</id>", spec)
                    self.assertIn("<project_license>LGPL-2.1-or-later AND Zlib", spec)
                    path = Path(temporary) / f"{package}.spec"
                    path.write_text(spec, encoding="utf-8")
                    expanded = subprocess.run(["rpmspec", "-P", str(path)], capture_output=True, text=True, check=False)
                    self.assertEqual(expanded.returncode, 0, expanded.stderr)

    def test_only_configured_non_native_packages_are_allowed(self):
        with self.assertRaises(build_non_native_srpm.BuildError):
            build_non_native_srpm.spec_for("freecad", "1.1.4", "1")

    def test_weekly_and_wrong_channel_versions_are_rejected(self):
        for package, version in (("freecad-non-native", "weekly-2026.11.18"), ("freecad-non-native", "26.3rc2")):
            with self.subTest(package=package, version=version), self.assertRaises(build_non_native_srpm.BuildError):
                build_non_native_srpm.spec_for(package, version, "1")

    def test_payload_identity_and_hash_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload = Path(temporary)
            apprun = payload / "AppRun"
            apprun.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            apprun.chmod(0o755)
            (payload / "freecad-icon.svg").write_text("<svg/>\n", encoding="utf-8")
            manifest = {
                "package": "freecad-non-native",
                "architecture": "x86_64",
                "source_sha256": "a" * 64,
            }
            (payload / "payload-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            build_non_native_srpm.verify_payload(payload, "freecad-non-native", "x86_64")
            with self.assertRaises(build_non_native_srpm.BuildError):
                build_non_native_srpm.verify_payload(payload, "freecad-non-native", "aarch64")

    def test_user_path_integration_is_idempotent_and_removable(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            install_user.ensure_local_bin_path(home)
            install_user.ensure_local_bin_path(home)
            profile = home / ".profile"
            self.assertEqual(profile.read_text().count(install_user.PATH_START), 1)
            install_user.remove_local_bin_path_if_unused(home)
            self.assertNotIn(install_user.PATH_START, profile.read_text())


if __name__ == "__main__":
    unittest.main()
