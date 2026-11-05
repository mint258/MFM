"""Allocated3642 native diagnostics; original46201 and all pool versions unchanged."""
import argparse
import collections
from concurrent.futures import ProcessPoolExecutor
import hashlib
import io
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import traceback
import unittest
from ..alpha_runtime_v1 import common as Q
from ..pubchem_alpha_technical_unknown_audit_v1.scan import frame
from ..pubchem_alpha_technical_unknown_audit_v1.core import classify,COUNTS
from .native import initialize,diagnose


def read(ref):
    Q.need(ref['bytes']<=2<<20,'Pinned small diagnostic metadata only')
    return Q.load(Q.verify(ref))


def admit(plan,proof,plan_path,proof_path):
    from ..alpha_runtime_v1.profile import admit as actual
    if 'reviewed_storage_budget_reference' in plan:
        budget=read(plan['reviewed_storage_budget_reference'])
        Q.need(budget['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2' and budget['reviewer']=='root'
            and budget['endpoint']==plan['endpoint']=='218.192.171.238:22' and budget['uid']==plan['uid']==1264
            and budget['quota_root']==plan['quota_authority']['quota_root']
            and budget['scope_total_caps_bytes']['reports']==plan['output_cap_bytes']
            and budget['other_future_reserved_bytes_for_each_scope']['reports']==plan['other_future_reserved_bytes']
            and budget['minimum_free_after_all_future_bytes']==plan['minimum_free_bytes'],
            'Exact reviewed aggregate report cap/future/floor authority, not old resource constants')
    authority=actual(plan,minimum_workers=16)
    request=proof['request']
    Q.need(plan['schema']=='PUBCHEM_ALPHA_GENERIC_UNKNOWN_DIAGNOSTIC_PLAN_V1'
        and plan['scope_key']==request['scope_key']=='pubchem_alpha_generic_unknown_diagnostic_v1'
        and plan['workers']==16,'Exact scoped sixteen-worker diagnostic')
    Q.need(request['producer_plan_reference']==Q.reference(plan_path)
        and request['execution_argv']==plan['execution_argv']
        and sys.argv[-4:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)]
        and request['execution_argv'][-4:]==sys.argv[-4:],'Actual exact plan and command')
    Q.need(proof['endpoint']==plan['endpoint']=='218.192.171.238:22'
        and proof['uid']==plan['uid']==os.getuid()==1264 and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID')
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'Actual Alpha UID/job/boot')
    refs={r['path']:r for r in request['source_references']}
    from ..pubchem_alpha_technical_unknown_audit_v1 import core,scan
    for path in [*Path(__file__).parent.glob('*.py'),Path(core.__file__),Path(scan.__file__)]:
        Q.need(refs.get(str(path.absolute()))==Q.reference(path),'Actual new and borrowed metadata source pins')
    for ref in request['source_references']:
        Q.need(ref['bytes']<=2<<20,'Source inventory cannot disguise input data');Q.verify(ref)
    return authority


