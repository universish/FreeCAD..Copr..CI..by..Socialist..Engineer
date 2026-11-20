import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_asset


HASH_A = "a" * 64
HASH_B = "b" * 64


class FetchAssetTests(unittest.TestCase):
    def test_sidecar_selects_exact_filename(self):
        content = f"{HASH_A}  ignored.rpm\n{HASH_B} *FreeCAD_1.1.4-Linux-x86_64.rpm\n"
        self.assertEqual(fetch_asset.parse_sha256_sidecar(content, "FreeCAD_1.1.4-Linux-x86_64.rpm"), HASH_B)

    def test_single_hash_sidecar_is_supported(self):
        self.assertEqual(fetch_asset.parse_sha256_sidecar(HASH_A + "\n", "artifact.AppImage"), HASH_A)

    def test_ambiguous_checksum_is_rejected(self):
        content = f"{HASH_A}  artifact.rpm\n{HASH_B}  artifact.rpm\n"
        with self.assertRaises(ValueError):
            fetch_asset.parse_sha256_sidecar(content, "artifact.rpm")

    def test_unlabelled_multiple_hashes_are_rejected(self):
        with self.assertRaises(ValueError):
            fetch_asset.parse_sha256_sidecar(f"{HASH_A}\n{HASH_B}\n", "artifact.rpm")

    def test_untrusted_url_schemes_and_hosts_are_rejected(self):
        for url in ("http://github.com/file", "https://example.com/file"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                fetch_asset.validate_https_url(url)

    def test_github_release_url_is_accepted(self):
        fetch_asset.validate_https_url("https://github.com/FreeCAD/FreeCAD/releases/download/v1/file.rpm")


if __name__ == "__main__":
    unittest.main()
