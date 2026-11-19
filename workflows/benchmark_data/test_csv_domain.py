import csv
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import pyarrow.parquet as pq
from workflows.benchmark_data import build_csv_domain as producer

class CsvProducerTests(unittest.TestCase):
    def run_fixture(self, dataset, blind, smiles_column="smiles", split_column="split", with_solvent=False, auxiliary_raw=False):
        parent=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control")
        root=Path(tempfile.mkdtemp(prefix="benchmark_csv_unit_",dir=str(parent)))
        raw=root/"raw"/dataset
        raw.mkdir(parents=True)
        name="expansion_data_test_blinded.csv" if blind else "test.csv"
        with (raw/name).open("w",newline="") as stream:
            writer=csv.writer(stream)
            writer.writerow([smiles_column,"y",split_column]+(["Solvent"] if with_solvent else []))
            writer.writerows([r+(["O"] if with_solvent else []) for r in [["CCO","1.23456789","train"],["C[NH+](C)C","2","test"],["invalid","3","test"]]])
        plan=root/"plan.json"
        source={
            "source_commit":"SYNTHETIC","blind_no_filter":blind,"smiles_column":smiles_column,"split_column":split_column,"files":[{"name":name,"bytes":100}]}
        if auxiliary_raw:
            (raw/"auxiliary_raw.csv").write_text("not,a,model,table\n")
            source["files"].append({"name":"auxiliary_raw.csv","bytes":20})
            source["domain_files"]=[name]
        plan.write_text(json.dumps({"data_root":str(root),"assets":{dataset:source}}))
        quota="Disk quotas for user zixiao (uid %d):\n/dev/sda1 3860254404 0 4294967296 142437135 0 0\n"%os.getuid()
        argv=["unit","--plan",str(plan),"--dataset",dataset,"--attempt","unit"]
        with patch.object(sys,"argv",argv),patch.object(producer,"guard"),patch.object(
                producer.subprocess,"check_output",return_value=quota):
            producer.main()
        out=root/"domain"/dataset/"unit"
        return json.loads((out/"manifest.json").read_text()),pq.read_table(out/"all_rows.parquet").to_pylist()

    def test_nonblind_rejections_and_source_values_survive(self):
        report,rows=self.run_fixture("MoleculeACE",False)
        self.assertEqual(report["counts"][0]["before"],3)
        self.assertEqual(report["counts"][0]["retained"],1)
        self.assertEqual(len(rows),3)
        self.assertEqual(json.loads(rows[0]["original_fields_json"])["y"],"1.23456789")
        self.assertEqual(rows[0]["official_split"],"train")
        self.assertEqual(rows[0]["model_atom_to_source"],[0,1,2])

    def test_blind_rows_are_kept_with_explicit_fallback(self):
        report,rows=self.run_fixture("ExpansionRx",True)
        self.assertEqual(report["counts"][0]["retained"],3)
        self.assertEqual(report["counts"][0]["blind_fallback_required"],2)
        self.assertTrue(all(r["official_split"]=="test_blinded" for r in rows))

    def test_author_supplied_scaffold_split_column_is_preserved(self):
        report,rows=self.run_fixture("PharmaBench",False,"Smiles_unify","scaffold_train_test_label")
        self.assertEqual(report["counts"][0]["retained"],1)
        self.assertEqual(rows[0]["official_split"],"train")
        self.assertEqual(rows[1]["official_split"],"test")

    def test_optical_solvent_is_preserved_without_filtering_it_as_chromophore(self):
        report,rows=self.run_fixture("Joung2020",False,"Chromophore",with_solvent=True)
        self.assertEqual(report["counts"][0]["retained"],1)
        self.assertEqual(json.loads(rows[0]["original_fields_json"])["Solvent"],"O")

    def test_auxiliary_raw_download_is_not_a_second_benchmark_split(self):
        report,rows=self.run_fixture("ExpansionRx",True,auxiliary_raw=True)
        self.assertEqual(len(rows),3)
        self.assertEqual(len(report["counts"]),1)
        self.assertEqual(report["source_files_not_model_records"],["auxiliary_raw.csv"])
if __name__=="__main__":unittest.main()
