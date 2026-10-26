"""Root metadata-only secondary deployment and independently reviewed acquisition plans."""
from __future__ import annotations
import argparse,hashlib,json,math,pathlib,re
from contracts import (SECONDARY_ROOT,ENDPOINT,UID,ALLOWED_NODES,need,pin,load,write_new,
    source_from_head,validate_alpha_authority)
REL=pathlib.Path('workflows/expansion/secondary_source_acquisition_v1')


def remap(origin,target):return {'path':str(target),'bytes':origin['bytes'],'sha256':origin['sha256']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository',type=pathlib.Path,required=True);p.add_argument('--head-dir',type=pathlib.Path,required=True)
    p.add_argument('--catalog',type=pathlib.Path,required=True);p.add_argument('--authority',type=pathlib.Path,required=True)
    p.add_argument('--output-dir',type=pathlib.Path,required=True);p.add_argument('--secondary-python',required=True)
    p.add_argument('--node',required=True);p.add_argument('--name',required=True);p.add_argument('--reviewer',required=True)
    p.add_argument('--stage',choices=('profile','sql'),default='profile');p.add_argument('--profile-receipt',type=pathlib.Path)
    p.add_argument('--profile-cost',type=pathlib.Path);p.add_argument('--sql-wall-seconds',type=int)
    a=p.parse_args();here=a.repository/REL
    need(a.reviewer=='root' and pathlib.Path(__file__).absolute()==here/'materialize_v1.py','ROOT_INTEGRATED_REVIEWED_METADATA_ENTRY_REQUIRED')
    need(re.fullmatch(r'[a-z0-9_]{1,96}',a.name) and a.node in ALLOWED_NODES and pathlib.Path(a.secondary_python).is_absolute(),'NEW_NAME_ACTUAL_ALPHA_NODE_AND_ABSOLUTE_PYTHON_REQUIRED')
    need(not a.output_dir.exists(),'NEW_LOCAL_METADATA_PACKAGE_ONLY')
    authority=load(a.authority);validate_alpha_authority(authority)
    receipt=load(a.head_dir/'receipt.json');catalog_ref=pin(a.catalog)
    need(receipt['schema']=='SB5_OFFICIAL_SOURCE_HEAD_RECEIPT_V1' and receipt['status']=='HEAD_OBSERVATIONS_COMPLETE_ALL_SOURCE_COVERAGE_PENDING'
        and receipt['job_id']=='4521094' and receipt['uid']==1278,'ACTUAL_MAIN30HEAD_LINEAGE_REQUIRED_NOT_SECONDARY_PROOF')
    need(receipt['catalog_reference']['sha256']==catalog_ref['sha256'] and receipt['catalog_reference']['bytes']==catalog_ref['bytes'],'ACTUAL_CATALOG_LINEAGE_REQUIRED')
    observed={row['source_id']:row['reference'] for row in receipt['observations']};headers={};origins=[]
    for name in ('coconut_csv_full','coconut_csv_lite','coconut_sql'):
        local=a.head_dir/(name+'.json');actual=pin(local)
        need(actual==observed[name],'ACTUAL_HEAD_FILE_PIN_CHANGED')
        headers[name]=load(local);origins.append((local,SECONDARY_ROOT/'authority/coconut_head'/local.name))
    full=source_from_head(headers['coconut_csv_full'],'coconut_csv_full');sql=source_from_head(headers['coconut_sql'],'coconut_sql')
    selected=full if a.stage=='profile' else sql
    stage='CSV_ZIP_PROFILE' if a.stage=='profile' else 'PLAIN_SQL_FULL_DOWNLOAD'
    profile=None;cost=None;extra_parents=[];projection=None
    if a.stage=='sql':
        need(a.profile_receipt is not None and a.profile_cost is not None and a.sql_wall_seconds is not None,'SQL_NEEDS_ACTUAL_PROFILE_COST_AND_NEW_EXPLICIT_WALL_REVIEW')
        profile=load(a.profile_receipt);cost=load(a.profile_cost)
        need(profile['schema']=='SECONDARY_COCONUT_ACQUISITION_RECEIPT_V1' and profile['status']=='ACTUAL_CSV_ZIP_PROFILE_COMPLETE_NOT_IDENTITY_AUTHORITY'
            and profile['endpoint']==ENDPOINT and profile['uid']==UID and profile['payload_download_complete'],'ACTUAL_SECONDARY_PROFILE_REQUIRED')
        need(cost['schema']=='SECONDARY_COCONUT_ACTUAL_PARENT_COST_V1' and cost['successful_profile_and_parent_complete'] is True
            and cost['endpoint']==ENDPOINT and cost['uid']==UID and cost['actual_parent']['JobIDRaw']==profile['job_id'],'ACTUAL_SUCCESSFUL_PROFILE_PARENT_COST_REQUIRED')
        local_profile=pin(a.profile_receipt)
        need(cost['receipt']['bytes']==local_profile['bytes'] and cost['receipt']['sha256']==local_profile['sha256'],'ACTUAL_PROFILE_COST_REFERENCE_DIFFERS')
        seconds=profile['download_wall_seconds_observed'];size=profile['payload_reference']['bytes']
        need(type(seconds) in (int,float) and seconds>0 and size==full['expected_content_length'],'ACTUAL_PROFILE_DOWNLOAD_MEASUREMENT_REQUIRED')
        projected=seconds*sql['expected_content_length']/size
        wall=a.sql_wall_seconds;need(0<wall<=172800 and wall%60==0 and wall>=math.ceil(projected*1.5+120),'ROOT_SQL_WALL_MUST_BE_WHOLE_MINUTES_AND_COVER_MEASURED_PROJECTION_WITH_MARGIN')
        projection={'observed_profile_download_seconds':seconds,'observed_profile_bytes':size,'linear_payload_seconds':projected,
            'linear_allocated_core_seconds_estimate':projected*16,'same_endpoint_path_throughput_assumption_not_guarantee':True,
            'actual_profile_allocated_core_seconds':cost['allocated_core_seconds']}
        origins.extend([(a.profile_receipt,SECONDARY_ROOT/'authority/coconut_profile'/('profile_'+profile['job_id']+'.json')),
                        (a.profile_cost,SECONDARY_ROOT/'authority/coconut_profile'/('profile_cost_'+profile['job_id']+'.json'))])
    else:wall=3600
    source_files=[*sorted(here.glob('*.py'))]
    if (here/'README.md').is_file():source_files.append(here/'README.md')
    origins.extend((path,SECONDARY_ROOT/REL/path.name) for path in source_files)
    origins.extend([(a.authority,SECONDARY_ROOT/'authority/secondary_resource_authorization.json'),
        (a.head_dir/'receipt.json',SECONDARY_ROOT/'authority/coconut_head/receipt.json'),
        (a.catalog,SECONDARY_ROOT/'authority/coconut_head/catalog.json')])
    deploy=[];refs=[]
    for local,target in origins:
        actual=pin(local);target_ref=remap(actual,target);refs.append(target_ref)
        deploy.append({'origin_reference':actual,'secondary_reference':target_ref})
    need(len({r['path'] for r in refs})==len(refs),'UNIQUE_SECONDARY_DEPLOYMENT_TARGETS_REQUIRED')
    control=SECONDARY_ROOT/'control/source_acquisition';plan_path=control/(a.name+'.plan.json');review_path=control/(a.name+'.review.json')
    proof_path=SECONDARY_ROOT/'control/secondary_startup'/(a.name+'.json');output=SECONDARY_ROOT/'artifacts/source_acquisition'/a.name
    argv=[a.secondary_python,'-B',str(SECONDARY_ROOT/REL/'run_v1.py'),'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    head_refs={name:next(r for r in refs if r['path']==str(SECONDARY_ROOT/'authority/coconut_head'/(name+'.json'))) for name in headers}
    parents=[next(r for r in refs if r['path']==str(SECONDARY_ROOT/'authority/coconut_head/receipt.json')),head_refs['coconut_csv_full'],head_refs['coconut_sql']]
    if a.stage=='sql':parents.extend(r for r in refs if '/authority/coconut_profile/' in r['path'])
    output_cap=1024**3 if a.stage=='profile' else selected['expected_content_length']+512*1024**2
    limits={'max_zip_members':128,'max_csv_members':8,'max_total_inflated_bytes':32*1024**3,'max_columns':512,
        'max_header_name_characters':256,'max_field_characters':8*1024**2,'max_physical_line_characters':16*1024**2,
        'max_physical_lines_per_record':256,'max_logical_record_characters':16*1024**2}
    parameters={'network_workers':1,'maximum_host_concurrency':2,'range_requests_authorized':False,
        'expected_raw_bytes':selected['expected_content_length'],'source_id':selected['source_id'],'CSV_inactive_coverage_claimed':False,
        'normalization_or_release_authorized':False}
    common={'stage':stage,'source':selected,'scope_parameters':parameters,'wall_seconds':wall,'output_cap_bytes':output_cap,
        'endpoint':ENDPOINT,'uid':UID,'run_root':str(SECONDARY_ROOT),'execution_argv':argv,'parent_evidence_references':parents}
    review=dict(common,schema='EXACT_SECONDARY_SOURCE_ROOT_REVIEW_V1',status='APPROVED_FOR_EXACT_STAGE',reviewer='root',
        resource_authority_reference=next(r for r in refs if r['path']==str(SECONDARY_ROOT/'authority/secondary_resource_authorization.json')),
        approved_source_references=refs,actual_profile_and_cost_reviewed=a.stage=='sql',profile_projection=projection,
        note='Source download/structure only. No chemistry, identity, active-inactive completeness, release, or automatic SQL promotion.')
    a.output_dir.mkdir(parents=True)
    write_new(a.output_dir/'review.json',review);review_ref=remap(pin(a.output_dir/'review.json'),review_path)
    plan=dict(common,schema='SECONDARY_COCONUT_ACQUISITION_PLAN_V1',plan_path=str(plan_path),startup_proof_path=str(proof_path),
        root_review_reference=review_ref,resource_authority_reference=review['resource_authority_reference'],source_references=refs+[review_ref],
        source_head_references=head_refs,output_directory=str(output),python_version_expected='3.12.7',
        node=a.node,partition='cpu',cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',memory_requested=False,exclusive_requested=False,
        curl_max_time_seconds=max(30,wall-300),csv_limits=limits,algorithm_self_rss_soft_limit_bytes=512*1024**2,
        minimum_mem_available_bytes=512*1024**2,SQL_auto_submission=False,identity_release_authorized=False,
        source_month_or_ETag_is_not_SHA_or_release_pin=True,profile_projection=projection)
    if a.stage=='sql':plan['accepted_profile_reference']=next(r for r in parents if '/authority/coconut_profile/profile_' in r['path'] and 'profile_cost_' not in r['path'])
    write_new(a.output_dir/'plan.json',plan);plan_ref=remap(pin(a.output_dir/'plan.json'),plan_path)
    spec={'schema':'SECONDARY_SOURCE_ACQUISITION_CPU_SPEC_V1','status':'PREPARED_NOT_SUBMITTED','kind':'source_acquisition',
        'endpoint':ENDPOINT,'uid':UID,'node':a.node,'partition':'cpu','cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'memory_requested':False,'exclusive_requested':False,'wall_seconds':wall,'output_cap_bytes':output_cap,
        'effective_free_reserve_bytes':200000000000,'working_directory':str(SECONDARY_ROOT),'execution_argv':argv,
        'plan_reference':plan_ref,'root_review_reference':review_ref,'startup_proof_path':str(proof_path),
        'source_references':refs+[review_ref,plan_ref],'automatic_submission':False,'actual_cost_closure_required':True}
    write_new(a.output_dir/'spec.json',spec)
    proposal={'schema':'COCONUT_PLAIN_SQL_NEXT_STAGE_PROPOSAL_V1','status':'PENDING_REAL_PROFILE_COST_AND_SEPARATE_ROOT_REVIEW',
        'source':sql,'physical_SHA256':None,'download_authorized':False,'auto_submission':False,
        'required_actual_parents':['CSV_ZIP_PROFILE complete receipt','this endpoint terminal sacct cost closure'],
        'SQL_is_plain_file_not_ZIP':True,'CSV_inactive_coverage_proven':False}
    write_new(a.output_dir/'sql_proposal.json',proposal)
    deploy.extend([{'origin_reference':pin(a.output_dir/'review.json'),'secondary_reference':review_ref},
                   {'origin_reference':pin(a.output_dir/'plan.json'),'secondary_reference':plan_ref}])
    write_new(a.output_dir/'deployment_manifest.json',{'schema':'SECONDARY_EXACT_SOURCE_DEPLOYMENT_V1','endpoint':ENDPOINT,
        'uid':UID,'run_root':str(SECONDARY_ROOT),'files':deploy,'network_or_transfer_commands_run':False})
    print(json.dumps({'status':spec['status'],'stage':stage,'spec':pin(a.output_dir/'spec.json'),
        'deployment_manifest':pin(a.output_dir/'deployment_manifest.json'),'physical_data_bodies_read':False,'SQL_auto_submission':False}))
if __name__=='__main__':main()
