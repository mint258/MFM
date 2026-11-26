"""Only the new E1 final-report consumer, using synthetic closed summaries."""
import copy,unittest
from e1_report import validate_closed,render,TASKS
from final_report_22B import require_closed,ReportNotReady
from pathlib import Path
import tempfile

def closed():
    def comparison(verdict="tie"):
        return dict(bootstrap_draws_per_seed=1000,decision=dict(verdict=verdict,delta=0.,ci_lower=-.01,ci_upper=.01))
    rows=[]
    for k in (1,2,5,10):
        rows.append(dict(k=k,frozen_primary="synthetic/frozen.json",full_primary="synthetic/full.json",
            full_task_rows=[dict(task=t,seed_count=3,mae_seed_mean=1.,mae_seed_std=.1,scratch_improvement_seed_mean=.1) for t in sorted(TASKS)],
            frozen_R1=comparison(),frozen_R3=comparison("loss" if k==1 else "tie"),full=comparison()))
    return dict(status="COMPLETE",k_star=2,frozen_recipe=["A1","B3","B4","F2"],samples=3000000,
        cells=[dict(k=k,actual_mean_k=float(k),clip_threshold=33.) for k in (1,2,5,10)],results=rows,
        conditional_seed1_required=False)

class E1ReportConsumerTests(unittest.TestCase):
    def test_closed_consumer_reports_all_cells_and_rejects_missing_seed(self):
        value=closed();text=render(value)
        self.assertIn("本线k*=2",text);self.assertIn("round4 F2",text);self.assertIn("frozen_R1",text)
        broken=copy.deepcopy(value);broken["results"][1]["full_task_rows"][0]["seed_count"]=2
        with self.assertRaisesRegex(ValueError,"x3seeds"):validate_closed(broken)
        broken=copy.deepcopy(value);broken["conditional_seed1_required"]=True
        with self.assertRaisesRegex(ValueError,"seed1"):validate_closed(broken)

    def test_missing_registered_E1_file_blocks_final_report(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ReportNotReady,"E1"):require_closed(Path(root))

if __name__=="__main__":unittest.main()
