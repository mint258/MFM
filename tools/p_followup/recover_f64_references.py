"""Recover the four F32 comparison columns for completed B1 staging, without rewriting it."""
import argparse,collections,concurrent.futures as cf,multiprocessing,os,pathlib,time
import lmdb
import numpy as np
from resources import REPO,CONTROL,SIDE,load,save,guard
from phychem_mfm.phase1.p_f64_sidecar import record_handle_equal
from phychem_mfm.phase1.v31_loader import MFM4Dataset,decode_mfm4,record_key,split_metadata
CACHE=CONTROL/'B1_F32_reference_cache'


def recover_range(task):
    kind,lo,hi=task;labels=collections.Counter();carrying=0;done=0
    DATA._env=lmdb.open(str(DATA.directory),readonly=True,lock=False,readahead=True,max_readers=512);DATA._pid=os.getpid()
    with DATA._env.begin(buffers=True) as tx:
        for mi in range(lo,hi):
            start,end=map(int,OFFSETS[mi:mi+2]);rows=range(start,end)
            selected=sorted((r for r in rows if bytes(TABLE[r]['record_handle'])[:1]==kind.encode()),key=lambda r:int(TABLE[r]['conformer_index']))
            for row in selected:
                ci=int(TABLE[row]['conformer_index']);handle=record_key(kind,mi,ci)
                if int(TABLE[row]['molecule_index'])!=mi or not record_handle_equal(TABLE[row]['record_handle'],handle):raise ValueError('Recovered F32 row/handle differs')
                payload=tx.get(handle)
                if payload is None:raise KeyError((kind,mi,ci))
                target=DATA.view.extract({1:np.empty(0,np.int16)},decode_mfm4(payload,array_ids={23}),
                    mask_overrides=(DATA._record_masks if kind=='P' else PRIME).get((mi,ci)),raw_only=True)
                present=False
                for j,name in enumerate(NAMES):
                    t=target.get(name)
                    if t is not None and t.valid.all() and np.isfinite(t.raw).all():REF[row,j]=t.raw.flat[0];labels[kind]+=1;present=True
                carrying+=int(present);done+=1
            if mi%10000==0:REF.flush();guard();print('B1_F32_CACHE_RANGE',kind,lo,hi,mi,done,flush=True)
    REF.flush();DATA.close();return dict(kind=kind,records=done,carrying=carrying,labels=dict(labels))


def main():
    global DATA,TABLE,REF,OFFSETS,PRIME,NAMES
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    guard(force=True);started=time.monotonic();CACHE.mkdir(exist_ok=True)
    if (CACHE/'manifest.json').exists():raise FileExistsError('Complete F32 recovery cache already exists')
    c=load(REPO/'configs/p_followup/C_dedup.json');NAMES=load(REPO/'results/p_followup/B_field_selection.json')['selected_fields']
    manifest=load(pathlib.Path(c['root'])/'manifest.json');splits={};all_carrying=0
    for split in ['TRAIN','FULL']:
        directory,meta=split_metadata(pathlib.Path(c['root']),split);count=manifest['conformers'][split+'_P']+manifest['conformers'][split+'_U']
        TABLE=np.load(SIDE/split/'values.npy',mmap_mode='r');OFFSETS=np.load(SIDE/split/'molecule_offsets.npy',mmap_mode='r')
        if len(TABLE)!=count or int(OFFSETS[-1])!=count or len(OFFSETS)!=meta['molecule_count']+1:raise ValueError('B1 completed staging bounds differ')
        path=CACHE/(split+'.npy');REF=np.lib.format.open_memmap(path,mode='w+',dtype='<f4',shape=(count,len(NAMES)));REF[:]=np.nan;REF.flush()
        view=load(c['training_view']);view=dict(view,fields=[f for f in view['fields'] if f.get('name',f.get('field_key')) in NAMES])
        DATA=MFM4Dataset(c['root'],split=split,training_view=view,normalizations=load(c['normalizations']),k=10)
        from phychem_mfm.phase1.v31_record_masks import published_record_masks
        PRIME=published_record_masks(load(c['normalizations']),directory,dataset='Pprime')
        edges=np.linspace(0,meta['molecule_count'],a.workers+1,dtype=np.int64)
        tasks=[(kind,int(lo),int(hi)) for kind in ['P','U'] for lo,hi in zip(edges[:-1],edges[1:])]
        with cf.ProcessPoolExecutor(a.workers,mp_context=multiprocessing.get_context('fork')) as pool:
            pending={pool.submit(recover_range,t) for t in tasks};rows=[]
            try:
                while pending:
                    ready,pending=cf.wait(pending,timeout=5,return_when=cf.FIRST_COMPLETED);guard(force=True)
                    for future in ready:rows.append(future.result())
            except BaseException:
                # Only this producer's own workers write the recovery cache.
                children=list(pool._processes.values())
                for child in children:
                    if child.is_alive():child.terminate()
                for child in children:
                    child.join(timeout=5)
                    if child.is_alive():child.kill();child.join(timeout=5)
                raise
        if sum(r['records'] for r in rows)!=count:raise ValueError('F32 recovery coverage differs')
        labels=collections.Counter()
        for r in rows:labels.update(r['labels'])
        carrying=sum(r['carrying'] for r in rows);all_carrying+=carrying
        splits[split]=dict(D6_directory=str(directory),values=str(SIDE/split/'values.npy'),molecule_offsets=str(SIDE/split/'molecule_offsets.npy'),
            reference_F32=str(path),records=count,records_carrying_selected=carrying,valid_values_by_kind=dict(labels))
        DATA.close();del TABLE,REF,OFFSETS;print('B1_F32_CACHE_SPLIT',split,count,carrying,time.monotonic()-started,flush=True)
    if all_carrying!=13562621:raise ValueError(('Recovery differs from completed original B1 scan',all_carrying))
    save(CACHE/'manifest.json',dict(status='COMPLETE',D6_root=c['root'],fields=NAMES,splits=splits,records_carrying_selected=all_carrying,
        seconds=time.monotonic()-started,workers=a.workers,original_scan_job='4535157',recovery_job=os.environ.get('SLURM_JOB_ID'),sidecar_staging_rewritten=False,source_index_created=False))
    print('B1_F32_CACHE_COMPLETE',all_carrying,time.monotonic()-started,flush=True)
if __name__=='__main__':main()
