"""Small exact Root plans; allocation-side footer-member directory resolution."""
from __future__ import annotations
import argparse,gzip,hashlib,json
from pathlib import Path
from workflows.data_v1_final.labels.footer_continuation_v1.resume import partition
RUN=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=RUN/'repository'
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python';SCOPE='labels_bounded_typed_projection_v1'


def need(ok,code):
    if not ok:raise ValueError(code)


def triple(r):return {k:r[k] for k in ('path','bytes','sha256')}


def load(path):
    p=Path(path);need(p.stat().st_size<=2<<20,'SMALL_METADATA_ONLY')
    return json.loads(p.read_text(encoding='utf-8-sig'))


def pin(path):
    p=Path(path).absolute();need(p.stat().st_size<=2<<20,'SMALL_SOURCE_PIN_ONLY');raw=p.read_bytes()
    need(len(raw)<=2<<20,'SMALL_SOURCE_PIN_ONLY')
    return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def require(r):
    need(pin(r['path'])==triple(r),'CURRENT_SMALL_PIN_DIFFERS:'+r['path']);return r['path']


def unique(refs):
    out={}
    for r in refs:
        r=triple(r);need(r['path'] not in out or out[r['path']]==r,'CONFLICTING_REFERENCE');out[r['path']]=r
    return list(out.values())


