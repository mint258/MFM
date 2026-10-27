"""Whole-molecule cache reuse and physical-source D7 tasks; no new geometry."""
import gzip,json,pathlib
from workflows.data_v1_final.conformers.pm7_population_cache_v1 import contract as PC,run as OLD
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import contract as B,io as BIO
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as R
from . import contract as C,hof

def catalog(ctx,ref):
    path=ctx.require(ref)
    with gzip.open(path,'rb') as stream:raw=stream.read((32<<20)+1);C.need(len(raw)<=32<<20 and stream.read(1)==b'','ORIGINAL_BOUNDED_CATALOG_EOF')
    return [json.loads(line) for line in raw.splitlines() if line]

def setup(ctx,db,plan):
    for key in ('formal_source','per_molecule','whole_molecule_roster'):ctx.require(plan[key])
    ctx.formal_reference=plan['formal_source']
    db.execute('CREATE VIEW formal AS SELECT * FROM read_parquet('+C.q(plan['formal_source']['path'])+')')
    db.execute('CREATE VIEW roster AS SELECT * FROM read_parquet('+C.q(plan['whole_molecule_roster']['path'])+')')
    C.need(db.execute('SELECT count(*),count(DISTINCT record_id),count(DISTINCT molecule_id) FROM formal').fetchone()==(11231854,11231854,1220466),'ALL_ORIGINAL_PM7_RECORD_AND_MOLECULE_COUNTS')
    C.need(db.execute('SELECT count(*),sum(records),count(DISTINCT molecule_id) FROM roster').fetchone()==(1220466,11231854,1220466),'ALL_WHOLE_MOLECULE_ROSTER_UNFILTERED')
    shards=ctx.read(plan['future_shards_reference']);C.need(shards['roster_reference']==plan['whole_molecule_roster'] and len(shards['descriptors'])==247,'ORIGINAL247_DESCRIPTORS_NOT_NEW_PARTITION')
    C.need(sum(r['molecules'] for r in shards['descriptors'])==1220466 and sum(r['records'] for r in shards['descriptors'])==11231854,'EXACT247_MOLECULE_RECORD_UNION')
    db.execute('CREATE TABLE prior_cache(molecule_id VARCHAR PRIMARY KEY,row_json VARCHAR,producer_job_id VARCHAR)');registered={}
    for entry in ctx.plan['cache_registered_parents']:
        req=C.meta(entry['request_reference']);sub=C.meta(entry['submission_reference']);receipt=C.meta(entry['receipt_reference']);jid=str(sub['job_id'])
        C.need(C.G.meta_pin(entry['accounting_reference']['path'])==entry['accounting_reference'],'ACTUAL_CACHE_ACCOUNT_PIN')
        _,_,parents=C.G.account(entry['accounting_reference']['path'],[jid],c0=[jid]);C.need(receipt['unknown_molecules']==0 and receipt['unstarted_molecules']==0,'ONLY_ACTUAL_CLOSED_CACHE_PREFIX_REUSED')
        registered[jid]={'request':req,'submission':sub,'accounting':parents[jid]}
        for row in catalog(ctx,receipt['catalog_reference']):
            previous=db.execute('SELECT row_json FROM prior_cache WHERE molecule_id=?',[row['molecule_id']]).fetchone()
            if previous:
                old=json.loads(previous[0]);C.need(old['cache_key']==row['cache_key'] and old['geometry_packet_reference']==row['geometry_packet_reference'],'OVERLAPPING_PREFIX_MUST_REFERENCE_SAME_ACTUAL_PACKET')
            else:db.execute('INSERT INTO prior_cache VALUES(?,?,?)',[row['molecule_id'],C.canonical(row).decode(),jid])
    ctx.cache_registered=registered;ctx.day_registered={}
    db.execute('CREATE TABLE prior_day(molecule_id VARCHAR PRIMARY KEY,row_json VARCHAR,producer_job_id VARCHAR)')
    import pyarrow.parquet as pq
    for previous in ctx.plan.get('previous_postprocess_parents',[]):
        sub=C.meta(previous['submission_reference']);request=C.meta(previous['request_reference']);receipt=C.meta(previous['receipt_reference']);jid=str(sub['job_id'])
        ctx.day_registered[jid]={'request':request,'submission':sub,'receipt':receipt}
        for batch in pq.ParquetFile(ctx.require(receipt['catalog_reference'])).iter_batches(batch_size=1024):
            for row in batch.to_pylist():
                old=db.execute('SELECT row_json FROM prior_day WHERE molecule_id=?',[row['molecule_id']]).fetchone()
                if old:C.need(json.loads(old[0])['packet_reference']==row['packet_reference'],'PREVIOUS_DAY_PREFIX_DUPLICATE_CONFLICT')
                else:db.execute('INSERT INTO prior_day VALUES(?,?,?)',[row['molecule_id'],C.canonical(row).decode(),jid])
    return shards['descriptors']

