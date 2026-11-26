"""New transport admission only; no real shared filesystem, labels or models."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.d_recipe import shared_admission as a


class DSharedAdmissionTests(unittest.TestCase):
    def test_owned_local_phase_does_not_use_historical_shared_or_peer_forecasts(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = self.fixture(directory)
            local = Path(directory) / "d_recipe_fixture"
            local.mkdir()
            transport.update(local_output_root=str(local), registered_model_share_future_bytes=10**30)
            with patch.object(a.shared_guard, "REGISTRY", Path(directory)), \
                 patch.object(a, "LOCAL_BASE", Path(directory)), \
                 patch.object(a.socket, "gethostname", return_value=transport["node"]), \
                 patch.object(a.time, "time", return_value=100), \
                 patch.object(a.shared_guard, "_same_device", return_value={"/", "/tmp"}), \
                 patch.object(a.shared_guard, "check_with_timeout") as check:
                result = a.admit(transport, [local / "collection"])
            self.assertEqual(result["mounts"], [])
            self.assertEqual([(x.args[1], x.args[2]) for x in check.call_args_list],
                             [("node_ram", 100), ("node_disk", 20)])

    def fixture(self, directory):
        transport = dict(node="compute-0-19", reservation_ids=["ram", "tmp", "out"],
                         ram_peak_bytes=100, local_future_bytes=20,
                         shared_future_bytes={"/share": 300})
        entries = [dict(id="ram", kind="node_ram", node=transport["node"], bytes=100),
                   dict(id="tmp", kind="node_disk", node=transport["node"], path="/tmp", bytes=20),
                   dict(id="out", kind="shared_fs", path="/share", bytes=300)]
        (Path(directory) / "d-recipe.json").write_text(json.dumps(
            dict(line="d-recipe", expires=200, entries=entries)))
        return transport

    def test_claim_sums_use_only_own_registry_and_canonical_checks_once(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = self.fixture(directory)
            # Historical copied peer figures are intentionally ignored.
            transport["registered_model_share_future_bytes"] = 10**30
            with patch.object(a.shared_guard, "REGISTRY", Path(directory)), \
                 patch.object(a.socket, "gethostname", return_value=transport["node"]), \
                 patch.object(a.time, "time", return_value=100), \
                 patch.object(a.shared_guard, "_same_device", return_value={"/", "/tmp"}), \
                 patch.object(a.shared_guard, "check_with_timeout") as check:
                a.admit(transport, [Path(a.__file__).resolve().parents[2] / "results/d_recipe"])
            self.assertEqual([(x.args[1], x.args[2]) for x in check.call_args_list],
                             [("node_ram", 100), ("node_disk", 20), ("shared_fs", 300)])

    def test_expired_own_claim_and_escaped_output_refuse_before_capacity_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = self.fixture(directory)
            with patch.object(a.shared_guard, "REGISTRY", Path(directory)), \
                 patch.object(a.socket, "gethostname", return_value=transport["node"]), \
                 patch.object(a.time, "time", return_value=201), \
                 patch.object(a.shared_guard, "check_with_timeout") as check:
                with self.assertRaisesRegex(ValueError, "Current own D reservations"):
                    a.admit(transport, ["/unowned/output"])
                check.assert_not_called()
            with patch.object(a.shared_guard, "REGISTRY", Path(directory)), \
                 patch.object(a.socket, "gethostname", return_value=transport["node"]), \
                 patch.object(a.time, "time", return_value=100), \
                 patch.object(a.shared_guard, "check_with_timeout") as check:
                with self.assertRaisesRegex(ValueError, "escaped"):
                    a.admit(transport, ["/unowned/output"])
                check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
