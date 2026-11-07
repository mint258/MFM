"""Close baseline common coverage, then require actual post-QM validation evidence."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

from common_v1 import IO, formal_review, frozen_authorities, load, pilot_review, runtime
from close_batch_v1 import assess


def coverage(expected, observed, pending):
    """N1 stays in the denominator; missing rows never become filled successes."""
    if len(expected)!=len(set(expected)) or len(observed)!=len(set(observed)):
        raise ValueError('DUPLICATE_EXPECTED_OR_COMPLETED_SCIENTIFIC_INPUT_KEYS')
    missing=set(expected)-set(observed);extra=set(observed)-set(expected)
    return {'expected_records':len(expected),'closed_records':len(observed),
      'missing_records':len(missing),'unexpected_records':len(extra),
      'pending_two_real_geometries':pending,'baseline_coverage_complete':not missing and not extra,
      'whole_common_coverage_complete':not missing and not extra and pending==0}


def index(a,c):
    decision,plan=formal_review(a.root_review,a.plan,c)
    frozen_authorities(plan['common_manifest'],plan['order_manifest'],plan['geometry_manifest'])
    pd,pr,pg=pilot_review(plan['pilot_review']['path'],c['pilot_config']['path'])
    imported=json.loads(a.pilot_import.read_text())
    if decision['pilot_import']!=IO.reference(a.pilot_import):raise ValueError('ROOT_REVIEW_PILOT_IMPORT_SHA_MISMATCH')
    if imported['status']!='REAL2000_PILOT_KEYS_IMPORTED_NO_QM' or imported['pilot_review']!=plan['pilot_review']:
        raise ValueError('EXACT_REAL_PILOT_IMPORT_REQUIRED')
    imports={r['key']:r for r in imported['entries']}
    expected={};batch_ids=set()
    prepared_refs=json.loads(a.prepared_index.read_text())
    for ref in prepared_refs:
        packet=json.loads(IO.require_pin(ref).read_text())
        if packet['plan']!=IO.reference(a.plan) or packet['batch_id'] in batch_ids:
            raise ValueError('UNIQUE_PREPARED_BATCHES_FROM_EXACT_PLAN_REQUIRED')
        batch_ids.add(packet['batch_id'])
        for line in IO.require_pin(packet['pairs']).read_text().splitlines():
            pair=json.loads(line);key=pair['once_key']
            if key in expected:raise ValueError('PLANNED_SCIENTIFIC_INPUT_KEY_COLLISION')
            expected[key]={'once_key':key,'record_id':pair['record_id'],'molecule_id':pair['molecule_id'],
                 'canonical_geometry_id':pair['canonical_geometry_id'],'batch_id':packet['batch_id']}
    if batch_ids!={r['batch_id'] for r in plan['batches']} or len(expected)!=plan['requested_records']:
        raise ValueError('ALL_PLANNED_BATCH_INPUTS_REQUIRED_FOR_BASELINE_COVERAGE_AUDIT')
    observed={};family_refs=[];pilot_scope=[]
    for key,row in imports.items():
        if key not in expected:continue
        IO.require_pin(row['ledger']);pilot_scope.append(row['record_id'])
        observed[key]=dict(expected[key],source='real_pilot',all_twelve_success=row['all_twelve_success'])
    parents={str(pr['runtime']['job_id']):pg['actual_parent']};total_seconds=pg['allocated_core_seconds'];bad=[]
    closure_refs=json.loads(a.closures_index.read_text())
    for pin in closure_refs:
        saved=json.loads(IO.require_pin(pin).read_text())
        result=json.loads(IO.require_pin(saved['result']).read_text())
        raw_proof=json.loads(IO.require_pin(result['stable_raw_retention_proof']).read_text())
        if raw_proof['status']!='ALL_REQUIRED_RETAINED_CALLS_SHA_VERIFIED':
            raise ValueError('ACTUAL_STABLE_AND_FAILED_CALL_RAW_PROOF_INCOMPLETE')
        IO.require_pin(saved['raw_sacct'])
        rows=list(csv.DictReader(Path(saved['raw_sacct']['path']).read_text().splitlines(),delimiter='|'))
        actual=assess(result,rows,pg['allocated_core_seconds_per_requested_conformer'])
        if actual['gates']!=saved['gates'] or actual['allocated_core_seconds']!=saved['allocated_core_seconds']:
            raise ValueError('CLOSURE_DISAGREES_WITH_ACTUAL_RAW_PARENT_ACCOUNTING')
        jid=str(result['runtime']['job_id'])
        if jid in parents:raise ValueError('DUPLICATE_PARENT_COST_NOT_ALLOWED')
        parents[jid]=actual['actual_parent'];total_seconds+=actual['allocated_core_seconds']
        if not all(actual['gates'].values()):bad.append(pin)
        if result['plan']!=IO.reference(a.plan):raise ValueError('RESULT_FROM_DIFFERENT_PLAN')
        for ref in result['family_parquets']:IO.require_pin(ref);family_refs.append(ref)
        for row in result['outcomes']:
            if row.get('source')=='closed_real_pilot':
                if row['once_key'] not in imports:raise ValueError('UNREGISTERED_REUSED_OUTCOME')
                continue
            key=row['once_key']
            if key not in expected or key in observed:raise ValueError('DUPLICATE_OR_UNEXPECTED_COMPUTED_OUTCOME')
            IO.require_pin(row['outcome'])
            actual_outcome=json.loads(Path(row['outcome']['path']).read_text())
            statuses=actual_outcome['task_statuses']
            if len(statuses)!=12 or {r['task'] for r in statuses}!=set(IO.TASKS) or actual_outcome['once_key']!=key:
                raise ValueError('ACTUAL_FORMAL_OUTCOME_MUST_HAVE_ALL_TWELVE_TASKS')
            if all(r['scope_status']=='SUCCESS' for r in statuses)!=row['all_twelve_success']:
                raise ValueError('ACTUAL_FORMAL_SUCCESS_FLAG_DISAGREES_WITH_OUTCOMES')
            observed[key]=dict(expected[key],source='new_formal',all_twelve_success=row['all_twelve_success'],outcome=row['outcome'])
    proof=coverage(list(expected),list(observed),plan['pending_two_real_geometries'])
    if total_seconds/3600>decision['approved_total_core_hours_cap']:bad.append({'status':'ACTUAL_TOTAL_CORE_HOURS_EXCEEDS_ROOT_CAP'})
    out=IO.new_output(a.output,c)
    import pyarrow as pa
    import pyarrow.parquet as pq
    pq.write_table(pa.Table.from_pylist([observed[k] for k in sorted(observed)]),out/'record_mapping.parquet',compression='zstd')
    for ref in imported['family_parquets']:IO.require_pin(ref)
    family_manifest=IO.write_json(out/'family_manifest.json',{'schema':'PPRIME_BASELINE_FAMILY_REFERENCE_INDEX_V1',
      'new_family_parquets':family_refs,'pilot_family_parquets':imported['family_parquets'],
      'pilot_required_record_id_filter':sorted(pilot_scope),'scope_filter_required':True,
      'permanent_float_dtype':'float64','geometry_source':'uff_sprime','copied_or_invented_label_values':False,
      'record_mapping':IO.reference(out/'record_mapping.parquet')})
    IO.write_json(out/'data_index.json',{'schema':'PPRIME_BASELINE_DATA_INDEX_V1',
      'status':'PPRIME_BASELINE_INDEX_CLOSED_AWAITING_POST_QM_VALIDATION' if proof['baseline_coverage_complete'] and not bad else 'PPRIME_BASELINE_INDEX_INCOMPLETE_STOP',
      'plan':IO.reference(a.plan),'common_manifest':plan['common_manifest'],'order_manifest':plan['order_manifest'],
      'geometry_manifest':plan['geometry_manifest'],'pilot_review':plan['pilot_review'],'root_review':IO.reference(a.root_review),
      'pilot_import':IO.reference(a.pilot_import),'prepared_index':IO.reference(a.prepared_index),
      'closures_index':IO.reference(a.closures_index),'coverage':proof,'family_manifest':family_manifest,
      'actual_parent_rows':list(parents.values()),'allocated_core_seconds':total_seconds,'allocated_core_hours':total_seconds/3600,
      'cost_scope':'pilot plus all supplied formal QM parents, including failures; preprocessing/validation remain in Root global ledger',
      'bad_closures':bad,'whole_common_accepted':False,'post_QM_validation_pending':True})


def accept(a,c):
    idx=json.loads(a.data_index.read_text())
    if idx['status']!='PPRIME_BASELINE_INDEX_CLOSED_AWAITING_POST_QM_VALIDATION' or not idx['coverage']['whole_common_coverage_complete']:
        raise ValueError('WHOLE_COMMON_INCLUDING_N1_MUST_HAVE_TWO_REAL_GEOMETRIES_AND_CLOSED_OUTCOMES')
    evidence=json.loads(a.validation.read_text())
    if evidence.get('schema')!='PPRIME_FULL_VALIDATION_CLOSURE_V1' or evidence.get('status')!='ALL_VALIDATION_CLOSED':
        raise ValueError('ACTUAL_POST_QM_VALIDATION_CLOSURE_REQUIRED')
    if evidence.get('data_index')!=IO.reference(a.data_index):raise ValueError('VALIDATION_DATA_INDEX_SHA_MISMATCH')
    required={'wp5_same_audit_passed','float64_family_readback_passed','all_raw_retention_verified',
       'outlier_scan_1_5_completed','outlier_stop_threshold_resolved','P_vs_Pprime_distribution_and_correlation_completed',
       'independent_Pprime_TRAIN_normalization_completed','vector_frame_actual_audit_passed'}
    if set(evidence.get('gates',{}))!=required or any(evidence['gates'][key] is not True for key in required):
        raise ValueError('ALL_ACTUAL_QC_ANOMALY_DISTRIBUTION_NORMALIZATION_AND_FRAME_GATES_REQUIRED')
    sources=evidence.get('sources',{})
    if set(sources)!={'wp5_audit','float64_readback','raw_retention','outlier_scan','P_vs_Pprime','Pprime_normalization','vector_frame'}:
        raise ValueError('PINNED_ACTUAL_VALIDATION_REPORTS_REQUIRED_NOT_BOOLEAN_ONLY')
    for pin in sources.values():IO.require_pin(pin)
    out=IO.new_output(a.output,c)
    IO.write_json(out/'manifest.json',{'schema':'PPRIME_ALL_COMMON_V1_ACCEPTED',
       'status':'PPRIME_ALL_COMMON_V1_ACCEPTED','data_index':IO.reference(a.data_index),
       'actual_validation_closure':IO.reference(a.validation),'common_manifest':idx['common_manifest'],
       'family_manifest':idx['family_manifest'],'geometry_source':'uff_sprime','permanent_float_dtype':'float64',
       'common_membership_or_original_N_changed':False,'legacy_P_labels_filled_into_Pprime':False})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['index','accept'])
    for name in ('config','root-preflight','output'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('root-review','plan','pilot-import','prepared-index','closures-index','data-index','validation'):
        p.add_argument('--'+name,type=Path)
    a=p.parse_args();c,_=load(a.config);runtime(c,a.root_preflight,a.config)
    required=('root_review','plan','pilot_import','prepared_index','closures_index') if a.stage=='index' else ('data_index','validation')
    if any(getattr(a,k) is None for k in required):p.error('missing inputs for '+a.stage)
    (index if a.stage=='index' else accept)(a,c)


if __name__=='__main__':main()
