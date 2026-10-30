"""Finite original old-complete mother; no full-Common/HOF gate or future pin."""
import csv,io,os
from pathlib import Path
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import contract as OLD
from workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1 import metadata as PM
P=OLD.P;need=OLD.need;meta=OLD.meta;reference=OLD.reference;unique=OLD.unique;RUN=OLD.RUN;REPO=OLD.REPO;PY=OLD.PY
HERE=REPO/'workflows/data_v1_final/export/bounded_old_complete_d5_resume_v2'
KEY='bounded_old_complete_d5_resume_v2';MODULE='workflows.data_v1_final.export.bounded_old_complete_d5_resume_v2.run'
PLAN='BOUNDED_OLD_COMPLETE_D5_DAY_PLAN_V1';STATUS='ROOT_REVIEWED_EXECUTABLE_OLD_COMPLETE_D5'
FILES=('__init__.py','contract.py','metadata.py','adopt.py','produce.py','children.py','distributions.py','run.py','source_inverse.py','test_boundaries.py','README.md','resume.py')
NESTED=(120000,240000,600000);ALLOWED_TABLES={'full_population_membership','complete_old_mother','pilot55k','diagnostic20k_molecule_preselection',*('train_'+str(n) for n in NESTED)}

def scope(p):
    return {'scope_version':p['scope_version'],'purpose':'INDEPENDENT_OLD_COMPLETE_SPRIME_D5_COMPONENTS_NOT_FINAL_COMMON',
      'node':p['node'],'requested_cpus':16,'wall_seconds':86400,'softwall_drain_seconds':900,
      'output_directory':p['output_directory'],'whole_output_cap_bytes':p['whole_output_cap_bytes'],
      'seed':20261025,'nested_TRAIN':list(NESTED),'pilot_TRAIN':50000,'pilot_VAL':5000,'diagnostic_TRAIN':20000,
      'heldout_base_geometries':40000,'fixed_random_only':True,'energy_diversity_and_RMSD_or_HOF_computed':False,
      'closed_feature_reuse_review_reference':p['closed_feature_reuse_review_reference'],'all_actual_heldout_children_and_input_views_excluded_before_first_k':True,'new_QM_UFF_calls':0,'final_Common_or_D6_release':False}

def parent(chain):
    request=meta(chain['request_reference']);proof=meta(chain['proof_reference']);submission=meta(chain['submission_reference'])
    account=meta(chain['accounting_reference']);job=str(submission['job_id']);need(str(proof['job_id'])==job and proof['uid']==1278,'ACTUAL_ORIGINAL_PARENT_UID_JOB')
    rows=[r for r in account['parents'] if str(r['job_id'])==job]
    need(account['query_returncode']==0 and account['uid']==1278 and account['endpoint']=='202.38.247.57:22' and len(rows)==1
      and rows[0]['state'] in ('COMPLETED','FAILED','TIMEOUT','CANCELLED') and account['raw_sacct_reference']==chain['raw_reference'],
      'ACTUAL_TERMINAL_ORIGIN_WITH_COST_AND_RAW_NOT_FUTURE_OR_FAKE_C0')
    raw,ref=P.small(chain['raw_reference']['path']);need(ref==chain['raw_reference'],'EXACT_ORIGINAL_ACCOUNT_RAW_PIN')
    source=[r for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),delimiter='|') if r['JobIDRaw']==job]
    need(len(source)==1 and source[0]['UID']=='1278' and source[0]['State'].split()[0]==rows[0]['state']
      and source[0]['ExitCode']==rows[0]['exit_code'] and int(source[0]['AllocCPUS'])==rows[0]['alloc_cpus']
      and int(source[0]['ElapsedRaw'])==rows[0]['elapsed_raw_seconds'] and source[0]['NodeList']==rows[0]['node'],'ORIGIN_RAW_STATE_CPU_NODE_ELAPSED_EQUAL')
    need(proof['request']==request and request['job_name']==submission['job_name'],'EXACT_ORIGIN_REGISTERED_REQUEST_NOT_ANOTHER_SCOPE')
    return job,rows[0]

