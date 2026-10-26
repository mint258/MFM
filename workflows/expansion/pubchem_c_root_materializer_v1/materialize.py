"""Alpha Root metadata only: explicit freeze, then exactly one v13 shard plan.

No scientific index/journal/Parquet/TSV/gzip body is opened. No query, process
launch, SSH, Slurm submission, claim creation or pool release is implemented.
"""
import argparse,copy,csv,hashlib,io,json,os,re,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import contracts as C
from . import math_v1 as M
HERE=Q.ROOT/'code/pubchem_c_root_materializer_v1'
FILES=('__init__.py','materialize.py','math_v1.py','test_v1.py','README.md','approval_schema.json')
SCOPE7=Q.ROOT/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'
DENIED=set()


def pin_metadata(path):
    path=Q.literal(path);Q.need(path.suffix in {'.json','.py','.md','.txt','.sbatch'},'ONLY_NAMED_SMALL_METADATA_OR_CODE')
    Q.need(str(path) not in DENIED,'SCIENTIFIC_BODY_MUST_NEVER_BE_METADATA_READ');return Q.ref(path)


def meta(reference,schema=None,basename=None):
    Q.normalized(reference);path=Q.literal(reference['path'])
    Q.need(path.suffix=='.json' and str(path) not in DENIED and (basename is None or path.name==basename),'EXPLICIT_JSON_METADATA_ROLE_NOT_SCIENTIFIC_BODY')
    raw=Q.read_small(path);Q.need(len(raw)==reference['bytes'] and Q.sha(raw)==reference['sha256'],'ACTUAL_METADATA_PIN_CHANGED')
    value=json.loads(raw,object_pairs_hook=Q.pairs_unique)
    if schema is not None:Q.need(value['schema']==schema,'EXACT_METADATA_SCHEMA:'+schema)
    return value


def merge(*groups):
    values={}
    for group in groups:
        for value in group:
            Q.normalized(value);Q.need(value['path'] not in values or values[value['path']]==value,'CONFLICTING_PRODUCER_OR_ROOT_PIN')
            Q.need(value['path'] not in DENIED,'NO_SCIENTIFIC_BODY_IN_NEW_SOURCE_OR_PARENT_SET');values[value['path']]=dict(value)
    return [values[key] for key in sorted(values)]


def explicit_root(path,kind):
    reference=pin_metadata(path);value=meta(reference)
    Q.need(value['schema']==kind and value['status']=='ROOT_APPROVED' and value['reviewer']=='root'
        and value['endpoint']==Q.ENDPOINT and value['uid']==1264 and value['run_root']==str(Q.ROOT),'EXPLICIT_ROOT_APPROVAL_NOT_GENERATOR_SELF_APPROVAL')
    observed=[Q.ref(HERE/name) for name in FILES]
    Q.need(len(value['generator_source_references'])==len(observed) and {Q.canonical(r) for r in value['generator_source_references']}=={Q.canonical(r) for r in observed},'EXACT_PRE_REVIEWED_GENERATOR_SOURCE_SET')
    return value,reference


def accounting(reference,job):
    value=meta(reference,'SECONDARY_CPU_ACTUAL_ACCOUNTING_EVIDENCE_V1');p=value['actual_parent']
    Q.need(value['query_returncode']==0 and value['endpoint']==Q.ENDPOINT and value['uid']==1264
        and p['JobIDRaw']==job and p['State']=='COMPLETED' and p['ExitCode']=='0:0' and p['UID']=='1264'
        and p['AllocCPUS']=='16' and p['NodeList'] in Q.NODES and p['Partition']=='cpu','ACTUAL_OWN_ALPHA_CPU16_C0_ACCOUNTING')
    raw=value['raw_sacct_reference'];Q.normalized(raw);Q.need(Path(raw['path']).suffix=='.txt'
        and raw['bytes']<=65536 and raw['path'] not in DENIED,'BOUNDED_ACTUAL_RAW_SACCT_ONLY')
    text=Q.read_small(Q.literal(raw['path']));Q.need(len(text)==raw['bytes'] and Q.sha(text)==raw['sha256'],'EXACT_RAW_SACCT_PIN')
    rows=list(csv.DictReader(io.StringIO(text.decode('utf-8','strict')),delimiter='|'));selected=[r for r in rows if r.get('JobIDRaw')==job]
    Q.need(len(selected)==1 and all(selected[0][k]==p[k] for k in ('UID','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','Partition'))
        and int(p['ElapsedRaw'])>=0 and value['allocated_core_seconds_observed']==int(p['ElapsedRaw'])*16,'RAW_PARENT_COST_AND_STATE_BINDING')
    return value,raw


