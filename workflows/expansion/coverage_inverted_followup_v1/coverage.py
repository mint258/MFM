"""Thin original fixed1M coverage entry using the full-manifest compiled worker."""
import argparse
from functools import partial
import os
from pathlib import Path
from types import FunctionType
from ..alpha_runtime_v1 import common as Q, profile
from ..exact_nn_cached_v1 import coverage as original
from ..alpha_sharded_novelty_v1.run import ShardGuard
from . import general_workers
from .admission import after_equivalence


def run(plan_path, proof_path):
    plan = Q.load(plan_path); proof = Q.load(proof_path)
    actual = profile.admit(plan, minimum_workers=16); request = proof['request']
    Q.need(request['producer_plan_reference'] == Q.reference(plan_path)
           and request['execution_argv'] == plan['execution_argv']
           and str(proof['job_id']) == actual['job_id'] == os.environ['SLURM_JOB_ID']
           and proof['uid'] == actual['uid'] == 1264 and proof['endpoint'] == actual['endpoint']
           and proof['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
           'Actual scientific coverage allocation and startup binding')
    for source in [*Path(__file__).parent.glob('*.py'), Path(original.__file__), Path(general_workers.fixed_result.__code__.co_filename)]:
        Q.need(Q.reference(source) in request['source_references'], 'Actual wrapper/original native source pinned')
    equivalence_ref = after_equivalence(plan, proof, Path(plan_path).parent / 'augmented_kernel_equivalence.json')
    worker = partial(general_workers.exact_batches,
                     backend_adoption_reference=plan['backend_adoption_reference'],
                     reference_manifest_reference=plan['reference_manifest'],
                     reference_role=plan['reference_role'])
    scope = {**vars(original), 'exact_batches': worker, 'Guard': ShardGuard}
    function = FunctionType(original.run.__code__, scope, original.run.__name__,
                            original.run.__defaults__, original.run.__closure__)
    function.__kwdefaults__ = original.run.__kwdefaults__
    Q.need(function.__code__ is original.run.__code__, 'Original coverage body and fixed sample export order unchanged')
    result = function(plan_path, startup_proof=proof_path)
    root = Path(plan['output_directory'])
    candidates = [path for path in root.glob('attempt*.receipt.json') if Q.load(path) == result]
    Q.need(len(candidates) == 1, 'Actual original completed coverage receipt required')
    output = dict(result, producer_schema='CPP_FULL_MANIFEST_FIXED1M_COVERAGE_V1',
                  original_coverage_receipt_reference=Q.reference(candidates[0]),
                  original_coverage_function_code_object_preserved=True,
                  native_backend_adoption_reference=plan['backend_adoption_reference'],
                  general_worker_source_reference=Q.reference(general_workers.__file__), actual_parent=actual,
                  augmented_reference_native_equivalence_reference=equivalence_ref,
                  new_per_job_Root_acceptance_required=False)
    return Q.write(root / 'compiled_coverage_manifest.json', output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--startup-proof', required=True)
    args = parser.parse_args()
    print(run(args.plan, args.startup_proof))


if __name__ == '__main__':
    main()
