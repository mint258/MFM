"""New fit transport gates/recovery only; no production values or fitting."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from tools.d_recipe.reference_fit_ssh import (fit_or_reuse, publish_once,
                                             require_final_collector, require_full_collection)


class SSHReferenceFitTests(unittest.TestCase):
    def test_complete_original_TRAIN_and_actual_collector_exit_are_required(self):
        config = dict(model_name="D-L2:fixture")
        marker = dict(schema="D_A1_COLLECTION_V1", status="COLLECTION_COMPLETE", closed_rows=9,
                      binding=dict(rows=9, split="TRAIN", configuration=config))
        require_full_collection(config, marker)
        marker["closed_rows"] = 8
        with self.assertRaisesRegex(ValueError, "full-TRAIN"):
            require_full_collection(config, marker)
        record = dict(execution_id="ssh:P_D_fixture", node="compute-0-11", status="COMPLETE",
                      returncode=0, remaining_children=[], owned_tree_reaped=True,
                      supervisor=dict(pid=100, start_ticks=10, uids=[os.getuid()] * 4),
                      parent=dict(pid=99, start_ticks=9, uids=[os.getuid()] * 4))
        require_final_collector(record, record["execution_id"], record["node"], lambda pid: None)
        with self.assertRaisesRegex(ValueError, "still exists"):
            require_final_collector(record, record["execution_id"], record["node"],
                lambda pid: SimpleNamespace(start_ticks=10 if pid == 100 else 9, uids=(os.getuid(),) * 4))
        record.update(status="CURSOR_SAVED_NOT_COMPLETE", returncode=75)
        with self.assertRaisesRegex(ValueError, "must complete"):
            require_final_collector(record, record["execution_id"], record["node"], lambda pid: None)

    def test_committed_local_result_resumes_publication_without_dataset_or_refit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "label_parameters.json"
            source.write_text(json.dumps(dict(fixture="committed")))
            build, fitter = Mock(side_effect=AssertionError("No second read")), Mock(side_effect=AssertionError("No refit"))
            result = fit_or_reuse(dict(output=str(root)), build_dataset=build, fitter=fitter,
                                  guard=Mock(), may_start=lambda: False)
            destination = root / "shared" / "label_parameters.json"
            self.assertEqual(publish_once(result, destination), "FROZEN_PARAMETERS_PUBLISHED")
            self.assertEqual(destination.read_bytes(), source.read_bytes())
            self.assertEqual(publish_once(result, destination), "REUSE_PUBLISHED_PARAMETERS")
            build.assert_not_called()
            fitter.assert_not_called()

    def test_original_fitter_is_called_once_and_reader_closes_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            reader = SimpleNamespace(close=Mock())
            fitter = Mock(side_effect=RuntimeError("fixture fitting failure"))
            with self.assertRaisesRegex(RuntimeError, "fixture fitting failure"):
                fit_or_reuse(dict(output=directory), build_dataset=lambda: reader, fitter=fitter,
                             guard=Mock(), may_start=lambda: True)
            fitter.assert_called_once()
            reader.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
