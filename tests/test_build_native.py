import subprocess
import sys
import tempfile
import unittest
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_native_srpm


class NativeSourceBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "FreeCAD"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "ci@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "CI"], check=True)
        subprocess.run(["git", "-C", str(self.root), "remote", "add", "origin", "https://github.com/FreeCAD/FreeCAD.git"], check=True)
        (self.root / "CMakeLists.txt").write_text("project(FreeCAD)\n", encoding="utf-8")
        (self.root / "tracked.txt").write_text("source\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "CMakeLists.txt", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], check=True)
        subprocess.run(["git", "-C", str(self.root), "tag", "1.2.3"], check=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_version_release_validation(self):
        build_native_srpm.validate_version("26.3rc2", "1")
        for version, release in (("../bad", "1"), ("1.2", "0"), ("1.2", "1;touch/tmp/x")):
            with self.subTest(version=version, release=release), self.assertRaises(build_native_srpm.BuildError):
                build_native_srpm.validate_version(version, release)

    def test_native_spec_profiles_are_coinstallable_and_expand(self):
        expected = {
            "freecad": ("freecad", "org.freecad.FreeCAD.desktop"),
            "freecad-candidate": ("freecad-can", "org.freecad.FreeCAD.Candidate.desktop"),
        }
        with tempfile.TemporaryDirectory() as temporary:
            for package, (command, desktop_file) in expected.items():
                with self.subTest(package=package):
                    rendered = build_native_srpm.spec_for(package, "26.3rc2" if "candidate" in package else "1.1.4", "1")
                    path = Path(temporary) / f"{package}.spec"
                    path.write_text(rendered, encoding="utf-8")
                    expanded = subprocess.run(["rpmspec", "-P", str(path)], capture_output=True, text=True, check=False)
                    self.assertEqual(expanded.returncode, 0, expanded.stderr)
                    self.assertRegex(expanded.stdout, rf"(?m)^Name:\s+{re.escape(package)}$")
                    self.assertIn(f"/usr/bin/{command}", expanded.stdout)
                    self.assertIn(desktop_file, expanded.stdout)
                    self.assertIn(f"XDG_CONFIG_HOME=\"\\${{XDG_CONFIG_HOME:-\\$HOME/.config}}/{package}\"", expanded.stdout)

    def test_weekly_versions_are_rejected_before_source_generation(self):
        with self.assertRaises(build_native_srpm.BuildError):
            build_native_srpm.validate_version("weekly-2026.11.18", "1")

    def test_exact_clean_upstream_tag_is_required(self):
        build_native_srpm.validate_checkout(self.root, "1.2.3")
        build_native_srpm.validate_checkout(self.root, "1.2.3", "freecad-candidate", prerelease=True)
        with self.assertRaises(build_native_srpm.BuildError):
            build_native_srpm.validate_checkout(self.root, "1.2.4")
        with self.assertRaises(build_native_srpm.BuildError):
            build_native_srpm.validate_checkout(self.root, "1.2.3", "freecad-candidate")

    def test_native_profile_rejects_undefined_upstream_cmake_options(self):
        helper = self.root / "cMake/FreeCAD_Helpers/InitializeFreeCADBuildOptions.cmake"
        helper.parent.mkdir(parents=True)
        helper.write_text('option(FREECAD_USE_EXTERNAL_JSON "system json" OFF)\n', encoding="utf-8")
        spec = "  -DFREECAD_USE_EXTERNAL_JSON=ON\n  -DFREECAD_USE_EXTERNAL_FMT=ON\n  -DCMAKE_INSTALL_PREFIX=/usr\n"
        with self.assertRaisesRegex(build_native_srpm.BuildError, "FREECAD_USE_EXTERNAL_FMT"):
            build_native_srpm.validate_native_profile(self.root, spec)

    def test_native_profile_accepts_declared_upstream_cmake_options(self):
        helper = self.root / "cMake/FreeCAD_Helpers/InitializeFreeCADBuildOptions.cmake"
        helper.parent.mkdir(parents=True)
        helper.write_text('option(FREECAD_USE_EXTERNAL_JSON "system json" OFF)\n', encoding="utf-8")
        build_native_srpm.validate_native_profile(
            self.root,
            "  -DFREECAD_USE_EXTERNAL_JSON=ON\n  -DCMAKE_INSTALL_PREFIX=/usr\n",
        )

    def test_local_changes_are_rejected(self):
        (self.root / "tracked.txt").write_text("modified\n", encoding="utf-8")
        with self.assertRaises(build_native_srpm.BuildError):
            build_native_srpm.validate_checkout(self.root, "1.2.3")

    def test_source_tar_contains_tracked_files_and_is_valid(self):
        archive = Path(self.temp.name) / "source.tar.gz"
        build_native_srpm.make_source_archive(self.root, archive)
        listing = subprocess.run(["tar", "-tzf", str(archive)], check=True, capture_output=True, text=True).stdout.splitlines()
        self.assertIn("CMakeLists.txt", listing)
        self.assertIn("tracked.txt", listing)


if __name__ == "__main__":
    unittest.main()
