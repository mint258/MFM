"""Allocated exact original502 technical UNKNOWN evidence audit, no chemistry."""
import argparse
import collections
import concurrent.futures as cf
import csv
import io
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import traceback
import unittest
from ..alpha_runtime_v1.common import load, need, reference, verify, write
from .core import COUNTS
from .scan import scan


def metadata(ref):
    need(ref['bytes'] <= 2<<20, 'Only small pinned source metadata')
    return load(verify(ref))


def admission(plan,proof,plan_path,proof_path):
    from ..alpha_runtime_v1.profile import admit
    authority=admit(plan,minimum_workers=16)
    request=proof['request']
    need(plan['schema']=='PUBCHEM_ALPHA_TECHNICAL_UNKNOWN_AUDIT_PLAN_V1'
         and plan['scope_key']==request['scope_key']=='pubchem_alpha_technical_unknown_audit_v1', 'Exact diagnostic scope')
    need(request['producer_plan_reference']==reference(plan_path), 'Actual exact diagnostic plan')
    need(request['execution_argv']==plan['execution_argv']
         and sys.argv[-4:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)]
         and request['execution_argv'][-4:]==sys.argv[-4:], 'Exact actual node launcher command')
    need(proof['endpoint']==plan['endpoint']=='218.192.171.238:22'
         and proof['uid']==plan['uid']==os.getuid()==1264
         and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID')
         and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'Actual Alpha UID/job/boot')
    refs={r['path']:r for r in request['source_references']}
    from ..pubchem_closed500_bulk_v2 import schema
    for path in [*Path(__file__).parent.glob('*.py'),Path(schema.__file__)]:
        need(refs.get(str(path.absolute()))==reference(path), 'Actual new source and pure Arrow schema pins')
    for ref in request['source_references']:
        need(ref['bytes'] <= 2<<20,'Source inventory cannot disguise scientific bodies');verify(ref)
    return authority


