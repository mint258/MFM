"""Operational64 validation of the actual new production worker API, not a full pool."""
import argparse
import functools
import hashlib
from pathlib import Path
import struct
import unittest
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.guard import Guard
from ..exact_nn_cached_v1 import engine as old
from ..exact_nn_popcount_alpha_validate_v1 import inputs as historical
from ..exact_nn_popcount_alpha_validate_v1 import run as benchmark
from . import authority,entry,workers

MODULE='workflows.expansion.exact_nn_popcount_production_v1.validation'


def execute(plan_path,proof_path):
    plan,actual,source_refs=entry.admit(plan_path,proof_path,MODULE)
    Q.need(plan['schema']=='ALPHA_POPCOUNT_WORKER_INTEGRATION_VALIDATION_PLAN_V1'
        and plan['workers']==16,'Separate native16worker64 validation, never partial full-pool plan')
    benchmark.resources(plan);entry.scientific.allocation_guard(plan)
    guard=Guard(plan)
    try:
        out=Path(plan['output_directory']);out.mkdir(parents=True,exist_ok=False)
        adoption,packed=authority.adopted(plan['backend_adoption_reference'])
        bound=historical.read(plan['inputs_reference']);data,receipt=historical.validate_bound(bound)
        Q.need(bound['reference_manifest_reference']==adoption['reference_manifest_reference'],'Same actual196 reference as206')
        m,selected,digest,path,stamp=benchmark.queries(bound,plan,data,receipt)
        # Actual metadata-only entry fixtures, reported separately from native worker evidence.
        from . import test_wiring
        suite=unittest.defaultTestLoader.loadTestsFromModule(test_wiring)
        tests=unittest.TextTestRunner(verbosity=2).run(suite)
        Q.need(tests.wasSuccessful()and not tests.skipped,'Metadata entry fixtures must pass without skips')
        original=old.load_reference(m['fingerprints']['path'],old.file_frame(Path(m['fingerprints']['path'])),authority.N,plan['parent_rss_cap_bytes'])
        expected={i:original.nearest(raw)for i,row,raw in selected}
        old.enforce_rss(plan['parent_rss_cap_bytes']);ready=[];observed={};batches=[]
        rows=[(i,raw)for i,row,raw in selected]
        for result in workers.exact_batches(m['fingerprints']['path'],authority.N,
                (rows[i:i+4]for i in range(0,64,4)),workers=16,worker_rss_cap_bytes=plan['worker_rss_cap_bytes'],
                ready_callback=ready.append,backend_adoption_reference=plan['backend_adoption_reference']):
            for identity,raw,value in result.pop('results'):
                Q.need(type(identity)is int and 0<=identity<64 and raw==selected[identity][2]
                    and hashlib.sha256(raw).hexdigest()==data['results'][identity]['fingerprint_sha256']
                    and identity not in observed and value=={k:v for k,v in expected[identity].items()if k!='searched_popcount_groups'}
                    and struct.pack('<d',value['score'])==struct.pack('<d',expected[identity]['score']),
                    'Actual production IPC fields/F64 must match complete original oracle')
                observed[identity]=dict(result=value,fingerprint_sha256=hashlib.sha256(raw).hexdigest(),
                    score_bits=struct.pack('<d',value['score']).hex())
            batches.append(result);guard.check()
        Q.need(len(ready)==16 and len({r['worker_pid']for r in ready})==16
            and all(r['reference_records_loaded']==authority.N and 'reference_decode_calls'not in r for r in ready)
            and sorted(observed)==list(range(64)),'All16 native-only full loads and all64 query results')
        validation206=authority.read(adoption['measurements_reference']);pairs={x['query_ordinal']:x for x in validation206['paired_queries']}
        for i in range(64):
            values=observed[i]['result'];old200=data['results'][i]['result'];old206=pairs[i]['native']
            Q.need(values==old200=={k:v for k,v in old206.items()if k!='searched_popcount_groups'}
                and observed[i]['score_bits']==pairs[i]['score_bits'],'Historical200/206 exact fields/F64 bindings')
        clone=entry.clone_run(functools.partial(workers.exact_batches,backend_adoption_reference=plan['backend_adoption_reference']))
        Q.need(clone.__code__ is entry.scientific.run.__code__ and clone.__globals__['Guard']is entry.scientific.Guard,
            'Entry native batch injection leaves original code and Guard unchanged')
        Q.need(benchmark.query_stamp(path)==stamp,'Frozen1M query source changed')
        Q.verify(m['fingerprints']);Q.verify(m['keys']);guard.sample();guard.check()
        metrics=Q.write(out/'measurements.json',dict(schema='ALPHA_NATIVE_WORKER_ENTRY64_MEASUREMENTS_V1',workers=ready,
            queries=observed,original_full_results=expected,batches=batches,metadata_fixture_tests=tests.testsRun,
            query_identity_sha256=digest,QueryCache_used=False,debug_groups_in_IPC=False))
        return Q.write(out/'receipt.json',dict(schema='ALPHA_POPCOUNT_WORKER_ENTRY_INTEGRATION_VALIDATION_V1',
            status='WORKER_ENTRY_VALIDATED_PENDING_ROOT_ACTUAL_C0_REVIEW',actual_parent=actual,
            backend_adoption_reference=plan['backend_adoption_reference'],build_manifest_reference=adoption['build_manifest_reference'],
            binary_reference=adoption['binary_reference'],reference_manifest_reference=adoption['reference_manifest_reference'],
            inputs_reference=plan['inputs_reference'],production_source_references=[Q.reference(p)for p in Path(__file__).parent.glob('*.py')],
            reference_molecules=authority.N,measured_queries=64,full_reference_worker_count=16,
            all_worker_fields_and_F64_equal_original_and_206=True,entry_code_object_preserved=True,
            entry_global_changes=['exact_batches'],measurements_reference=metrics,source_references=source_refs,
            plan_reference=Q.reference(plan_path),startup_proof_reference=Q.reference(proof_path),runtime=guard.receipt(),
            metadata_entry_fixtures_mock_scientific_dispatch=True,full_pool_execution_claimed=False,
            full_pool_entry_execution_on_complete_pool=False,cache_reuse_or_training_approved=False))
    finally:guard.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();execute(a.plan,a.startup_proof)


if __name__=='__main__':main()
