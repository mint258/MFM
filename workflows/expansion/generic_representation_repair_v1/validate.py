"""Actual native validation of versioned representation repair; no Common emit."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import io
import json
import multiprocessing as mp
import os
from pathlib import Path
import unittest
from . import library as L
from ..alpha_common_hold_native_diagnostic_v1 import contracts as NC
from ..alpha_common_hold_native_diagnostic_v1.run import CONTROLS
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.profile import admit
from ..alpha_runtime_v1.guard import Guard
from ..alpha_common_graph_continuation_v1 import io as I

STATE=None


def initialize(plan,barrier,directory):
    global STATE
    try:
        for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
        STATE=L.initialize()
        declared={r['path']:r for r in plan['code_references']+plan.get('scientific_source_references',[])}
        for proof in STATE['source_proof']['private_function_proofs']:
            path=proof['original_source_path'];I.need(declared.get(path)==Q.reference(path),'Exact original source for private AST-derived function')
        for path in (Path(L.__file__),Path(L.N.__file__),Path(STATE['official']['installed_source']['path'])):
            I.need(declared.get(str(path))==Q.reference(path),'Actual repair/native/official source dependency pin')
        Q.write(Path(directory)/('worker_%s.json'%os.getpid()),dict(uid=os.getuid(),job_id=os.environ['SLURM_JOB_ID'],pid=os.getpid(),source_proof=STATE['source_proof']))
        barrier.wait()
    except BaseException:
        barrier.abort()
        raise


def ready(index):return dict(index=index,pid=os.getpid(),initialized=STATE is not None)


def compare(task):
    value=L.evaluate(None,task['source_smiles'],0);f=value['features']
    if task['kind']=='normal':
        original=STATE['original_kernel'](None,task['source_smiles'],0)
        I.need(value['original_kernel_passed'] and not value['representation_repair_applied']
          and I.canonical(f)==I.canonical(original),'Every original normal feature byte must remain unchanged')
        return dict(task=task,normal_original_all_feature_bytes_equal=True,evaluation=value,worker_pid=os.getpid())
    native=task['native'];stages=native['stages'];atoms=native['independent_original_template_parse']['result']['atoms']
    from collections import Counter
    counts=Counter(a['atomic_number'] for a in atoms if a['atomic_number']!=1)
    expected=dict(full_key=stages['independent_template_full_InChIKey']['result'],
      isomeric_smiles=stages['independent_template_canonical_isomeric_SMILES']['result'],
      ecfp4_2048_hex=stages['independent_template_ECFP4_2048']['result'],reasons=[],
      source_smiles=task['source_smiles'],cid=None,ordinal=0,heavy_atoms=sum(counts.values()),elements=sorted(counts),
      non_h_composition=json.dumps(sorted(counts.items()),separators=(',',':')),
      element_combination=','.join(map(str,sorted(counts))),isotopic_atoms=sum(a['isotope']>0 for a in atoms))
    from .. import screen
    expected['wp5_key']=screen.wp5_key(expected['full_key'])
    for name,event in stages.items():
        if name.startswith('independent_original_template_descriptor.'):
            I.need(event['status']=='PASS','Old native independent non-generic descriptor must have passed')
            expected[name.split('.',1)[1]]=event['result']
    whole=native['whole_Murcko_generic_stages']['diagnostic_deferred_sanitize_candidate']
    expected['generic_murcko']=whole['key'];rings=[]
    for fragment in native['ring_fragments']:
        event=fragment.get('generic_stages_after_original_fragment_sanitize')
        if event is None:
            I.need(fragment['exact_original_fragment_sanitize']['exception_type']=='KekulizeException','Only original exact ring fallback allowed')
            event=fragment['generic_stages_on_uncorrupted_fragment']
        candidate=event['diagnostic_deferred_sanitize_candidate'];I.need(candidate['status']=='PASS','Actual original native candidate ring key required');rings.append(candidate['key'])
    expected['generic_ring_systems']=sorted(rings)
    # Canonical JSON preserves exact Python binary64 round-trip values; do not
    # add a numerical tolerance or substitute a different original molecule.
    differences={k:dict(actual=f.get(k),expected=v) for k,v in expected.items() if k not in f or I.canonical(f[k])!=I.canonical(v)}
    I.need(set(f)==set(expected) and not differences and value['representation_repair_applied']
      and not value['original_kernel_passed'] and value['original_error']['type']=='AtomValenceException',
      'Complete repaired119 feature schema/non-generic values/native generic keys must match exact prior native evidence')
    return dict(molecule_id=task['molecule_id'],effective_role='TRAIN',native_records=task['native_records'],
      features=f,repair_provenance=value,independent_native_all_non_generic_values_exactly_equal=True,
      independent_native_generic_keys_exactly_equal=True,worker_pid=os.getpid())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path);a=p.parse_args()
    plan=Q.load(a.plan);proof=Q.load(a.startup_proof)
    I.need(plan['schema']=='ALPHA_GENERIC_REPRESENTATION_REPAIR_VALIDATION_PLAN_V1'
      and proof['request']['producer_plan_reference']==Q.reference(a.plan) and proof['request']['execution_argv']==plan['execution_argv']
      and proof['uid']==os.getuid()==1264 and str(proof['job_id'])==os.environ['SLURM_JOB_ID']
      and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'Actual new independent Alpha validation parent')
    for path in Path(__file__).parent.glob('*.py'):I.need(Q.reference(path) in proof['request']['source_references'],'Current repair package pinned in startup')
    actual=admit(plan);out=Path(plan['output_directory']);I.need(not out.exists(),'Fresh validation output');out.mkdir(parents=True);guard=Guard(plan)
    try:
        from .test_metadata import Metadata
        log=io.StringIO();tests=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Metadata))
        I.need(tests.testsRun==2 and tests.wasSuccessful() and not tests.skipped,'Repair2 metadata boundaries before DATA')
        testref=I.save(out/'metadata_tests2.json',dict(tests=2,failures=0,errors=0,skips=0,transcript=log.getvalue()))
        native=I.read(plan['native_diagnostic_receipt_reference']);account=I.read(plan['native_diagnostic_actual_accounting_reference'])
        I.need(account.get('schema')=='ROOT_ALPHA_COMMON_GENERIC_DIAGNOSTIC_ACTUAL_ACCEPTANCE_V1'
          and account.get('status')=='ACCEPTED_DIAGNOSTIC_FACTS_NO_PRODUCTION_ADOPTION'
          and account.get('reviewer')=='root' and account.get('producer_receipt_reference')==plan['native_diagnostic_receipt_reference']
          and account.get('diagnostic_candidate_adopted') is False,'Actual Root diagnostic facts, without fabricated old production adoption')
        parent=NC.actual_c0(account,native['job_id']);I.need(str(native['job_id'])=='1885171' and native['HOLD_MIDs']==119 and native['native_records']==352
          and native['kernel_or_chemical_rules_modified'] is False and native['diagnostic_candidate_adopted'] is False,'Exact original native119 diagnostic authority')
        raw=account['raw_sacct_reference'];I.need(Q.reference(raw['path'])==I.triple(raw),'Actual native raw accounting pin')
        body=I.Body(native['native_stage_DATA'],guard);tasks=[]
        try:
            for raw in body.stream:
                value=json.loads(raw);task=value['task'];I.need(task['kind']=='original_HOLD','Only original119 single-source graphs')
                tasks.append(dict(kind='repair',molecule_id=task['molecule_id'],source_smiles=task['source_smiles'],native_records=task['native_records'],native=value))
            I.need(len(tasks)==len({t['molecule_id'] for t in tasks})==119 and sum(t['native_records'] for t in tasks)==352,'Exact119/352 native validation scope')
            body.check();inputframe=list(body.frame)
        finally:body.close()
        directory=out/'workers';directory.mkdir();ctx=mp.get_context('spawn');barrier=ctx.Barrier(16)
        with ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,initargs=(plan,barrier,str(directory))) as pool:
            startup=list(pool.map(ready,range(16)));normal=list(pool.map(compare,[dict(kind='normal',source_smiles=s) for s in CONTROLS]))
            normal_ref=I.save(out/'normal8_all_original_feature_bytes.json',dict(cases=normal,startup16=startup))
            path=out/'repaired119_complete_features.DATA.jsonl';count=records=0
            with path.open('xb') as stream:
                for value in pool.map(compare,tasks):
                    guard.check();stream.write(I.canonical(value));count+=1;records+=value['native_records']
                stream.flush();os.fsync(stream.fileno())
        worker_refs=[Q.reference(p) for p in sorted(directory.glob('worker_*.json'))]
        I.need(len(worker_refs)==16 and count==119 and records==352,'Actual16 native validation workers/full119 complete features')
        I.save(out/'receipt.json',dict(schema='ALPHA_GENERIC_REPRESENTATION_REPAIR_VALIDATION_PRODUCER_V1',
          status='COMPLETE_PENDING_ACTUAL_ALPHA_C0_AND_ROOT_TECHNICAL_REVIEW',plan=Q.reference(a.plan),startup_proof=Q.reference(a.startup_proof),
          uid=os.getuid(),job_id=os.environ['SLURM_JOB_ID'],profile_admission=actual,metadata_tests=testref,
          normal8_all_original_feature_bytes=normal_ref,repaired119_complete_features=I.pin(path,guard.check),actual_worker_proofs=worker_refs,
          native_diagnostic_receipt_reference=plan['native_diagnostic_receipt_reference'],native_diagnostic_actual_accounting_reference=plan['native_diagnostic_actual_accounting_reference'],
          native_DATA_current_frame=inputframe,HOLD_MIDs_repaired=119,native_records_repaired=352,
          original_kernel_passed_for_repaired119=False,original_failures_preserved=True,all_non_generic_values_exactly_equal=True,
          all_normal_success_feature_bytes_unchanged=True,representation_version=L.VERSION,
          chemical_rules_changed=False,original_graph_changed=False,frozen_or_installed_code_modified=False,
          Common_reference_emitted=False,scientific_or_training_release=False,runtime=guard.receipt()))
    finally:guard.close()


if __name__=='__main__':main()
