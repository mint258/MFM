"""One-job compact v3.1 repack; one final 1000-P check, no content hashes."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,json,multiprocessing as mp,os,pathlib,random,shutil,subprocess,time
import numpy as np
from .codec import encode,encode_key
from .legacy_reader import OldStore
from .schema_fields import compile_schema
from .assemble import assemble_molecule
P=pathlib.Path
_CACHE=None
_DESCRIPTORS=None
_SCHEMA=None
_DIAGNOSTIC_MIDS=None
ROLE_CODES={'TRAIN':0,'VAL':1,'FULL':2,'embargo':3}

def load(path):
    with open(path,'r',encoding='utf-8-sig') as f:return json.load(f)

def save(path,value):
    path=P(path);temp=path.with_name(path.name+'.writing')
    with temp.open('w',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
    os.replace(temp,path)

def referenced_parquets(value):
    found={}
    def visit(v):
        if isinstance(v,dict):
            if {'path','bytes','sha256'}<=set(v) and str(v['path']).endswith('.parquet'):
                found[v['path']]={k:v[k]for k in ('path','bytes','sha256')}
            else:
                for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(value);return list(found.values())

def descriptors(index,holdout,plan):
    result=[];source_prefix=plan['old_shared_root'];cache=P(plan['old_node_cache_root'])
    for reference in index['store_references']:
        closed=load(reference['path']);original=closed['path'];path=original
        if not holdout and original.startswith(source_prefix+'/'):
            candidate=cache/P(original).relative_to(source_prefix)
            if (candidate/'data.mdb').is_file():path=str(candidate)
        result.append(dict(name=closed.get('name',P(original).name),path=path,original_path=original,
            kind=closed['kind'],geometry_source=closed['geometry_source'],view_id=closed.get('view_id'),
            family=closed.get('family'),is_holdout=holdout,records=int(closed.get('records',0))))
    return result

def init_worker(desc,schema,diagnostic):
    global _CACHE,_DESCRIPTORS,_SCHEMA,_DIAGNOSTIC_MIDS
    _CACHE=collections.OrderedDict();_DESCRIPTORS=desc;_SCHEMA=schema;_DIAGNOSTIC_MIDS=set(diagnostic)
    os.environ['CUDA_VISIBLE_DEVICES']=''

def reader_for(path):
    if path in _CACHE:
        item=_CACHE.pop(path);_CACHE[path]=item;return item
    while len(_CACHE)>=160:_CACHE.popitem(last=False)[1].close()
    item=OldStore(path);_CACHE[path]=item;return item

def work(task):
    group,mids=task;answer=[]
    for mid in mids:
        readers=[]
        for desc in _DESCRIPTORS:
            if desc['is_holdout']:
                if mid not in _DIAGNOSTIC_MIDS:continue
            elif desc['group']!=group:continue
            readers.append((desc,reader_for(desc['path'])))
        item=assemble_molecule(mid,readers,_SCHEMA)
        if item.get('complete',True) is False:
            raise RuntimeError('SCIENTIFIC_LAYOUT_NOT_LOSSLESS:'+mid+':'+repr(item.get('topology_differences')))
        answer.append(item)
    return answer

class Writer:
    def __init__(self,path,estimate):
        import lmdb
        self.path=P(path);self.path.mkdir(parents=True,exist_ok=False)
        self.env=lmdb.open(str(self.path),map_size=2*estimate,subdir=True,max_dbs=0)
        self.count=collections.Counter();self.bytes=collections.Counter()
    def put_many(self,items):
        import lmdb
        while True:
            try:
                with self.env.begin(write=True)as tx:
                    for kind,mi,ci,raw in items:
                        key=encode_key(kind,mi,ci) if kind!='M' else encode_key(kind,mi)
                        if not tx.put(key,raw,overwrite=False):raise ValueError('DUPLICATE_COMPACT_KEY')
                break
            except lmdb.MapFullError:self.env.set_mapsize(self.env.info()['map_size']*2)
        for kind,mi,ci,raw in items:
            self.count[kind]+=1;self.bytes[kind]+=len(raw)+len(encode_key(kind,mi,ci)if kind!='M'else encode_key(kind,mi))
    def close(self):
        self.env.sync();self.env.close();self.env=None

class IDMap:
    def __init__(self,path):
        import pyarrow as pa,pyarrow.parquet as pq
        self.schema=pa.schema([('record_kind',pa.string()),('molecule_index',pa.uint32()),('conformer_index',pa.uint16()),
          ('molecule_id',pa.string()),('native_record_id',pa.string()),('sprime_conf_idx',pa.int64()),
          ('legacy_geometry_ids',pa.list_(pa.string())),('holdout',pa.bool_()),
          ('atom_permutations',pa.list_(pa.struct([('path',pa.string()),('gid',pa.string()),('source_to_M',pa.list_(pa.int32()))])))])
        self.writer=pq.ParquetWriter(path,self.schema,compression=None,use_dictionary=True);self.rows=0
    def append(self,rows):
        import pyarrow as pa
        if rows:self.writer.write_table(pa.Table.from_pylist(rows,schema=self.schema));self.rows+=len(rows)
    def close(self):self.writer.close()

def identity_row(kind,mi,ci,mid,record,held):
    ident=record.get('identity',{});aliases=ident.get('legacy_geometry_ids',ident.get('geometry_ids',[]))
    if not aliases and ident.get('geometry_id'):aliases=[ident['geometry_id']]
    return dict(record_kind=kind,molecule_index=mi,conformer_index=ci,molecule_id=mid,
      native_record_id=ident.get('native_record_id'),sprime_conf_idx=ident.get('sprime_conf_idx'),
      legacy_geometry_ids=list(aliases),holdout=bool(held),atom_permutations=ident.get('atom_permutations',[]))

def compact_once(source,destination):
    destination=P(destination);destination.mkdir(exist_ok=False)
    binary=shutil.which('mdb_copy') or '/share/apps/softwares/anaconda3/bin/mdb_copy'
    subprocess.run([binary,'-c',str(source),str(destination)],check=True)

def du(path):return int(subprocess.check_output(['du','-s','-B1',str(path)],text=True).split()[0])

def parquet_mids(reference):
    import pyarrow.parquet as pq
    return set(pq.read_table(reference['path'],columns=['molecule_id'])['molecule_id'].to_pylist())

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True);args=parser.parse_args()
    plan=load(args.plan);started=time.monotonic();root=P(plan['output_root']);scratch=P(plan['working_root'])
    if root.exists()or scratch.exists():raise FileExistsError('NEW_V31_ROOT_REQUIRED_OLD_V30_NEVER_OVERWRITTEN')
    if os.getuid()!=1278 or os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise RuntimeError('OWN_CPU_ONLY_PARENT_REQUIRED')
    root.mkdir(parents=True);scratch.mkdir(parents=True)
    d3=load(plan['D3_index']);d5=load(plan['D5_index']);configs=d3['actual_configuration_references']
    registry=load(configs['registry_reference']['path']);mapping=load(configs['mapping_reference']['path']);policy=load(configs['target_policy_reference']['path'])
    refs=referenced_parquets([d3,d5,registry,policy])
    for reference in plan.get('parquet_manifest_references',[]):
        refs.extend(referenced_parquets(load(reference['path'])))
    refs=list({r['path']:r for r in refs}.values())
    schema=compile_schema(registry,mapping,policy,plan['versions'],refs,plan['code_commit'])
    schema.update(role_codebook=ROLE_CODES,source_D3_reference=plan['D3_index_reference'],source_D5_reference=plan['D5_index_reference'],
      F64_authority='ORIGINAL_WP5_FLOAT64_PARQUET_NO_NEW_F64_COPY',input_parquet_manifest_references=plan.get('parquet_manifest_references',[]),
      original_available_conformer_orders=d3.get('available_orders',['fixed_random']),D6=False,Model_payload_ACK=False,
      heldout_geometry_policy='STORED_WITH_HOLDOUT_MARKS_NEVER_TRAINED',schema_shared_by=['TRAIN','VAL'])
    ds=descriptors(d3,False,plan)+descriptors(d5,True,plan)
    groups=collections.defaultdict(list)
    for item in ds:
        if not item['is_holdout']:
            item['group']=int(item['name'].split('_')[1]);groups[item['group']].append(item)
    tasks=[];mids_seen=set();expected_source=collections.Counter()
    for item in ds:
        if item['kind']=='geometry'and item['view_id'] is None:expected_source[item['geometry_source']]+=item['records']
    for group,items in sorted(groups.items()):
        base=next(x for x in items if x['kind']=='geometry'and x['geometry_source']=='pm7'and x['view_id']is None)
        with OldStore(base['path'])as reader:mids=sorted({mid for mid,gid in reader.iter_index()})
        if mids_seen.intersection(mids):raise ValueError('DUPLICATE_OLD_MOLECULE_GROUP')
        mids_seen.update(mids)
        tasks.extend((group,mids[i:i+plan['molecules_per_task']])for i in range(0,len(mids),plan['molecules_per_task']))
    diagnostic=parquet_mids(d5['actual_seen_diagnostic_molecule_ids_reference'])
    writers={role:Writer(scratch/role,plan['estimated_split_bytes'][role])for role in ('TRAIN','VAL')}
    for role in writers:(root/('v31_pilot_'+role)).mkdir()
    maps={role:IDMap(root/('id_map_'+role+'.parquet'))for role in writers}
    schema['r73_channel_codebook']=['__ABSENT__'];channels={};indices=collections.Counter();counts=collections.Counter();topology=[]
    rng=random.Random(plan['sample_seed']);sample=[];P_seen=0;total=0
    progress=P(plan['progress_path'])
    context=mp.get_context('spawn')
    pool=cf.ProcessPoolExecutor(max_workers=plan['workers'],mp_context=context,initializer=init_worker,initargs=(ds,schema,list(diagnostic)))
    iterator=iter(tasks);pending=collections.deque()
    for _ in range(plan['workers']*2):
        try:pending.append(pool.submit(work,next(iterator)))
        except StopIteration:break
    try:
        while pending:
            result=pending.popleft().result()
            for item in result:
                role=item['role'];mi=indices[role];indices[role]+=1;mid=item['mid'];arrays=item['m_arrays'];arrays[5]=np.asarray(ROLE_CODES[role],dtype='u1')
                p_records=item['p_records'];u_records=item['u_records'];arrays[6]=np.asarray([len(p_records),len(u_records)],dtype='<u2')
                encoded=[('M',mi,None,encode(arrays))];rows=[identity_row('M',mi,None,mid,{},False)]
                for kind,records,holdid in [('P',p_records,13),('U',u_records,14)]:
                    for ci,record in enumerate(records):
                        body=record['arrays']
                        if kind=='P'and record.get('r73_channels') is not None:
                            packed=[]
                            for triple in record['r73_channels']:
                                codes=[]
                                for word in triple:
                                    if word is None:codes.append(0);continue
                                    if word not in channels:
                                        channels[word]=len(schema['r73_channel_codebook']);schema['r73_channel_codebook'].append(word)
                                    codes.append(channels[word])
                                packed.append(codes)
                            body[32]=np.asarray(packed,dtype='<u2').reshape((-1,3))
                        encoded.append((kind,mi,ci,encode(body)))
                        held=bool(arrays[holdid][ci]);rows.append(identity_row(kind,mi,ci,mid,record,held))
                        if kind=='P':
                            P_seen+=1;candidate=dict(role=role,molecule_index=mi,conformer_index=ci,identity=record['identity'],
                              qa_sources=[x for x in item.get('qa_sources',[])if x['kind']=='labels']+record['qa_sources'])
                            if len(sample)<1000:sample.append(candidate)
                            else:
                                take=rng.randrange(P_seen)
                                if take<1000:sample[take]=candidate
                writers[role].put_many(encoded);maps[role].append(rows)
                counts.update(P=len(p_records),U=len(u_records));topology.extend(item.get('topology_differences',[]));total+=1
            save(progress,dict(phase='EXPORT',molecules=total,expected=55000,counts=dict(counts),roles=dict(indices),elapsed_seconds=time.monotonic()-started))
            try:pending.append(pool.submit(work,next(iterator)))
            except StopIteration:pass
    finally:
        pool.shutdown(wait=True,cancel_futures=True)
        for writer in writers.values():writer.close()
        for table in maps.values():table.close()
    export_seconds=time.monotonic()-started
    # Exactly one compact copy per split, into the fresh shared final directories.
    for role in writers:
        target=root/('v31_pilot_'+role)
        target.rmdir();compact_once(scratch/role,target)
    save(root/'schema.json',schema)
    if topology:
        import pyarrow as pa,pyarrow.parquet as pq
        pq.write_table(pa.Table.from_pylist(topology),root/'topology_differences.parquet',compression=None)
    # The sole final check suite: accumulated alignment, 1000 original-v30 P records, counts.
    from .verify import verify_samples
    roots={r:str(root/('v31_pilot_'+r))for r in writers}
    numerical=verify_samples(sample,roots,schema)
    assert dict(indices)=={'TRAIN':50000,'VAL':5000} and total==len(mids_seen)==55000
    assert counts['P']==expected_source['pm7'] and counts['U']==expected_source['uff_sprime'],(counts,expected_source)
    import lmdb
    for role in writers:
        with lmdb.open(roots[role],readonly=True,create=False,lock=False,subdir=True)as env:
            assert env.stat()['entries']==sum(writers[role].count.values())==maps[role].rows
    for role in writers:
        w=writers[role]
        os.rename(root/('id_map_'+role+'.parquet'),root/('v31_pilot_'+role)/'id_map.parquet')
        save(root/('v31_pilot_'+role)/'manifest.json',dict(version='v3.1',data_version='v1-pilot-provisional',role=role,
          molecule_count=indices[role],records=dict(w.count),record_key_value_bytes=dict(w.bytes),
          mean_record_key_value_bytes={k:w.bytes[k]/w.count[k]for k in w.count},
          LMDB_directory='v31_pilot_'+role,schema='../schema.json',ID_mapping='id_map.parquet',
          default_database_only=True,content_hashes_computed=False,compact_copy_performed_once=True,
          numeric_check=numerical,topology_difference_count=len(topology),code_commit=plan['code_commit'],
          input_D3_reference=plan['D3_index_reference'],input_D5_reference=plan['D5_index_reference'],
          D6=False,Model_payload_ACK=False,export_seconds=export_seconds))
    save(progress,dict(phase='COPY',molecules=total,counts=dict(counts),numeric_check=numerical))
    transfers=[];remaining=list(plan['gpu_nodes'])
    while remaining:
        deferred=[]
        for node in remaining:
            destination=plan['node_destination_root']
            try:
                subprocess.run(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=15',node,'test "$(id -u)" = 1278 && mkdir -p '+destination],check=True,timeout=90)
                subprocess.run(['rsync','-a','--sparse','--protect-args','-e','ssh -o BatchMode=yes -o ConnectTimeout=15',str(root)+'/',node+':'+destination+'/'],check=True,timeout=1800)
                transfers.append(dict(node=node,directory=destination,status='RSYNC_SPARSE_COMPLETED'))
            except(subprocess.CalledProcessError,subprocess.TimeoutExpired)as error:
                deferred.append(node);save(progress,dict(phase='WAIT_NODE_COPY',node=node,error=str(error),completed=transfers,remaining=deferred))
        remaining=deferred
        if remaining:time.sleep(60)
    logical=sum(p.stat().st_size for p in root.rglob('*')if p.is_file());allocated=du(root)
    summary=dict(status='D3_V31_EXPORTED_VALIDATED_AND_DISTRIBUTED',shared_root=str(root),roles=dict(indices),
      P_records=counts['P'],U_records=counts['U'],logical_bytes=logical,du_bytes=allocated,export_seconds=export_seconds,
      total_seconds=time.monotonic()-started,mean_record_bytes={k:sum(w.bytes[k]for w in writers.values())/sum(w.count[k]for w in writers.values())for k in ('M','P','U')},
      full_v1_size_extrapolation=dict(basis='LINEAR_MOLECULE_SCALING_DESCRIPTIVE_NOT_CAPACITY_ADMISSION',source_molecules=1220466,estimated_du_bytes=allocated*1220466/55000,old_Common_candidate_molecules=1196122,old_Common_candidate_estimated_du_bytes=allocated*1196122/55000),
      numerical=numerical,topology_differences=len(topology),transfers=transfers,old_v30_preserved=True,Model_payload_ACK=False,D6=False)
    save(progress,summary);print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()