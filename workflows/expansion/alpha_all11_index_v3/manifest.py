"""Portable I/O seam for the unchanged original V3 compose code object."""
import argparse
import json
from pathlib import Path
import traceback
from types import FunctionType
from .reader import Reader,S
from .runtime import admit
from .science import initialize


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan=json.loads(args.plan.read_text());proof=json.loads(args.startup_proof.read_text())
    authority=admit(plan,proof,args.plan,args.startup_proof,'ALPHA_ALL11_SOURCE_MANIFEST_PLAN_V3','alpha_all11_manifest_v3')
    from workflows.expansion.alpha_runtime_v1.guard import Guard
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False);C,M,objects=initialize(proof);reader=Reader(plan,guard.check)
        ready9=reader.json(plan['ready9_manifest_reference'])
        # No original module global is patched. Only this new callable has an
        # explicit read_ref I/O binding; its original compose code object is exact.
        namespace=dict(M.compose.__globals__);namespace['read_ref']=reader.json
        compose=FunctionType(M.compose.__code__,namespace,M.compose.__name__,M.compose.__defaults__,M.compose.__closure__)
        result=compose(ready9,plan['root_molnet21_acceptance_reference'],plan['root_coconut735_acceptance_reference'])
        result['prior_manifest_reference']=plan['ready9_manifest_reference']
        from .headers import approvals
        _,mol,coco=approvals(reader,result,ready9,C);guard.check()
        manifest_ref=S.save(out/'all11_source_manifest.json',result)
        S.save(out/'receipt.json',dict(schema='ALPHA_ALL11_SOURCE_MANIFEST_PRODUCER_V3',
            status='SOURCE_MANIFEST_COMPOSED_PENDING_ACTUAL_INDEX_AND_FILTER',source_manifest_reference=manifest_ref,
            plan_reference=S.pin(args.plan),startup_proof_reference=S.pin(args.startup_proof),profile_admission=authority,
            original_function_objects=objects,original_compose_code_object_identical=compose.__code__ is M.compose.__code__,
            portable_read_ref_is_explicit_IO_seam=True,original_module_globals_modified=False,
            actual_prior_user_scope_disposition_ids=sorted(coco['scope_source_ids']),
            source_consumption=S.save(out/'source_consumption.json',dict(files=reader.consumption)),runtime=guard.receipt(),
            current_adapter_creates_new_user_or_scientific_approval=False,index_or_filter_created=False,
            actual_parent_C0_pending_root_readback=True,global_pool_release=False))
    except BaseException as exc:
        if out.is_dir():S.save(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),
            partials_retained=True,pending_scope_not_approved_by_adapter=True,index_or_filter_created=False))
        raise
    finally:guard.close()


if __name__=='__main__':main()
