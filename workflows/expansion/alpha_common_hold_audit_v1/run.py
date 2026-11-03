"""Allocated metadata-only audit of all119 closed Alpha Common graph HOLDs."""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import unittest
import io
from . import core
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.profile import admit
from ..alpha_runtime_v1.guard import Guard
from ..alpha_common_graph_continuation_v1 import io as I
from ..common_molecular_fp_candidate_v1 import selection as S,contracts as C


def closed(plan):
    receipt=I.read(plan['common_receipt_reference']);account=I.read(plan['actual_accounting_reference'])
    I.need(account.get('schema')=='ROOT_ALPHA_FULL_COMMON_ACTUAL_TERMINAL_HOLD_V1'
      and account.get('status')=='ACTUAL_C0_SOURCE_GRAPH_HOLD_REVIEW_REQUIRED' and account.get('reviewer')=='root'
      and account.get('full_reference_accepted') is False and account.get('subset_reference_accepted') is False
      and account.get('producer_receipt_reference')==plan['common_receipt_reference'],
      'Exact independent Root terminal HOLD accounting, not scientific reference acceptance')
    raw_account=account['raw_sacct_reference']
    I.need(I.pin(raw_account['path'])==I.triple(raw_account),'Actual original raw accounting bytes')
    parents=account.get('actual_parents') or [account.get('actual_parent',{})]
    matches=[p for p in parents if str(p.get('JobIDRaw',p.get('job_id'))) == str(receipt['job_id'])]
    I.need(len(matches)==1,'Exactly one independent actual parent accounting row required')
    p=matches[0]
    I.need(p.get('State',p.get('state'))=='COMPLETED' and p.get('ExitCode',p.get('exit_code'))=='0:0'
      and str(p.get('UID',p.get('uid')))=='1264','Actual Alpha C0 required, without full-reference acceptance fiction')
    I.need(account.get('endpoint',p.get('endpoint'))=='218.192.171.238:22'
      and p.get('User','alpha')=='alpha','Actual Alpha endpoint/account, not Main parent impersonation')
    I.need(receipt['schema']=='ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1' and receipt['mode']=='full'
      and receipt['uid']==1264 and str(receipt['job_id'])=='1885153' and receipt['full_population_graph_computed'] is True
      and receipt['full_reference_candidate'] is False and receipt['Main_origin_parent_C0_claimed'] is False,
      'Exact honest closed original producer with unresolved graph HOLDs required')
    r=receipt['result']
    I.need(r['status']=='SOURCE_GRAPH_HOLD_NOT_A_SUBSET_REFERENCE' and r['HOLD_MIDs']==119
      and r['strict5_rows']==1196003 and r['expected_all_common_census']['molecules']==1196122
      and r['scan']['selected_MIDs']==1196122 and len(r['all_output_journals_current_SHA_readback'])==4
      and len(r['input_current_SHA_frames'])==33 and len(r['actual_worker_proofs'])==16,
      'Closed complete full-source119HOLD producer required; no subset acceptance')
    I.need(plan['formal_reference'] in [row['destination_reference'] for row in r['input_current_SHA_frames']],
      'Use exact original formal input from actual33 held inputs')
    return receipt,r,p


