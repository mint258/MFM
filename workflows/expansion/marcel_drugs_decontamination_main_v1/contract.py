"""Actual4523818/Root union authority. Only its87MB union is scientific DATA."""
from pathlib import Path
from workflows.expansion.marcel_kraken_decontamination_main_v1 import contract as K
from workflows.expansion.marcel_drugs_native_graph_full_v1 import contract as F
Q=K.Q;meta=K.meta;data_reference=K.data_reference
HERE=Q.REPO/'workflows/expansion/marcel_drugs_decontamination_main_v1'
FILES=('__init__.py','contract.py','projection.py','runtime.py','run.py','materialize.py','test_v1.py','README.md')
OLD=tuple(dict.fromkeys([*(K.HERE/n for n in K.FILES),*K.OLD,*F.source_paths(),
    Q.REPO/'workflows/expansion/identity_v2/projection_v2.py']))
KEY='marcel_drugs_decontamination_main_v1';MODULE='workflows.expansion.marcel_drugs_decontamination_main_v1.run'
STAGE='DRUGS_ACTUAL558002_CONSERVATIVE_UNIONS_TO_STRICT_ALL_SOURCE_IDENTITIES'
CAP=512<<20;N=75099;CONFORMERS=558002;ARCHIVE_SHA='47dbe1fc06fcfe1c94d9bd381dccfc19016466f637a46c25592db23b770ef830'
VERSION='MARCEL/Drugs:archive-sha256-'+ARCHIVE_SHA
ROOT_ACCEPT=Q.ROOT/'control/root_actual_drugs558002_native_union_acceptance_v1.json'
UNION=Q.ROOT/'artifacts/expansion/marcel_drugs_native_graph_full_v1/full_v1/all_CSV_names_all_source_and_native_full_key_unions.jsonl'
PARAMETERS={'actual_full_native_parent':'4523818','all_source_context_rows':633101,'CSV_names':N,'SDF_conformers':CONFORMERS,
    'native_profile_adopted':1000,'new_full_native':557002,'source_native_different_conformers':126,'different_names':31,'multi_SMILES_names':290,
    'input_DATA_files':1,'only_already_observed_name_union_DATA':True,'all_source_native_key_variants_retained':True,
    'output_role':'all','native_split':'UNKNOWN_NOT_INFERRED','source_id':'ARCHIVE_SHA_AND_ORIGINAL_CSV_ORDINAL_LOCATOR',
    'original_consumer_full_keys_wp5_Writer_Budget_and_JSONL_reader_objects':True,'new_graph_key_SDF_or_archive_parsing':False,
    'new_fixture_methods':3,'all3_before_any_DATA':True,'allocated_cpus':16,'sequential_streams':1,'maximum_JSONL_line_bytes':8<<20,
    'wall_seconds_maximum':1800,'whole_output_cap_bytes':CAP,'new_network_UFF_QM_calls':0,'global_pool_release':False,
    'old_DATA_and_once_unchanged':True,'cost_overrun_action':'REPORT_AND_CONTINUE'}

def unique(refs):
    found={}
    for r in refs:
        Q.need(type(r) is dict and type(r['bytes'])is int and r['bytes']>=0,'SOURCE_OR_POSITIVE_PARENT_REFERENCE')
        Q.need(r['path'] not in found or found[r['path']]==r,'CONFLICTING_SAME_PATH_PINS');found[r['path']]=r
    return list(found.values())

