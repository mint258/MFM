"""B1: stream delivered D6 and existing physical locators; original CELL reader only."""
import argparse,collections,concurrent.futures as cf,hashlib,importlib.util,json,pathlib,sqlite3,sys,time,multiprocessing
import numpy as np
import pyarrow.parquet as pq
from resources import REPO,R,CONTROL,SIDE,load,save,guard
from phychem_mfm.phase1.v31_loader import MFM4Dataset,decode_mfm4,record_key,split_metadata

INDEX='/lfshome/zixiao/data_v1_20261025/D6_full_physical_index_20261105_v3/manifest.json'
COMPONENT=R/'runs/data_v1_20261025/control/window2_20261105/D6_node20_shared_candidate_20261108_v1/source_snapshot86/workflows/data_v1_final/labels/common.py'
COMPONENT_SPEC=importlib.util.spec_from_file_location('original_d6_components',COMPONENT)
COMMON=importlib.util.module_from_spec(COMPONENT_SPEC);COMPONENT_SPEC.loader.exec_module(COMMON)
FIELDS={};FILES={};WANTED={}

def ro(path):return sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)

def source_file(item):
    fid,groups=item;reference=FILES[fid]['reference'];path=pathlib.Path(reference['path'])
    if path.stat().st_size!=reference['bytes']:raise ValueError('Physical-index source size differs:'+str(path))
    q=pq.ParquetFile(path,pre_buffer=False);outputs=[]
    # CELL scalars use these original leaves; array payloads are omitted unless needed.
    columns=['record_id','molecule_id','calc_type','total_atoms','numeric_issues']
    leaves=['registry_id','kind','f64','i64','boolean','text']
    columns+=['values.list.element.'+v for v in leaves]
    for rg,entries in sorted(groups.items()):
        table=q.read_row_group(rg,columns=columns,use_threads=False)
        if 'values' not in table.column_names:raise ValueError('Projected original CELL column absent')
        selected_ids={f['registry_id'] for fs in FIELDS.values() for f in fs}
        for row_index,slot in entries:
            raw=table.slice(row_index,1).to_pylist()[0];task=raw['calc_type']
            if task not in FIELDS:continue
            if any(cell['registry_id'] in selected_ids and cell['kind'] in (5,6,7) for cell in raw.get('values') or []):
                raw=q.read_row_group(rg,columns=['record_id','molecule_id','calc_type','total_atoms','numeric_issues','values'],use_threads=False).slice(row_index,1).to_pylist()[0]
            key=(raw['molecule_id'],raw['record_id'])
            if WANTED.get(key)!=slot:
                outputs.append((slot,{f['field_key']:np.nan for f in FIELDS[task]}));continue
            values={}
            for field,value,indices,reason in COMMON.task_components(raw,'REGISTRY_CELL',FIELDS[task]):
                values[field['field_key']]=float(value[0]) if reason is None and len(value)==1 and COMMON.numeric(value[0]) else np.nan
            outputs.append((slot,values))
        del table
    q.close();return outputs

def d6_worker(rows):
    DATA._open();rows=[r for r in rows if r['record_kind'] in ('P','U')]
    packed=np.zeros(len(rows),dtype=TABLE_DTYPE)
    for name in NAMES:packed[name]=np.nan
    reference=np.full((len(rows),len(NAMES)),np.nan,np.float32);identities=[];labels=collections.Counter()
    with DATA._env.begin(buffers=True) as transaction:
        for i,r in enumerate(rows):
            kind=r['record_kind'];mi=int(r['molecule_index']);ci=int(r['conformer_index']);handle=record_key(kind,mi,ci)
            payload=transaction.get(handle)
            if payload is None:raise KeyError((kind,mi,ci))
            arrays=decode_mfm4(payload,array_ids={23})
            target=DATA.view.extract({1:np.empty(0,np.int16)},arrays,
                mask_overrides=(DATA._record_masks if kind=='P' else PRIME_MASKS).get((mi,ci)),raw_only=True)
            packed[i]['molecule_index']=mi;packed[i]['conformer_index']=ci;packed[i]['record_handle']=handle
            present=False
            for j,name in enumerate(NAMES):
                t=target.get(name)
                if t is not None and t.valid.all() and np.isfinite(t.raw).all():reference[i,j]=t.raw.flat[0];present=True;labels[kind]+=1
            if present:
                rid=r['native_record_id'] if kind=='P' else 'pprime:'+r['molecule_id']+':'+str(r['sprime_conf_idx'])
                identities.append((i,r['molecule_id'],rid))
    return packed,reference,identities,labels

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024**2),b''):h.update(block)
    return h.hexdigest()

