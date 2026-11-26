"""Run only the two repaired calling-contract tests, then the one cohort producer."""
from cpu_ssh_runtime import execution_handle
import argparse,json,os
from pathlib import Path
from a5_contracts import require_runtime_configuration
from finetune_entry import CooperativeStop,set_actual_deadline
from finetune_statistics_entry import require_cpu_admission,atomic_json

def run(c):
    require_runtime_configuration(c)
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);require_cpu_admission(c)
        out=Path(c["output"]);out.mkdir(parents=True,exist_ok=True)
        receipt=out/"two_contract_tests.json"
        if not receipt.exists():
            import pytest
            from finetune_entry import REPO
            status=pytest.main(["-q","-p","no:cacheprovider",str(REPO/"tools/p_recipe/test_a5_contracts.py")])
            if status:return int(status)
            atomic_json(receipt,dict(status="PASS",tests=2,job=execution_handle(),
                old_regression_repeated=False))
        from a5_cohort_entry import run as cohort
        return cohort(c)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",required=True)
    args=p.parse_args();raise SystemExit(run(json.loads(Path(args.configuration).read_text())))

