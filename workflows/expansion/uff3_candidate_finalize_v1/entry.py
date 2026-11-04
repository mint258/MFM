"""Strict native Alpha candidate closure entry, fresh small private SQL stage."""
import argparse
import fcntl
import os
from pathlib import Path
import stat
from ..alpha_runtime_v1 import common as Q
from ..uff3_alpha_runtime_v1 import entry as admission
from . import producer

MODULE='workflows.expansion.uff3_candidate_finalize_v1.entry'


def execute(plan_path,proof_path):
    plan,actual,refs=admission.admit(plan_path,proof_path,module=MODULE)
    Q.need(plan['schema']=='PUBCHEM_UFF3_CANDIDATE_CLOSURE_PLAN_V1'
        and plan.get('expected_molecules',2500000)==2500000 and plan['maximum_conformers']==3,
        'Full2.5M candidate-only closure plan; never a test/prefix/future4+ release')
    proof=Q.load(proof_path);pins=[Q.reference(p)for p in Path(__file__).parent.glob('*.py')]
    Q.need(all(r in plan['code_references']and r in proof['request']['source_references']for r in pins),
           'Actual finalizer/validators/storage source pins in native startup')
    from ..uff3_alpha_runtime_v1.quality_gate import require_within_one_percent
    from ..uff3_alpha_runtime_v1.terminal import parent
    qa=admission.read(plan['qa_report_reference']);parent(qa['runtime'],plan['qa_actual_accounting_reference'])
    require_within_one_percent(qa)
    review=admission.partition(plan);routing=Path(plan['output_scope_root']);out=Path(plan['output_directory'])
    Q.need(out.parent==routing and not out.exists()and not any(p.is_symlink()for p in(out,*out.parents)),
           'Fresh independent closure stage; existing molecule/family outputs are read-only inputs')
    fd=os.open(routing/'uff_alpha_routing.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    lock=os.fdopen(fd,'a+b');fact=os.fstat(lock.fileno())
    try:
        Q.need(stat.S_ISREG(fact.st_mode)and fact.st_uid==Q.UID and fact.st_nlink==1,'Own literal routing lock')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        Q.need(all(p.name=='uff_alpha_routing.lock'for p in routing.iterdir()),'Exclusive empty closure routing scope')
        routing_bytes=admission.routing_overhead(review,routing)
        reserve=plan['metadata_wrapper_reserved_bytes']
        Q.need(type(reserve)is int and 1<<20<=reserve<plan['output_cap_bytes'],'Finite candidate manifest reserve')
        runtime={**plan,'output_scope_root':str(out),'output_cap_bytes':plan['output_cap_bytes']-reserve,
            'other_future_reserved_bytes':plan['other_future_reserved_bytes']+reserve,
            'original_launcher_plan_reference':Q.reference(plan_path),
            'original_startup_proof_reference':Q.reference(proof_path),
            'actual_routing_ancestor_allocated_bytes':routing_bytes}
        out.mkdir();derived=Q.write(out/'derived_closure_plan.json',runtime)
        result=producer.run(runtime,actual)
        result.update(original_launcher_plan_reference=Q.reference(plan_path),startup_proof_reference=Q.reference(proof_path),
            derived_runtime_plan_reference=derived,source_references=refs+pins,
            storage_partition=plan['storage_partition'])
        Q.need(len(Q.canonical(result))<reserve//2,'Actual small candidate manifest fits reserved metadata cap')
        return Q.write(out/'candidate_manifest.json',result)
    finally:lock.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();print(execute(a.plan,a.startup_proof))


if __name__=='__main__':main()