"""Aggregate report exceptions preserve the raw-data ban; synthetic files only."""
import tempfile,unittest
from pathlib import Path
from tools.check_repository import check,BENCHMARK_REPORT_TABLES
class RepositoryReportTableTests(unittest.TestCase):
    def run_case(self,name,content):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/"docs").mkdir()
            (root/"docs/SOURCE_MANIFEST.json").write_text('{"files":[]}')
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
            return check(root,[name],verify_export=False)
    def test_exact_registered_aggregate_paths_are_allowed(self):
        for name,columns in BENCHMARK_REPORT_TABLES.items():
            header=sorted(columns)
            with self.subTest(name=name):
                self.assertEqual(self.run_case(name,",".join(header)+"\n"+",".join(["synthetic"]*len(header))+"\n")["status"],"PASS")
    def test_unregistered_csv_and_weight_paths_remain_forbidden(self):
        for name in ("results/benchmark/other.csv","raw/labels.csv","results/benchmark/weights.pt"):
            with self.subTest(name=name):self.assertEqual(self.run_case(name,"endpoint_key,decision,reason\n")["status"],"FAIL")
    def test_individual_data_cannot_hide_under_an_allowed_report_name(self):
        for field in ("record_id","evaluation_id","full_inchikey","smiles","y_true","prediction"):
            with self.subTest(field=field):
                self.assertEqual(self.run_case("results/benchmark/B1_task_screen.csv","endpoint_key,decision,reason,"+field+"\n")["status"],"FAIL")
    def test_wrong_header_is_rejected_but_empty_closed_comparison_is_allowed(self):
        path="results/benchmark/C1_second_seed_registered_comparisons.csv"
        self.assertEqual(self.run_case(path,"unrelated\n")["status"],"FAIL")
        self.assertEqual(self.run_case(path,"status\n")["status"],"PASS")
        self.assertEqual(self.run_case(path,"status\nunregistered\n")["status"],"FAIL")
        self.assertEqual(self.run_case("results/benchmark/B1_task_screen.csv","status\n")["status"],"FAIL")
