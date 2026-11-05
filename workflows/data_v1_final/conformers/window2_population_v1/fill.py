"""Close S-prime deficits from D7 parts: stop after N consecutive no-new candidates."""
from __future__ import annotations
import argparse
import collections
import concurrent.futures as cf
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import time

from . import d7
from .run import read, info, save


def select_stream(existing, candidates, target, distance):
    """Fixed generation-order acceptance, exactly the taskbook's N-no-new stop."""
    chosen=list(existing);stale=0;consumed=0
    for row in candidates:
        if len(chosen)>=target:break
        consumed+=1
        good=row is not None and row.get('valid',True)
        if good:
            values=[distance(row,old) for old in chosen]
            if any(not math.isfinite(value) or value<0 for value in values):
                raise ValueError('NONFINITE_CANDIDATE_RMSD')
            good=all(value>=0.5 for value in values)
        if good:
            chosen.append(row);stale=0
        else:
            stale+=1
        if stale>=target:break
    return chosen,stale,consumed


def seed_for(mid):
    # This is the original scientific random-seed recipe, not a content hash.
    value=int.from_bytes(hashlib.sha256(('sprime-ETKDGv3-v1:'+mid).encode()).digest()[:4],'big')
    return max(value&0x7fffffff,1)


def fill_one(task):
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import AllChem, rdtrajectory
    science=d7.SCIENCE
    meta,stats=task['meta'],task['d7']
    mid=meta['molecule_id'];target=int(meta['S_conformers'])
    kept=json.loads(stats['sprime_unique_ids_json']) if stats.get('sprime_unique_ids_json') else []
    base={'molecule_id':mid,'target_N':target,'kept_original_sprime_ids':kept,
        'final_unique_count':len(kept),'new_conformers':[],'generated_candidates':0,
        'optimized_candidates':0,'consecutive_no_new':0,'source_valid':True,
        'source_fill_status':meta.get('fill_status'),'effective_role':meta['effective_role'],
        'status':'ALREADY_COMPLETE','insufficient':len(kept)<target,'error':None}
    if stats['status']!='COMPLETE':
        return dict(base,status='EXECUTION_UNRESOLVED',source_valid=False,error=stats.get('error'))
    if meta['Sprime_status']=='UFF_UNSUPPORTED':
        return dict(base,status='UFF_UNSUPPORTED',insufficient=True)
    if len(kept)>=target:return base
    pointers=sorted(task['records'],key=lambda row:row['record_id'])
    raw=[d7.native(row) for row in pointers]
    energies=[float(science.plain(science.field(item,'energy')).reshape(-1)[0])
        if science.field(item,'energy') is not None else float('inf') for item in raw]
    if not any(math.isfinite(value) for value in energies):
        raise ValueError('PM7_MINIMUM_ENERGY_MISSING')
    lowest=min(range(len(raw)),key=lambda i:(energies[i],pointers[i]['record_id']))
    mol,numbers,xyz=science.graph(raw[lowest]);signature=science.ordered_graph(mol)
    for item in raw:
        other,z,_=science.graph(item)
        if not np.array_equal(z,numbers) or science.ordered_graph(other)!=signature:
            raise ValueError('SOURCE_ATOM_ORDER_OR_GRAPH_MISMATCH')
    stereo_source,stereo_signature=science.fix_stereo(mol,str(science.field(raw[lowest],'smiles')))
    if not AllChem.UFFHasAllMoleculeParams(mol):
        return dict(base,status='UFF_UNSUPPORTED',insufficient=True)
    byid={row['sprime_conf_idx']:row for row in task['uff']}
    if not set(kept)<=set(byid):raise ValueError('D7_KEEP_IDS_NOT_IN_ACTUAL_SPRIME_SOURCE')
    chosen=[dict(byid[key],valid=True) for key in kept]
    distance=lambda left,right:science.rmsd(mol,left['coordinates'],right['coordinates'])
    seed=seed_for(mid);params=AllChem.ETKDGv3()
    params.randomSeed=seed;params.numThreads=1;params.enforceChirality=True
    params.pruneRmsThresh=-1.;params.maxIterations=200;params.useRandomCoords=False
    # Recreating a growing prefix with the same fixed seed preserves the exact
    # original native candidate stream. UFF is called only on new suffix IDs.
    generated_prefix=[];processed=0;requested=target;stale=0
    new=[];source_record=pointers[lowest]['record_id']
    next_idx=max([row['sprime_conf_idx'] for row in task['uff']]+[target-1,task.get('max_original_attempt_idx',-1)])+1
    while len(chosen)<target and stale<target:
        mol.RemoveAllConformers()
        try:ids=list(AllChem.EmbedMultipleConfs(mol,numConfs=requested,params=params))
        except (RuntimeError,ValueError):ids=[]
        if not ids and processed==0 and not params.useRandomCoords:
            params.useRandomCoords=True
            ids=list(AllChem.EmbedMultipleConfs(mol,numConfs=requested,params=params))
        original=[np.asarray(mol.GetConformer(cid).GetPositions(),dtype=np.float64).copy() for cid in ids]
        if len(ids)<processed or any(not np.allclose(original[i],old,atol=1e-12,rtol=1e-12)
            for i,old in enumerate(generated_prefix)):
            raise ValueError('FIXED_SEED_NATIVE_CANDIDATE_PREFIX_CHANGED')
        for ordinal in range(processed,len(ids)):
            cid=ids[ordinal];base['generated_candidates']+=1
            candidate=None
            try:
                field=AllChem.UFFGetMoleculeForceField(mol,confId=cid)
                code,trajectory=field.MinimizeTrajectory(snapshotFreq=1,maxIts=2000,energyTol=1e-6,forceTol=1e-4)
                base['optimized_candidates']+=1
                coordinates=np.asarray(mol.GetConformer(cid).GetPositions(),dtype=np.float64)
                energy=float(field.CalcEnergy())
                good=code==0 and np.isfinite(coordinates).all() and math.isfinite(energy) and science.check_geometry_stereo(mol,cid)
                if good:
                    candidate={'molecule_id':mid,'sprime_conf_idx':next_idx,'geometry_source':'uff_sprime',
                        'atomic_numbers':numbers.tolist(),'coordinates':coordinates.tolist(),
                        'uff_energy_kcal_mol':energy,'status':'SUCCESS','converged':True,
                        'iterations':len(trajectory),'seed':seed,'candidate_id':ordinal,
                        'source_record_id':source_record,'stereo_source':stereo_source,
                        'stereo_signature':stereo_signature,'origin':'v1_window2_N_no_new',
                        'ordinary_sprime_member':True,'below_dedup_threshold':False,'valid':True}
            except (RuntimeError,ValueError) as exc:
                base['last_candidate_error']=repr(exc)
            selected,new_stale,_=select_stream(chosen,[candidate],target,distance)
            # select_stream's single-item stale is combined with the ongoing
            # native stream; a newly retained geometry resets the counter.
            if len(selected)>len(chosen):
                chosen=selected;stale=0;new.append(candidate);next_idx+=1
            else:stale+=new_stale
            if len(chosen)>=target or stale>=target:break
        if len(chosen)>=target or stale>=target:break
        missing=max(0,requested-len(ids))
        base['generated_candidates']+=missing;stale=min(target,stale+missing)
        if stale>=target:break
        generated_prefix=original;processed=len(ids);requested+=target
    base.update(status='COMPLETE' if len(chosen)>=target else 'EXHAUSTED_N_NO_NEW',
        final_unique_count=len(chosen),new_conformers=new,consecutive_no_new=stale,
        insufficient=len(chosen)<target,seed=seed,source_record_id=source_record)
    return base