def source_core(receipt,manifest):
    required=[*(str(C.HERE/name) for name in C.FILES),*(row['target_reference']['path'] for row in manifest['files'])]
    by_path={r['path']:r for r in receipt['source_references']}
    Q.need(len(manifest['files'])==6 and all(path in by_path for path in required),'ACTUAL_B13_AND_FROZEN6_SOURCE_PINS')
    for row in manifest['files']:Q.need(row['target_reference']==by_path[row['target_reference']['path']], 'FROZEN6_TARGET_PIN_IDENTITY')
    for path in required:Q.verify(by_path[path])  # Only the fixed known13+6 source files; no arbitrary producer body follows.
    return [by_path[path] for path in required]


def context(root):
    ar,br=root['a_receipt_reference'],root['b_receipt_reference']
    a=meta(ar,'ALPHA_PUBCHEM_PHYSICAL_INVENTORY_RECEIPT_V1','receipt.json')
    b=meta(br,'ALPHA_PUBCHEM_UNIFORM_PROFILE_RECEIPT_V1','receipt.json')
    for value in (a,b):Q.need(value['endpoint']==Q.ENDPOINT and value['uid']==1264 and value['node'] in Q.NODES,'ACTUAL_ALPHA_PRODUCER_RECEIPT')
    Q.need(a['job_id']=='1884794' and a['mode']=='inventory' and a['status']=='ALPHA_PHYSICAL500_COMPLETE_NO_CHEMISTRY'
        and a['inventory']['records']==C.N and a['inventory']['part_count']==500 and a['inventory']['uncompressed_bytes']==C.UNCOMPRESSED_BYTES
        and a['inventory']['all500_parts_equal_Main_SHA_rows_bytes'] is True and a['inventory']['gzip_EOF_CRC_revalidated'] is True,'EXACT_ACTUAL_A1884794_FULL500_CLOSURE')
    Q.need(b['job_id']=='1884795' and b['mode']=='profile' and b['status']=='ALPHA_UNIFORM10000_EQUIVALENT_PROFILE_COMPLETE'
        and b['scope_parameters']==C.parameters('profile') and b['comparison']['scientific_mismatches']==0 and b['comparison']['compared_rows']==10000
        and b['comparison']['method']=='ALL_FIELDS_TYPED_BINARY64_NO_NUMERIC_TOLERANCE'
        and b['longest_excluded_from_uniform_mean'] is True and b['longest_diagnostic']['completed_rows']==16
        and b['full_source_pool_release_authorized'] is False and b['technical_unknown_is_chemical_exclusion'] is False,'EXACT_ACTUAL_B1884795_EQUIVALENT_SCIENTIFIC_PROFILE')
    for value in (a,b):
        f=value['fixtures'];Q.need(f['tests_run']==5 and all(f[key]==0 for key in ('failures','errors','skips','expected_failures','unexpected_successes')),'ACTUAL_FIVE_FIXTURES_NOT_FUTURE_RESULTS')
    DENIED.update(r['path'] for r in (a['raw_reference'],a['inventory']['source_index'],a['inventory']['uniform_locators'],a['inventory']['longest_locators'],
        b['reference_journal'],b['uniform']['features'],b['uniform']['full_dispatch_and_result_journal']))
    bp=meta(b['plan_reference'],C.MODES['profile']['plan'],'plan.json')
    DENIED.update(r['path'] for r in bp['data_references']);DENIED.add(bp['main_index_reference']['path'])
    Q.need(bp['mode']=='profile' and bp['scope_key']==C.MODES['profile']['key'] and bp['endpoint']==Q.ENDPOINT and bp['uid']==1264
        and bp['alpha_inventory_receipt_reference']==ar and bp['alpha_inventory_accounting_reference']==root['a_accounting_reference']
        and bp['source_references']==b['source_references'] and bp['raw_reference']==a['raw_reference']==b['raw_reference']
        and bp['frozen_manifest_reference']==a['frozen_manifest_reference']==b['frozen_manifest_reference'],'ACTUAL_B_PLAN_CONTEXT_NOT_REWRITTEN')
    Q.need(bp['raw_reference']['sha256']==C.RAW_SHA and bp['raw_reference']['bytes']==C.RAW_BYTES,'SAME_OFFICIAL_ORIGINAL_RAW')
    aa,aa_raw=accounting(root['a_accounting_reference'],'1884794');ba,ba_raw=accounting(root['b_accounting_reference'],'1884795')
    Q.need(aa['actual_parent']['NodeList']==a['node'] and ba['actual_parent']['NodeList']==b['node'],'ACTUAL_PRODUCER_NODE_COST_MATCH')
    raw_receipt=meta(bp['alpha_raw_validation_receipt_reference'],basename='receipt.json')
    Q.need(raw_receipt['job_id']=='1884769' and raw_receipt['status']=='EXACT_MAIN_PUBLIC_RAW_COPY_SHA_GZIP_EOF_VALIDATED'
        and raw_receipt['actual_alpha_raw_reference']==bp['raw_reference'],'REUSED_ACTUAL_ALPHA_COMPLETE_RAW_AUTHORITY')
    raw_account,raw_sacct=accounting(bp['alpha_raw_validation_accounting_reference'],'1884769')
    manifest=meta(bp['frozen_manifest_reference'],'PUBCHEM_ALPHA_EXACT_SCIENTIFIC_SOURCE_COPIES_V1','frozen_manifest.json')
    core=source_core(b,manifest);measurement=M.measured(b['uniform'])
    proposal_ref=b['proposed_full_partition'];proposal=meta(proposal_ref,'ALPHA_PUBCHEM_EXCLUSIVE_ORDINAL_MANIFEST_V1','proposed_full_partition_not_authorized.json')
    M.partition(proposal)
    Q.need(proposal['status']=='PROPOSED_NOT_ROOT_FROZEN' and proposal['profile_receipt_reference'] is None
        and proposal['source_raw_sha256']==C.RAW_SHA and proposal['source_index_reference']==a['inventory']['source_index']
        and proposal['alpha_inventory_receipt_reference']==ar,'ACTUAL_CPU_B_METADATA_PROPOSAL_NOT_LOGIN_INDEX_PARSE')
    parents=merge(bp['parent_evidence_references'],[ar,root['a_accounting_reference'],aa_raw,br,root['b_accounting_reference'],ba_raw,b['plan_reference'],
        bp['alpha_raw_validation_receipt_reference'],bp['alpha_raw_validation_accounting_reference'],raw_sacct])
    costs={'1884794':aa['allocated_core_seconds_observed'],'1884795':ba['allocated_core_seconds_observed'],'1884769':raw_account['allocated_core_seconds_observed']}
    return {'a':a,'b':b,'b_plan':bp,'core':core,'measurement':measurement,'proposal':proposal,'proposal_reference':proposal_ref,
        'parents':parents,'known_alpha_three_parent_core_seconds':costs,'known_three_parent_core_seconds_sum':sum(costs.values()),
        'cost_scope':'EXACT_THESE_THREE_ALPHA_PARENTS_NOT_WHOLE_DATA_LINE_MASTER'}


