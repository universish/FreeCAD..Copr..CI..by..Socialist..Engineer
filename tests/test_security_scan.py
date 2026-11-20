import platform
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import security_scan


class SecurityInspectionTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("readelf") or not shutil.which("true"):
            self.skipTest("readelf and a system ELF executable are required")
        machine = platform.machine().lower()
        self.arch = "aarch64" if machine in {"aarch64", "arm64"} else "x86_64"
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "payload"
        self.root.mkdir()
        shutil.copy2(shutil.which("true"), self.root / "FreeCAD")

    def tearDown(self):
        self.temp.cleanup()

    def test_hashes_elf_architecture_and_scripts_are_reported(self):
        (self.root / "AppRun").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        payload, findings = security_scan.inspect_payload(self.root, self.arch)
        self.assertEqual(findings, [])
        self.assertTrue(payload["elf_files"])
        self.assertTrue(payload["scripts"])
        self.assertTrue(all(len(item["sha256"]) == 64 for item in payload["files"]))

    def test_escaping_symlink_is_a_blocking_finding(self):
        (self.root / "escape").symlink_to("../../outside")
        _, findings = security_scan.inspect_payload(self.root, self.arch)
        self.assertTrue(any("symlink escapes" in item["reason"] for item in findings))

    def test_build_host_shebang_is_blocking(self):
        (self.root / "bad-script").write_text("#!/home/runner/old/python\n", encoding="utf-8")
        (self.root / "bad-script").chmod(0o755)
        _, findings = security_scan.inspect_payload(self.root, self.arch)
        self.assertTrue(any("build-host shebang" in item["reason"] for item in findings))


if __name__ == "__main__":
    unittest.main()