def extract(plan,out,guard):
    ref=plan['technical_audit_receipt_reference'];audit=read(ref);facts=read(plan['technical_audit_actual_reference'])
    Q.need(facts['schema']=='ROOT_ALPHA_TECHNICAL_UNKNOWN_METADATA_AUDIT_ACTUAL_ACCEPTANCE_V1'
        and facts['status']=='ACCEPTED_DIAGNOSTIC_FACTS_NO_SCIENTIFIC_ADOPTION'
        and facts['reviewer']=='root' and facts['producer_receipt_reference']==ref
        and facts['scientific_acceptance'] is False and facts['technical_recovery_accepted'] is False,
        'Actual closed diagnostic facts, no scientific adoption fabricated')
    account=facts['actual_accounting']
    Q.need(account['job_id']=='1885173' and account['state']=='COMPLETED' and account['exit_code']=='0:0'
        and account['uid']==1264,'Actual1885173C0 source diagnostic')
    r=audit['result']
    Q.need(audit['schema']=='PUBCHEM_ALPHA_TECHNICAL_UNKNOWN_AUDIT_PRODUCER_V1'
        and audit['profile_admission']['job_id']=='1885173' and audit['profile_admission']['uid']==1264
        and r['source_endpoint']=='218.192.171.238:22' and r['source_uid']==1264
        and r['technical_rows']==46201 and r['source_rows']==124857440
        and r['all_source_counts']==COUNTS and r['logical_descriptors']==500 and r['physical_fragments']==502
        and r['original_technical_UNKNOWN_retained'] is True,'Exact whole source scientific census retained')
    source_plan=read(r['source_references']['original_handoff_plan_reference'])
    original_refs={Path(x['path']).name:x for x in source_plan['original_science_references']}
    Q.need(set(original_refs)=={'common.py','screen.py','features_legacy_compatible_v2.py','features_generic_candidate_v1.py'},
        'All four original frozen Alpha scientific modules')
    for original in original_refs.values():Q.verify(original)
    tasks=[];seen=set();counts=collections.Counter();body_frames=[]
    extras=out/'other57_original_evidence_only.DATA.jsonl';selected=out/'selected3642_original_source_manifest.DATA.jsonl'
    Q.need(len(r['DATA'])==len(r['fragment_receipts'])==502,'All502 audit DATA references')
    with extras.open('xb') as other,selected.open('xb') as selection:
        for data_ref,fragment_ref in zip(r['DATA'],r['fragment_receipts']):
            guard.check();fragment=read(fragment_ref)
            Q.need(fragment['DATA']==data_ref,'Exact existing closed audit fragment DATA')
            path=Path(data_ref['path']);before=frame(path.lstat());digest=hashlib.sha256();offset=0;lines=0
            with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
                Q.need(frame(os.fstat(stream.fileno()))==before,'Current opened diagnostic DATA frame')
                for raw in stream:
                    digest.update(raw);lines+=1;v=json.loads(raw);row=v['original_typed_fields'];ordinal=row['ordinal']
                    Q.need(raw.endswith(b'\n') and ordinal not in seen and row['category']=='technicalUnresolved'
                        and classify(row)==v['recorded_exception_observation'],'Exact unique unchanged original recorded evidence')
                    Q.need(hashlib.sha256(row['source_smiles'].encode('utf-8')).hexdigest()==row['source_smiles_sha256'],
                        'Exact original whole source SMILES hash')
                    seen.add(ordinal);observation=v['recorded_exception_observation']
                    item=dict(DATA_reference=data_ref,record_ordinal_1based=lines,byte_offset=offset,bytes=len(raw),
                        sha256=hashlib.sha256(raw).hexdigest(),observation=v)
                    if observation['generic_RemoveHs_AtomValence_trace_candidate']:
                        Q.need(len(observation['errors'])==1 and observation['errors'][0]['exception_type']=='AtomValenceException'
                            and row['audit_parse_succeeded'] is True,'Exact witnessed generic exception scope')
                        tasks.append(item);counts['generic3642']+=1;selection.write(Q.canonical(item)+b'\n')
                    elif observation['errors']:
                        Q.need(len(observation['errors'])==1,'Exact one original other exception')
                        e=observation['errors'][0];kind=e['exception_type'];frames=e['traceback_frames']
                        if kind=='KekulizeException':
                            Q.need(frames[-1]['function']=='MolToInchiKey'
                                and frames[-1]['path'].endswith('/rdkit/Chem/inchi.py')
                                and any(f['path'].endswith('/screen.py') and f['function']=='features' and f['line']==56 for f in frames),
                                'Original56 exact InChI call trace, no generic claim')
                            counts['InChI56']+=1
                        else:
                            Q.need(kind=='ValueError' and e['message']=='Invalid full InChIKey'
                                and row['cid_source_ascii']=='15525738' and ordinal==11509755
                                and any(f['function']=='wp5_key' for f in frames),'Exact original one full-key validation error')
                            counts['wp5key1']+=1
                        other.write(Q.canonical(dict(source=item,evidence_only=True,original_trace_unchanged=True,
                            chemistry_attempted=False,InChI_or_raw_graph_repair_attempted=False,cause_inferred=False))+b'\n')
                    else:
                        Q.need(row['technical_codes']==['LEGACY_NON_X_REASON_PRESERVED:PARSE_FAILED']
                            and row['audit_parse_succeeded'] is False,'Original42502 parse-failed evidence')
                        counts['parse_failed42502']+=1
                    offset+=len(raw)
                Q.need(frame(os.fstat(stream.fileno()))==before==frame(path.lstat())
                    and offset==data_ref['bytes']==before['st_size'] and lines==data_ref['rows']
                    and digest.hexdigest()==data_ref['sha256'],'Fresh complete same-file audit DATA SHA/rows')
            body_frames.append(dict(reference=data_ref,current_frame=before,fresh_full_DATA_SHA_verified=True))
        for stream in (other,selection):stream.flush();os.fsync(stream.fileno())
    Q.need(len(seen)==46201 and dict(counts)==dict(generic3642=3642,InChI56=56,wp5key1=1,parse_failed42502=42502),
        'Complete exact46201 evidence partition, no scope change')
    return tasks,original_refs,dict(counts=dict(counts),current_closed_audit_DATA_frames=body_frames,
        other57_original_evidence_only=dict(Q.reference(extras),rows=57),selected3642_original_manifest=dict(Q.reference(selected),rows=3642),
        all_source_audit_DATA_freshly_SHA_verified=True,source_audit_DATA_bytes=sum(x['bytes'] for x in r['DATA']),
        original93GB_typed_bodies_reopened=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path)
    p.add_argument('--startup-proof',required=True,type=Path);a=p.parse_args()
    plan=Q.load(a.plan);proof=Q.load(a.startup_proof);authority=admit(plan,proof,a.plan,a.startup_proof)
    from ..alpha_runtime_v1.guard import Guard
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False)
        from ..generic_representation_repair_v1.test_metadata import Metadata
        transcript=io.StringIO();tests=unittest.TextTestRunner(stream=transcript,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Metadata))
        tested=Q.write(out/'shared_library_metadata_tests.json',dict(tests=tests.testsRun,errors=len(tests.errors),
            failures=len(tests.failures),skips=len(tests.skipped),transcript=transcript.getvalue()))
        Q.need(tests.testsRun==2 and tests.wasSuccessful() and not tests.skipped,'Existing shared library metadata boundaries')
        tasks,original_refs,source=extract(plan,out,guard)
        directory=out/'workers';directory.mkdir();ctx=mp.get_context('spawn');barrier=ctx.Barrier(16)
        counts=collections.Counter();output=out/'native3642_diagnostic.DATA.jsonl';total=0
        with ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,
                initargs=(plan,barrier,str(directory),original_refs)) as pool,output.open('xb') as stream:
            for result in pool.map(diagnose,tasks,chunksize=1):
                guard.check();stream.write(Q.canonical(result)+b'\n');counts[result['diagnostic_status']]+=1;total+=1
                if total%64==0:print(json.dumps(dict(event='GENERIC_UNKNOWN_NATIVE_DIAGNOSTICS',completed=total,expected=3642)),flush=True)
            stream.flush();os.fsync(stream.fileno())
        workers=[Q.reference(path) for path in sorted(directory.glob('worker_*.json'))]
        Q.need(total==3642 and len(workers)==16,'Complete exact3642 native diagnostic/16 actual worker proofs')
        Q.write(out/'receipt.json',dict(schema='PUBCHEM_ALPHA_GENERIC_UNKNOWN_DIAGNOSTIC_PRODUCER_V1',
            status='COMPLETE_DIAGNOSTIC_NO_SCIENTIFIC_ADOPTION',plan_reference=Q.reference(a.plan),
            startup_proof_reference=Q.reference(a.startup_proof),profile_admission=authority,source=source,
            shared_library_metadata_tests=tested,DATA=dict(Q.reference(output),rows=3642),diagnostic_counts=dict(counts),
            actual_worker_proofs=workers,source_original_UNKNOWN_rows=46201,original_UNKNOWNs_modified=0,
            other_InChI56_or_wp5key1_chemistry_or_repair_attempts=0,raw_graph_or_InChI_repair=False,
            pool_minCID_baseline_or_source_scope_changed=False,scientific_acceptance=False,
            actual_parent_C0_pending_root_readback=True,runtime=guard.receipt()))
    except BaseException as exc:
        if out.is_dir():Q.write(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),
            partials_retained=True,pool_or_original_UNKNOWN_modified=False))
        raise
    finally:guard.close()


if __name__=='__main__':main()
