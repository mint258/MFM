"""Alpha launcher metadata entry; directly dispatch the unchanged full-pool run."""
import argparse
import os
from pathlib import Path
import sys
from ..alpha_runtime_v1 import common as Q, profile
from . import run as scientific

MODULE = 'workflows.expansion.exact_nn_cached_v1.alpha_full_pool_entry'


def identity():
    return dict(uid=os.getuid(), endpoint=Q.ENDPOINT, job_id=os.environ.get('SLURM_JOB_ID'),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def small_path(path):
    Q.need(Q.frame(path)[2] <= 2 << 20, 'Small pinned launcher/plan/query metadata only')
    ref = Q.reference(path)
    body = Q.load(path)
    Q.need(Q.reference(path) == ref, 'Metadata changed while reading')
    return body, ref


def execute(plan_path, startup_proof):
    plan_path, startup_proof = Path(plan_path), Path(startup_proof)
    plan, plan_ref = small_path(plan_path)
    proof, unused = small_path(startup_proof)
    Q.need(plan.get('schema') == 'PUBCHEM_EXACT_CACHED_NN_PLAN_V1'
        and 'max_queries' not in plan, 'Full-pool entry rejects every max_queries override')
    actual = profile.admit(plan, minimum_workers=16)
    native = identity(); request = proof['request']; argv = plan['execution_argv']
    Q.need(native['uid'] == plan['uid'] == proof['uid'] == actual['uid'] == 1264
        and plan['endpoint'] == proof['endpoint'] == actual['endpoint'] == Q.ENDPOINT
        and native['job_id'] and str(proof['job_id']) == actual['job_id'] == native['job_id']
        and native['boot_id'] == proof['boot_id'], 'Actual Alpha UID/endpoint/Slurm job/boot required')
    Q.need(plan.get('scope_key') and request['scope_key'] == plan['scope_key']
        and request['producer_plan_reference'] == plan_ref
        and request['execution_argv'] == argv, 'Exact native launcher scope/plan pin/argv binding')
    Q.need(len(argv) == 9 and argv[0] == sys.executable
        and argv[1:3] == ['-I', '-B'] and Path(argv[3]).is_absolute() and argv[4] == MODULE
        and argv[5:] == ['--plan', str(plan_path), '--startup-proof', str(startup_proof)]
        and sys.argv[1:] == argv[5:], 'Exact isolated guarded-entry module and current command arguments')
    for path in (Path(__file__), Path(scientific.__file__), Path(argv[3])):
        ref = Q.reference(path)
        Q.need(ref in request['source_references'] and ref in plan['code_references'],
            'Actual entry, original run and guarded-launcher source pins required')
    # This is only small metadata. The original function retains all full input
    # body SHA, typed all11/filter/population gates, exact math and completion.
    Q.need(plan['query_manifest']['bytes'] <= 2 << 20, 'Small complete query-manifest reference required')
    query = Q.load(Q.verify(plan['query_manifest']))
    Q.need(query.get('schema') in ('EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1',
            'expansion_decontaminated_query_projection_v1') and query.get('status') == 'COMPLETE'
        and type(query['projection']['rows']) is int and query['projection']['rows'] > 0,
        'Closed complete decontaminated full-pool query manifest; no cost-pilot projection')
    # Direct call: no FunctionType clone, Guard replacement, global rebinding,
    # fresh statistical receipt or body verification outside the original run.
    return scientific.run(plan_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--startup-proof', required=True, type=Path)
    args = parser.parse_args()
    execute(args.plan, args.startup_proof)


if __name__ == '__main__':
    main()
