"""Allocated Alpha entry for the existing synthetic native UFF smoke only."""
import argparse
import os
from pathlib import Path
import traceback
from workflows.expansion.alpha_runtime_v1 import common as Q,profile
from workflows.expansion.alpha_runtime_v1.guard import Guard


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--startup-proof',type=Path,required=True)
    args=parser.parse_args();plan=Q.load(args.plan);proof=Q.load(args.startup_proof)
    admission=profile.admit(plan,minimum_workers=16);request=proof['request']
    Q.need(plan['schema']=='ALPHA_UFF_NATIVE_SMOKE_PLAN_V1'
      and request['scope_key']==plan['scope_key']=='alpha_uff_native_smoke_v1'
      and request['producer_plan_reference']==Q.reference(args.plan),'ACTUAL_ALPHA_NATIVE_SMOKE_PLAN')
    Q.need(request['execution_argv']==plan['execution_argv']
      and plan['execution_argv'][plan['execution_argv'].index('--plan')+1]==str(args.plan)
      and plan['execution_argv'][plan['execution_argv'].index('--startup-proof')+1]==str(args.startup_proof),
      'ACTUAL_NATIVE_SMOKE_STARTUP_ARGV')
    Q.need(str(proof['job_id'])==os.environ['SLURM_JOB_ID'] and proof['uid']==os.getuid()==1264
      and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
      'REAL_ALPHA_NATIVE_SMOKE_PARENT')
    Q.need(Q.reference(__file__) in request['source_references'],'CURRENT_NATIVE_SMOKE_WRAPPER_SOURCE_PIN')
    output=Path(plan['output_directory']);guard=Guard(plan)
    try:
        guard.check();Q.need(not output.exists(),'FRESH_NATIVE_SMOKE_OUTPUT');output.mkdir(parents=True)
        capsule_ref=plan['source_capsule_reference'];Q.verify(capsule_ref)
        # Resolve and verify the real transported original sources before the
        # native adapter/smoke module can load original numerical functions.
        from workflows.expansion.portable_sources_v1.kernel import get_capsule
        capsule=get_capsule(capsule_ref);capsule.load();guard.check()
        from workflows.expansion.uff3_candidate_v1 import native_smoke
        result=native_smoke.run(output/'native',capsule_ref)
        guard.sample();guard.check()
        Q.write(output/'receipt.json',dict(schema='ALPHA_UFF_NATIVE_SMOKE_PRODUCER_V1',status=result['status'],
          plan_reference=Q.reference(args.plan),startup_proof_reference=Q.reference(args.startup_proof),
          source_capsule_reference=capsule_ref,native_result_reference=Q.reference(output/'native/result.json'),
          profile_admission=admission,resources=guard.receipt(),endpoint='218.192.171.238:22',
          uid=os.getuid(),job_id=os.environ['SLURM_JOB_ID'],fixtures_only_no_candidate_release=True,
          actual_parent_C0_pending_Root_accounting=True,production_run_started=False,
          scientific_function_objects_changed=False,new_PM7_xTB_Pprime_calls=0))
    except BaseException as exc:
        if output.is_dir():Q.write(output/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),
          resources=guard.receipt(),partials_retained=True,fixtures_only_no_candidate_release=True))
        raise
    finally:guard.close()


if __name__=='__main__':main()
