"""Stdlib-only smallmetadata builder. Never reads/stat-hashes data bodies or submits."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
RUN=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=RUN/'repository'
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
SCOPE='label_lossless_projection_512_v1'
PARAMETERS={'records':4251,'molecules':512,'source_groups':16,'task_slots':14,
 'enabled_components':146,'declared_components':264,'source_selection':'existing_canonical_512',
 'new_UFF_QM_calls':0,'final_D4':False,'full_population':False,'candidate_masks_only':True}


def load(path):
    if Path(path).stat().st_size>2<<20:raise ValueError('SMALL_METADATA_ONLY')
    raw=Path(path).read_bytes()
    if len(raw)>2<<20:raise ValueError('SMALL_METADATA_ONLY')
    return json.loads(raw.decode('utf-8-sig'))


def pin(path):
    p=Path(path).absolute()
    if p.stat().st_size>2<<20:raise ValueError('SMALL_PIN_ONLY')
    raw=p.read_bytes()
    if len(raw)>2<<20:raise ValueError('SMALL_PIN_ONLY')
    return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def triple(value):return {k:value[k] for k in ('path','bytes','sha256')}


def unique(refs):
    out={}
    for p in refs:
        q=triple(p)
        if q['path'] in out and out[q['path']]!=q:raise ValueError('CONFLICTING_REFERENCE')
        out[q['path']]=q
    return list(out.values())


def save(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:json.dump(value,stream,sort_keys=True,indent=2);stream.write('\n')
    return pin(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('payload-config','owner-plan','parent-profile','parent-accounting','parent-raw-accounting',
                'authority','metadata-directory','output','reason'):
        parser.add_argument('--'+key,required=True)
    parser.add_argument('--approve',action='store_true');a=parser.parse_args()
    if not a.approve or not a.reason.strip():raise ValueError('EXPLICIT_ROOT_REVIEW_REQUIRED')
    if Path(__file__).absolute().parent!=REPO/'workflows/data_v1_final/labels/lossless_projection_pilot_v1':
        raise ValueError('ACTUAL_ROOT_SOURCE_ONLY_NO_CHILD_PIN_SUBSTITUTION')
    science=load(a.payload_config);plan=load(science['sources']['plan']['path']);owners=load(a.owner_plan)
    if science['mode']!='pilot' or plan['mode']!='pilot' or owners['mode']!='pilot':raise ValueError('NO_FULL_SCOPE')
    if (plan['records'],plan['molecules'],len(plan['groups']))!=(4251,512,16):raise ValueError('EXACT_EXISTING_512')
    if (owners['records'],owners['molecules'],len(owners['groups']))!=(4251,512,16):raise ValueError('EXACT_EXISTING_OWNER_PLAN')
    if (sum(g['expected_records'] for g in owners['groups'])!=4251
        or sum(g['expected_molecules'] for g in owners['groups'])!=512
        or len({g['source_job_id'] for g in owners['groups']})!=16):raise ValueError('WHOLE_ORIGINAL_OWNER_MASS')
    if owners['coverage_fingerprint']!=plan['coverage_fingerprint']:raise ValueError('SOURCE_SCOPE_DIFFERENT')
    if science['calibration'] is None:raise ValueError('MATCHED_ORIGINAL_PILOT_CALIBRATION_REQUIRED')
    calibration=load(science['calibration']['path'])
    if calibration['mode']!='pilot' or calibration['coverage_fingerprint']!=plan['coverage_fingerprint']:raise ValueError('CALIBRATION_SCOPE_DIFFERENT')
    profile=load(a.parent_profile);accounting=load(a.parent_accounting);parent=accounting['actual_parent']
    if (profile.get('schema')!='ALPHA_LABEL_PAYLOAD512_REDUCTION_STAGE_CLOSURE_V1'
        or profile.get('status')!='REDUCTION_CLOSED_CANDIDATES_NOT_FROZEN'
        or (profile.get('records'),profile.get('molecules'))!=(4251,512)
        or profile.get('quality_stop_fields')!=[]):raise ValueError('ACTUAL_512_PAYLOAD_REDUCTION_REQUIRED')
    if (str(parent['JobIDRaw'])!=str(profile['job_id']) or parent['State']!='COMPLETED'
        or parent['ExitCode']!='0:0' or parent['UID']!='1264' or parent['AllocCPUS']!='16'
        or accounting.get('query_returncode')!=0 or accounting.get('actual_terminal') is not True):
        raise ValueError('ACTUAL_ALPHA_PARENT_C0_ACCOUNTING_REQUIRED_NOT_MAIN_PROOF')
    raw_pin=pin(a.parent_raw_accounting);origin_raw=accounting['raw_sacct_reference']
    if any(raw_pin[k]!=origin_raw[k] for k in ('bytes','sha256')):raise ValueError('ROOT_RAW_ACCOUNTING_COPY_DIFFERS')
    raw_lines=Path(a.parent_raw_accounting).read_text(encoding='utf-8-sig').splitlines()
    rows=[line.split('|') for line in raw_lines if line.startswith(str(profile['job_id'])+'|')]
    if len(rows)!=1 or rows[0][1:5]!=['alpha','1264','COMPLETED','0:0']:raise ValueError('RAW_ACTUAL_ALPHA_PARENT_NOT_C0')
    old_by_owner={g['source_job_id']:g for g in plan['groups']}
    for group in owners['groups']:
        other=old_by_owner[group['source_job_id']]
        if unique(group['label_files'])!=unique(other['label_files']):raise ValueError('ORIGINAL_LABEL_SOURCE_CHANGED')
        if triple(group['owner_index'])!=triple(other['owner_index']):raise ValueError('ORIGINAL_SELECTION_CHANGED')
        if not group['base_files']:raise ValueError('EXPLICIT_BASE_GEOMETRY_REQUIRED')
    raw_registry=load(science['sources']['raw_registry']['path'])
    provenance_paths={'values.positions_A','values.elements','values.perturb_seed','values.perturb_sigma_A'}
    extras={}
    for row in raw_registry['entries']:
        if row['task']=='xtb_perturbed_gradient' and row['source_path'] in provenance_paths:
            extras.setdefault(row['task'],[]).append(row['registry_id'])
    if set(r['source_path'] for r in raw_registry['entries'] if r['registry_id'] in extras.get('xtb_perturbed_gradient',[]))!=provenance_paths:
        raise ValueError('EXACT_PERTURBED_GEOMETRY_PROVENANCE_FIELDS_REQUIRED')
    # Small dependency chain is verified by physical Root files, never silent path rebinding.
    parents=[pin(a.parent_profile),pin(a.parent_accounting),raw_pin]
    small=[pin(a.owner_plan),pin(a.payload_config),*parents,pin(a.authority),science['calibration'],*science['sources'].values(),*science['adapter_source_pins']]
    for p in small:
        if pin(p['path'])!=triple(p):raise ValueError('ACTUAL_ROOT_SMALL_PIN_DIFFERS:'+p['path'])
    from workflows.data_v1_final.labels.payload_audit_v1.materialize import sources
    source_refs=sources(small)
    source_refs=unique(source_refs+[pin(p) for p in Path(__file__).parent.iterdir() if p.suffix in ('.py','.md','.json')])
    data=[plan['canonical_index'],plan['expected_roles']]
    for group in owners['groups']:data += [group['owner_index'],*group['label_files'],*group['base_files']]
    data=unique(data);output=Path(a.output).absolute();directory=Path(a.metadata_directory).absolute()
    prefix=RUN/'artifacts/labels/source_status_v1'
    if prefix not in output.parents or output.exists():raise ValueError('NEW_RESOURCE_COMPATIBLE_OUTPUT_ONLY')
    if RUN not in directory.parents or directory.exists():raise ValueError('NEW_METADATA_DIRECTORY_ONLY')
    directory.mkdir(parents=True,mode=0o700)
    cfg={'schema':'LOSSLESS_LABEL_PROJECTION_CONFIG_V1','mode':'pilot','scope_parameters':PARAMETERS,
      'science':science,'owner_plan':pin(a.owner_plan),'canonical_index':plan['canonical_index'],
      'coverage_fingerprint':plan['coverage_fingerprint'],'extra_geometry_registry_ids':extras,
      'small_references':unique(small),'source_references':source_refs,'data_references':data,
      'workers':16,'source_read_batch_records':science['source_read_batch_records'],
      'worker_rss_stop_bytes':science['worker_rss_stop_bytes'],'row_serialized_cap_bytes':64<<20,
      'group_output_cap_bytes':384<<20,'whole_output_cap_bytes':8<<30,
      'source_whole_sha_policy':'INHERITED_PRODUCER_SHA_STABLE_FSTAT_NOT_FRESH_HASH',
      'full_population_authorized':False,'normalization_completed':False}
    cfg_ref=save(directory/'config.json',cfg)
    binding={'schema':'LOSSLESS_LABEL_PROJECTION_RESOURCE_BINDING_V1','scientific_config_reference':cfg_ref,
      'scope_key':SCOPE,'scope_parameters':PARAMETERS,'memavailable_soft_floor_bytes':4<<30,
      'resource_evidence_local_cap_bytes':64<<20,'resource_evidence_output':str(output)+'_resource_observation',
      'software_scan_worker_cap_bytes':science['worker_rss_stop_bytes']}
    bp=save(directory/'resource_binding.json',binding)
    argv=[PY,'-B','-m','workflows.data_v1_final.labels.lossless_projection_pilot_v1.run',
          '--config',cfg_ref['path'],'--output',str(output),'--startup-proof','__ROOT_STARTUP_PROOF__']
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE',
      'reviewer':'root','reason':a.reason,'resource_authority_reference':pin(a.authority),
      'kind':'analysis','scope_key':SCOPE,'scope_parameters':PARAMETERS,'scope_mode':'BOUNDED_PERFORMANCE_BATCH',
      'pilot':True,'wall_seconds':7200,'estimated_peak_output_bytes':8<<30,'stage_output_cap_bytes':8<<30,
      'execution_argv':argv,'bounded_batch_limits_reviewed':True,'profile_reviewed':True,
      'approved_profile_reference':pin(a.parent_profile),'parent_evidence_references':parents}
    rp=save(directory/'scope_review.json',review)
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':True,'cpus':16,
      'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':7200,'estimated_peak_output_bytes':8<<30,
      'stage_output_cap_bytes':8<<30,'execution_argv':argv,'source_references':unique(source_refs+[cfg_ref,bp,rp]),
      'data_references':data,'scope_key':SCOPE,'scope_parameters':PARAMETERS,
      'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','review':rp,'parent_profile':pin(a.parent_profile)},
      'producer_resource_binding_reference':bp}
    save(directory/'stage_spec.json',spec)
    save(directory/'preparation_receipt.json',{'status':'METADATA_ONLY_NOT_SUBMITTED','data_files':len(data),
      'producer_referenced_data_bytes':sum(p['bytes'] for p in data),'body_stat_or_hash_performed':False,
      'source_whole_sha_policy':cfg['source_whole_sha_policy'],'output_8GiB_is_cap_not_forecast':True,
      'accounting_copy_locator_mapping':{'origin_Alpha_reference':origin_raw,'observed_Main_copy_reference':raw_pin},
      'scientific_function_reuse':{'source_columns':'payload_audit_v1.run.source_columns',
       'evaluate':'payload_audit_v1.payload.evaluate','component_values':'pinned common.component_values',
       'mask_rules':'pinned pilot_masks.source_value_mask/add_cross_field_checks',
       'copied_or_modified_scientific_functions':[]},'root_sources':source_refs})
    print(json.dumps({'status':'METADATA_ONLY_NOT_SUBMITTED','directory':str(directory),'data_refs':len(data)}))

if __name__=='__main__':main()
