"""Stdlib metadata manifest/spec. Never source Parquet bodies, submit or retry."""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
from .footer import static_scenario
RUN=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=RUN/'repository';HERE=Path(__file__).absolute().parent
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python';SCOPE='labels_wp5_footer_inventory_v1'
PARAMETERS={'label_files':2024,'base_files':184,'files':2208,'workers':16,
 'label_physical_rows':157254650,'inherited_label_canonical_rows':157245956,'inherited_label_shadow_rows':8694,
 'base_producer_physical_rows':11232475,'inherited_base_canonical_rows':11231854,'inherited_base_difference':621,
 'producer_source_bytes':575920810664,'data_page_or_value_reads':False,'new_masks':False,'final_D4':False}


def load(path,cap=2<<20):
    path=Path(path)
    if path.stat().st_size>cap:raise ValueError('METADATA_INPUT_CAP_BEFORE_READ')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def pin(path,cap=2<<20):
    path=Path(path).absolute()
    if path.stat().st_size>cap:raise ValueError('METADATA_PIN_CAP_BEFORE_READ')
    raw=path.read_bytes();return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def triple(r):return {k:r[k] for k in ('path','bytes','sha256')}


def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
    return pin(path)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('prepared-census','census-reduction','resource-authority','metadata-directory','output','reason'):p.add_argument('--'+k,required=True)
    p.add_argument('--approve',action='store_true');a=p.parse_args()
    if not a.approve or not a.reason.strip():raise ValueError('EXPLICIT_ROOT_REVIEW_REQUIRED')
    if HERE!=REPO/'workflows/data_v1_final/labels/footer_inventory_v1':raise ValueError('ACTUAL_ROOT_METADATA_ENTRY')
    prepared=load(a.prepared_census);census=load(a.census_reduction)
    if (prepared['record_count'],prepared['source_file_count'],prepared['physical_task_rows'],prepared['canonical_task_rows'])!=(11231854,2024,157254650,157245956):
        raise ValueError('ORIGINAL_CLOSED_SOURCE_SCOPE_ONLY')
    if census['status']!='SOURCE_METADATA_CENSUS_COMPLETE_PAYLOAD_AUDIT_PENDING' or census['prepared_plan']!=pin(a.prepared_census):
        raise ValueError('ACTUAL_CLOSED_CENSUS_REQUIRED')
    catref=prepared['authority_locators']['catalog']
    # Exactly known3.48MiB catalog JSON is metadata, not Parquet/scientific data.
    if pin(catref['path'],cap=4<<20)!=catref:raise ValueError('ACTUAL_CLOSED_CATALOG_BYTES')
    catalog=load(catref['path'],cap=4<<20)
    labels=[r for shard in prepared['shards'] for r in shard['files']]
    bases=[r for r in catalog['artifacts'] if r.get('family')=='base_geometry'];files=[];seen=set()
    for kind,rows in (('label',labels),('base',bases)):
        for r in rows:
            if r['path'] in seen:raise ValueError('DUPLICATE_SOURCE_FILE_REFERENCE')
            seen.add(r['path']);files.append({**triple(r),'source_kind':kind,'family':r['family'],'rows':r['rows'],
              'source_job_id':r['source_job_id'] if kind=='label' else r['job_id'],
              'source_file_group':r['source_file_group'] if kind=='label' else r['file_group'],
              'canonical_rows_inherited':r['latest_rows'] if kind=='label' else None,
              'source_wholebody_SHA_basis':'INHERITED_PRODUCER_CLOSED_CATALOG_NOT_CURRENT_JOB_HASH'})
    if (len(labels),len(bases),sum(r['rows'] for r in labels),sum(r['rows'] for r in bases),
        sum(r['latest_rows'] for r in labels),sum(r['bytes'] for r in files))!=(2024,184,157254650,11232475,157245956,575920810664):
        raise ValueError('EXACT_LABEL_BASE_FILE_ROW_BYTE_CONSERVATION')
    files=sorted(files,key=lambda r:r['path'])
    for i,r in enumerate(files):r['file_id']=i
    # Scheduling estimate only: actual footer size/row-group count is not known.
    shards=[{'shard_id':i,'files':[]} for i in range(16)];cost=[0]*16
    for r in sorted(files,key=lambda r:(-math.ceil(r['rows']/32768),r['path'])):
        sid=min(range(16),key=lambda i:(cost[i],i));shards[sid]['files'].append(r);cost[sid]+=1+math.ceil(r['rows']/32768)
    scenario=static_scenario(files);directory=Path(a.metadata_directory).absolute();output=Path(a.output).absolute()
    if RUN not in directory.parents or directory.exists() or RUN/'artifacts/labels/source_status_v1' not in output.parents or output.exists():
        raise ValueError('FRESH_OWNED_EXTERNAL_PATHS_ONLY')
    directory.mkdir(parents=True,mode=0o700)
    # Files appear once: shards refer to stable file IDs; runtime expands metadata only.
    book={'schema':'WP5_FOOTER_SOURCE_INVENTORY_V1','files':files,
      'shards':[{'shard_id':s['shard_id'],'file_ids':[r['file_id'] for r in s['files']]} for s in shards],
      'producer_bytes_not_current_body_hash':True,'base621_and_label8694_are_separate_inherited_differences':True}
    book_ref=save(directory/'source_inventory.json',book);scenario_ref=save(directory/'static_size_scenario.json',scenario)
    sources=[pin(x) for x in HERE.iterdir() if x.suffix in ('.py','.md')]
    dependency=REPO/'workflows/data_v1_final/labels/source_status_cpu_auto_memory_v1'
    sources += [pin(dependency/x) for x in ('support.py','resource_runtime.py')]
    sources += [pin(x) for x in (REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py')]
    small=[pin(a.prepared_census),pin(a.census_reduction),pin(a.resource_authority),book_ref,scenario_ref]
    sources=list({r['path']:r for r in sources+small}.values())
    cfg={'schema':'WP5_FOOTER_INVENTORY_CONFIG_V1','scope_parameters':PARAMETERS,'workers':16,
      'source_inventory_reference':book_ref,'small_references':small,'source_references':sources,
      'one_footer_cap_bytes':128<<20,'one_source_serialized_cap_bytes':64<<20,'worker_rss_soft_cap_bytes':3<<30,
      'whole_output_cap_bytes':512<<20,'compressed_member_data_cap_bytes':432<<20,
      'observer_reserve_bytes':64<<20,'summary_admin_reserve_bytes':16<<20,'output_inode_cap':128,
      'source_input_mode':'HEADER4_TRAILER8_EXACT_DECLARED_FOOTER_ONLY;NO_ORIGINAL_PARQUET_PREFETCH'}
    cfg_ref=save(directory/'config.json',cfg)
    binding={'schema':'WP5_FOOTER_INVENTORY_RESOURCE_BINDING_V1','scientific_config_reference':cfg_ref,
      'scope_key':SCOPE,'scope_parameters':PARAMETERS,'resource_authority_reference':pin(a.resource_authority),
      'memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20,
      'resource_evidence_output':str(output)+'_resource_observation','software_scan_worker_cap_bytes':3<<30}
    bp=save(directory/'resource_binding.json',binding)
    argv=[PY,'-B','-m','workflows.data_v1_final.labels.footer_inventory_v1.run','--config',cfg_ref['path'],
      '--startup-proof','__ROOT_STARTUP_PROOF__','--output',str(output)]
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root',
      'reason':a.reason,'resource_authority_reference':pin(a.resource_authority),'kind':'analysis','pilot':False,
      'scope_key':SCOPE,'scope_parameters':PARAMETERS,'scope_mode':'BOUNDED_METADATA_PREPARATION','wall_seconds':3600,
      'estimated_peak_output_bytes':512<<20,'stage_output_cap_bytes':512<<20,'execution_argv':argv,
      'source_status_stage':None,'parent_evidence_references':[pin(a.prepared_census),pin(a.census_reduction)],
      'bounded_batch_limits_reviewed':True,'metadata_only':True,'no_source_body_pages':True}
    rp=save(directory/'scope_review.json',review)
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':False,'cpus':16,
      'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':3600,'estimated_peak_output_bytes':512<<20,
      'stage_output_cap_bytes':512<<20,'source_status_stage':None,'execution_argv':argv,
      'source_references':list({r['path']:r for r in sources+[cfg_ref,bp,rp]}.values()),
      'data_references':[triple(r) for r in files],
      'scope_key':SCOPE,'scope_parameters':PARAMETERS,'scope':{'mode':'BOUNDED_METADATA_PREPARATION','review':rp,'parent_profile':None},
      'producer_resource_binding_reference':bp}
    save(directory/'stage_spec.json',spec)
    save(directory/'preparation_receipt.json',{'status':'METADATA_ONLY_NOT_SUBMITTED','source_files':2208,
      'label_physical_rows':157254650,'base_producer_physical_rows':11232475,'label_inherited_difference':8694,
      'base_inherited_difference':621,'static_scenario_reference':scenario_ref,'actual_RG_counts_unknown':True,
      'data_bodies_statted_or_hashed':False,'catalog_JSON_only_actual_metadata_reference':catref,
      'full_values_Common_D4_authorized':False,'output512MiB_is_cap_not_guaranteed_inventory_size':True})
    print(json.dumps({'status':'METADATA_ONLY_NOT_SUBMITTED','directory':str(directory),'source_files':2208}))

if __name__=='__main__':main()