def save(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();need(len(raw)<=2<<20,'GENERATED_METADATA_CAP')
    with Path(path).open('xb') as f:f.write(raw)
    return pin(path)


def actual_parent(manifest_path,proof_path,accounting_path,raw_path,allow_failed=False):
    """Main's actual small accounting shape, including an unchanged raw header."""
    proof=load(proof_path);request=proof['request'];a=load(accounting_path)
    need(a['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and a['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
      and a['query_returncode']==0 and a['uid']==1278,'ACTUAL_MAIN_PARENT_ACCOUNTING')
    need(pin(raw_path)==a['raw_sacct_reference'],'EXACT_PARENT_RAW_ACCOUNTING')
    parents=[r for r in a['parents'] if str(r['job_id'])==str(proof['job_id'])];need(len(parents)==1,'EXACT_PARENT_ID')
    parent=parents[0];need(parent['alloc_cpus']==16 and parent['state'] in (('COMPLETED','FAILED') if allow_failed else ('COMPLETED',)),'ACTUAL_TERMINAL_PARENT')
    if parent['state']=='COMPLETED':need(parent['exit_code']=='0:0','ACTUAL_C0_REQUIRED')
    lines=Path(raw_path).read_text(encoding='utf-8-sig').splitlines();header=lines[0].split('|')
    rows=[dict(zip(header,s.split('|'))) for s in lines[1:] if s.split('|')[0]==str(proof['job_id'])]
    need(len(rows)==1 and rows[0]['UID']=='1278' and rows[0]['AllocCPUS']=='16'
      and rows[0]['State']==parent['state'] and rows[0]['ExitCode']==parent['exit_code'],'RAW_PARENT_FIELDS_DIFFER')
    need(load(require(proof['request_reference']))==request,'HISTORICAL_REQUEST_BINDING')
    argv=request['execution_argv'];need(argv.count('--output')==1 and Path(argv[argv.index('--output')+1])==Path(manifest_path).parent,'PARENT_OUTPUT_BINDING')
    manifest=load(manifest_path);config=manifest['config']
    need(argv.count('--config')==1 and argv[argv.index('--config')+1]==config['path'] and config in request['source_references'],'PARENT_CONFIG_BINDING')
    return parent,[pin(manifest_path),pin(proof_path),pin(accounting_path),pin(raw_path),proof['request_reference']]


def footer_inputs(manifest):
    need(manifest['status']=='ALL2208_SOURCE_FOOTERS_OBSERVED_VALUES_PENDING' and manifest['observed_files']==2208
      and manifest['observed_label_files']==2024 and manifest['observed_base_files']==184
      and manifest['pending_file_ids']==[] and manifest['errors']==[],'FULL_ACTUAL_FOOTER_REQUIRED_NOT_VALUES')
    book_ref=manifest['source_inventory_reference'];book=load(require(book_ref))
    if manifest['schema']=='WP5_FOOTER_CONTINUATION_V1':layers=manifest['layers']
    else:
        need(manifest['schema']=='WP5_FOOTER_INVENTORY_V1','SUPPORTED_FOOTER_MANIFEST')
        assigned={s['shard_id']:s['file_ids'] for s in book['shards']}
        layers=[{'report':s['report'],'assigned_file_ids':assigned[s['shard_id']]} for s in manifest['shards']]
    reports={r['report']['path']:load(require(r['report'])) for r in layers}
    completed,pending,streams,jobs=partition(book,layers,reports)
    need(len(completed)==2208 and not pending,'ACTUAL_ALL_SOURCE_MEMBER_INDEX')
    return book,completed,streams,[book_ref,*[r['report'] for r in layers]],jobs


def resolve(cfg,witness):
    """CPU-only metadata-body IO after fresh guard and all pure fixtures.

    No original Parquet is touched. Whole metadata streams are verified once;
    only selected complete gzip members are decompressed. No actual RG count is
    guessed from a writer default. Root's fixed selector bounds selected files
    and the first N actual row groups, or an explicit closed-cursor interval.
    """
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import require as body_require
    footer=load(require(cfg['footer_manifest_reference']));book,index,streams,_,_=footer_inputs(footer)
    selected=load(require(cfg['selector_reference']))['sources'];ids={r['file_id'] for r in selected}
    needed=unique(index[i]['inventory_reference'] for i in ids)
    for r in needed:body_require(r)
    byid={r['file_id']:r for r in book['files']};ranges=[];byselector={}
    for selector in selected:byselector.setdefault(selector['file_id'],[]).append(selector)
    required={}
    if cfg['previous_manifest_reference'] is None:
        for row in witness['witnesses']:
            need(row['file_id'] in ids,'WITNESS_MUST_USE_THE_APPROVED_SOURCE_FILES')
            required.setdefault(row['file_id'],set()).add(row['row_group'])
    for file_id,selectors in sorted(byselector.items()):
        observed=index[file_id];stream=observed['inventory_reference']
        lo,hi=observed['gzip_member_byte_lo'],observed['gzip_member_byte_hi']
        need(0<hi-lo<=128<<20,'BOUNDED_INHERITED_METADATA_MEMBER')
        with Path(stream['path']).open('rb') as f:f.seek(lo);compressed=f.read(hi-lo)
        need(len(compressed)==hi-lo and hashlib.sha256(compressed).hexdigest()==observed['gzip_member_sha256'],'ACTUAL_FOOTER_MEMBER_BYTES')
        raw=gzip.decompress(compressed);del compressed
        need(len(raw)==observed['uncompressed_member_bytes'] and len(raw)<=64<<20
          and hashlib.sha256(raw).hexdigest()==observed['uncompressed_member_sha256'],'ACTUAL_METADATA_MEMBER_RAW_SIGNATURE')
        groups=[];schema=None;head=None
        for line in raw.splitlines():
            if b'"type":"column_chunk"' in line:continue
            item=json.loads(line)
            if item['type']=='source':head=item
            elif item['type']=='schema':schema=item
            elif item['type']=='row_group':
                keep=item['row_group'] in required.get(file_id,set())
                for selector in selectors:
                    if 'physical_row_lo' in selector:
                        keep=keep or item['physical_row_hi']>selector['physical_row_lo'] and item['physical_row_lo']<selector['physical_row_hi']
                    else:keep=keep or item['row_group']<selector['row_groups_per_file']
                if keep:groups.append(item)
        del raw
        need(head is not None and schema is not None and groups,'SELECTED_ACTUAL_RG_METADATA_REQUIRED')
        source=byid[file_id];need(head['source']==source and schema['physical_rows']==source['rows'],'EXACT_FOOTER_SOURCE_SCHEMA')
        from .parts import slices
        need(required.get(file_id,set())<={g['row_group'] for g in groups},'ACTUAL_WITNESS_RGS_MUST_EXIST')
        intervals=[]
        if 'physical_row_lo' in selectors[0]:intervals=[(s['physical_row_lo'],s['physical_row_hi']) for s in selectors]
        else:
            for g in groups:
                if intervals and intervals[-1][1]==g['physical_row_lo']:intervals[-1]=(intervals[-1][0],g['physical_row_hi'])
                else:intervals.append((g['physical_row_lo'],g['physical_row_hi']))
        end=-1
        for start,stop in sorted(intervals):
            need(start>=end,'NO_OVERLAPPING_PHYSICAL_SEGMENTS');end=stop
            subset=[g for g in groups if g['physical_row_hi']>start and g['physical_row_lo']<stop];list(slices(subset,start,stop))
            key=hashlib.sha256(json.dumps([triple(source),start,stop],sort_keys=True,separators=(',',':')).encode()).hexdigest()[:24]
            ranges.append({'range_id':key,'file_id':file_id,'source':source,'physical_row_lo':start,'physical_row_hi':stop,
              'groups':subset,'file_row_groups':schema['row_groups'],'expected_footer_sha256':observed['actual_footer_sha256'],
              'footer_observed_source_frame':observed['source_frame_before_after'],'metadata_member_reference':stream})
    need(len({r['file_id'] for r in ranges})==len(ids),'ALL_SELECTED_SOURCE_FILES_RESOLVED')
    return {'schema':'BOUNDED_LABEL_ACTUAL_RANGE_PLAN_V1','ranges':ranges,'actual_selected_physical_rows':sum(r['physical_row_hi']-r['physical_row_lo'] for r in ranges),
      'actual_selected_row_groups':sum(len(r['groups']) for r in ranges),'footer_reference':cfg['footer_manifest_reference'],
      'source_metadata_streams_fullSHA_verified':needed,'source_label_body_read':False,
      'witness_discovery_reference_required':True,'noncontiguous_segments_share_one_source_handle':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('footer-manifest','footer-proof','footer-accounting','footer-raw-accounting','profile-manifest','profile-proof',
              'profile-accounting','profile-raw-accounting','resource-authority','metadata-directory','output','reason'):p.add_argument('--'+k,required=True)
    p.add_argument('--row-groups-per-file',type=int,default=1);p.add_argument('--whole-output-cap-bytes',type=int,default=32<<30)
    p.add_argument('--resume-manifest');p.add_argument('--resume-proof');p.add_argument('--resume-accounting');p.add_argument('--resume-raw-accounting')
    p.add_argument('--accept-unpublished-retained',action='store_true');p.add_argument('--approve',action='store_true');a=p.parse_args()
    need(a.approve and a.reason.strip(),'EXPLICIT_ROOT_FINITE_BATCH_REVIEW')
    need(Path(__file__).absolute().parent==REPO/'workflows/data_v1_final/labels/bounded_projection_v1','ROOT_SOURCE_PATH_REQUIRED')
    footer=load(a.footer_manifest);_,footer_parents=actual_parent(a.footer_manifest,a.footer_proof,a.footer_accounting,a.footer_raw_accounting)
    book,completed,streams,footer_small,_=footer_inputs(footer)
    profile=load(a.profile_manifest);_,profile_parents=actual_parent(a.profile_manifest,a.profile_proof,a.profile_accounting,a.profile_raw_accounting)
    need(profile['schema']=='LOSSLESS_LABEL_PROJECTION_PILOT_V1' and profile['status']=='PILOT_CACHE_CLOSED_FULL_NOT_AUTHORIZED'
      and profile['quality_stop_fields']==[] and profile['scope_parameters']['records']==4251,'ACTUAL_ACCEPTED_512_BITCACHE_PROFILE')
    baseline_ref=profile['config'];baseline=load(require(baseline_ref));science=baseline['science'];source_plan=load(require(science['sources']['frozen_source_plan']))
    canonical=source_plan['canonical_index'];need(source_plan['record_count']==11231854 and source_plan['molecule_count']==1220466,'ORIGINAL_CANONICAL_POPULATION')
    owners=load(require(baseline['owner_plan']));source_by_path={r['path']:r for r in book['files']}
    refs=[r for g in owners['groups'] for r in [*g['label_files'],*g['base_files']]];selected={}
    for r in refs:
        source=source_by_path[r['path']];need(triple(source)==triple(r),'EXACT_EXISTING_SOURCE_SELECTION')
        selected[source['file_id']]={'file_id':source['file_id'],'row_groups_per_file':a.row_groups_per_file}
    need(1<=a.row_groups_per_file<=64 and len(selected)>=16 and len(selected)<2208,'FINITE_SMALL_RG_PROFILE_NOT_FULL')
    selectors=list(selected.values());previous=None;resume_parents=[]
    if a.resume_manifest:
        need(all((a.resume_proof,a.resume_accounting,a.resume_raw_accounting)),'ACTUAL_TERMINAL_RESUME_EVIDENCE')
        previous=load(a.resume_manifest);_,resume_parents=actual_parent(a.resume_manifest,a.resume_proof,a.resume_accounting,a.resume_raw_accounting,allow_failed=True)
        need(previous['schema']=='BOUNDED_LABEL_PROJECTION_BATCH_V1' and not previous['errors']
          and not previous['quality_stop_fields_global_lower_bound'] and not previous['parity']['mismatches']
          and not previous['partial_observed_rate_review_fields'] and not previous['coverage']['duplicate_keys'],
          'RESOURCE_PARTIAL_ONLY_NO_SCIENTIFIC_ERROR_RETRY')
        need(previous['footer_manifest_reference']==pin(a.footer_manifest),'UNCHANGED_ACTUAL_FOOTER_AUTHORITY')
        if previous['unpublished_tickets']:need(a.accept_unpublished_retained,'ROOT_MUST_EXPLICITLY_RETAIN_UNPUBLISHED_NO_AUTO_RETRY')
        old_cfg=load(require(previous['config']));need(old_cfg['baseline_projection_config_reference']==baseline_ref,'SAME_FROZEN_SCIENCE_BASELINE')
        old_ranges=load(require(previous['actual_range_plan']))['ranges'];by_range={r['range_id']:r for r in old_ranges};selected={};selectors=[]
        for row in previous['cursors']:
            if row['next_physical_row']<row['physical_row_hi']:
                original=by_range[row['range_id']];selectors.append({'file_id':original['file_id'],
                  'physical_row_lo':row['next_physical_row'],'physical_row_hi':row['physical_row_hi']})
                selected[original['file_id']]=True
        need(selectors,'NO_PENDING_RANGE_NO_NEW_JOB')
    whole=a.whole_output_cap_bytes;need(8<<30<=whole<=32<<30,'ROOT_FINITE_BATCH_CAP_8_TO_32GIB_NOT_FORECAST')
    profile_reports=[r['report'] for r in profile['groups']];parity_caches=[]
    for r in profile_reports:parity_caches.append(load(require(r))['cache'])
    parameters={'selected_source_files':len(selected),'prefix_row_groups_per_source':a.row_groups_per_file if previous is None else None,
      'selector_mode':'CLOSED_CURSOR_REMAINDER' if previous else 'EXISTING512_SOURCES_FIRST_ACTUAL_RGS',
      'workers':16,'declared_fields':264,'enabled_components':146,'global_records':11231854,'new_UFF_QM_calls':0,
      'whole_output_cap_bytes':whole,'full_population':False,'normalization':False,'candidate_masks_only':True,
      'witness_policy':'ACTUAL_512_DETERMINISTIC_TASK_FIELD_AND_OBSERVED_CODEC_V1','max_witness_keys_and_extra_RGs':512,
      'footer_manifest_sha256':pin(a.footer_manifest)['sha256'],'accepted_profile_sha256':pin(a.profile_manifest)['sha256']}
    output=Path(a.output).absolute();directory=Path(a.metadata_directory).absolute()
    need(RUN/'artifacts/labels/source_status_v1' in output.parents and not output.exists()
      and RUN in directory.parents and not directory.exists(),'NEW_EXTERNAL_ROOT_METADATA_AND_OUTPUT')
    directory.mkdir(parents=True,mode=0o700)
    selector=save(directory/'selector.json',{'schema':'BOUNDED_LABEL_PHYSICAL_SELECTOR_V1','sources':selectors,
      'record_ordinals_are_not_physical_IO_offsets':True,'full_source_population_authorized':False})
    parents=unique([*footer_parents,*profile_parents,*resume_parents]);small=unique([*parents,*footer_small,*profile_reports,baseline_ref,
      baseline['owner_plan'],pin(a.resource_authority),selector,*baseline['small_references']])
    from workflows.data_v1_final.labels.payload_audit_v1.materialize import sources
    code=unique(sources(small)+baseline['source_references']+[pin(q) for q in Path(__file__).parent.iterdir() if q.suffix in ('.py','.md')]
      +[pin(q) for q in (REPO/'workflows/data_v1_final/labels/footer_continuation_v1').glob('*.py')]
      +[pin(REPO/'workflows/data_v1_final/labels/footer_inventory_v1/footer.py')])
    for r in code:require(r)
    cfg={'schema':'BOUNDED_LABEL_PROJECTION_CONFIG_V1','scope_parameters':parameters,'workers':16,'science':science,
      'baseline_projection_config_reference':baseline_ref,'canonical_index':canonical,'footer_manifest_reference':pin(a.footer_manifest),
      'selector_reference':selector,'extra_geometry_registry_ids':baseline['extra_geometry_registry_ids'],
      'source_read_batch_records':science['source_read_batch_records'],'worker_rss_stop_bytes':3<<30,'row_serialized_cap_bytes':64<<20,
      'typed_part_cap_bytes':128<<20,'window_soft_target_bytes':32<<20,'max_physical_window_rows':8192,
      'whole_output_cap_bytes':whole,'admin_reserve_bytes':1<<30,'observer_reserve_bytes':64<<20,'output_inode_cap':8192,
      'small_references':small,'source_references':code,'parity_cache_references':unique(parity_caches),
      'previous_manifest_reference':pin(a.resume_manifest) if previous else None,
      'review_calibration_reference':None,'calibration_state':'PENDING_MATCHED_FULL_TRAIN_NO_512_SCALE_REUSE',
      'logical_statistics_partition_reference':None,'norm_fit_allowed':False,'full_population_authorized':False}
    config=save(directory/'config.json',cfg)
    binding={'schema':'BOUNDED_LABEL_PROJECTION_RESOURCE_BINDING_V1','scientific_config_reference':config,'scope_key':SCOPE,'scope_parameters':parameters,
      'resource_authority_reference':pin(a.resource_authority),'memavailable_soft_floor_bytes':4<<30,
      'resource_evidence_local_cap_bytes':64<<20,'resource_evidence_output':str(output)+'_resource_observation','software_scan_worker_cap_bytes':3<<30}
    bp=save(directory/'resource_binding.json',binding)
    argv=[PY,'-B','-m','workflows.data_v1_final.labels.bounded_projection_v1.run','--config',config['path'],
      '--startup-proof','__ROOT_STARTUP_PROOF__','--output',str(output)]
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root','reason':a.reason,
      'resource_authority_reference':pin(a.resource_authority),'kind':'analysis','pilot':True,'scope_key':SCOPE,'scope_parameters':parameters,
      'scope_mode':'BOUNDED_PERFORMANCE_BATCH','wall_seconds':7200,'estimated_peak_output_bytes':whole,'stage_output_cap_bytes':whole,
      'source_status_stage':None,'execution_argv':argv,'bounded_batch_limits_reviewed':True,'profile_reviewed':True,
      'approved_profile_reference':pin(a.profile_manifest),'parent_evidence_references':parents,'full_generation_authorized':False}
    rp=save(directory/'scope_review.json',review)
    data=unique([canonical,*streams,*parity_caches,*[triple(next(r for r in book['files'] if r['file_id']==i)) for i in selected]])
    if previous:data=unique(data+[previous['coverage']['reference']])
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':True,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
      'wall_seconds':7200,'estimated_peak_output_bytes':whole,'stage_output_cap_bytes':whole,'source_status_stage':None,'execution_argv':argv,
      'source_references':unique(code+[config,bp,rp]),'data_references':data,'scope_key':SCOPE,'scope_parameters':parameters,
      'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','review':rp,'parent_profile':pin(a.profile_manifest)},'producer_resource_binding_reference':bp}
    save(directory/'stage_spec.json',spec)
    save(directory/'preparation_receipt.json',{'status':'SOURCE_METADATA_ONLY_NOT_SUBMITTED','selected_sources':len(selected),
      'Parquet_SQLite_gzip_cache_bodies_read_or_statted':False,'actual_ranges_resolved_after_CPU_fixtures':True,
      'whole_cap_is_not_output_forecast':True,'matched_full_TRAIN_calibration':'PENDING','norm_D4_full_not_authorized':True})
    print(json.dumps({'status':'METADATA_ONLY_NOT_SUBMITTED','directory':str(directory),'sources':len(selected)}))

if __name__=='__main__':main()
