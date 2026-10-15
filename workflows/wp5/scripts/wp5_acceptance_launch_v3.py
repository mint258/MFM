"""Launch only the previously prepared, hash-bound authorized 200-record plan."""
from __future__ import annotations
import argparse,ast,json,subprocess
from pathlib import Path
from wp5_acceptance_catalog_v2 import ROOT,sha,require_slurm
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--recompute-plan",type=Path);p.add_argument("--check",action="store_true");a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print("ACCEPTANCE_LAUNCH_AST_PASS_NO_QM");return
    require_slurm(24)
    plan=json.loads(a.recompute_plan.read_text())
    if plan["selected_records"]!=200 or plan["requested_quantum_slots"]!=2400:raise ValueError("AUTHORIZED_200_RECORD_SCOPE_REQUIRED")
    for name in ("runner","protocol","dictionaries","node_authority","node_scope_plan"):
        if sha(plan[name])!=plan[name+"_sha256"]:raise ValueError("PREPARED_RECOMPUTE_BINDING_CHANGED:"+name)
    for name in ('audit_manifest','reproduction_package','production_contract'):
        reference=plan[name]
        if sha(reference['path'])!=reference['sha256']:raise ValueError('PREPARED_CURRENT_SCOPE_REF_CHANGED:'+name)
    command=plan["command"]
    if command[0]!=plan["expected_python"] or command[1]!=plan["runner"]:raise ValueError("PREPARED_EXECUTABLE_BINDING_DIFFERS")
    result=subprocess.run(command,stdin=subprocess.DEVNULL)
    raise SystemExit(result.returncode)
if __name__=="__main__":main()
