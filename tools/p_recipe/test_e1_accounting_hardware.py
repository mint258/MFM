"""Only E1 additions to the original accounting and telemetry estimators."""
import unittest
from e1_hardware import summarize_telemetry
from write_weekly_cost_current import cost_records,bucket

class E1AccountingHardwareTests(unittest.TestCase):
    def test_irregular_telemetry_uses_time_weighted_original_trapezoids(self):
        rows=[dict(timestamp=t,power_watts=p,memory_mib=2,job_id="j",gpu_uuid="u") for t,p in [(0,100),(1,200),(3,100)]]
        r=summarize_telemetry(rows,"j","u")
        self.assertEqual(r["power_time_weighted_mean_watts"],150)
        self.assertEqual(r["power_observation_seconds"],3)
        rows[1]["gpu_uuid"]="another"
        with self.assertRaisesRegex(ValueError,"UUID"):summarize_telemetry(rows,"j","u")

    def test_new_E1_buckets_preserve_single_physical_handles_and_CPU_exclusion(self):
        def gpu(j,kind):return dict(backend="Slurm",node="compute-0-5",job_id=j,kind=kind)
        ledger=dict(runs=dict(E1_k1=gpu(1,"E1_TRAINING"),alias_E1_k1=gpu(1,"E1_TRAINING"),
            E1FT_full_k1=gpu(2,"F"),CPU=dict(backend="Slurm",node="compute-0-12",job_id=3,kind="E1_CPU")))
        native=dict(observed_at=1,rows={str(j):dict(job_id=str(j),job_name=str(j),node="compute-0-12" if j==3 else "compute-0-5",
            state="COMPLETED",elapsed_seconds=100,start="2026-11-24T00:00:00") for j in (1,2,3)})
        records,skipped,aliases=cost_records(ledger,native)
        self.assertEqual([bucket(x) for _,x in records],["analysis_E1_training","analysis_E1_full"])
        self.assertEqual(sum(x["elapsed_seconds"] for _,x in records),200)
        self.assertEqual(len(aliases),1);self.assertEqual(len(skipped),1)

if __name__=="__main__":unittest.main()
