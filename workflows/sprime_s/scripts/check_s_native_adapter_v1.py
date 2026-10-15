"""Validate adapter under a provisional historical interface; no model training."""
from __future__ import annotations
import concurrent.futures as cf
import hashlib,json,multiprocessing as mp,os,pickle,random,socket,time
from pathlib import Path
import numpy as np,torch
from prepare import ROOT,PROJECT,POP,save,sha
from s_native_adapter_v1 import MappedRecordIndex,ManifestViewsDataset,CountIndex,identity
from phychem_mfm.phase1.full_corpus_loader import _length_header,_load_bound_native_transport,NATIVE_TRANSPORT_POLICY,BlockAtomBatchSampler

CANDIDATE=PROJECT/'docs/phase1/evidence/stage59_three_epoch_protocol_v1/actual_scientific_freeze_v1/phase1_three_epoch_scientific_protocol.json'

def init():
    torch.set_num_threads(1);torch.set_num_interop_threads(1)

def snapshot_shard(row):
    import lmdb
    sid,source=row;path=Path(source)
    if not path.is_absolute():path=PROJECT/path
    before=identity(path)
    with lmdb.open(str(path),subdir=False,readonly=True,create=False,lock=False,readahead=False,meminit=False) as env:
        with env.begin() as tx:
            header=tx.get(b'__len__');length=_length_header(header);entries=tx.stat()['entries']
        last=env.info()['last_txnid']
    assert identity(path)==before
    return str(sid),{'path':str(path),'declared_source_path':source,'name':path.name,'identity':list(before),
                    'length':length,'length_header_sha256':hashlib.sha256(header).hexdigest(),'entries':entries,'last_txnid':last}

def check_views(task):
    role,indices,transport,snapshot,view_params=task
    transport_path=Path(transport['path']);binding={'policy':NATIVE_TRANSPORT_POLICY,'source_sha256':transport['sha256']}
    function=_load_bound_native_transport(transport_path,binding,identity(transport_path))
    index=MappedRecordIndex(role,binding,snapshot,verify_hashes=False)
    dataset=ManifestViewsDataset(index,native_transport=function,native_transport_binding=binding,
        seed=0,geometry_level=view_params['geometry_level'],topology_level=view_params['topology_level'],
        cache_bytes=64<<20,max_cache_entries=256,max_handles=2,close_at_block_size=4096,max_record_bytes=64<<20)
    result=[]
    try:
        for logical in indices:
            ref=index.ref(logical);first=dataset[logical];second=dataset[logical]
            assert first.logical_index==logical and first.record_key==ref.record_id and len(first.views)==3
            with dataset._handles.get(ref.shard_id).begin() as tx:raw=tx.get(f'{ref.real_index:09d}'.encode())
            item=pickle.loads(raw);get=lambda key:item.get(key) if isinstance(item,dict) else getattr(item,key)
            native_x=get('x').reshape(-1,1);native_pos=get('pos')
            for ordinal,(a,b) in enumerate(zip(first.views,second.views)):
                assert a.sample_type_id.item()==ordinal and a.target_pos.shape==(ref.native_n_atoms,3)
                assert torch.equal(a.target_x,native_x) and torch.equal(a.target_pos,native_pos),'ATOM_ORDER_OR_TARGET_CHANGED'
                assert torch.equal(a.x,b.x) and torch.equal(a.pos,b.pos) and torch.equal(a.element_corrupt_mask,b.element_corrupt_mask),'NONDETERMINISTIC_VIEW'
                assert torch.equal(a.x.ne(native_x).any(dim=1),a.element_corrupt_mask.view(-1))
            assert torch.equal(first.views[0].x,native_x) and torch.equal(first.views[0].pos,native_pos)
            result.append({'role':role,'logical_index':logical,'record_id':ref.record_id,'molecule_id':ref.molecule_id,
                           'native_n_atoms':ref.native_n_atoms,'payload_sha256':ref.payload_sha256,'three_views':'PASS','same_seed':'PASS','atom_order':'PASS'})
    finally:dataset.close()
    return result