def reuse(ctx,db,task,plan):
    mid=task['meta']['molecule_id'];row=db.execute('SELECT row_json FROM prior_cache WHERE molecule_id=?',[mid]).fetchone();ledger=PC.LEDGER/(task['cache_key']+'.json')
    if row is None:
        C.need(not ledger.exists(),'CONSUMED_LEGACY_CACHE_NOT_IN_VERIFIED_CLOSED_PREFIX_NO_RETRY');return None
    row=json.loads(row[0]);claim_ref=ctx.reference(ledger);claim=ctx.read(claim_ref)
    C.need(row['cache_key']==task['cache_key'] and row['claim_reference']==claim_ref and str(claim['job_id']) in ctx.cache_registered
      and claim['molecule_id']==mid and claim['uid']==1278 and claim['node']=='compute-0-13','REAL_CLOSED_PRIOR_CACHE_CLAIM_AND_PARENT')
    if claim['action']=='IMPORT32':
        geometry=C.meta(plan['geometry32_receipt_reference']);attached=C.meta(plan['hof32_receipt_reference']);g={r['molecule_id']:r for r in geometry['packets']};h={r['molecule_id']:r for r in attached['packets']}
        OLD.imported32(task,g[mid],h[mid],ctx.out)
        packet=BIO.read_packet(g[mid]['packet_reference']);extra=ctx.read(h[mid]['packet_reference'],128<<20);packet=dict(packet)
        packet.update(orders=extra['orders'],hof_by_record=extra['hof_by_record'],hof_valid_count=extra['hof_valid_count'],hof_range_complete=extra['hof_range_complete'],hof_range_kcal_mol=extra['hof_range_kcal_mol'],status='PM7_GEOMETRY_CACHE_COMPLETE_HOF_COMPLETE')
        packet['pm7']=[dict(r,energy=task['hof'][r['conformer_id']]['value_kcal_mol']) for r in packet['pm7']]
    else:_,packet=OLD.validate_packet(task,claim,claim_ref)
    C.need(packet['source_records']==task['records'] and packet['hof_by_record']==task['hof'],'EXACT_RECORD_PAYLOAD_AND_CANONICAL_HOF_IDENTITY_FOR_REUSE')
    return packet

def batch(ctx,db,descriptor):
    import pyarrow as pa
    metas=db.execute('SELECT * FROM roster WHERE file_group=? AND shard_index=? ORDER BY molecule_hash,molecule_id',[descriptor['file_group'],descriptor['shard_index']]).fetch_arrow_table().to_pylist()
    C.need(len(metas)==descriptor['molecules'] and sum(r['records'] for r in metas)==descriptor['records'],'ENTIRE_ORIGINAL_DESCRIPTOR_NOT_PARTIAL_OR_SELECTED_SAMPLE')
    db.register('batch_mids',pa.table({'molecule_id':[m['molecule_id'] for m in metas]}))
    cols=('record_id','molecule_id','source_path','real_index','record_payload_sha256','total_atoms','smiles','file_group','conformer_id')
    records=db.execute('SELECT '+','.join('f.'+n for n in cols)+' FROM formal f JOIN batch_mids USING(molecule_id) ORDER BY molecule_id,record_id').fetch_arrow_table().to_pylist()
    by={m['molecule_id']:[] for m in metas}
    for r in records:by[r['molecule_id']].append(r)
    C.need(len(records)==descriptor['records'] and len({r['record_id'] for r in records})==len(records),'EXACT_BATCH_RECORD_UNION')
    return metas,by

