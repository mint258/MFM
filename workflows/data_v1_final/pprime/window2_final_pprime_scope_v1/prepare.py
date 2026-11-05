"""Anti-join final real first-two geometries against closed QC and Native claims.

Run once after the final population and supplemental producer are closed. Reads
only metadata for existing labels; reads each newly needed geometry once and
stores its original F64 values for the unchanged original compute_pair engine.
"""
from __future__ import annotations
import argparse, collections, functools, gzip, json, os, sqlite3
from pathlib import Path
from .binding import BindingStore,same_geometry

def read(ref):
    return json.loads(Path(ref['path'] if isinstance(ref,dict) else ref).read_text(encoding='utf-8-sig'))

def save(path,value):
    path=Path(path);temporary=path.with_name(path.name+'.writing')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    os.replace(temporary,path)

def info(path,records=None):
    result={'path':str(path),'bytes':Path(path).stat().st_size}
    if records is not None:result['records']=records
    return result

def path(ref):return str(ref['path'] if isinstance(ref,dict) else ref)
def need(ok,message):
    if not ok:raise ValueError(message)

def key(row):
    need(isinstance(row.get('molecule_id'),str) and type(row.get('sprime_conf_idx')) is int,'ACTUAL_PHYSICAL_KEY_REQUIRED')
    return row['molecule_id'],row['sprime_conf_idx']

def record_id(k):return 'pprime:'+k[0]+':'+str(k[1])

def selected_rows(scope,eligible_only=True):
    import pyarrow.parquet as pq
    result={}
    for batch in pq.ParquetFile(path(scope['selected_geometry_table'])).iter_batches(batch_size=8192):
        for row in batch.to_pylist():
            if eligible_only and (not row['common_population'] or row['effective_role'] not in ('TRAIN','VAL')):continue
            need(row['fixed_random_rank'] in (0,1),'RANK_GE_2_FORBIDDEN')
            k=key(row);need(k not in result,'DUPLICATE_SELECTED_PHYSICAL_ID');result[k]=row
    ranks=collections.defaultdict(set)
    for row in result.values():ranks[row['molecule_id']].add(row['fixed_random_rank'])
    need(all(r in ({0},{0,1}) for r in ranks.values()),'FIRST_MIN_TWO_ACTUAL_RANKS_REQUIRED')
    return result

def old_closed_keys(index_ref,wanted,bindings):
    """QC defines the closed record universe; base pointers supply actual U IDs.

    The already produced full index is consumed as metadata, avoiding a second
    scan of the original 192k family publications. No record ID is parsed.
    """
    index=read(index_ref);need(index['schema']=='D6_FULL_ORIGINAL_PHYSICAL_LOCATOR_INDEX_V1','CLOSED_OLD_LOCATOR_INDEX_REQUIRED')
    identity=path(index['identity_database']);closed={};files=None
    storages=[index['QC_locations'],*[part['storage'] for part in index['partitions']]]
    for storage in storages:
        db=sqlite3.connect('file:'+path(storage)+'?mode=ro',uri=True)
        try:
            db.execute('ATTACH DATABASE ? AS identities',('file:'+identity+'?mode=ro',))
            for ordinal,rid,mid,file_id,locator in db.execute('''SELECT p.ordinal,i.record_id,i.mid,p.file,p.locator
                FROM pointers p JOIN identities.pprime_records i ON i.ordinal=p.ordinal WHERE p.domain=1'''):
                value=json.loads(locator);conf=value.get('sprime_conf_idx')
                if conf is None:continue
                need(type(conf) is int,'OLD_BASE_ACTUAL_INTEGER_UFF_ID')
                k=(mid,conf)
                if k not in wanted:continue
                matched,evidence=same_geometry(value,bindings.get(k))
                if matched is None:
                    if files is None:files={entry['id']:entry for entry in read(index['files_reference'])}
                    original=next((row for row in bindings.base_rows(files[file_id]['reference']['path']) if row['record_id']==rid),None)
                    need(original is not None and original['molecule_id']==mid,'OLD_CLOSED_BASE_SOURCE_IDENTITY')
                    matched,evidence=same_geometry(original,bindings.get(k))
                need(matched is not None,'INSUFFICIENT_REAL_GEOMETRY_BINDING_EVIDENCE')
                if not matched:continue
                need(k not in closed or closed[k]['record_id']==rid,'CONFLICTING_CLOSED_PPRIME_PHYSICAL_ID')
                closed[k]={'record_id':rid,'source':'closed_old_QC_and_base_locator_index','geometry_binding':evidence}
        finally:db.close()
    return closed