def sources(plan,guard):
    original=metadata(plan['original_handoff_plan_reference'])
    need(original['schema']=='ALPHA_ORIGINAL502_TYPED_HANDOFF_PLAN_V1'
         and original['endpoint']=='218.192.171.238:22' and original['uid']==1264
         and original['source_counts']==COUNTS and original['source_rows']==124857440
         and original['fragment_count']==502 and original['logical_descriptor_count']==500, 'Exact original full source plan')
    projection_ref=plan['full502_projection_manifest_reference'];projection=metadata(projection_ref)
    need(projection['schema']=='PUBCHEM_ALL_CLOSED_PROJECTIONS_V2'
         and projection['producer_schema']=='PUBCHEM_ALPHA_ORIGINAL502_TYPED_COVERAGE_V1'
         and projection['counts']==COUNTS and projection['source_rows']==124857440
         and projection['coverage_reference']==original['coverage_reference']
         and projection['frozen_manifest_reference']==original['frozen_manifest_reference']
         and projection['source_snapshot_sha256']==original['source_snapshot_sha256']
         and projection['source_typed_bodies_full_SHA_verified'] is True, 'Actual prior full502 source SHA closure')
    actual=metadata(plan['full502_actual_parent_reference'])
    need(actual['schema']=='ROOT_ACTUAL_ALPHA_TYPED502_V1' and actual['endpoint']=='218.192.171.238:22'
         and actual['uid']==1264 and actual['actual_terminal'] is True and actual['job_id']=='1885148'
         and actual['projection_manifest']==projection_ref and actual['counts']==COUNTS
         and actual['source_typed_bodies_full_SHA_verified'] is True, 'Actual original closed source parent evidence')
    rows=list(csv.DictReader(io.StringIO(actual['actual_sacct']),delimiter='|'))
    rows=[r for r in rows if r['JobIDRaw']=='1885148']
    need(len(rows)==1 and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0', 'Actual1885148C0, not inferred from file existence')
    producer=metadata(plan['full502_producer_receipt_reference'])
    need(producer['schema']=='ALPHA_ORIGINAL502_ADMITTED_PARENT_RECEIPT_V1'
         and producer['stage']=='project' and producer['actual_parent']['job_id']=='1885148'
         and producer['actual_parent']['endpoint']=='218.192.171.238:22' and producer['actual_parent']['uid']==1264
         and producer['plan_reference']==plan['original_handoff_plan_reference']
         and producer['projection_manifest']==projection_ref, 'Actual parent binds exact original source plan')
    coverage=metadata(original['coverage_reference']);metadata(original['frozen_manifest_reference'])
    need(coverage['counts']==COUNTS,'Original full coverage census')
    verify(plan['original_typed_kernel_reference'])
    for ref in original['original_science_references']:verify(ref)
    result=[];next_ordinal=1;total=collections.Counter();ids=set();descriptors=set()
    need(len(original['fragments'])==len(projection['fragments'])==502,'All502 physical fragments')
    for spec,closed_ref in zip(original['fragments'],projection['fragments']):
        guard.check();closed=metadata(closed_ref)
        need(closed['schema']=='PUBCHEM_CLOSED_FRAGMENT_PROJECTION_V2' and closed['source_fragment']==spec
             and closed['source_sha256']==spec['Parquet_reference']['sha256']
             and closed['source_whole_SHA_verified_on_same_FD'] is True
             and closed['all_source_counts']==spec['counts'] and closed['input_rows']==spec['rows'], 'Historical exact closed fragment SHA/count proof')
        need(spec['first_ordinal']==next_ordinal and spec['last_ordinal']-next_ordinal+1==spec['rows']
             and spec['fragment_id'] not in ids, 'Complete unique physical source interval coverage')
        need(Path(spec['Parquet_reference']['path']).is_absolute()
             and spec['Parquet_reference']['path'].startswith('/gfshome/alpha/codex_data_v1_20261026/artifacts/'), 'Only original own Alpha typed bodies')
        total.update(spec['counts']);ids.add(spec['fragment_id']);descriptors.add(spec['descriptor_index'])
        next_ordinal=spec['last_ordinal']+1;result.append((spec,closed_ref))
    need(next_ordinal==124857441 and dict(total)==COUNTS and descriptors==set(range(500)), 'Whole logical500/physical502 census')
    return result


def execute(plan,out,guard):
    inputs=sources(plan,guard);directory=out/'fragments';directory.mkdir()
    results=[];pending={};todo=iter(inputs)
    with cf.ProcessPoolExecutor(max_workers=plan['workers'],mp_context=mp.get_context('spawn')) as pool:
        for unused in range(plan['workers']):
            item=next(todo,None)
            if item is not None:pending[pool.submit(scan,*item,str(directory))]=item[0]['fragment_id']
        while pending:
            done,unused=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED);guard.check()
            for future in done:
                fragment=pending.pop(future);results.append(future.result())
                print(json.dumps(dict(event='TECHNICAL_EVIDENCE_FRAGMENT_CLOSED',fragment_id=fragment,closed=len(results))),flush=True)
                item=next(todo,None)
                if item is not None:pending[pool.submit(scan,*item,str(directory))]=item[0]['fragment_id']
    totals=collections.Counter();categories=collections.Counter()
    for result in results:totals.update(result['counts']);categories.update(result['all_source_counts'])
    need(len(results)==502 and totals['rows']==46201 and dict(categories)==COUNTS,'Complete all46201 diagnostic, no sample or prefix')
    fragments={r['source_fragment']['fragment_id']:r for r in results}
    return dict(schema='PUBCHEM_ALPHA_TECHNICAL_UNKNOWN_EVIDENCE_AUDIT_V1',status='COMPLETE_DIAGNOSTIC_UNKNOWN_UNCHANGED',
        source_endpoint='218.192.171.238:22',source_uid=1264,source_rows=124857440,logical_descriptors=500,physical_fragments=502,
        all_source_counts=dict(categories),technical_rows=46201,counts=dict(totals),
        fragment_receipts=[reference(directory/spec['fragment_id']/'receipt.json') for spec,ref in inputs],
        DATA=[fragments[spec['fragment_id']]['DATA'] for spec,ref in inputs],
        source_references={k:plan[k] for k in ('original_handoff_plan_reference','full502_projection_manifest_reference',
            'full502_actual_parent_reference','full502_producer_receipt_reference','original_typed_kernel_reference')},
        source_body_fresh_full_SHA_verified=False,historical_complete_full_SHA_evidence_reused=True,
        current_source_frames_stable=True,historical_inode_or_same_device_claimed=False,
        full_original_source_category_columns_scanned=True,only_selected_row_group_evidence_columns_read=True,
        chemistry_or_QM_calls=0,raw_source_or_journal_replayed=False,pool_or_minCID_or_sample_changed=False,
        original_technical_UNKNOWN_retained=True,technical_recoverability_inferred=False,scientific_acceptance=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path)
    p.add_argument('--startup-proof',required=True,type=Path);a=p.parse_args()
    plan=load(a.plan);proof=load(a.startup_proof);authority=admission(plan,proof,a.plan,a.startup_proof)
    from ..alpha_runtime_v1.guard import Guard
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False)
        from .test_source import Source
        stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Source))
        tested=write(out/'source_tests.json',dict(tests=tests.testsRun,errors=len(tests.errors),failures=len(tests.failures),
            skips=len(tests.skipped),transcript=stream.getvalue()))
        need(tests.wasSuccessful() and tests.testsRun==1 and not tests.skipped,'Recorded-trace classification boundary fixture')
        result=execute(plan,out,guard)
        write(out/'receipt.json',dict(schema='PUBCHEM_ALPHA_TECHNICAL_UNKNOWN_AUDIT_PRODUCER_V1',plan_reference=reference(a.plan),
            startup_proof_reference=reference(a.startup_proof),profile_admission=authority,source_tests=tested,
            result=result,runtime=guard.receipt(),actual_parent_C0_pending_root_readback=True,scientific_acceptance=False))
    except BaseException as exc:
        if out.is_dir():write(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),partials_retained=True,
            original_pool_or_UNKNOWN_modified=False))
        raise
    finally:guard.close()


if __name__=='__main__':main()
