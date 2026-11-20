import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import update_state


class UpdateStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.results = self.root / "build-results"
        self.metadata = self.root / "build-metadata"
        self.reports = self.root / "security-reports"
        self.payloads = self.root / "payloads"
        self.state = self.root / "state"
        self.chroots = self.root / "chroots.txt"
        self.chroots.write_text("fedora-44-x86_64\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def native_inputs(self, status="succeeded"):
        manifest = {
            "schema_version": 1,
            "channels": {
                "stable": {
                    "version": "1.1.4",
                    "tag": "1.1.4",
                    "native": {
                        "changed": True,
                        "package": "freecad",
                        "release": 1,
                        "packaging_fingerprint": "abc123",
                    },
                    "non_native": {"changed": False, "package": "freecad-non-native"},
                }
            },
        }
        self.write_json(self.root / "manifest.json", manifest)
        self.write_json(self.results / "copr-result-freecad" / "freecad.json", {
            "package": "freecad",
            "srpm": "freecad-1.1.4-1.src.rpm",
            "build_id": 123,
            "build_url": "https://copr.fedorainfracloud.org/coprs/universish/FreeCAD../build/123/",
            "chroots": {"fedora-44-x86_64": {"status": status}},
        })
        srpm_path = self.metadata / "freecad-1.1.4-1.src.rpm"
        srpm_path.parent.mkdir(parents=True, exist_ok=True)
        srpm_path.write_bytes(b"test SRPM artifact")
        self.write_json(self.metadata / "freecad-native-srpm.json", {
            "package": "freecad",
            "source_commit": "a" * 40,
            "source_archive_sha256": "b" * 64,
            "srpm": "freecad-1.1.4-1.src.rpm",
            "srpm_sha256": hashlib.sha256(srpm_path.read_bytes()).hexdigest(),
        })
        self.write_json(self.reports / "security-report-native-freecad" / "native-security-report.json", {
            "package": "freecad",
            "architecture": "source",
            "source_commit": "a" * 40,
            "clamav_database_update": {"exit_code": 0},
            "clamav": {"upstream-source": {"status": "clean"}},
            "findings": [],
            "virustotal": {"status": "disabled", "malicious_hashes": []},
        })

    def invoke(self):
        argv = [
            "update_state.py",
            "--manifest", str(self.root / "manifest.json"),
            "--results-dir", str(self.results),
            "--payload-dir", str(self.payloads),
            "--build-metadata-dir", str(self.metadata),
            "--security-dir", str(self.reports),
            "--chroots", str(self.chroots),
            "--state-dir", str(self.state),
        ]
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return update_state.main()

    def test_nested_copr_artifact_updates_state_after_all_gates(self):
        self.native_inputs()
        self.assertEqual(self.invoke(), 0)
        state = json.loads((self.state / "freecad.json").read_text(encoding="utf-8"))
        self.assertEqual(state["copr_builds"][0]["id"], 123)
        self.assertEqual(state["source_commit"], "a" * 40)
        self.assertEqual(state["srpm_artifact"]["sha256"], hashlib.sha256(b"test SRPM artifact").hexdigest())

    def test_failed_copr_chroot_preserves_previous_state(self):
        self.native_inputs(status="failed")
        previous = self.state / "freecad.json"
        previous.parent.mkdir(parents=True)
        previous.write_text('{"version":"previous"}\n', encoding="utf-8")
        original = previous.read_bytes()
        self.assertEqual(self.invoke(), 1)
        self.assertEqual(previous.read_bytes(), original)

    def test_mismatched_copr_srpm_preserves_previous_state(self):
        self.native_inputs()
        result_path = self.results / "copr-result-freecad" / "freecad.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["srpm"] = "freecad-1.1.3-1.src.rpm"
        result_path.write_text(json.dumps(result), encoding="utf-8")
        previous = self.state / "freecad.json"
        previous.parent.mkdir(parents=True)
        previous.write_text('{"version":"previous"}\n', encoding="utf-8")
        original = previous.read_bytes()
        self.assertEqual(self.invoke(), 1)
        self.assertEqual(previous.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