def supplemental_keys(roots,wanted,bindings):
    """Closed QC+base pairs and any claims that must never be automatically run."""
    import pyarrow.parquet as pq
    closed={};claims={};rid_keys={record_id(k):k for k in wanted}
    for root_ref in roots:
        root=Path(path(root_ref));manifest=read(root/'manifest.json')
        need(manifest.get('original_native_recipe_900s_unchanged') and manifest.get('no_Pprime_rank_ge_2'),'SUPPLEMENTAL_PRODUCER_NOT_CLOSED_OR_SCIENCE_CHANGED')
        for batch in manifest['batches']:
            by={entry['family']:entry for entry in batch['files']}
            if not by:continue
            need('QC' in by and 'base_geometry' in by,'CLOSED_QC_BASE_PAIR_REQUIRED')
            qc={row['record_id']:row['molecule_id'] for row in pq.read_table(path(by['QC']),columns=['record_id','molecule_id']).to_pylist()}
            base=bindings.base_rows(path(by['base_geometry']))
            need(len(qc)==len(base),'QC_BASE_CLOSED_RECORD_COUNT_DIFFERS')
            for row in base:
                need(qc.get(row['record_id'])==row['molecule_id'],'QC_BASE_PHYSICAL_ALIGNMENT')
                k=key(row)
                if k in wanted:
                    matched,evidence=same_geometry(row,bindings.get(k))
                    need(matched is not None,'SUPPLEMENTAL_GEOMETRY_BINDING_EVIDENCE_REQUIRED')
                    if not matched:continue
                    need(k not in closed or closed[k]['record_id']==row['record_id'],'SUPPLEMENTAL_PHYSICAL_ID_CONFLICT')
                    closed[k]={'record_id':row['record_id'],'source':str(root),'geometry_binding':evidence}
        claimfile=root/'claims.sqlite'
        if claimfile.exists():
            db=sqlite3.connect('file:'+str(claimfile)+'?mode=ro',uri=True)
            try:
                for rid,status in db.execute('SELECT record_id,status FROM claims'):
                    if rid in rid_keys:claims[rid_keys[rid]]={'record_id':rid,'source':str(root),'claim_status':status}
            finally:db.close()
    return closed,claims

@functools.lru_cache(maxsize=4)
def parquet_group(filename,group):
    import pyarrow.parquet as pq
    return pq.ParquetFile(filename).read_row_group(group)

@functools.lru_cache(maxsize=2)
def packet(filename):
    with gzip.open(filename,'rb') as stream:return json.load(stream)

def geometry(row):
    """One actual source row; never synthesize an extra conformer or ordinal."""
    import pyarrow.parquet as pq
    filename=row['source_path'];position=int(row['source_row_index']);need(position>=0,'NEGATIVE_SOURCE_ROW')
    if row['source_format']=='parquet':
        pf=pq.ParquetFile(filename);offset=0
        for group in range(pf.num_row_groups):
            count=pf.metadata.row_group(group).num_rows
            if position<offset+count:
                raw=parquet_group(filename,group).slice(position-offset,1).to_pylist()[0];break
            offset+=count
        else:raise ValueError('ACTUAL_GEOMETRY_ROW_MISSING')
    elif row['source_format']=='reproduction_json_gz':
        value=packet(filename);need(value['summary']['molecule_id']==row['molecule_id'],'PACKET_MID_DIFFERS')
        raw=value['conformers'][position]
    else:raise ValueError('UNSUPPORTED_ACTUAL_SOURCE_FORMAT:'+str(row['source_format']))
    need(raw.get('molecule_id',row['molecule_id'])==row['molecule_id'],'GEOMETRY_MID_DIFFERS')
    need(raw['status']=='SUCCESS' and raw['converged'] is True,'GEOMETRY_NOT_ACTUALLY_USABLE')
    need(type(raw['sprime_conf_idx']) is int,'ORIGINAL_PHYSICAL_ID_REQUIRED')
    need(isinstance(raw.get('source_record_id'),str) and raw['source_record_id'],'SOURCE_NATIVE_ANCHOR_REQUIRED')
    numbers=raw.get('atomic_numbers',raw.get('z'))
    need(bool(raw.get('atom_order_sha256')) or numbers is not None,'EXISTING_ATOM_WITNESS_OR_ACTUAL_ORDERED_Z_REQUIRED')
    if numbers is not None:need(len(numbers)==len(raw['coordinates']),'GEOMETRY_ATOM_COORDINATE_ALIGNMENT')
    return raw