def main():
    global FIELDS,FILES,WANTED,DATA,PRIME_MASKS,NAMES,TABLE_DTYPE
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    if not 1<=a.workers<=16:raise ValueError('B CPU limit16')
    guard(force=True,lustre=True);started=time.monotonic();SIDE.mkdir(parents=True,exist_ok=True)
    if (SIDE/'manifest.json').exists():raise FileExistsError('Final B1 manifest exists; do not regenerate')
    c=load(REPO/'configs/p_followup/C_dedup.json');names=load(REPO/'results/p_followup/B_field_selection.json')['selected_fields']
    projection=load('/lfshome/zixiao/data_v1_20261025/full_projection_coverage_20261105_r2/manifest.json')
    fields=[f for f in load(projection['field_map_reference']['path']) if f['field_key'] in names]
    assert len(fields)==4
    for f in fields:FIELDS.setdefault(f['task'],[]).append(f)
    manifest=load(pathlib.Path(c['root'])/'manifest.json');tables={};references={};offsets={};splits={};ranges=[];prefix=0;done=0;first=False
    total=sum(manifest['conformers'].values())
    dtype=np.dtype([('molecule_index','<u4'),('conformer_index','<u2'),('record_handle','S7')]+[(n,'<f8') for n in names]);NAMES=names;TABLE_DTYPE=dtype
    # Numeric source routing is memory-only; no new full source index is persisted.
    WANTED={};seen={}
    for split in ['TRAIN','FULL']:
        guard(force=True,lustre=True);directory,meta=split_metadata(pathlib.Path(c['root']),split)
        count=int(manifest['conformers'][split+'_P']+manifest['conformers'][split+'_U'])
        out=SIDE/split;out.mkdir(exist_ok=True);values=out/'values.npy';route=out/'molecule_offsets.npy'
        table=np.lib.format.open_memmap(values,mode='w+',dtype=dtype,shape=(count,))

        ref=np.full((count,len(names)),np.nan,dtype=np.float32);offset=np.zeros(meta['molecule_count']+1,dtype=np.int64)
        view=load(c['training_view']);view=dict(view,fields=[f for f in view['fields'] if f.get('name',f.get('field_key')) in names])
        data=MFM4Dataset(c['root'],split=split,training_view=view,normalizations=load(c['normalizations']),k=10)
        from phychem_mfm.phase1.v31_record_masks import published_record_masks
        prime_masks=published_record_masks(load(c['normalizations']),directory,dataset='Pprime')
        position=0;last_mi=-1;carrying=0;labels=collections.Counter();DATA=data;PRIME_MASKS=prime_masks
        q=pq.ParquetFile(directory/'id_map.parquet',pre_buffer=False)
        columns=['record_kind','molecule_index','conformer_index','molecule_id','native_record_id','sprime_conf_idx']
        batches=iter(q.iter_batches(batch_size=4096,columns=columns,use_threads=False));pending=collections.deque()
        with cf.ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('fork')) as pool:
            for _ in range(a.workers*2):
                batch=next(batches,None)
                if batch is not None:pending.append(pool.submit(d6_worker,batch.to_pylist()))
            while pending:
                packed,raw,identities,counts=pending.popleft().result();n=len(packed)
                if n:
                    index=packed['molecule_index'].astype(np.int64)
                    if index[0]<last_mi or np.any(np.diff(index)<0):raise ValueError('D6 record order differs')
                    last_mi=int(index[-1]);table[position:position+n]=packed;ref[position:position+n]=raw;np.add.at(offset,index+1,1)
                    for row,mid,rid in identities:
                        key=(sys.intern(mid),rid)
                        if key in WANTED:raise ValueError(('Duplicate original physical identity',key))
                        WANTED[key]=prefix+position+row
                    carrying+=len(identities);labels.update(counts);position+=n;done+=n
                batch=next(batches,None)
                if batch is not None:pending.append(pool.submit(d6_worker,batch.to_pylist()))
                if not first and done>=total*.01:
                    elapsed=time.monotonic()-started;print('B1_FIRST_PERCENT_D6',dict(records=done,total=total,seconds=elapsed,records_per_second=done/elapsed,D6_remaining_hours=(total-done)*elapsed/done/3600,source_phase_not_yet_measured=True,reader_workers=a.workers),flush=True);first=True
                guard(lustre=True)
                if done//100000!=(done-n)//100000:table.flush();print('B1_D6',split,done,total,flush=True)
        q.close();data.close();assert position==count
        np.cumsum(offset,out=offset);np.save(route,offset);table.flush();tables[split]=table;references[split]=ref;offsets[split]=offset;seen[split]=np.zeros(ref.shape,dtype=bool)
        splits[split]=dict(D6_directory=str(directory),values=str(values),molecule_offsets=str(route),records=count,records_carrying_selected=carrying,valid_values_by_kind=dict(labels));ranges.append((prefix,prefix+count,split));prefix+=count
    physical=load(INDEX);FILES={f['id']:f for f in load(physical['files_reference']['path'])};families={f['family_source'] for f in fields}|{'QC'}
    locators={};canonical=ro(physical['canonical_reference']['path']);length=int(physical.get('original_P_records',0))
    if not length:length=canonical.execute('SELECT MAX(record_ordinal)+1 FROM records').fetchone()[0]
    pslots=np.full(length,-1,np.int64)
    for ordinal,rid,mid in canonical.execute('SELECT record_ordinal,record_id,molecule_id FROM records'):
        slot=WANTED.get((mid,rid))
        if slot is not None:pslots[ordinal]=slot
    canonical.close();identity=ro(physical['identity_database']['path']);uslots={}
    for ordinal,rid,mid in identity.execute('SELECT ordinal,record_id,mid FROM pprime_records'):
        slot=WANTED.get((mid,rid))
        if slot is not None:uslots[ordinal]=slot
    identity.close();print('B1_ROUTING',dict(D6_physical_records=len(WANTED),original_P_mapped=int((pslots>=0).sum()),original_Pprime_mapped=len(uslots)),flush=True)
    mismatch=collections.Counter();matched=collections.Counter();duplicate=collections.Counter();source_done=0;source_first=False
    def apply(outputs):
        nonlocal source_done,source_first
        for global_row,values in outputs:
            lo,hi,split=next(r for r in ranges if r[0]<=global_row<r[1]);row=global_row-lo
            for name,value in values.items():
                j=names.index(name);expected=references[split][row,j]
                if not np.isfinite(expected):continue
                if seen[split][row,j]:
                    duplicate[name]+=1
                    if np.isfinite(tables[split][name][row]):mismatch[name]+=1
                    tables[split][name][row]=np.nan;continue
                seen[split][row,j]=True
                matched[name]+=1
                if not np.isfinite(value) or np.float32(value).view('u4')!=np.asarray(expected).view('u4'):
                    mismatch[name]+=1;tables[split][name][row]=np.nan
                else:tables[split][name][row]=value
            source_done+=1
        if not source_first and source_done>=len(WANTED)*.01*4:
            elapsed=time.monotonic()-started;print('B1_FIRST_PERCENT_SOURCE',dict(task_records=source_done,seconds=elapsed,end_to_end_estimated_hours=elapsed*len(WANTED)*4/source_done/3600),flush=True);source_first=True
    storages=[physical['QC_locations'],*[v['storage'] for v in physical['partitions']]]
    for part,storage in enumerate(storages):
        guard(lustre=True);connection=ro(storage['path']);loc=collections.defaultdict(lambda:collections.defaultdict(list))
        for domain,ordinal,fid,rg,row in connection.execute('SELECT domain,ordinal,file,rg,r FROM locations'):
            if FILES[fid]['family'] not in families:continue
            slot=int(pslots[ordinal]) if domain==0 and ordinal<len(pslots) else uslots.get(ordinal,-1) if domain==1 else -1
            if slot>=0:loc[fid][rg].append((row,slot))
        connection.close();print('B1_LOCATOR_PART',part,len(storages),'files',len(loc),flush=True)
        with cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
            iterator=iter(loc.items());pending=set()
            for _ in range(a.workers*2):
                item=next(iterator,None)
                if item is not None:pending.add(pool.submit(source_file,item))
            while pending:
                ready,pending=cf.wait(pending,return_when=cf.FIRST_COMPLETED)
                for future in ready:
                    apply(future.result());guard(lustre=True)
                    item=next(iterator,None)
                    if item is not None:pending.add(pool.submit(source_file,item))
        for table in tables.values():table.flush()
        print('B1_SOURCE_PROGRESS',part,source_done,'seconds',time.monotonic()-started,flush=True)
    field_status={};enabled=[]
    for j,name in enumerate(names):
        valid=sum(int(np.isfinite(v[:,j]).sum()) for v in references.values());found=matched[name]
        missing=valid-found;bad=mismatch[name]+missing;rate=bad/valid if valid else 0.
        status='COMPLETE' if rate<=.0001 else 'UNRESOLVED'
        field_status[name]=dict(status=status,D6_valid_values=valid,source_aligned_values=found-mismatch[name],mismatch=mismatch[name],missing_source=missing,duplicate_source_rows=duplicate[name],mismatch_rate=rate)
        if status=='COMPLETE':enabled.append(name)
    for table in tables.values():table.flush()
    for split,s in splits.items():
        s['values_bytes']=pathlib.Path(s['values']).stat().st_size;s['values_SHA256']=digest(pathlib.Path(s['values']));s['molecule_offsets_SHA256']=digest(pathlib.Path(s['molecule_offsets']))
    result=dict(status='COMPLETE',enabled_fields=enabled,requested_fields=names,field_status=field_status,splits=splits,source_physical_index=INDEX,original_component_reader=str(COMPONENT),seconds=time.monotonic()-started,workers=a.workers,sidecar_default=None,enabled_in_C_D=False,new_full_source_index=False)
    save(SIDE/'manifest.json',result);save(REPO/'configs/p_followup/B_sidecar_manifest.json',result);print('B1_COMPLETE',field_status,flush=True)
if __name__=='__main__':main()