def new_control(path):
    path=Q.literal(path);Q.need(Q.ROOT/'control' in path.parents and not path.exists(),'NEW_OWN_CONTROL_METADATA_LEAF_ONLY')
    path.mkdir(parents=True,mode=0o700,exist_ok=False);return path


def freeze(approval_path,out):
    root,approval_ref=explicit_root(approval_path,'ROOT_APPROVED_PUBCHEM_C_METADATA_FREEZE_V1')
    for key in ('actual_profile_equivalence_reviewed','actual_related_cost_accounting_reviewed','one_part_partition_reviewed',
                'technical_unknown4_preserved_not_excluded','scientific_quality_thresholds_unchanged','metadata_freeze_only_no_submission'):
        Q.need(root[key] is True,'EXPLICIT_ROOT_FREEZE_DECISION:'+key)
    Q.need(type(root['parts_per_shard']) is int and root['parts_per_shard']==1 and root['expected_shards']==500 and root['population_N']==C.N
        and root['pool_decontamination_or_filtered_dedup1M_release'] is False,'EXACT500_PHYSICAL_SCOPE_WITH_NO_GLOBAL_RELEASE')
    ctx=context(root);rows=[]
    for shard in ctx['proposal']['shards']:
        n=shard['last_ordinal']-shard['first_ordinal']+1;rows.append(dict(shard,**M.reviewed_limits(ctx['measurement'],root,n)))
    out=new_control(out);source=ctx['measurement']
    budget={'schema':'ALPHA_PUBCHEM_PROFILE_DERIVED_OUTPUT_BUDGET_V1','status':'ROOT_REVIEWED_ACTUAL_PROFILE_COST_AND_STORAGE',
        'profile_receipt_reference':root['b_receipt_reference'],'frozen_manifest_reference':ctx['b']['frozen_manifest_reference'],
        'root_approval_reference':approval_ref,'uniform_rows':10000,'uniform_event_reference':source['event_reference'],'uniform_Parquet_reference':source['Parquet_reference'],
        'uniform_event_plus_Parquet_bytes':source['row_payload_bytes'],'reported_uniform_worker_task_phase_sums':ctx['b']['uniform']['worker_task_phase_sums'],
        'reported_uniform_phase_wall_seconds':ctx['b']['uniform']['phase_wall_seconds'],'longest_excluded_from_uniform_projection':True,
        'total_bundle_bytes_or_comparison_journal_used_in_mean':False,'group_receipt_worker_logs_fixtures_directory_metadata_in_Root_admin_reserve':True,
        'worst_case_feature_size_proven':False,'reviewed_shards':rows,'known_actual_cost_scope':ctx['cost_scope'],
        'known_alpha_three_parent_core_seconds':ctx['known_alpha_three_parent_core_seconds'],'known_three_parent_core_seconds_sum':ctx['known_three_parent_core_seconds_sum'],
        'all_other_original_failed_startup_and_future_parents_still_require_Root_master_accounting':True,'cost_overrun_action':'REPORT_AND_CONTINUE',
        'sum_planned_shard_caps_not_simultaneous_reservation_bytes':sum(row['output_cap_bytes'] for row in rows),'actual_storage_admission_deferred_to_current_v13_controller':True,
        'pool_release_authorized':False,'future_jobIDs_created':False}
    budget_ref=Q.write_new(out/'profile_output_budget.json',budget)
    partition=copy.deepcopy(ctx['proposal']);partition.update(status='ROOT_FROZEN_EXCLUSIVE_SUBMISSION_MANIFEST',
        profile_receipt_reference=root['b_receipt_reference'],profile_output_budget_reference=budget_ref,
        original_proposal_reference=ctx['proposal_reference'],root_approval_reference=approval_ref)
    M.partition(partition);partition_ref=Q.write_new(out/'full_shard_manifest.json',partition)
    receipt={'schema':'PUBCHEM_C_METADATA_FREEZE_RECEIPT_V1','status':'ROOT_REVIEWED_BUDGET_AND500_PARTITION_METADATA_CLOSED_NO_SUBMISSION',
        'endpoint':Q.ENDPOINT,'uid':1264,'root_approval_reference':approval_ref,'a_receipt_reference':root['a_receipt_reference'],
        'a_accounting_reference':root['a_accounting_reference'],'b_receipt_reference':root['b_receipt_reference'],
        'b_accounting_reference':root['b_accounting_reference'],'b_plan_reference':ctx['b']['plan_reference'],
        'proposed_partition_reference':ctx['proposal_reference'],'profile_output_budget_reference':budget_ref,'full_shard_manifest_reference':partition_ref,
        'actual_parent_evidence_references':ctx['parents'],'same_scientific_core_source_references':ctx['core'],
        'generator_source_references':root['generator_source_references'],'known_actual_cost_scope':ctx['cost_scope'],
        'known_alpha_three_parent_core_seconds':ctx['known_alpha_three_parent_core_seconds'],
        'shards':500,'scientific_index_or_journal_Parquet_bodies_read':0,'jobs_queried_submitted_or_claims_created':0,
        'source_or_old_results_modified':False,'pool_decontamination_filtered_dedup1M_release':False,'created_at':Q.now()}
    return Q.write_new(out/'freeze_receipt.json',receipt)


