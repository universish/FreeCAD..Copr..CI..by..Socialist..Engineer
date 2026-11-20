import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import submit_copr


class FakeBuildChroots:
    def __init__(self, statuses):
        self.statuses = statuses
        self.calls = {}

    def get(self, _build_id, chroot):
        rows = self.statuses[chroot]
        index = self.calls.get(chroot, 0)
        self.calls[chroot] = index + 1
        return {"status": rows[min(index, len(rows) - 1)], "chroot": chroot}


class FakeClient:
    def __init__(self, statuses):
        self.build_chroot_proxy = FakeBuildChroots(statuses)


class FakeBuildList:
    def __init__(self, rows):
        self.rows = rows

    def get_list(self, _owner, _project, packagename):
        self.package = packagename
        return self.rows


class FakeExistingBuildClient:
    def __init__(self, rows):
        self.build_proxy = FakeBuildList(rows)


def copr_build(build_id, state="succeeded", filename="freecad-1.1.4-1.src.rpm", chroots=None):
    return {
        "id": build_id,
        "state": state,
        "source_package": {
            "name": "freecad",
            "version": "1.1.4-1",
            "url": f"https://download.copr.fedorainfracloud.org/results/source/{filename}",
        },
        "chroots": chroots or ["fedora-44-x86_64"],
    }


class CoprMonitoringTests(unittest.TestCase):
    def test_reuses_successful_exact_srpm_build_with_all_chroots(self):
        client = FakeExistingBuildClient([copr_build(41), copr_build(42)])
        found = submit_copr.find_existing_build(
            client, "owner", "project", "freecad", "freecad-1.1.4-1.src.rpm",
            "1.1.4-1", ["fedora-44-x86_64"],
        )
        self.assertEqual(found["id"], 42)

    def test_does_not_reuse_different_srpm_or_incomplete_chroots(self):
        rows = [
            copr_build(41, filename="freecad-1.1.3-1.src.rpm"),
            copr_build(42, filename="repacked-freecad-1.1.4-1.src.rpm"),
            copr_build(43, chroots=["fedora-44-x86_64", "fedora-45-x86_64"]),
        ]
        client = FakeExistingBuildClient(rows)
        found = submit_copr.find_existing_build(
            client, "owner", "project", "freecad", "freecad-1.1.4-1.src.rpm",
            "1.1.4-1", ["fedora-44-x86_64", "fedora-44-aarch64"],
        )
        self.assertIsNone(found)

    def test_failed_exact_build_is_eligible_for_retry(self):
        client = FakeExistingBuildClient([copr_build(41, state="failed")])
        found = submit_copr.find_existing_build(
            client, "owner", "project", "freecad", "freecad-1.1.4-1.src.rpm",
            "1.1.4-1", ["fedora-44-x86_64"],
        )
        self.assertIsNone(found)

    def test_waits_until_every_chroot_has_a_terminal_success(self):
        client = FakeClient({
            "fedora-44-x86_64": ["running", "succeeded"],
            "fedora-44-aarch64": ["pending", "succeeded"],
        })
        clock = [0.0]

        def sleep(seconds):
            clock[0] += seconds

        results, timed_out = submit_copr.monitor_chroots(
            client, 42, list(client.build_chroot_proxy.statuses), 100, 10,
            monotonic=lambda: clock[0], sleep=sleep,
        )
        self.assertFalse(timed_out)
        self.assertEqual(set(results), set(client.build_chroot_proxy.statuses))
        self.assertTrue(all(row["status"] == "succeeded" for row in results.values()))

    def test_returns_partial_results_when_deadline_expires(self):
        client = FakeClient({"fedora-44-x86_64": ["running"]})
        clock = [0.0]
        results, timed_out = submit_copr.monitor_chroots(
            client, 42, ["fedora-44-x86_64"], 5, 10,
            monotonic=lambda: clock[0], sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        )
        self.assertTrue(timed_out)
        self.assertEqual(results["fedora-44-x86_64"]["status"], "running")

    def test_terminal_failure_does_not_wait_for_other_targets(self):
        client = FakeClient({
            "fedora-44-x86_64": ["failed"],
            "fedora-44-aarch64": ["pending"],
        })
        clock = [0.0]
        results, timed_out = submit_copr.monitor_chroots(
            client, 42, list(client.build_chroot_proxy.statuses), 100, 10,
            monotonic=lambda: clock[0], sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        )
        self.assertFalse(timed_out)
        self.assertEqual(results["fedora-44-x86_64"]["status"], "failed")
        self.assertEqual(client.build_chroot_proxy.calls["fedora-44-aarch64"], 1)


if __name__ == "__main__":
    unittest.main()
