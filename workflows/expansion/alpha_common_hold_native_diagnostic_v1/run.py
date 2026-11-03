"""Diagnostic-only native119 stage traces; never repairs kernel or Common."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import collections
import io
import json
import multiprocessing as mp
import os
from pathlib import Path
import unittest
from . import science,contracts
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.profile import admit
from ..alpha_runtime_v1.guard import Guard
from ..alpha_common_graph_continuation_v1 import io as I

CONTROLS=('CC','c1ccccc1','c1ncccc1','c1[nH]ccc1','C1[C@](Cl)(F)O1','c1ccc2ccccc2c1','C1CCC2(CC1)CCCCC2','CC(=O)N1CCCCC1')


def inputs(plan,guard):
    receipt=I.read(plan['hold_audit_receipt_reference']);account=I.read(plan['hold_audit_actual_accounting_reference'])
    I.need(account.get('schema')=='ROOT_ALPHA_COMMON_HOLD119_METADATA_AUDIT_ACTUAL_ACCEPTANCE_V1'
      and account.get('status')=='ACCEPTED_COMPLETE_ORIGINAL_HOLD_EVIDENCE_ONLY'
      and account.get('reviewer')=='root' and account.get('producer_receipt_reference')==plan['hold_audit_receipt_reference']
      and account.get('complete_Common_reference_accepted') is False,'Independent actual original audit acceptance, no scientific reference release')
    parent=contracts.actual_c0(account,receipt['job_id'])
    raw=account['raw_sacct_reference'];I.need(Q.reference(raw['path'])==I.triple(raw),'Actual audit raw accounting bytes required')
    I.need(receipt['schema']=='ALPHA_COMMON_HOLD119_METADATA_AUDIT_PRODUCER_V1'
      and str(receipt['job_id'])=='1885169' and receipt['uid']==1264
      and receipt['HOLD_MIDs']==119 and receipt['native_records']==352
      and receipt['graph_selection_or_repair_applied'] is False and receipt['complete_Common_reference_accepted'] is False,
      'Exact original119/352 no-repair audit required')
    body=I.Body(receipt['exact_HOLD_evidence'],guard);tasks=[]
    try:
        for ordinal,raw in enumerate(body.stream):
            guard.check();row=json.loads(raw);sources=row['original_Creator_source_rows']
            variants={s['original_selection']['variant_id']:s['original_selection']['source_smiles_for_original_template'] for s in sources}
            native=row['diagnosis']['graph_variant_results']
            I.need(len(variants)==len(native)==1 and native[0]['status']=='FEATURE_COMPUTE_UNRESOLVED'
              and native[0]['error']['type']=='AtomValenceException' and set(variants)=={native[0]['variant_id']}
              and row['effective_role']=='TRAIN' and len(sources)==row['native_records'],'All119 original single unresolved AtomValence variants retained')
            variant,smiles=next(iter(variants.items()));I.need(isinstance(smiles,str) and smiles,'Exact original Creator template source')
            tasks.append(dict(kind='original_HOLD',molecule_id=row['molecule_id'],ordinal=ordinal,
              source_smiles=smiles,variant_id=variant,native_records=len(sources),original_audit_evidence_reference=body.reference,
              original_native_error=native[0]['error']))
        I.need(len(tasks)==len({t['molecule_id'] for t in tasks})==119 and sum(t['native_records'] for t in tasks)==352,'Whole119/352 input census')
        body.check();return tasks,dict(audit_receipt=plan['hold_audit_receipt_reference'],actual_parent=parent,
          actual_accounting_reference=plan['hold_audit_actual_accounting_reference'],DATA_reference=body.reference,DATA_frame=list(body.frame))
    finally:body.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path);a=p.parse_args()
    plan=Q.load(a.plan);proof=Q.load(a.startup_proof)
    I.need(plan['schema']=='ALPHA_COMMON_HOLD119_NATIVE_DIAGNOSTIC_PLAN_V1'
      and plan.get('diagnostic_candidate_adoption_authorized') is False
      and proof['request']['producer_plan_reference']==Q.reference(a.plan) and proof['request']['execution_argv']==plan['execution_argv']
      and proof['uid']==os.getuid()==1264 and str(proof['job_id'])==os.environ['SLURM_JOB_ID']
      and proof['endpoint']=='218.192.171.238:22' and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'Actual independent native diagnostic parent')
    for path in Path(__file__).parent.glob('*.py'):I.need(Q.reference(path) in proof['request']['source_references'],'Current diagnostic package source pin required')
    I.need(plan['official_Murcko_source_reference'] in proof['request']['source_references'],'Actual installed official Murcko source must be declared')
    Q.verify(plan['official_Murcko_source_reference'])
    actual=admit(plan,minimum_workers=16);out=Path(plan['output_directory']);I.need(not out.exists(),'Fresh diagnostic output preserving old HOLDs');out.mkdir(parents=True)
    guard=Guard(plan)
    try:
        from .test_metadata import Metadata
        transcript=io.StringIO();tests=unittest.TextTestRunner(stream=transcript,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Metadata))
        I.need(tests.testsRun==2 and tests.wasSuccessful() and not tests.skipped,'Exact2 metadata tests before DATA/native')
        test_ref=I.save(out/'metadata_tests2.json',dict(tests=tests.testsRun,failures=len(tests.failures),errors=len(tests.errors),skips=len(tests.skipped),transcript=transcript.getvalue()))
        tasks,origin=inputs(plan,guard);workers=out/'workers';workers.mkdir();ctx=mp.get_context('spawn');barrier=ctx.Barrier(16)
        controls=[dict(kind='normal_degree_le4_control',source_smiles=s,ordinal=i) for i,s in enumerate(CONTROLS)]
        with ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=science.initialize,initargs=(plan,barrier,str(workers))) as pool:
            ready=list(pool.map(science.worker_ready,range(16)))
            I.need(len(ready)==16 and all(v['uid']==1264 and v['original_native_sources_loaded'] for v in ready),'Sixteen startup tasks submitted before the16-worker barrier/8controls')
            control_results=list(pool.map(science.diagnose,controls))
            for value in control_results:
                guard.check();events=[value['whole_Murcko_generic_stages']];ring_keys=[]
                I.need(value['original_full_features_candidate']['status']=='PASS'
                  and value['original_full_features_candidate']['result'].get('reasons')==[], 'Normal neutral control original kernel must pass')
                for fragment in value['ring_fragments']:
                    if fragment['exact_original_fragment_sanitize']['status']=='PASS':
                        event=fragment['generic_stages_after_original_fragment_sanitize']
                    else:
                        I.need(fragment['exact_original_fragment_sanitize']['exception_type']=='KekulizeException',
                          'Only unchanged original compatibility fallback may bypass ring pre-sanitize')
                        event=fragment['generic_stages_on_uncorrupted_fragment']
                    events.append(event);ring_keys.append(event['diagnostic_deferred_sanitize_candidate'].get('key'))
                for event in events:
                    I.need(all(a['heavy_degree']<=4 for a in event['source_snapshot']['atoms'])
                      and event['official_and_candidate_keys_exactly_equal'],'Every normal-control original Murcko/ring key must match candidate exactly')
                original=value['original_full_features_candidate']['result']
                I.need(original['generic_murcko']==events[0]['diagnostic_deferred_sanitize_candidate']['key']
                  and original['generic_ring_systems']==sorted(ring_keys),
                  'Candidate normal-control keys must equal full original frozen kernel values, including original ring pre-sanitize order')
            controls_ref=I.save(out/'native_normal_controls8.json',dict(cases=control_results,source_startup_tasks16=ready,
              original_keys_exactly_equal_for_all_normal_controls=True,adoption_authorized=False))
            data=out/'hold119_native_stages.DATA.jsonl';observed=[]
            with data.open('xb') as stream:
                for value in pool.map(science.diagnose,tasks):
                    guard.check();stream.write(I.canonical(value));observed.append(value)
                stream.flush();os.fsync(stream.fileno())
        proofs=[Q.reference(p) for p in sorted(workers.glob('worker_*.json'))]
        I.need(len(proofs)==16 and len(observed)==119,'Actual16fresh workers and full119 native diagnostics')
        exceptions=collections.Counter(v['original_full_features_candidate'].get('exception_type',v['original_full_features_candidate']['status']) for v in observed)
        source_proofs=[Q.load(Q.verify(p)) for p in proofs]
        I.need(all(p['uid']==1264 and p['job_id']==os.environ['SLURM_JOB_ID'] for p in source_proofs),'Honest native worker UID/job proofs')
        I.save(out/'receipt.json',dict(schema='ALPHA_COMMON_HOLD119_NATIVE_DIAGNOSTIC_PRODUCER_V1',
          status='DIAGNOSTIC_COMPLETE_PENDING_ACTUAL_ALPHA_C0_AND_ROOT_SCIENTIFIC_REVIEW',plan=Q.reference(a.plan),startup_proof=Q.reference(a.startup_proof),
          uid=os.getuid(),job_id=os.environ['SLURM_JOB_ID'],profile_admission=actual,origin=origin,metadata_tests=test_ref,
          native_normal_controls=controls_ref,native_stage_DATA=I.pin(data,guard.check),actual_worker_proofs=proofs,
          official_Murcko_source_proof=source_proofs[0]['official_Murcko_source'],HOLD_MIDs=119,native_records=352,
          actual_original_kernel_exception_counts=dict(exceptions),original_HOLDs_preserved=True,
          kernel_or_chemical_rules_modified=False,diagnostic_candidate_adopted=False,Common_reference_emitted=False,
          filtering_or_ranking_changed=False,runtime=guard.receipt()))
    finally:guard.close()


if __name__=='__main__':main()