def plan_one(approval_path,out):
    root,approval_ref=explicit_root(approval_path,'ROOT_APPROVED_SINGLE_PUBCHEM_C_SHARD_PLAN_V1')
    Q.need(root['single_shard_only_no_submission'] is True,'EXPLICIT_ONE_SHARD_METADATA_ONLY_APPROVAL')
    fr=root['freeze_receipt_reference'];f=meta(fr,'PUBCHEM_C_METADATA_FREEZE_RECEIPT_V1','freeze_receipt.json')
    Q.need(f['status']=='ROOT_REVIEWED_BUDGET_AND500_PARTITION_METADATA_CLOSED_NO_SUBMISSION' and f['shards']==500,'ACTUAL_COMPLETE_METADATA_FREEZE_NOT_PARTIAL')
    frozen_root=meta(f['root_approval_reference'],'ROOT_APPROVED_PUBCHEM_C_METADATA_FREEZE_V1');ctx=context(frozen_root)
    Q.need(f['a_receipt_reference']==frozen_root['a_receipt_reference'] and f['b_receipt_reference']==frozen_root['b_receipt_reference']
        and f['same_scientific_core_source_references']==ctx['core'],'SAME_CURRENT_ACTUAL_A_B_AND13_PLUS6_CORE')
    partition=meta(f['full_shard_manifest_reference'],'ALPHA_PUBCHEM_EXCLUSIVE_ORDINAL_MANIFEST_V1');M.partition(partition)
    budget=meta(f['profile_output_budget_reference'],'ALPHA_PUBCHEM_PROFILE_DERIVED_OUTPUT_BUDGET_V1')
    Q.need(partition['source_raw_sha256']==C.RAW_SHA and partition['source_index_reference']==ctx['a']['inventory']['source_index']
        and partition['alpha_inventory_receipt_reference']==frozen_root['a_receipt_reference']
        and partition['shards']==ctx['proposal']['shards'] and partition['original_proposal_reference']==ctx['proposal_reference'],
        'FROZEN_PARTITION_EXACTLY_THE_ACTUAL_B_PROPOSAL_WITH_NO_INDEX_BODY_READ')
    Q.need(budget['status']=='ROOT_REVIEWED_ACTUAL_PROFILE_COST_AND_STORAGE'
        and budget['profile_receipt_reference']==frozen_root['b_receipt_reference'] and budget['frozen_manifest_reference']==ctx['b']['frozen_manifest_reference']
        and budget['uniform_event_plus_Parquet_bytes']==ctx['measurement']['row_payload_bytes']
        and budget['longest_excluded_from_uniform_projection'] is True and budget['worst_case_feature_size_proven'] is False,'ACTUAL_UNIFORM_ONLY_BUDGET_BINDING')
    rederived=[dict(row,**M.reviewed_limits(ctx['measurement'],frozen_root,row['last_ordinal']-row['first_ordinal']+1)) for row in partition['shards']]
    Q.need(budget['reviewed_shards']==rederived,'ALL500_PROFILE_MATH_AND_EXPLICIT_ROOT_LIMITS_REDERIVED_EXACTLY')
    index=root['shard_index'];Q.need(type(index) is int and 0<=index<500,'EXACT_SINGLE_SHARD_INDEX')
    shard=partition['shards'][index];limits=[row for row in budget['reviewed_shards'] if row['shard_index']==index]
    Q.need(partition['status']=='ROOT_FROZEN_EXCLUSIVE_SUBMISSION_MANIFEST' and partition['profile_output_budget_reference']==f['profile_output_budget_reference']
        and partition['profile_receipt_reference']==frozen_root['b_receipt_reference'] and len(limits)==1,'MATCHED_ROOT_FROZEN_MANIFEST_AND_BUDGET')
    limits=limits[0];Q.need(root['wall_seconds']==limits['wall_seconds'] and root['output_cap_bytes']==limits['output_cap_bytes'],'ROOT_SINGLE_PLAN_MATCHES_REVIEWED_WALL_CAP')
    catalog_ref=root['supplemental_source_catalog_reference'];catalog=meta(catalog_ref,'ROOT_APPROVED_PUBCHEM_C_SOURCE_CATALOG_V1')
    Q.need(catalog['status']=='ROOT_APPROVED' and catalog['reviewer']=='root' and catalog['endpoint']==Q.ENDPOINT
        and catalog['uid']==1264 and catalog['run_root']==str(Q.ROOT),'ROOT_APPROVED_CURRENT_V13_SUPPLEMENTAL_SOURCE_PINS')
    core_paths={ref['path'] for ref in ctx['core']};Q.need(all(ref in ctx['b']['source_references'] for ref in ctx['core']),'SAME_ACTUAL_B_SCIENTIFIC_CORE')
    source_refs=merge(ctx['b']['source_references'],catalog['source_references'],root['generator_source_references'],
        [approval_ref,fr,f['root_approval_reference'],catalog_ref,f['profile_output_budget_reference'],f['full_shard_manifest_reference']])
    required_queue={str(Q.ROOT/'code/secondary_cpu_readonly_queue_v13'/name) for name in ('controller.py','adapters.py')}
    Q.need(required_queue<={r['path'] for r in source_refs},'EXACT_V13_TWO_SOURCE_PINS_REQUIRED')
    for value in source_refs:
        if value['path'] in required_queue:Q.verify(value)  # Known source-code pair, before importing v13.
    node=root['node'];science_out=Q.literal(root['output_directory']);proof=Q.literal(root['startup_proof_path'])
    Q.need(node in Q.NODES and Q.ROOT/'artifacts' in science_out.parents and not science_out.exists()
        and Q.ROOT/'control' in proof.parents and not proof.exists(),'NEW_EXACT_NODE_ARTIFACT_LEAF_AND_STARTUP_PATH')
    bp=ctx['b_plan'];Q.need(root['python']==bp['python'],'SAME_ACTUAL_B_PYTHON_EXECUTABLE_NO_NEW_RUNTIME_GUESS')
    out=Q.literal(out);Q.need(Q.ROOT/'control' in out.parents and not out.exists(),'NEW_SINGLE_SHARD_PLAN_METADATA_LEAF')
    plan_path=out/'plan.json';argv=[bp['python'],'-B','-m',C.MODULE,'--plan',str(plan_path),'--startup-proof',str(proof)]
    bounds=[shard[key] for key in ('first_part','last_part','first_ordinal','last_ordinal')];spec=C.MODES['full_shard']
    fields=('endpoint','uid','run_root','raw_reference','main_index_reference','main_evidence_references','metadata_relocation_reference',
        'frozen_manifest_reference','alpha_raw_validation_receipt_reference','alpha_raw_validation_accounting_reference',
        'resource_authority_reference','cost_decision_reference','alpha_inventory_receipt_reference','alpha_inventory_accounting_reference')
    plan={key:copy.deepcopy(bp[key]) for key in fields}
    plan.update(schema=spec['plan'],producer_key=spec['key'],scope_key=spec['key'],stage=spec['stage'],mode='full_shard',
        scope_parameters=C.parameters('full_shard',*bounds),scope_mode=spec['scope_mode'],performance_profile=False,kind='analysis',pilot=False,
        python=bp['python'],node=node,cpus=16,memory_policy=Q.POLICY,wall_seconds=limits['wall_seconds'],output_cap_bytes=limits['output_cap_bytes'],
        execution_argv=argv,startup_proof_path=str(proof),output_directory=str(science_out),shard_index=index,
        **{key:shard[key] for key in ('first_part','last_part','first_ordinal','last_ordinal')},
        source_references=source_refs,data_references=[ctx['a']['inventory']['source_index']],parent_evidence_references=ctx['parents'],
        accepted_profile_receipt_reference=frozen_root['b_receipt_reference'],accepted_profile_accounting_reference=frozen_root['b_accounting_reference'],
        full_shard_manifest_reference=f['full_shard_manifest_reference'],profile_output_budget_reference=f['profile_output_budget_reference'],
        metadata_freeze_receipt_reference=fr,root_single_shard_approval_reference=approval_ref,scientific_body_IO_by_generator=0,
        automatic_submission_authorized=False,full_source_pool_release_authorized=False,guide_filtered_dedup_1M_reference_completed=False)
    from secondary_cpu_readonly_queue_v13 import adapters as V13
    review={key:copy.deepcopy(plan[key]) for key in V13.REVIEW_FIELDS}
    review.update(schema='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1',status='APPROVED_FOR_EXACT_STAGE',reviewer='root',
        approved_source_references=source_refs,actual_profile_equivalence_and_cost_reviewed=True,
        explicit_root_single_shard_approval_reference=approval_ref,metadata_generation_is_not_scientific_or_storage_acceptance=True)
    out=new_control(out);plan['root_review_reference']=Q.write_new(out/'root_review.json',review)
    plan_ref=Q.write_new(plan_path,plan)
    adapter=V13.readonly(plan_path,None,node,limits['wall_seconds'])  # Only the already-reviewed metadata contract; never submission.
    return Q.write_new(out/'materialization_receipt.json',{'schema':'PUBCHEM_C_SINGLE_SHARD_METADATA_RECEIPT_V1','status':'EXACT_V13_METADATA_CONTRACT_CLOSED_NO_SUBMISSION',
        'plan_reference':plan_ref,'root_review_reference':plan['root_review_reference'],'freeze_receipt_reference':fr,'root_approval_reference':approval_ref,
        'shard_index':index,'exact_bounds':{key:shard[key] for key in ('first_part','last_part','first_ordinal','last_ordinal')},
        'source_references_verified_by_v13_metadata_adapter':True,'scientific_body_hashes_or_reads':0,'jobs_queried_submitted_or_claims_created':0,
        'future_jobID_or_startup_proof_hash_created':False,'storage_admission_pending_current_scope7_controller':True,'pool_release_authorized':False})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('freeze','plan-one'));p.add_argument('--root-approval',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();Q.login()
    value=freeze(args.root_approval,args.output) if args.action=='freeze' else plan_one(args.root_approval,args.output)
    print(json.dumps({'metadata_receipt_reference':value,'scientific_body_reads':0,'submissions':0,'claims_created':0,'global_release':False}))
    return 0

if __name__=='__main__':raise SystemExit(main())