def safe_fill(task):
    try:return fill_one(task)
    except Exception as exc:
        return {'molecule_id':task['meta']['molecule_id'],'target_N':task['meta']['S_conformers'],
            'effective_role':task['meta']['effective_role'],'status':'EXECUTION_UNRESOLVED',
            'source_valid':False,'source_fill_status':task['meta'].get('fill_status'),
            'kept_original_sprime_ids':[],'final_unique_count':None,'new_conformers':[],
            'generated_candidates':0,'optimized_candidates':0,'consecutive_no_new':0,
            'insufficient':None,'error':repr(exc)}


def run(plan):
    import pyarrow as pa
    import pyarrow.parquet as pq
    out=Path(plan['output']);out.mkdir(parents=True,exist_ok=True)
    d7plan=read(plan['d7_plan']);d7plan.update(workspace=plan['workspace'],output=plan['output'],workers=plan['workers'])
    db,common=d7.prepare(d7plan,plan['workspace'])
    checkpoint=out/'checkpoint.json';done=read(checkpoint) if checkpoint.exists() else {'parts':[]}
    parts=list(done['parts']);finished={row['part'] for row in parts}
    d7root=Path(read(plan['d7_plan'])['output'])
    bounds=dict(db.execute('SELECT molecule_id,max(sprime_conf_idx) FROM baseline GROUP BY molecule_id').fetchall())
    with cf.ProcessPoolExecutor(max_workers=plan['workers'],mp_context=mp.get_context('spawn'),initializer=d7.initialize,
        initargs=(d7plan['science_path'],)) as pool:
        while True:
            available=read(d7root/'checkpoint.json')['parts'] if (d7root/'checkpoint.json').exists() else []
            for part in available:
                ordinal=part['part']
                if ordinal in finished:continue
                statistics=pq.read_table(part['path']).to_pylist()
                mids=[row['molecule_id'] for row in statistics]
                db.register('batch',pa.table({'molecule_id':mids}))
                metas=db.execute('SELECT m.* FROM members m JOIN batch USING(molecule_id)').fetch_arrow_table().to_pylist();db.unregister('batch')
                jobs=d7.tasks(db,metas);byid={row['molecule_id']:row for row in statistics}
                for job in jobs:
                    job['d7']=byid[job['meta']['molecule_id']]
                    job['max_original_attempt_idx']=bounds.get(job['meta']['molecule_id'],-1)
                values=list(pool.map(safe_fill,jobs,chunksize=4))
                newrows=[row for value in values for row in value.pop('new_conformers')]
                path=out/('states-%06d.parquet'%ordinal)
                pq.write_table(pa.Table.from_pylist(values),path,compression='zstd')
                record={'part':ordinal,'states':info(path,len(values)),'new_geometry':None}
                if newrows:
                    geom=out/('geometry-%06d.parquet'%ordinal)
                    pq.write_table(pa.Table.from_pylist(newrows),geom,compression='zstd')
                    record['new_geometry']=info(geom,len(newrows))
                parts.append(record);finished.add(ordinal)
                temporary=out/'checkpoint.next.json';temporary.write_text(json.dumps({'parts':parts}),encoding='utf-8');os.replace(temporary,checkpoint)
                print(json.dumps({'stage':'Sprime_N_no_new','closed_parts':len(parts),
                    'molecules':sum(row['states']['records'] for row in parts),'new_conformers':len(newrows)}),flush=True)
            if (d7root/'manifest.json').exists() and len(finished)==len(available):break
            time.sleep(30)
    db.close()
    counts=collections.Counter();total=0
    for part in parts:
        for row in pq.read_table(part['states']['path'],columns=['status']).column('status').to_pylist():counts[row]+=1;total+=1
    save(out/'manifest.json',{'schema':'SPRIME_N_NO_NEW_FINAL_V1','status':'COMPLETE' if not counts['EXECUTION_UNRESOLVED'] else 'PARTIAL_WITH_EXPLICIT_UNRESOLVED',
        'parts':parts,'molecules':total,'status_counts':dict(counts),'input_common':plan['common'],
        'preserve_source_atom_order':True,'stop_rule':'N consecutive candidates with no new >=0.5A conformer',
        'force_duplicate_fill':False,'content_hashes_computed':False})


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True)
    args=parser.parse_args();run(read(args.plan))


if __name__=='__main__':main()