def reviews(p):
    v=meta(p['bounded_input_review_reference'])
    need(v['schema']=='ROOT_BOUNDED_OLD_COMPLETE_D5_INPUT_REVIEW_V1' and v['status']=='APPROVED_EXACT_OLD_COMPLETE_MOTHER_NOT_FINAL_COMMON'
      and v['reviewer']=='root' and v['scope_version']==p['scope_version'] and v['seed']==20261025
      and v['nested_TRAIN']==list(NESTED) and v['pilot_counts']=={'TRAIN':50000,'VAL':5000} and v['diagnostic_TRAIN']==20000
      and v['frozen_preselection_not_reselected']is True and v['pending_Sprime_availability_not_new_scientific_exclusion']is True
      and v['original_quality_thresholds_and_Se_exception_unchanged']is True and v['final_Common_or_D6_release']is False,
      'EXPLICIT_CURRENT_OLD_COMPLETE_MOTHER_SCOPE_NOT_FULL_GATE_WAIVER')
    need(v['actual_parent_evidence_references'],'REAL_NONEMPTY_PRIOR_PARENT_EVIDENCE')
    reuse,qa,origin=PM.hof_reuse(p)
    actual=meta(p['actual_UFF_child_census_review_reference'])
    need(actual['schema']=='ROOT_D5_BOUNDED_OLD_COMPLETE_ACCEPTED_TRAINING_CHILD_SCOPE_V1'
      and actual['status']=='APPROVED_EXACT_CURRENT_ACCEPTED_CORPUS_INPUTS_NOT_GLOBAL_NATIVE_CALL_CENSUS'
      and actual['reviewer']=='root' and actual['accepted_Pprime_training_source_references']==[]
      and actual['current_UFF_Pprime_input_child_training_rows_admitted']==0 and actual['current_UFF_Pprime_label_training_rows_admitted']==0
      and actual['ordinary_UFF_training_geometry_label_groups']==['S','D'] and actual['independent_QA_outputs_authorized_for_training']is False
      and actual['actual_prepared2000_native_invoke_attempts']==0 and actual['actual_prepared2000_production_once_written']is False
      and actual['CPU_must_verify_no_unlisted_training_QM_sources_are_accepted']is True
      and actual['original_WP5_source_inventory_reference']==p['source_inventory_reference']
      and actual['original_WP5_footer_manifest_reference']==p['footer_manifest_reference']
      and actual['original_actual_WP5_perturbed_children_and_input_views_must_be_fully_reconstructed_and_antijoined']is True
      and actual['empty_accepted_Pprime_set_is_explicit_current_Root_scope_decision_not_claim_of_global_no_QM']is True
      and actual['future_Pprime_outputs_not_automatically_admitted']is True and actual['full_Common_or_D6_release']is False,
      'EXACT_ROOT_CURRENT_TRAINING_CORPUS_EMPTY_PPRIME_NOT_GLOBAL_NATIVE_ZERO')
    meta(actual['declared_Pprime_preparation_pureQA_reference'])
    frame=meta(p['source_metadata_frame_review_reference']);wp5=meta(p['WP5_input_derivation_authority_reference'])
    need(frame['schema']=='ROOT_PILOT_RAW_METADATA_SOURCE_FRAME_REVIEW_V1' and frame['status']=='APPROVED_ORIGINAL_INHERITED_SHA_FOOTER_FD_GUARD'
      and frame['reviewer']=='root' and frame['node']==p['node'] and frame['source_inventory_reference']==p['source_inventory_reference']
      and frame['footer_manifest_reference']==p['footer_manifest_reference'] and frame['fresh_original_Parquet_whole_SHA_claimed']is False,
      'TRUE_CURRENT_NODE_RAW_METADATA_FOOTER_SCOPE_BEFORE_NATIVE_WORK')
    meta(frame['actual_same_storage_mapping_probe_reference'])
    need(wp5['schema']=='ROOT_BOUNDED_PILOT_WP5_INPUT_DERIVATION_AUTHORITY_V1' and wp5['status']=='APPROVED_EXACT_ORIGINAL_CALL_INPUTS_WITHIN_PILOT'
      and wp5['reviewer']=='root' and wp5['pilot_input_review_reference']==p['bounded_input_review_reference']
      and wp5['source_inventory_reference']==p['source_inventory_reference'] and wp5['actual_per_call_both_input_hashes_required']is True
      and wp5['no_new_QM_UFF_or_graph_repair']is True,'ROOT_EXPLICIT_FULL20K_SOURCE_INPUT_HASH_AUTHORITY_NOT_OLD55K_ALIAS')
    return v,reuse,qa,origin,actual

def plan(p):
    need(p['schema']==PLAN and p['status']==STATUS and p['reviewer']=='root' and p['node'] in PM.ANALYSIS_NODES
      and p['cpus']==p['requested_cpus']==p['workers']==16 and p['wall_seconds']==86400 and p['softwall_drain_seconds']==900
      and p['whole_output_cap_bytes']==32<<30 and p['scope_parameters']==scope(p),'TRUTHFUL_GENERIC16_DAY32GIB_NEW_SCOPE')
    need(Path(p['output_directory']).parent==RUN/'artifacts/labels/source_status_v1/bounded_old_complete_d5_resume_v2','FRESH_OWN_OUTPUT_NAMESPACE')
    need(p['source_references'] and p['data_references'] and p['actual_parent_evidence_references'],'EXACT_SOURCE_DATA_AND_REAL_PRIOR_CHAIN')
    for r in p['source_references']:need(P.pin(r['path'])==r,'CURRENT_EXPLICIT_SOURCE_OR_SMALL_META')
    reviews(p)
    from . import resume
    resume.review(p);return p

def random_last(mid,source,ids):
    from workflows.data_v1_final.conformers import selection
    need(source in ('pm7','uff_sprime') and len(ids)>=2 and len(ids)==len(set(ids)),'TWO_REAL_DISTINCT_ORDINARY_BASES_PER_DIAGNOSTIC_SOURCE')
    return max(ids,key=lambda key:(selection.stable_key(20261025,mid,source,key),str(key)))

def keep_target(row,excluded):
    return row['geometry_id']not in excluded and row.get('parent_geometry_id')not in excluded