def task(ctx,meta,records,plan,hof_reference):
    C.need(len(records)==meta['records']==meta['original_pm7_count'] and len({r['record_id'] for r in records})==len(records),'NO_NEW_N_OR_RECORD_REMOVAL')
    return {'schema':'PM7_POPULATION_CACHE_TASK_V1','cache_key':PC.task_key(plan['formal_source'],plan['hof_authority_review'],records),
      'meta':meta,'records':records,'hof':hof.values(ctx.db,records),'hof_mode':'CANONICAL_VERIFIED','software_bound':B.software_bound(meta['records'],meta['maximum_total_atoms']),
      'source_population_authority':C.meta(plan['population_prepared_reference'])['source_authority_reference'],'hof_source_provenance_reference':hof_reference,'golden_packet_reference':None}

def d7_task(ctx,db,meta,records,energies):
    import pyarrow.parquet as pq
    membership=db.execute('SELECT * FROM final_common WHERE molecule_id=?',[meta['molecule_id']]).fetch_arrow_table().to_pylist()
    if not membership or not membership[0]['common_population']:return None
    member=membership[0];maps=db.execute('SELECT * FROM uff_sources WHERE molecule_id=? ORDER BY sprime_conf_idx',[meta['molecule_id']]).fetch_arrow_table().to_pylist();rows=[];packets={}
    for m in maps:
        ref={'path':m['source_path'],'bytes':m['source_bytes'],'sha256':m['source_sha256']};ctx.require(ref)
        if m['source_format']=='parquet':
            found=db.execute('SELECT row_json,source_row_index FROM old_uff_rows WHERE molecule_id=? AND sprime_conf_idx=? AND source_path=?',
              [meta['molecule_id'],m['original_sprime_conf_idx'],ref['path']]).fetchall()
            C.need(len(found)==1 and found[0][1]==m['source_row_index'],'EXACT_ORIGINAL_PHYSICAL_UFF_ROW_AND_FILE_OFFSET');r=json.loads(found[0][0])
        else:
            if ref['path'] not in packets:packets[ref['path']]=R.read_packet(ref,ctx.value)
            r=packets[ref['path']]['conformers'][m['source_row_index']]
            C.need(r['geometry_sha256']==m['geometry_sha256'] and r['sprime_conf_idx']==m['kernel_sprime_conf_idx'],'ACTUAL_GENERATED_KERNEL_ROW_TO_NEW_PHYSICAL_ID')
        C.need(r['seed']==m['seed'] and r['source_record_id']==m['native_anchor_record_id'] and r['atom_order_sha256']==m['atom_order_sha256'],'UNMODIFIED_GEOMETRY_SOURCE_ANCHOR_AND_SEED')
        rows.append(dict(r,sprime_conf_idx=m['sprime_conf_idx'])) # Local read view only; original DATA bytes never change.
    C.need(len(rows)==member['merged_uff_count'],'ORDINARY_SPRIME_ROWS_CONSERVED_NO_N1_EXTRA_INSERT')
    return {'meta':dict(member,Sprime_conformers=len(rows)),'records':records,'sprime':rows,'hof':energies}