def check_sampler_block(task):
    lo,hi,role,binding,snapshot,params=task
    index=MappedRecordIndex(role,binding,snapshot,verify_hashes=False);count_index=CountIndex(index)
    sampler=BlockAtomBatchSampler(count_index,seed=0,epoch=0,**params)
    batches=0;indices=[];maximum_padded=0;maximum_native=0
    try:
        for block in range(lo,hi):
            cursor=(block,0)
            while cursor[0]==block:
                batch,cursor=sampler._next(cursor);assert batch
                sizes=[count_index.ref(i).native_n_atoms for i in batch]
                padded=params['padded_cost_multiplier']*len(batch)*max(sizes)**2
                assert len(batch)<=params['max_molecules']
                assert len(batch)==1 or (sum(sizes)<=params['max_native_atoms'] and padded<=params['max_padded_cost'])
                indices.extend(batch);batches+=1;maximum_padded=max(maximum_padded,padded);maximum_native=max(maximum_native,sum(sizes))
    finally:index.close();count_index.close()
    return np.asarray(indices,dtype='<u4'),batches,maximum_padded,maximum_native

def main():
    import duckdb
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    init();start=time.time();cfg=json.loads(CANDIDATE.read_text())
    assert sha(CANDIDATE)=='cde2ca717934955f340a5f160a3390ff1dd6eda12c9ffbab93fc54fce0c8a2a4'
    transport=cfg['draft_provenance']['runner_artifacts']['native_transport']
    assert sha(transport['path'])==transport['sha256'] and Path(transport['path']).stat().st_size==transport['bytes']
    binding={'policy':NATIVE_TRANSPORT_POLICY,'source_sha256':transport['sha256']}
    db=duckdb.connect();db.execute('SET threads=16');db.execute("SET memory_limit='20GB'")
    shards=db.execute(f"SELECT DISTINCT shard_id,source_path FROM read_parquet('{POP/'formal_record_index.parquet'}') ORDER BY shard_id").fetchall();db.close()
    assert len(set(sid for sid,path in shards))==len(shards)
    context=mp.get_context('spawn')
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=init) as pool:
        snapshot={'status':'READ_ONLY_NATIVE_SHARD_SNAPSHOT','shards':dict(pool.map(snapshot_shard,shards))}
        save(ROOT/'training_inputs_v1/shard_snapshot_v1.json',snapshot)
        tasks=[]
        for role in ['train','full','routine']:
            index=MappedRecordIndex(role,binding,snapshot,verify_hashes=True);index._open()
            selected=sorted(set([0,len(index)-1,int(np.argmax(index._atoms)),*random.Random(911).sample(range(len(index)),32)]));index.close()
            tasks.extend((role,selected[i:i+3],transport,snapshot,cfg['views']) for i in range(0,len(selected),3))
        reads=[r for group in pool.map(check_views,tasks) for r in group]
        index=MappedRecordIndex('train',binding,snapshot,verify_hashes=False);count_index=CountIndex(index)
        params=cfg['sampler'];sampler=BlockAtomBatchSampler(count_index,seed=0,epoch=0,**params)
        tasks=[(lo,min(lo+64,sampler.n_blocks),'train',binding,snapshot,params) for lo in range(0,sampler.n_blocks,64)]
        visit=np.zeros(len(index),dtype=np.uint8);records=batches=max_padded=max_native=0
        for ids,n,padded,native in pool.map(check_sampler_block,tasks):
            assert len(np.unique(ids))==len(ids) and not np.any(visit[ids])
            visit[ids]=1;records+=len(ids);batches+=n;max_padded=max(max_padded,padded);max_native=max(max_native,native)
        assert records==11104772 and bool(np.all(visit))
        index.verify_unchanged();index.close();count_index.close()
    save(ROOT/'reports/s_native_adapter_check_v1.json',{'status':'INPUT_ADAPTER_ONLY_PASS','job_id':os.environ['SLURM_JOB_ID'],
        'hostname':socket.gethostname(),'effective_processes':16,'input_manifest_sha256':sha(ROOT/'training_inputs_v1/manifest.json'),
        'shard_snapshot_sha256':sha(ROOT/'training_inputs_v1/shard_snapshot_v1.json'),
        'candidate_interface_protocol':{'path':str(CANDIDATE),'sha256':sha(CANDIDATE),'selected_for_B_training':False},
        'native_transport_sha256':transport['sha256'],'sampled_view_records':len(reads),'sample_checks':reads,
        'metadata_sampler_one_pass':{'distinct_record_positions':records,'duplicates':0,'missing':0,'batches':batches,
            'maximum_padded_cost':max_padded,'maximum_native_atoms':max_native,'provisional_sampler':params},
        'all_training_records_actually_read':False,'optimizer_updates':0,'model_training_started':False,
        'original_lmdb_written':False,'new_lmdb_created':False,'elapsed_seconds':time.time()-start})
    print(json.dumps({'status':'INPUT_ADAPTER_ONLY_PASS','sampled_view_records':len(reads),'sampler_record_positions':records,'batches':batches}),flush=True)

if __name__=='__main__':main()