def inputs(plan):
    ref=plan['accepted_native_union_root_review_reference'];Q.need(ref['path']==str(ROOT_ACCEPT),'SPECIFIC_ACTUAL_ROOT_UNION_REVIEW')
    r=meta(ref);b=meta(r['receipt_reference']);_,raw=K.K.account(r['accounting_reference'],b)
    Q.need(r['schema']=='ROOT_ACTUAL_DRUGS558002_NATIVE_CONSERVATIVE_UNION_REVIEW_V1'
        and r['status']=='ACTUAL_TECHNICAL_C0_ALL_NATIVE_OBSERVATIONS_ACCEPTED_FOR_CONSERVATIVE_UNION_ONLY' and r['reviewer']=='Root'
        and r['accepted_coverage']=={'source_key_rows':558002,'native_profile_adopted_not_replayed':1000,'new_native':557002,
            'native_completed':558002,'technical_unknown':0,'source_comparison_unknown':0,'source_native_key_mismatch_rows':126,
            'names_with_key_mismatch':31,'all_names':75099,'original_multi_SMILES_names':290}
        and r['scientific_global_decontamination_or_candidate_pool_release'] is False,'ACTUAL_ACCEPTED_CONSERVATIVE_UNION_NOT_GLOBAL_RELEASE')
    Q.need(b['schema']=='MARCEL_DRUGS_NATIVE_GRAPH_FULL_RECEIPT_V1'
        and b['status']=='ALL558002_NATIVE_GRAPH_OBSERVATIONS_COMPLETE_UNKNOWNS_AND_CONSERVATIVE_UNIONS_RETAINED'
        and b['mode']=='full' and str(b['job_id'])=='4523818' and b['uid']==1278 and b['node']=='compute-0-14'
        and b['endpoint']=='202.38.247.57:22' and b['all_native_graph_completed_rows']==558002
        and b['native_graph_NOT_YET_EXAMINED_rows']==b['native_graph_unknown_rows']==b['native_graph_source_key_comparison_UNKNOWN_rows']==0
        and b['native_graph_source_key_set_mismatch_rows']==126 and b['all_name_union_counts']=={
            'names':75099,'original_multi_SMILES_names':290,'names_with_unknown_native':0,'names_with_native_source_mismatch':31}
        and b['input_context']=={'all_source_rows':633101,'CSV_rows':75099,'SDF_rows':558002,'CSV_duplicate_name_groups':0,
            'CSV_missing_or_empty_names':0,'SDF_duplicate_ID_groups':0,'SDF_without_CSV_name':0,'CSV_without_SDF_name':0,
            'source_multi_SMILES_name_groups':290} and b['global_decontamination_or_pool_or_training_release'] is False,
        'ACTUAL_ALL558002_AND75099_CONTEXT_PRESERVED')
    old=meta(b['plan_reference']);proof=meta(b['startup_proof_reference']);request=meta(proof['request_reference'])
    Q.need(str(proof['job_id'])=='4523818' and proof['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1'
        and proof['uid']==1278 and proof['node']==b['node'] and proof['execution_admission_granted'] is True and request==proof['request']
        and request['execution_argv']==[Q.PY,'-B','-m',F.MODULE,'--plan',b['plan_reference']['path'],'--startup-proof',b['startup_proof_reference']['path']]
        and request['scope_key']==F.KEY and request['scope_parameters']==old['scope_parameters']==F.parameters()
        and request['kind']=='analysis' and request['cpus']==16 and request['pilot'] is False
        and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and request['data_references']==b['data_references']
        and b['plan_reference'] in request['source_references'],'ACTUAL_FULL_NATIVE_PLAN_PROOF_C0_NOT_FUTURE')
    for path in F.source_paths():Q.need(Q.pin(path) in request['source_references'],'UNCHANGED_ACTUAL_FULL_PRODUCER_SOURCE')
    f=b['fixtures'];Q.need(f['tests_run']==3 and all(f[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'REAL_FULL_SOURCE3_PASS')
    union=data_reference(b['all_name_union_reference']);archive=data_reference(b['data_references'][0])
    Q.need(union==r['declared_large_DATA_references_not_opened_by_Root']['all_name_union_reference']
        and union=={'path':str(UNION),'bytes':87064062,'sha256':'3741dbb7c169e4c05b98b19137118de8c63dd8f9a888495a6f4ed0b988e52bc0'}
        and archive['sha256']==ARCHIVE_SHA and plan['data_references']==[union],'ONLY_ACTUAL87MB_UNION_DATA_NO_JOURNAL_BLOB_OR_ARCHIVE_OPEN')
    policy=meta(plan['decontamination_policy_reference']);entry=[s for s in policy['sources'] if s['dataset']=='marcel_drugs75k']
    Q.need(policy['schema']=='expansion_decontamination_sources_v1' and len(entry)==1 and entry[0]['required_roles']==['all']
        and not entry[0].get('required_subdatasets') and policy['identity_policy']['exact']=='full_inchikey'
        and policy['identity_policy']['wp5']=='inchikey_first14+colon+last_protonation_character','EXACT_EXISTING_FIVE_FIELD_POLICY')
    chain=r['verified_closed_small_metadata_chain'];Q.need(chain['plan_reference']==b['plan_reference']
        and chain['startup_proof_reference']==b['startup_proof_reference'],'ROOT_ACCEPTANCE_ACTUAL_PARENT_BINDING')
    parents=[ref,r['receipt_reference'],r['accounting_reference'],raw,b['plan_reference'],b['startup_proof_reference'],proof['request_reference'],plan['decontamination_policy_reference']]
    for key in ('accepted_native_profile_receipt_reference','accepted_native_profile_accounting_reference','accepted_source_key_full_receipt_reference',
                'accepted_source_key_full_accounting_reference','profile_budget_root_review_reference'):
        Q.need(chain[key]==b[key],'ROOT_ACCEPTED_PRODUCER_ANCESTRY');parents.append(b[key])
    for item in parents:Q.need(Q.pin(item['path'])==item,'ACTUAL_SMALL_PARENT_AND_POLICY_BYTE_PINS')
    return b,unique(parents),archive,entry[0]