def hold_rows(body):
    db=sqlite3.connect(body.path.as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        sql="""SELECT r.mid,r.status,m.role,m.source_role,m.n,s.n,r.strict5
          FROM results r JOIN members m USING(mid) LEFT JOIN seen s USING(mid)
          WHERE r.status<>'UNIQUE_GRAPH_PROJECTION_CANDIDATE' ORDER BY r.mid"""
        values=[dict(zip(('molecule_id','status','effective_role','source_role','native_records','seen_records','strict5'),row)) for row in db.execute(sql)]
        I.need(len(values)==119 and sum(v['native_records'] for v in values)==352
          and all(v['effective_role']=='TRAIN' and v['native_records']==v['seen_records'] and v['strict5'] is None for v in values),
          'Exact119 TRAIN MIDs/352 native records/NULLstrict5 conservation')
        body.check();return values,sql
    finally:db.close()


def graph_events(ref,mids,guard):
    path=Path(ref['path']);before=path.lstat();stamp=I.frame(before)
    I.need(stat.S_ISREG(before.st_mode) and before.st_uid==1264 and before.st_nlink==1 and before.st_size==ref['bytes']
      and not any(p.is_symlink() for p in (path,*path.parents)),'Exact owned closed journal required')
    digest=hashlib.sha256();events={mid:[] for mid in mids};locators=[];offset=lines=0
    # The unchanged writer's GRAPH_RESULT.features has no molecule_id; for a
    # reduction, sorted top-level molecule_id precedes strict5_projection.
    # This is only a prefilter; retained events are fully decoded and checked.
    token=re.compile(rb'"molecule_id":("(?:[^"\\]|\\.)*")')
    with path.open('rb') as stream:
        I.need(I.frame(os.fstat(stream.fileno()))==stamp,'Same closed journal FD')
        for raw in stream:
            guard.check();digest.update(raw);lines+=1
            match=token.search(raw);I.need(match is not None,'Original event MID field required')
            mid=json.loads(match.group(1))
            if mid in mids:
                event=json.loads(raw);I.need(event['molecule_id']==mid and event['phase'] in ('GRAPH_RESULT','MID_REDUCTION'),'Original matching top-level MID phase required')
                events[mid].append(event);locators.append(dict(molecule_id=mid,phase=event['phase'],byte_offset=offset,bytes=len(raw),line_1based=lines,line_sha256=hashlib.sha256(raw).hexdigest()))
            offset+=len(raw)
        I.need(I.frame(os.fstat(stream.fileno()))==stamp==I.frame(path.lstat())
          and offset==ref['bytes'] and digest.hexdigest()==ref['sha256'],'Single fullEOF journal SHA and stable FD required')
    return events,dict(reference=ref,frame=list(stamp),physical_lines=lines,physical_bytes=offset,
      single_pass_whole_EOF_SHA_verified=True,kept_event_locators=locators)


def creator_rows(body,mids,expected_physical,guard):
    import pyarrow as pa
    import pyarrow.compute as pc
    pf=body.parquet();available=set(pf.schema_arrow.names)
    columns=[*C.REQUIRED_IDENTITY_COLUMNS,*[c for c in C.OPTIONAL_IDENTITY_COLUMNS if c in available],'file_group']
    I.need(set(columns)<=available,'Original identity columns required')
    selected={mid:[] for mid in mids};physical=0;value_set=pa.array(sorted(mids),type=pa.string())
    for batch in pf.iter_batches(columns=columns,batch_size=8192,use_threads=False):
        guard.check();body.check()
        mask=pc.is_in(batch.column(batch.schema.get_field_index('molecule_id')),value_set=value_set)
        indices=pc.indices_nonzero(mask).to_pylist()
        for index,row in zip(indices,batch.filter(mask).to_pylist()):
            group=row.pop('file_group');value=S.select(row)
            selected[row['molecule_id']].append(dict(original_formal_physical_row_index=physical+index,
              original_file_group=group,original_selection=value))
        physical+=batch.num_rows
    I.need(physical==expected_physical==pf.metadata.num_rows,'Complete unchanged formal source physical EOF')
    body.check();return selected,dict(reference=body.reference,frame=list(body.frame),physical_rows=physical,
      actual_identity_columns=columns,original_selector_source=I.pin(S.__file__),chemistry_calls=0)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path);a=p.parse_args()
    plan=Q.load(a.plan);proof=Q.load(a.startup_proof)
    I.need(plan['schema']=='ALPHA_COMMON_HOLD119_METADATA_AUDIT_PLAN_V1'
      and proof['request']['producer_plan_reference']==I.pin(a.plan) and proof['request']['execution_argv']==plan['execution_argv']
      and proof['uid']==os.getuid()==1264 and str(proof['job_id'])==os.environ['SLURM_JOB_ID']
      and proof['endpoint']=='218.192.171.238:22' and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'Actual new independent Alpha audit parent required')
    for path in [*Path(__file__).parent.glob('*.py'),Path(S.__file__),Path(C.__file__),Path(I.__file__)]:
        I.need(I.pin(path) in proof['request']['source_references'],'Actual audit/original selector/I/O source pin required')
    actual=admit(plan,minimum_workers=16);receipt,result,parent=closed(plan)
    out=Path(plan['output_directory']);I.need(not out.exists(),'Fresh audit output preserving original producer required');out.mkdir(parents=True)
    guard=Guard(plan);bodies=[]
    try:
        from .test_metadata import Metadata
        transcript=io.StringIO();tests=unittest.TextTestRunner(stream=transcript,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Metadata))
        I.need(tests.testsRun==2 and tests.wasSuccessful() and not tests.skipped,'Two exact metadata fixtures before DATA')
        test_ref=I.save(out/'metadata_fixtures2.json',dict(tests=tests.testsRun,failures=len(tests.failures),errors=len(tests.errors),skips=len(tests.skipped),transcript=transcript.getvalue()))
        db=I.Body(result['census_index'],guard);bodies.append(db);holds,query=hold_rows(db);mids={v['molecule_id'] for v in holds}
        events,journal=graph_events(result['graph_results'],mids,guard)
        formal=I.Body(plan['formal_reference'],guard);bodies.append(formal)
        rows,formal_proof=creator_rows(formal,mids,result['scan']['formal_physical_rows_scanned'],guard)
        record_ids=[row['original_selection']['original_identity']['record_id'] for source in rows.values() for row in source]
        I.need(len(record_ids)==len(set(record_ids))==352,'All352 original native record IDs unique and retained')
        reasons=collections.Counter();fields=collections.Counter();details=[]
        for hold in holds:
            mid=hold['molecule_id'];source=rows[mid];analysis=core.diagnose(events[mid])
            I.need(len(source)==hold['native_records'],'Every119MID native Creator row conserved')
            variants={row['original_selection']['variant_id'] for row in source}
            graph_variants={v['variant_id'] for v in analysis['graph_variant_results']}
            if analysis['graph_variant_results']:I.need(variants==graph_variants,'All actual selected source variants bind rich graph events')
            I.need(analysis['reduced_projection_remains_HOLD'],'Original HOLD unchanged')
            for reason in analysis['original_reduction'].get('hold_reasons',[]):reasons[reason]+=1
            if analysis['original_reduction'].get('reason'):reasons[analysis['original_reduction']['reason']]+=1
            fields.update(analysis['exact_feature_field_differences'].keys())
            details.append(dict(**hold,original_Creator_source_rows=source,diagnosis=analysis))
        data=out/'hold119_exact_original_evidence.DATA.jsonl'
        with data.open('xb') as stream:
            for row in details:stream.write(I.canonical(row))
            stream.flush();os.fsync(stream.fileno())
        I.need(sum(len(rows[mid]) for mid in mids)==352,'Whole119/352 conservation')
        for body in bodies:body.check()
        I.save(out/'receipt.json',dict(schema='ALPHA_COMMON_HOLD119_METADATA_AUDIT_PRODUCER_V1',
          status='AUDIT_COMPLETE_PENDING_ACTUAL_NEW_ALPHA_C0_AND_ROOT_REVIEW',plan=I.pin(a.plan),startup_proof=I.pin(a.startup_proof),
          uid=os.getuid(),job_id=os.environ['SLURM_JOB_ID'],profile_admission=actual,
          original_Common_receipt=plan['common_receipt_reference'],original_actual_Alpha_parent=parent,
          original_actual_accounting_reference=plan['actual_accounting_reference'],
          metadata_fixtures=test_ref,exact_HOLD_evidence=I.pin(data,guard.check),HOLD_MIDs=119,native_records=352,
          molecules_by_role={'TRAIN':119},native_records_by_role={'TRAIN':352},reason_counts=dict(reasons),
          differing_feature_field_counts=dict(fields),census_query=query,census_source_reference=db.reference,
          graph_journal_single_EOF=journal,formal_Creator_source_readback=formal_proof,
          chemistry_calls=0,graph_selection_or_repair_applied=False,original_HOLDs_preserved=True,
          original_producer_modified=False,complete_Common_reference_accepted=False,runtime=guard.receipt()))
    finally:
        for body in bodies:body.close()
        guard.close()


if __name__=='__main__':main()
