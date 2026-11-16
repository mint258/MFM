"""D1 one-pass current-F32 means; one producer-owned actual-read check of1000MIDs."""
import argparse,concurrent.futures as cf,csv,json,os,pathlib,time
import numpy as np
import pyarrow.parquet as pq
from resources import REPO,R,CONTROL,MEAN,load,save,guard
from decomposition_math import molecular_moments,TrainMoments
from phychem_mfm.phase1.p_recipe_data import PRecipeDataset,dataset_configuration,train_indices
from phychem_mfm.phase1.v31_loader import decode_mfm4,record_key,split_metadata
from phychem_mfm.phase1.v31_training import element_offset

DATA=None;NAMES=None;CHECK=None

def init_worker(c,split,view,names,check):
    global DATA,NAMES,CHECK
    DATA=PRecipeDataset(c['root'],split=split,training_view=view,
        normalizations=load(c['normalizations']),label_parameters=c['label_parameters'],source='PM7',k=10)
    NAMES=names;CHECK=set(check)

def chunk(indices):
    means=[];counts=[];within=[];checks=[]
    specs={f['name']:f.get('normalization',DATA.view.normalizations[f['name']]) for f in DATA.view.fields}
    for index in indices:
        mi=int(index);m=DATA.record('M',mi);choices=DATA.choices(mi)
        offsets=np.array([element_offset(m[1],specs[n]) for n in NAMES])
        rows=[]
        DATA._open()
        with DATA._env.begin(buffers=True) as tx:
            for ci in choices:
                payload=tx.get(record_key('P',mi,int(ci)))
                if payload is None:raise KeyError(('P',mi,int(ci)))
                targets=DATA.view.extract(m,decode_mfm4(payload,array_ids={23}),
                    mask_overrides=DATA._record_masks.get((mi,int(ci))),raw_only=True)
                rows.append([float(targets[n].raw.flat[0]) if n in targets and targets[n].valid.all() else np.nan for n in NAMES])
        mean,count,ss=molecular_moments(np.asarray(rows,np.float64).reshape(-1,len(NAMES))-offsets)
        if mi in CHECK:
            actual=[]
            for ci in choices:
                sample=DATA.read(mi,int(ci))
                actual.append([float(sample['targets'][n].raw.flat[0])-offsets[j]
                    if n in sample['targets'] and sample['targets'][n].valid.all() else np.nan for j,n in enumerate(NAMES)])
            reference,reference_count,_=molecular_moments(np.asarray(actual,np.float64).reshape(-1,len(NAMES)))
            if not np.array_equal(count,reference_count) or not np.array_equal(np.isnan(mean),np.isnan(reference)):
                raise ValueError(('D1 actual-read valid/identity mismatch',mi))
            error=np.abs(mean-reference);bound=1e-9+1e-9*np.abs(reference)
            if np.any(error>bound):raise ValueError(('D1 actual-read mean mismatch',mi,float(np.nanmax(error))))
            checks.append(dict(molecule_index=mi,valid_fields=int(np.isfinite(mean).sum()),max_absolute_error=float(np.nanmax(error)) if np.isfinite(error).any() else None))
        means.append(mean);counts.append(count);within.append(ss)
    DATA._molecules.clear()
    return np.asarray(indices),np.asarray(means),np.asarray(counts,np.uint8),np.asarray(within),checks

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);a=parser.parse_args()
    if not 1<=a.workers<=16:raise ValueError('D1 permits at most16CPU')
    guard(force=True);c=load(REPO/'configs/p_followup/C_dedup.json')
    if c.get('p_f64_sidecar'):raise ValueError('D uses current F32, sidecar off')
    if c['p_recipe']!={**{'element_residual':True},'excluded_fields':c['p_recipe']['excluded_fields']}:raise ValueError('D baseline is C with A1 only')
    original=load(c['training_view']);excluded=set(c['p_recipe']['excluded_fields'])
    dataset=PRecipeDataset(**dataset_configuration(c))
    fields=[f for f in dataset.view.fields if f['group']=='P' and f['level']=='molecule' and f.get('representation','scalar')=='scalar' and f.get('loss_enabled',True) and f['name'] not in excluded]
    names=[f['name'] for f in fields];assert len(names)==33
    selected=set(names);view=dict(original,fields=[f for f in original['fields'] if f.get('name',f.get('field_key')) in selected])
    effective={f['name']:f.get('normalization',dataset.view.normalizations[f['name']]) for f in fields};dataset.close()
    eligibility=set(map(int,train_indices(c)));errors={v['field']:v['median_abs_error'] for v in load(REPO/'results/p_followup/B_field_selection.json')['fields']}
    directories={};sizes={}
    for split in ['TRAIN','FULL']:
        directory,meta=split_metadata(c['root'],split);directories[split]=directory;sizes[split]=meta['molecule_count']
    total=sum(sizes.values());chosen=np.random.default_rng(20261025).choice(total,1000,replace=False)
    checks={};offset=0
    for split,n in sizes.items():checks[split]=(chosen[(chosen>=offset)&(chosen<offset+n)]-offset).tolist();offset+=n
    fit=TrainMoments(len(names));all_checks=[];splits={};started=time.monotonic();done=0;reported=False
    MEAN.mkdir(parents=True,exist_ok=True)
    if (MEAN/'manifest.json').exists():raise FileExistsError('Completed D1 exists; do not rerun producer')
    for split,n in sizes.items():
        guard(force=True);out=MEAN/split;out.mkdir(exist_ok=True)
        paths={key:out/(key+'.npy') for key in ['means','counts','molecule_ids']}
        means=np.lib.format.open_memmap(paths['means'],mode='w+',dtype='<f8',shape=(n,len(names)));means[:]=np.nan
        counts=np.lib.format.open_memmap(paths['counts'],mode='w+',dtype='u1',shape=(n,len(names)));counts[:]=0
        mids=np.lib.format.open_memmap(paths['molecule_ids'],mode='w+',dtype='S64',shape=(n,))
        table=pq.read_table(directories[split]/'id_map.parquet',columns=['molecule_index','molecule_id'],filters=[('record_kind','=','M')],use_threads=False)
        rows=table.to_pydict();ix=np.asarray(rows['molecule_index']);assert np.array_equal(ix,np.arange(n))
        if any(len(v.encode())>64 for v in rows['molecule_id']):raise ValueError('MID exceeds reserved width')
        mids[:]=np.asarray(rows['molecule_id'],dtype='S64');mids.flush();del table,rows,ix
        with cf.ProcessPoolExecutor(a.workers,initializer=init_worker,initargs=(c,split,view,names,checks[split])) as pool:
            pending={};cursor=0
            while cursor<n or pending:
                while cursor<n and len(pending)<2*a.workers:
                    end=min(cursor+512,n);future=pool.submit(chunk,list(range(cursor,end)));pending[future]=cursor;cursor=end
                ready,_=cf.wait(pending,return_when=cf.FIRST_COMPLETED)
                for future in ready:
                    ix,mu,k,ss,verified=future.result();pending.pop(future)
                    guard();means[ix]=mu;counts[ix]=k;all_checks.extend([dict(split=split,**v) for v in verified])
                    if split=='TRAIN':
                        keep=np.asarray([int(i) in eligibility for i in ix]);fit.add(mu[keep],k[keep],ss[keep])
                    done+=len(ix)
                    if done//10000!=(done-len(ix))//10000:
                        means.flush();counts.flush();print('D1_PROGRESS',split,done,total,'seconds',time.monotonic()-started,flush=True)
                    if not reported and done>=total*.01:
                        elapsed=time.monotonic()-started;print('D1_ONE_PERCENT',dict(molecules=done,seconds=elapsed,molecules_per_second=done/elapsed,remaining_hours=(total-done)*elapsed/done/3600),flush=True);reported=True
        means.flush();counts.flush();del means,counts,mids
        splits[split]=dict(directory=str(directories[split]),molecules=n,**{k:str(p) for k,p in paths.items()})
    for split,n in sizes.items():
        guard(force=True);directory=MEAN/split;directory.mkdir(exist_ok=True)
        ids=directory/'molecule_ids.npy';mu=directory/'means.npy';cnt=directory/'valid_counts.npy'
        identities=pq.read_table(directories[split]/'id_map.parquet',columns=['molecule_index','molecule_id'],filters=[('record_kind','=','M')],use_threads=False)
        indices=identities['molecule_index'].to_numpy();assert np.array_equal(indices,np.arange(n))
        mids=identities['molecule_id'].to_pylist()
        if any(len(v.encode())>64 for v in mids):raise ValueError('MID exceeds declared storage width')
        np.save(ids,np.asarray(mids,dtype='S64'));del identities,mids
        means=np.lib.format.open_memmap(mu,mode='w+',dtype='<f8',shape=(n,len(names)))
        counts=np.lib.format.open_memmap(cnt,mode='w+',dtype='u1',shape=(n,len(names)))
        pending=set();chunks=iter([indices[i:i+1024] for i in range(0,n,1024)])
        split_started=time.monotonic()
        with cf.ProcessPoolExecutor(max_workers=a.workers,initializer=init_worker,initargs=(c,split,view,names,checks[split])) as executor:
            for _ in range(a.workers*2):
                part=next(chunks,None)
                if part is not None:pending.add(executor.submit(chunk,part))
            while pending:
                finished,pending=cf.wait(pending,return_when=cf.FIRST_COMPLETED)
                for future in finished:
                    index,mean,count,within,verified=future.result();guard()
                    means[index]=mean;counts[index]=count;all_checks.extend(dict(split=split,**r) for r in verified)
                    if split=='TRAIN':
                        good=np.fromiter((int(i) in eligibility for i in index),bool,len(index))
                        fit.add(mean[good],count[good],within[good])
                    done+=len(index)
                    if done>=max(1,int(.01*total)) and not reported:
                        elapsed=time.monotonic()-started
                        print('D1_FIRST_PERCENT',dict(molecules=done,total=total,seconds=elapsed,eta_seconds=elapsed/done*(total-done)),flush=True);reported=True
                    if done%10240<1024:means.flush();counts.flush();print('D1_PROGRESS',split,done,total,time.monotonic()-started,flush=True)
                    part=next(chunks,None)
                    if part is not None:pending.add(executor.submit(chunk,part))
        means.flush();counts.flush();del means,counts
        splits[split]=dict(directory=str(directories[split]),molecules=n,means=str(mu),valid_counts=str(cnt),molecule_ids=str(ids),seconds=time.monotonic()-split_started)
    assert len(all_checks)==1000
    result=fit.result(len(eligibility),errors,names);chosen=[name for name in names if result[name]['selected']]
    params=dict(status='D1_COMPLETE',candidate_fields=names,selected_fields=chosen,fields=result,
        normalizations=effective,source='current F32 promoted to F64; sidecar disabled',fit_train_molecules=len(eligibility),splits=splits,
        actual_read_check=dict(molecules=1000,seed=20261025,absolute_tolerance=1e-9,relative_tolerance=1e-9,results=all_checks),seconds=time.monotonic()-started,workers=a.workers)
    save(MEAN/'manifest.json',params);save(REPO/'configs/p_followup/D_parameters.json',dict(params,actual_read_check={k:v for k,v in params['actual_read_check'].items() if k!='results'}))
    rows=[dict(field=n,**v) for n,v in result.items()];path=REPO/'results/p_followup/D_field_selection.csv'
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print('D1_COMPLETE',dict(selected_fields=chosen,seconds=params['seconds'],check_molecules=1000),flush=True)
if __name__=='__main__':main()