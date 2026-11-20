import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import detect_release


class ReleaseDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = detect_release.load_policy()
        cls.fixture = json.loads((ROOT / "tests/fixtures/releases.json").read_text(encoding="utf-8"))

    def test_weekly_release_is_classified_and_never_selected(self):
        weekly = self.fixture[0]
        self.assertTrue(detect_release.is_weekly(weekly, self.policy))
        self.assertEqual(detect_release.classify_release(weekly, self.policy), "EXCLUDED_WEEKLY")
        self.assertIsNone(detect_release.choose_latest([weekly], "stable", self.policy))

    def test_version_families_and_prerelease_channel(self):
        self.assertEqual(detect_release.classify_release(self.fixture[1], self.policy), "CANDIDATE")
        self.assertEqual(detect_release.classify_release(self.fixture[2], self.policy), "STABLE")
        body_mentions_weekly = dict(self.fixture[1], body="Weekly development builds are listed separately.")
        self.assertEqual(detect_release.classify_release(body_mentions_weekly, self.policy), "CANDIDATE")
        title_mentions_weekly = dict(self.fixture[1], name="FreeCAD Weekly 2026.11.18")
        self.assertEqual(detect_release.classify_release(title_mentions_weekly, self.policy), "EXCLUDED_WEEKLY")
        body_identifies_weekly = dict(self.fixture[1], body="Build: weekly-2026.11.18")
        self.assertEqual(detect_release.classify_release(body_identifies_weekly, self.policy), "EXCLUDED_WEEKLY")
        for tag in ("27.1", "27.1.0"):
            self.assertEqual(detect_release.classify_release({"tag_name": tag, "prerelease": False}, self.policy), "STABLE")
        self.assertEqual(detect_release.classify_release({"tag_name": "nightly-2026.11.20"}, self.policy), "UNSUPPORTED")

    def test_artifact_priority_checksum_and_architecture(self):
        selected = detect_release.select_asset(self.fixture[2], "x86_64", self.policy)
        self.assertEqual(selected["format"], "rpm")
        self.assertIsNone(selected["checksum_url"])
        candidate = detect_release.select_asset(self.fixture[1], "aarch64", self.policy)
        self.assertEqual(candidate["name"], "FreeCAD_26.3rc2-Linux-aarch64-py311.AppImage")
        self.assertEqual(candidate["checksum_url"], "https://example.invalid/sha-arm")

    def test_detection_chooses_latest_supported_release_and_keeps_channels_separate(self):
        result = detect_release.detect(self.fixture, self.policy)
        self.assertEqual(set(result["channels"]), {"stable", "candidate"})
        self.assertEqual(result["channels"]["stable"]["version"], "1.1.4")
        self.assertEqual(result["channels"]["candidate"]["version"], "26.3rc2")
        self.assertEqual(result["channels"]["stable"]["native"]["package"], "freecad")
        self.assertEqual(result["channels"]["candidate"]["native"]["package"], "freecad-candidate")

    def test_forced_weekly_tag_is_not_treated_as_manual_override(self):
        with self.assertRaises(detect_release.DetectionError):
            detect_release.detect(self.fixture, self.policy, "weekly-2026.11.18", "candidate")

    def test_forced_candidate_tag_with_auto_channel_selects_candidate(self):
        result = detect_release.detect(self.fixture, self.policy, "26.3rc2", "auto")
        self.assertEqual(set(result["channels"]), {"candidate"})

    def copr_build(self, package, release, state="succeeded", chroots=None):
        return {
            "id": release,
            "state": state,
            "source_package": {
                "name": package,
                "version": f"1.1.4-{release}",
                "url": f"https://download.copr.fedorainfracloud.org/{package}-1.1.4-{release}.src.rpm",
            },
            "chroots": chroots or ["target-a", "target-b"],
        }

    def test_copr_counter_uses_only_fully_successful_exact_package_builds(self):
        builds = [
            self.copr_build("freecad", 2),
            self.copr_build("freecad", 5, state="failed"),
            self.copr_build("freecad", 7, chroots=["target-a"]),
            self.copr_build("freecad-candidate", 9),
            self.copr_build("freecad", 3, state="succeeded"),
        ]
        self.assertEqual(
            detect_release.successful_copr_release(builds, "freecad", "1.1.4", ["target-a", "target-b"]),
            3,
        )

    def test_copr_success_ahead_of_state_recovers_at_published_release(self):
        stable = self.fixture[2]
        baseline = detect_release.resolve_channel(stable, "stable", self.policy)
        packages = self.policy["packages"]["stable"]
        old_state = {
            packages["native"]: {
                "version": "1.1.4", "tag": "1.1.4", "release": 1,
                "packaging_fingerprint": baseline["native"]["packaging_fingerprint"],
            },
            packages["non_native"]: {
                "version": "1.1.4", "tag": "1.1.4", "release": 1,
                "packaging_fingerprint": baseline["non_native"]["packaging_fingerprint"],
                "assets": baseline["non_native"]["assets_fingerprint"],
            },
        }
        copr = {
            packages["native"]: [self.copr_build(packages["native"], 3)],
            packages["non_native"]: [self.copr_build(packages["non_native"], 3)],
        }
        with patch.object(detect_release, "package_state", side_effect=lambda package: old_state[package]):
            result = detect_release.resolve_channel(
                stable, "stable", self.policy, copr, ["target-a", "target-b"]
            )
        self.assertTrue(result["native"]["changed"])
        self.assertEqual(result["native"]["release"], 3)
        self.assertTrue(result["non_native"]["changed"])
        self.assertEqual(result["non_native"]["release"], 3)

    def test_changed_packaging_advances_after_successful_copr_release(self):
        stable = self.fixture[2]
        packages = self.policy["packages"]["stable"]
        old_state = {
            packages["native"]: {
                "version": "1.1.4", "tag": "1.1.4", "release": 2,
                "packaging_fingerprint": "old-fingerprint",
            },
            packages["non_native"]: {
                "version": "1.1.4", "tag": "1.1.4", "release": 2,
                "packaging_fingerprint": "old-fingerprint", "assets": {},
            },
        }
        copr = {
            packages["native"]: [self.copr_build(packages["native"], 4)],
            packages["non_native"]: [self.copr_build(packages["non_native"], 4)],
        }
        with patch.object(detect_release, "package_state", side_effect=lambda package: old_state[package]):
            result = detect_release.resolve_channel(
                stable, "stable", self.policy, copr, ["target-a", "target-b"]
            )
        self.assertEqual(result["native"]["release"], 5)
        self.assertEqual(result["non_native"]["release"], 5)

    def test_state_ahead_of_copr_success_history_fails_closed(self):
        stable = self.fixture[2]
        baseline = detect_release.resolve_channel(stable, "stable", self.policy)
        packages = self.policy["packages"]["stable"]
        old_state = {
            packages["native"]: {
                "version": "1.1.4", "tag": "1.1.4", "release": 2,
                "packaging_fingerprint": baseline["native"]["packaging_fingerprint"],
            },
            packages["non_native"]: {
                "version": "1.1.4", "tag": "1.1.4", "release": 2,
                "packaging_fingerprint": baseline["non_native"]["packaging_fingerprint"],
                "assets": baseline["non_native"]["assets_fingerprint"],
            },
        }
        with patch.object(detect_release, "package_state", side_effect=lambda package: old_state[package]):
            with self.assertRaises(detect_release.DetectionError):
                detect_release.resolve_channel(
                    stable,
                    "stable",
                    self.policy,
                    {packages["native"]: [], packages["non_native"]: []},
                    ["target-a", "target-b"],
                )

    def test_load_copr_builds_reads_public_paginated_api(self):
        response = BytesIO(json.dumps({"builds": [{"id": 11}]}).encode())
        with patch.object(detect_release.urllib.request, "urlopen", return_value=response) as urlopen:
            rows = detect_release.load_copr_builds("freecad", "owner/project")
        self.assertEqual(rows, [{"id": 11}])
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url.split("/api_3/build/list/")[0], detect_release.COPR_API)
        self.assertEqual(request.full_url.split("?")[0], f"{detect_release.COPR_API}/build/list/")
        self.assertIn("packagename=freecad", request.full_url)

    def test_load_copr_builds_rejects_repeated_page_ids(self):
        first_page = [{"id": item} for item in range(100)]
        second_page = [{"id": 99}]
        responses = [
            BytesIO(json.dumps({"builds": first_page}).encode()),
            BytesIO(json.dumps({"builds": second_page}).encode()),
        ]
        with patch.object(detect_release.urllib.request, "urlopen", side_effect=responses):
            with self.assertRaises(detect_release.DetectionError):
                detect_release.load_copr_builds("freecad", "owner/project")


if __name__ == "__main__":
    unittest.main()