def source_shards(source_plan):
    value=read(source_plan)
    if isinstance(value,list):rows=value
    elif 'sources' in value:rows=value['sources']
    else:
        found={int(row['shard_id']):row for manifest in value['manifests'].values() for row in manifest['shards']};rows=list(found.values())
    shards={row['path']:int(row['shard_id']) for row in rows}
    need(len(shards)==11 and set(shards.values())==set(range(11)),'EXACT_ORIGINAL_ELEVEN_NATIVE_SHARDS')
    return shards

def prepare(plan):
    import duckdb,pyarrow as pa,pyarrow.parquet as pq
    out=Path(plan['scope_output']);out.mkdir(parents=True,exist_ok=True)
    if (out/'manifest.json').exists():return read(out/'manifest.json')
    scope=read(plan['first2']);selected=selected_rows(scope);all_selected=selected_rows(scope,eligible_only=False)
    binding_path=out/'physical_bindings.sqlite'
    bindings=BindingStore(binding_path)
    # This is the single production geometry/alignment consumption. Downstream
    # fit uses these F64 bindings, and reuses any original base rows read here.
    for row in sorted(all_selected.values(),key=lambda row:(row['source_path'],row['source_row_index'])):
        bindings.add(row,geometry(row))
    common=read(plan['common'])
    for reference in common.get('physical_geometry_tables',[]):
        for batch in pq.ParquetFile(path(reference)).iter_batches(batch_size=8192):
            for row in batch.to_pylist():
                if row.get('geometry_source')=='uff_sprime':bindings.candidate(row)
    closed=old_closed_keys(plan['source_index'],selected,bindings)
    supplemental,claims=supplemental_keys(plan.get('additional_pprime_roots',[]),selected,bindings);closed.update(supplemental)
    needed=[row for k,row in selected.items() if k not in closed and k not in claims]
    needed.sort(key=lambda row:(row['source_path'],row['source_row_index']))
    unknown=[dict(selected[k],record_id=record_id(k),state='UNKNOWN_NATIVE_INTENT_WITHOUT_CLOSED_QC',claim=claim) for k,claim in claims.items() if k not in closed]
    # Existing inputs are retained on operational failure. Fresh output paths
    # avoid overwriting a partially built publication.
    taskpath=out/'tasks.parquet';need(not taskpath.exists(),'PARTIAL_SCOPE_EXISTS_USE_FRESH_OUTPUT_WITH_EXISTING_FILES_RETAINED')
    db=duckdb.connect();db.execute('SET threads='+str(int(plan.get('workers',16))))
    anchors=[];staged=[]
    try:
        for row in needed:
            raw=bindings.raw(key(row));anchor=raw['source_record_id'];anchors.append(anchor)
            staged.append(dict(row,native_anchor_record_id=anchor,original_sprime_conf_idx=raw['sprime_conf_idx'],
                atom_order_sha256=raw.get('atom_order_sha256'),source_member=row.get('source_member') or ('conformers' if row['source_format']=='reproduction_json_gz' else None),
                source_bytes=Path(row['source_path']).stat().st_size,physical_geometry_json=json.dumps(raw,ensure_ascii=False,allow_nan=False,separators=(',',':'))))
        db.register('anchors',pa.table({'record_id':pa.array(list(dict.fromkeys(anchors)),type=pa.string())}))
        quoted="'"+path(plan['native_record_index']).replace("'","''")+"'"
        sources={}
        for row in db.execute('SELECT p.* FROM read_parquet('+quoted+') p JOIN anchors a USING(record_id)').fetch_arrow_table().to_pylist():
            need(row['record_id'] not in sources,'NATIVE_ANCHOR_NOT_UNIQUE');sources[row['record_id']]=row
        shards=source_shards(plan['source_plan']);tasks=[];member_groups={}
        common=read(plan['common']);needed_mids={row['molecule_id'] for row in staged}
        for ref in common['membership_tables']:
            for batch in pq.ParquetFile(path(ref)).iter_batches(columns=['molecule_id','file_group'],batch_size=8192):
                for member in batch.to_pylist():
                    if member['molecule_id'] in needed_mids:
                        need(member['molecule_id'] not in member_groups,'COMMON_MEMBER_NATIVE_GROUP_DUPLICATE')
                        member_groups[member['molecule_id']]=member['file_group']
        for row in staged:
            source=sources.get(row['native_anchor_record_id']);need(source is not None and source['molecule_id']==row['molecule_id'],'NATIVE_ANCHOR_MID_ALIGNMENT')
            need(source['source_path'] in shards,'NATIVE_SOURCE_NOT_ORIGINAL_SHARD')
            source['shard_id']=shards[source['source_path']]
            heavy=int(source['heavy_atoms']);need(heavy>0,'NATIVE_ACTUAL_HEAVY_ATOMS_REQUIRED')
            source.update(effective_role=row['effective_role'],source_role=row['source_role'])
            group=member_groups.get(row['molecule_id'])
            if type(source.get('file_group')) is int:
                need(group is None or group==source['file_group'],'COMMON_NATIVE_FILE_GROUP_DIFFERS')
            else:source['file_group']=group
            need(type(source.get('file_group')) is int,'ORIGINAL_NATIVE_FILE_GROUP_REQUIRED')
            tasks.append(dict(row,record_id=record_id(key(row)),random_order_rank=int(row['fixed_random_rank']),
                native_source_json=json.dumps(source,ensure_ascii=False,allow_nan=False,separators=(',',':')),
                file_group=source['file_group'],size_stratum='0_20' if heavy<=20 else '21_40' if heavy<=40 else '41_75' if heavy<=75 else 'above_75',
                usage='PprimeOnly' if row.get('usage_domain')=='registered_pprime_extra' else 'ordinary_first2'))
        tasks.sort(key=lambda row:(row['molecule_id'],row['random_order_rank']))
        if tasks:table=pa.Table.from_pylist(tasks)
        else:table=pa.table({'molecule_id':pa.array([],type=pa.string()),'sprime_conf_idx':pa.array([],type=pa.int64()),'random_order_rank':pa.array([],type=pa.int64())})
        pq.write_table(table,taskpath,compression='zstd',row_group_size=1024)
        unknownpath=out/'unknown_native_intents.json';save(unknownpath,unknown)
        states=scope['record_level_state_table'];counts=collections.Counter()
        for batch in pq.ParquetFile(path(states)).iter_batches(columns=['effective_role','common_population','selected_first2','missing_to_two','reason'],batch_size=8192):
            for row in batch.to_pylist():
                if row['common_population'] and row['effective_role'] in ('TRAIN','VAL'):
                    counts[row['reason']]+=1;counts['actual_shortfall_to_two']+=int(row['missing_to_two'])
        bindings.close()
        result={'schema':'PPRIME_FINAL_PHYSICAL_FIRST2_CONTINUATION_SCOPE_V1','status':'FINAL_PHYSICAL_SCOPE_READY_WITH_EXPLICIT_UNKNOWN_AND_SHORTFALL',
            'first2':plan['first2'],'source_index':plan['source_index'],'additional_pprime_roots':plan.get('additional_pprime_roots',[]),
            'actual_first2_records':len(selected),'actual_chosen_MIDs':len({k[0] for k in selected}),
            'reused_closed_records':len(closed),'unknown_native_intents':len(unknown),'needed_records':len(tasks),
            'tables':{'tasks':info(taskpath,len(tasks)),'unknown_native_intents':info(unknownpath,len(unknown))},
            'physical_binding_database':info(binding_path,len(all_selected)),
            'geometry_binding':'existing input witnesses, otherwise original ordered Z/witness and F64 source coordinates; no key-only reuse',
            'record_level_state_table':states,'shortfall_counts':dict(counts),
            'no_new_N1_generation':True,'no_padding_or_duplication':True,'no_Pprime_rank_ge_2':True,
            'native_calls_in_scope_producer':0,'content_hashes_computed':False,'independent_QA_or_readback':False}
        need(result['reused_closed_records']+len(unknown)+len(tasks)==len(selected),'EXHAUSTIVE_FINAL_PHYSICAL_PARTITION')
        save(out/'manifest.json',result);return result
    finally:db.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True);args=parser.parse_args()
    print(json.dumps(prepare(read(args.plan)),ensure_ascii=False))
