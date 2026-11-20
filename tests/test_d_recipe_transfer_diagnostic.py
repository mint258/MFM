"""Test only the new D cache-transfer wrapper; rsync itself is reused."""
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.d_recipe.resources import DiskUnavailable
from tools.d_recipe.transfer_diagnostic import transfer


class TransferTests(unittest.TestCase):
    def configuration(self, scope):
        return dict(output=str(Path(scope)/"representation"), local_output_root=scope,
                    local_storage_peak_bytes=12*2**30, local_node="compute-0-17",
                    source_node="compute-0-7", forward_binding=dict(arm="D-R0", seed=0, samples=3000000))

    def closed(self, c):
        return SimpleNamespace(stdout=json.dumps(dict(schema="D_REPRESENTATION_FORWARD_V1",
                            status="FORWARD_COMPLETE", binding=c["forward_binding"])))

    @patch("tools.d_recipe.transfer_diagnostic.execution_site")
    def test_same_absolute_paths_are_preserved_and_transport_keeps_stdin(self, site):
        with tempfile.TemporaryDirectory(prefix="d_recipe_transfer_fixture_", dir="/tmp") as scope:
            c=self.configuration(scope); guard=Mock(); run=Mock(return_value=self.closed(c))
            result=transfer(c,guard=guard,run=run)
            site.assert_called_once_with(c,cpu=True)
            metadata=run.call_args.args[0]
            self.assertEqual(metadata[:2],["ssh","-n"])
            transport=guard.run.call_args.args[0]
            self.assertEqual(transport[-2:],["compute-0-7:"+scope+"/",scope+"/"])
            self.assertIn("--sparse",transport)
            self.assertIn("--partial",transport)
            self.assertNotIn("-n",transport[transport.index("-e")+1])
            self.assertNotIn("--delete",transport)
            self.assertNotIn("--checksum",transport)
            self.assertFalse(result["original_sources_copied"])
            self.assertFalse(result["scientific_values_changed"])

    @patch("tools.d_recipe.transfer_diagnostic.execution_site")
    def test_changed_source_checkpoint_never_starts_transport(self, site):
        with tempfile.TemporaryDirectory(prefix="d_recipe_transfer_fixture_", dir="/tmp") as scope:
            c=self.configuration(scope);guard=Mock()
            closed=json.loads(self.closed(c).stdout);closed["binding"]["seed"]=1
            with self.assertRaisesRegex(ValueError,"same registered"):
                transfer(c,guard=guard,run=Mock(return_value=SimpleNamespace(stdout=json.dumps(closed))))
            guard.run.assert_not_called()

    @patch("tools.d_recipe.transfer_diagnostic.execution_site")
    def test_insufficient_target_capacity_precedes_metadata_or_copy(self, site):
        with tempfile.TemporaryDirectory(prefix="d_recipe_transfer_fixture_", dir="/tmp") as scope:
            guard=Mock();guard.check.side_effect=DiskUnavailable("root floor")
            run=Mock()
            with self.assertRaises(DiskUnavailable):transfer(self.configuration(scope),guard=guard,run=run)
            run.assert_not_called();guard.run.assert_not_called()

    @patch("tools.d_recipe.transfer_diagnostic.execution_site")
    def test_source_observation_failure_propagates_without_starting_copy(self, site):
        with tempfile.TemporaryDirectory(prefix="d_recipe_transfer_fixture_", dir="/tmp") as scope:
            guard=Mock();run=Mock(side_effect=subprocess.CalledProcessError(255,["ssh"]))
            with self.assertRaises(subprocess.CalledProcessError):
                transfer(self.configuration(scope),guard=guard,run=run)
            guard.run.assert_not_called()

    @patch("tools.d_recipe.transfer_diagnostic.execution_site")
    def test_different_destination_condition_is_preserved(self, site):
        with tempfile.TemporaryDirectory(prefix="d_recipe_transfer_fixture_", dir="/tmp") as scope:
            c=self.configuration(scope);output=Path(c["output"]);output.mkdir()
            path=output/"manifest.json";path.write_text(json.dumps(dict(binding=dict(arm="D-R1"))))
            original=path.read_bytes();guard=Mock();run=Mock()
            with self.assertRaisesRegex(ValueError,"preserve"):
                transfer(c,guard=guard,run=run)
            self.assertEqual(path.read_bytes(),original)
            guard.run.assert_not_called();run.assert_not_called()

    @patch("tools.d_recipe.transfer_diagnostic.execution_site")
    def test_prohibited_gpu_source_is_rejected(self, site):
        with tempfile.TemporaryDirectory(prefix="d_recipe_transfer_fixture_", dir="/tmp") as scope:
            c=self.configuration(scope);c["source_node"]="compute-0-21"
            with self.assertRaisesRegex(ValueError,"allowed GPU"):
                transfer(c,guard=Mock(),run=Mock())


if __name__ == "__main__":unittest.main()
