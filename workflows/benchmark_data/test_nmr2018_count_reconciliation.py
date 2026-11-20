"""Tests for author split counts with repeated spectra."""
import pickle
import json
from pathlib import Path
import tempfile
from unittest import mock
import zipfile
import unittest
import pandas as pd
from .nmr2018_count_reconciliation import describe_author_split, reconcile

class CountReconciliationTests(unittest.TestCase):
    def test_repeated_spectra_do_not_become_distinct_molecules(self):
        raw=pickle.dumps({"test_df":pd.DataFrame({"molecule_id":[10,10,20]})})
        actual=describe_author_split(raw)
        self.assertEqual(actual["spectrum_records"],3)
        self.assertEqual(actual["unique_original_molecule_ids"],2)

    def test_wrong_container_fails_instead_of_inventing_counts(self):
        with self.assertRaises(ValueError):
            describe_author_split(pickle.dumps({"test":4}))

    def test_matching_spectrum_counts_do_not_hide_molecule_count_mismatch(self):
        sources={k:dict(records=3,unique_original_molecules=2) for k in ("1H","13C")}
        authors={k:dict(spectrum_records=3,unique_original_molecule_ids=1) for k in ("1H","13C")}
        result=reconcile(sources,authors)
        self.assertTrue(result["13C"]["same_spectrum_record_count"])
        self.assertFalse(result["13C"]["same_unique_molecule_count"])

    def test_complete_author_archive_to_count_manifest(self):
        from . import nmr2018_count_reconciliation as module
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/"raw/NMRShiftDB2_Jonas2019"
            source.mkdir(parents=True)
            payload=pickle.dumps({"test_df":pd.DataFrame({"molecule_id":[10,10,20]})})
            with zipfile.ZipFile(source/"Kwon2020_datasets.zip","w") as archive:
                for nucleus in ("13C","1H"):
                    archive.writestr("data_"+nucleus+".pickle",payload)
            prepared=root/"directive19/NMR2018/job_4536853"
            prepared.mkdir(parents=True)
            counts=[dict(nucleus=k,official_split="test",source_rows=3,unique_molecule_ids=2)
                    for k in ("13C","1H")]
            (prepared/"manifest.json").write_text(json.dumps({"counts":counts}))
            argv=["count","--root",str(root),"--quota-snapshot",str(root/"quota"),
                  "--attempt","test_counts"]
            with mock.patch("sys.argv",argv),mock.patch.object(module,"capacity"):
                module.main()
            result=json.loads((prepared.parent/"test_counts/manifest.json").read_text())
            self.assertTrue(result["all_test_unique_molecule_counts_match"])
            self.assertTrue(result["all_test_spectrum_counts_match"])