def recover_day(ctx,db,task,key,claim,d7_task):
    mid=task['meta']['molecule_id'];row=db.execute('SELECT row_json FROM prior_day WHERE molecule_id=?',[mid]).fetchone()
    C.need(row is not None and str(claim['job_id']) in ctx.day_registered,'EXISTING_CLAIM_HAS_NO_REAL_C0_REGISTERED_DAY_CLOSURE_HOLD')
    row=json.loads(row[0]);root=pathlib.Path(claim['output_directory']);ref=row['packet_reference'];claim_ref=ctx.reference(C.ROOT/'artifacts/conformers/postprocess_day_v1/claims'/(key+'.json'))
    C.need(claim['schema']=='POSTPROCESS_READONLY_MOLECULE_CLAIM_V1' and claim['uid']==1278 and claim['node'] in ('compute-0-14','compute-0-18')
      and claim['molecule_id']==mid and claim['key']==key and claim['cache_key']==task['cache_key'] and claim['packed_receipt_reference']==ctx.plan['packed_receipt_reference']
      and claim['original_records_SHA']==C.F.sha_value(task['records']) and claim['canonical_HOF_SHA']==C.F.sha_value(task['hof'])
      and row['claim_reference']==claim_ref and ref['path']==str(root/'molecules'/(key+'.json.gz')),'REAL_OLD_DAY_CLAIM_EXACT_SCIENTIFIC_INPUT_SOURCE')
    from . import statistics
    packet=statistics.packet(ctx,ref);start=ctx.read(packet['worker_start_reference']);C.need(packet['claim_reference']==claim_ref==start['claim_reference']
      and packet['runtime']['job_id']==start['job_id']==str(claim['job_id']) and packet['runtime']['uid']==start['uid']==1278
      and packet['runtime']['node']==start['node']==claim['node'] and packet['cache']['source_records']==task['records']
      and packet['cache']['hof_by_record']==task['hof'],'ACTUAL_PREVIOUS_DAY_SOURCE_RUNTIME_START_AND_FLOAT64_REOPEN')
    if d7_task is not None:
        d7=packet['d7'];C.need(d7 is not None and d7['cross_pm7_ids']==[r['conformer_id'] for r in sorted(packet['cache']['pm7'],key=lambda r:r['conformer_id'])]
          and set(d7['cross_uff_sprime_ids'])=={r['sprime_conf_idx'] for r in d7_task['sprime']},'PREVIOUS_D7_SAME_REAL_PHYSICAL_BASE_DOMAIN')
        for r in d7_task['sprime']:C.need(d7['geometry_hashes']['uff_sprime'][str(r['sprime_conf_idx'])]==ctx.geometry_sha(packet['cache']['atomic_numbers'],r['coordinates']),'PREVIOUS_D7_EXACT_SOURCE_GEOMETRY_NOT_RESOURCE_ALIAS')
    return row

def project_old_uff(ctx,db):
    """One sequential projection, not millions of random original-file opens."""
    import pyarrow as pa,pyarrow.parquet as pq
    manifest=C.meta(ctx.value['sprime_manifest']);db.execute('CREATE TABLE old_uff_rows(molecule_id VARCHAR,sprime_conf_idx BIGINT,row_json VARCHAR,source_path VARCHAR,source_row_index BIGINT,PRIMARY KEY(molecule_id,sprime_conf_idx))')
    columns=['molecule_id','sprime_conf_idx','coordinates','atom_order_sha256','source_record_id','seed','status','converged','uff_energy_kcal_mol','stereo_signature']
    for original in manifest['references']:
        if original['kind']!='conformers':continue
        ref=C.F.triple(original);path=ctx.require(ref);offset=0
        for batch in pq.ParquetFile(path).iter_batches(batch_size=4096,columns=columns):
            ctx.check();items=[]
            for i,row in enumerate(batch.to_pylist()):
                if row['status']=='SUCCESS' and row['converged'] is True:
                    items.append({'molecule_id':row['molecule_id'],'sprime_conf_idx':row['sprime_conf_idx'],'row_json':C.canonical(row).decode(),
                      'source_path':ref['path'],'source_row_index':offset+i})
            offset+=batch.num_rows
            if items:
                db.register('original_uff_batch',pa.Table.from_pylist(items));db.execute('INSERT INTO old_uff_rows SELECT b.* FROM original_uff_batch b JOIN final_common c USING(molecule_id) WHERE c.common_population')
                db.unregister('original_uff_batch')
        ctx.require(ref);db.commit()