"""Smallmetadata-only exact32 augmentation plan/spec; never data bodies or submit."""
from __future__ import annotations
import argparse,hashlib,json,pathlib
RUN=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=RUN/'repository'
HERE=pathlib.Path(__file__).absolute().parent
from workflows.data_v1_final.conformers.pm7_hof_augmentation32_v1 import contract as C
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'


def load(path):
    path=pathlib.Path(path)
    if path.stat().st_size>2<<20:raise ValueError('SMALL_METADATA_ONLY_NO_BODY')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def pin(path):
    path=pathlib.Path(path).absolute()
    if path.stat().st_size>2<<20:raise ValueError('SMALL_PIN_ONLY_NO_BODY')
    raw=path.read_bytes();return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def triple(r):return {k:r[k] for k in ('path','bytes','sha256')}


def unique(rows):
    result={}
    for row in rows:
        row=triple(row)
        if row['path'] in result and result[row['path']]!=row:raise ValueError('CONFLICTING_METADATA_REFERENCE')
        result[row['path']]=row
    return list(result.values())


def save(path,value):
    with pathlib.Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
    return pin(path)


def checked(ref):
    if pin(ref['path'])!=triple(ref):raise ValueError('ACTUAL_SMALL_REFERENCE_CHANGED:'+ref['path'])
    return load(ref['path'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('geometry-receipt','geometry-accounting','hof-authority-review','quota-reuse-review',
                 'resource-authority','metadata-directory','output','reason'):p.add_argument('--'+name,type=pathlib.Path if name!='reason' else str,required=True)
    p.add_argument('--approve',action='store_true');a=p.parse_args()
    if not a.approve or not a.reason.strip():raise ValueError('EXPLICIT_ROOT_REVIEW_REQUIRED')
    if HERE!=REPO/'workflows/data_v1_final/conformers/pm7_hof_augmentation32_v1':raise ValueError('ACTUAL_ROOT_SOURCE_REQUIRED')
    receipt=load(a.geometry_receipt);account=load(a.geometry_accounting);hof=load(a.hof_authority_review)
    if (receipt.get('schema')!='PM7_INDEPENDENT_CACHE32_RECEIPT_V1' or receipt.get('job_id')!='4521602'
        or receipt.get('status')!='ACTUAL32_PM7_GEOMETRY_AND_GOLDEN16_CLOSED_REQUIRES_ROOT_REVIEW'
        or receipt.get('geometry_complete')!=32 or receipt.get('completed_packets')!=32
        or receipt.get('golden_geometry_equal_count')!=16 or receipt.get('errors')
        or receipt.get('unstarted_molecule_ids') or receipt.get('dispatched_without_validated_return_ids')):
        raise ValueError('ONLY_ACTUAL_CLOSED_GEOMETRY32')
    parents=account.get('parents',[])
    if (account.get('status')!='ACTUAL_PARENT_ACCOUNTING_CLOSED' or account.get('endpoint')!='202.38.247.57:22'
        or account.get('uid')!=1278 or account.get('query_returncode')!=0 or len(parents)!=1
        or str(parents[0]['job_id'])!='4521602' or parents[0]['state']!='COMPLETED'
        or parents[0]['exit_code']!='0:0' or parents[0]['alloc_cpus']!=16):raise ValueError('ACTUAL_PARENT_C0_REQUIRED')
    raw_ref=account['raw_sacct_reference']
    if pin(raw_ref['path'])!=triple(raw_ref):raise ValueError('EXACT_RAW_ACCOUNTING_REQUIRED')
    lines=pathlib.Path(raw_ref['path']).read_text().splitlines();rows=[v.split('|') for v in lines if v.startswith('4521602|')]
    if len(rows)!=1 or rows[0][1:3]!=['COMPLETED','0:0']:raise ValueError('RAW_PARENT_C0_ROW_REQUIRED')
    prepared=checked(receipt['prepared_reference']);authority=checked(prepared['source_authority_reference'])
    if (authority['common'] is not False or authority['full_execution_authorized'] is not False
        or len(authority['selected_molecule_ids'])!=32 or len(authority['golden16_ids'])!=16
        or sum(row['software_bound']['records'] for row in prepared['tasks'])!=203):
        raise ValueError('EXACT_32_SOURCE203_AND_GOLDEN16')
    if (hof.get('schema')!='ROOT_PM7_CACHE_CANONICAL_HOF_AUTHORITY_V1' or hof.get('status')!='VERIFIED_FROZEN_PM7_B_SCALAR_READER'
        or hof.get('reviewer')!='root' or hof.get('endpoint')!='202.38.247.57:22' or hof.get('uid')!=1278
        or hof.get('registry_id')!=60 or hof.get('unit')!='kcal/mol' or hof.get('native_energy_fallback_allowed') is not False):
        raise ValueError('INDEPENDENT_REAL_ROOT_VERIFIED_HOF_REVIEW_REQUIRED_NO_AUTO_UPGRADE')
    projection=checked(hof['projection_receipt_reference']);source_files=checked(projection['source_files'])
    if projection['status']!='CATALOG_METADATA_PROJECTION_VERIFIED' or hof['source_files_reference']!=projection['source_files']:
        raise ValueError('EXACT_CLOSED_CATALOG_SOURCE_LOCATORS')
    previous_proof=checked(receipt['startup_proof_reference'])
    if str(previous_proof['job_id'])!='4521602':raise ValueError('EXACT_HISTORICAL_DEPENDENCY_INVENTORY')
    # Historical proof is only a source dependency inventory; never new admission.
    from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import io as I
    reuse,Q,quota_resources=I.R.quota_reuse(pin(a.quota_reuse_review),I.F.sources())
    dependencies=unique(previous_proof['request']['source_references']+I.sources()+
                        [pin(HERE/name) for name in C.FILES])
    for reference in dependencies:
        if pin(reference['path'])!=reference:raise ValueError('EXACT_CURRENT_ROOT_DEPENDENCY_BYTES_REQUIRED:'+reference['path'])
    metadata=unique([pin(a.geometry_receipt),pin(a.geometry_accounting),raw_ref,receipt['prepared_reference'],
      prepared['source_authority_reference'],receipt['startup_proof_reference'],pin(a.hof_authority_review),
      hof['projection_receipt_reference'],pin(a.quota_reuse_review),pin(a.resource_authority),*quota_resources,
      *hof.get('source_authority_evidence_references',[])])
    for reference in metadata:
        if pin(reference['path'])!=reference:raise ValueError('ACTUAL_METADATA_PIN_CHANGED')
    data=[hof['latest_owner_reference'],projection['catalog'],projection['verification'],projection['source_files']]
    goldens=[]
    for row in receipt['packets']:
        data.append(row['packet_reference']);golden=row['golden_comparison'].get('golden_reference')
        if golden is not None:data.append(golden);goldens.append(golden)
    if len(goldens)!=16:raise ValueError('EXACT16_ACTUAL_GOLDEN_DATA_POINTERS')
    data += [r for r in source_files if r['family']=='pm7_neutral']
    data=unique(data);sources=unique(dependencies+metadata)
    overlap={r['path'] for r in data}&{r['path'] for r in sources}
    if overlap:raise ValueError('SOURCE_AND_DATA_LOCATORS_MUST_BE_DISJOINT:'+','.join(sorted(overlap)))
    if C.BASE not in a.output.parents or a.output.exists() or RUN not in a.metadata_directory.parents or a.metadata_directory.exists():
        raise ValueError('FRESH_OWNED_EXTERNAL_PATHS_ONLY')
    a.metadata_directory.mkdir(parents=True,mode=0o700)
    plan={'schema':'ROOT_PM7_HOF_AUGMENTATION32_PLAN_V1','status':'APPROVED_EXACT32_DERIVED_ORDERS','reviewer':'root',
      'endpoint':'202.38.247.57:22','uid':1278,'scope_parameters':C.scope(),'hof_mode':'CANONICAL_VERIFIED',
      'geometry_receipt_reference':pin(a.geometry_receipt),'geometry_accounting_reference':pin(a.geometry_accounting),
      'prepared_reference':receipt['prepared_reference'],'source_authority_reference':prepared['source_authority_reference'],
      'hof_authority_review':pin(a.hof_authority_review),'metadata_source_references':metadata,
      'historical_proof_is_dependency_inventory_only':receipt['startup_proof_reference'],
      'new_fresh_startup_proof_required':True,'common':False,'full_cache_release':False}
    plan_ref=save(a.metadata_directory/'plan.json',plan)
    argv=[PY,'-B',str(HERE/'run.py'),'--plan',plan_ref['path'],'--root-preflight','__ROOT_STARTUP_PROOF__',
      '--quota-reuse-review',str(a.quota_reuse_review),'--output',str(a.output)]
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root',
      'reason':a.reason,'resource_authority_reference':pin(a.resource_authority),'kind':'analysis','scope_key':C.SCOPE,
      'scope_parameters':C.scope(),'scope_mode':'BOUNDED_METADATA_PREPARATION','pilot':False,'wall_seconds':3600,
      'estimated_peak_output_bytes':C.CAP,'stage_output_cap_bytes':C.CAP,'execution_argv':argv,
      'parent_evidence_references':[pin(a.geometry_receipt),pin(a.geometry_accounting),raw_ref],
      'bounded_batch_limits_reviewed':True,'source_status_stage':None}
    review_ref=save(a.metadata_directory/'scope_review.json',review)
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':False,'cpus':16,
      'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':3600,'estimated_peak_output_bytes':C.CAP,
      'stage_output_cap_bytes':C.CAP,'execution_argv':argv,'source_references':unique(sources+[plan_ref,review_ref]),
      'data_references':data,'scope_key':C.SCOPE,'scope_parameters':C.scope(),'source_status_stage':None,
      'scope':{'mode':'BOUNDED_METADATA_PREPARATION','review':review_ref,'parent_profile':None}}
    save(a.metadata_directory/'stage_spec.json',spec)
    save(a.metadata_directory/'input_locator_receipt.json',{'status':'SOURCE_METADATA_ONLY_NOT_SUBMITTED',
      'source_references':sources,'data_references':data,'source_data_bodies_opened_or_hashed':False,
      'actual_requested_molecules':32,'actual_parent_records':203,'golden_data_count':16,
      'all_pm7_family_files_are_locator_authority_not_all_will_be_read':True,
      'only_matching_current_owner_jobs_and_original_file_groups_read_by_canonical_hof':True,
      'producer_referenced_data_bytes_not_expected_read_bytes':sum(r['bytes'] for r in data),
      'scientific_functions_copied_or_modified':[],
      'direct_scientific_calls':['prepare32.canonical_hof','profile_common.read_hof_file/scalar_columns/decode_hof','core.geometry_orders']})
    print(json.dumps({'status':'METADATA_ONLY_NOT_SUBMITTED','metadata_directory':str(a.metadata_directory),'data_refs':len(data)}))

if __name__=='__main__':main()
