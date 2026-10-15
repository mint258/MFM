"""Validate earlier successful SCI under corrected stereo rules; rerun flagged cases."""
import argparse,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,tempfile,time,shutil
from pathlib import Path
import numpy as np
import pyarrow as pa,pyarrow.parquet as pq
from prepare import ROOT,save,sha
import sprime_full_v5 as science

def task_worker(task):
    rows,meta,old_summary,old_confs=task;mid=meta['molecule_id'];start=time.monotonic()
    marker=Path(os.environ['SPRIME_LOCAL_STATUS'])/(str(os.getpid())+'.json')
    marker.write_text(json.dumps({'molecule_id':mid,'pid':os.getpid(),'stage':'CHECK_SCI','started':time.time()}))
    if old_summary['status'] in {'SUCCESS','INSUFFICIENT_UNIQUE_CONFORMERS'} and old_confs:
        try:
            raw=[science.read(r) for r in rows]
            energies=[float(science.plain(science.field(d,'energy')).reshape(-1)[0]) for d in raw]
            lowest=min(range(len(rows)),key=lambda i:(energies[i],rows[i]['record_id']))
            mol,z,_=science.graph(raw[lowest]);source,signature=science.fix_stereo(mol,str(science.field(raw[lowest],'smiles')))
            seed=max(int.from_bytes(hashlib.sha256(('sprime-ETKDGv3-v1:'+mid).encode()).digest()[:4],'big')&0x7fffffff,1)
            from rdkit import Chem
            for c in old_confs:
                assert c['seed']==seed and c['source_record_id']==rows[lowest]['record_id']
                assert c['atom_order_sha256']==hashlib.sha256(z.astype('<i8').tobytes()).hexdigest()
                coords=np.asarray(c['coordinates'],dtype=np.float64)
                assert coords.shape==(len(z),3) and np.isfinite(coords).all()
                conf=Chem.Conformer(len(z))
                for i,p in enumerate(coords):conf.SetAtomPosition(i,p.tolist())
                conf.Set3D(True);cid=mol.AddConformer(conf,assignId=True)
                assert science.check_geometry_stereo(mol,cid)
                mol.RemoveConformer(cid)
            summary=dict(old_summary);summary.update(stereo_source=source,stereo_signature=signature,rejected_stereo_candidates=0,sci_reused=True,validation_seconds=time.monotonic()-start)
            for c in old_confs:c.update(stereo_source=source,stereo_signature=signature,sci_source_revision='pilot_v4_validated_by_v5')
            marker.write_text(json.dumps({'molecule_id':mid,'stage':'CACHED_SCI_CLOSED'}))
            return summary,old_confs
        except Exception:
            pass  # Recompute from the original source; never bless a failed SCI check.
    marker.write_text(json.dumps({'molecule_id':mid,'stage':'GENERATION_V5','started':time.time()}))
    summary,confs=science.process((rows,meta));summary.update(sci_reused=False,validation_seconds=time.monotonic()-start)
    for c in confs:c['sci_source_revision']='pilot_v5_recomputed'
    marker.write_text(json.dumps({'molecule_id':mid,'stage':'SCI_CLOSED','status':summary['status']}))
    return summary,confs

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--group',type=int,required=True);ap.add_argument('--workers',type=int,required=True);a=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and 16<=a.workers<=int(os.environ['SLURM_CPUS_PER_TASK'])
    baseline=ROOT/'pilot_v4';out=ROOT/'pilot_v5';out.mkdir(exist_ok=True,parents=True)
    receipt=json.loads((baseline/f'receipt_group{a.group}.json').read_text())
    for ref in receipt['references']:
        assert Path(ref['path']).stat().st_size==ref['bytes'] and sha(ref['path'])==ref['sha256']
    metas=pq.read_table(ROOT/'prepared/pilot_molecules.parquet',filters=[('file_group','=',a.group)]).to_pylist()
    cols=['record_id','molecule_id','source_path','real_index','record_payload_sha256','total_atoms','energy_raw','smiles','QC_molecule_chirality_conflict','QC_molecule_ez_conflict']
    rows=pq.read_table(ROOT/'prepared/pilot_records.parquet',columns=cols,filters=[('file_group','=',a.group)]).to_pylist()
    indexed={m['molecule_id']:[] for m in metas}
    for r in rows:indexed[r['molecule_id']].append(r)
    old={r['molecule_id']:r for r in pq.read_table(baseline/f'molecules_group{a.group}.parquet').to_pylist()}
    old_c={m['molecule_id']:[] for m in metas}
    for c in pq.read_table(baseline/f'conformers_group{a.group}.parquet').to_pylist():old_c[c['molecule_id']].append(c)
    assert len(old)==len(metas)==2000
    for name in ['molecules','conformers']:
        if (out/f'{name}_group{a.group}.parquet').exists():raise FileExistsError('Closed recovery cannot be replayed')
    scratch=Path(tempfile.mkdtemp(prefix='sprv3_'+os.environ['SLURM_JOB_ID']+'_',dir='/tmp'));os.chmod(scratch,0o700)
    os.environ['SPRIME_LOCAL_STATUS']=str(scratch)
    summaries=[];conformers=[];start=time.monotonic()
    try:
        with cf.ProcessPoolExecutor(max_workers=a.workers,mp_context=mp.get_context('spawn'),initializer=science.worker_init) as pool:
            futures=[pool.submit(task_worker,(indexed[m['molecule_id']],m,old[m['molecule_id']],old_c[m['molecule_id']])) for m in metas]
            for f in cf.as_completed(futures):
                m,c=f.result();summaries.append(m);conformers.extend(c)
                if len(summaries)%100==0:
                    counts={s:sum(r['status']==s for r in summaries) for s in {r['status'] for r in summaries}}
                    save(out/f'progress_group{a.group}.json',{'job_id':os.environ['SLURM_JOB_ID'],'completed':len(summaries),'total':2000,'status_counts':counts,'sci_reused':sum(r['sci_reused'] for r in summaries),'elapsed_seconds':time.monotonic()-start})
        summaries.sort(key=lambda r:r['molecule_id']);conformers.sort(key=lambda r:(r['molecule_id'],r['sprime_conf_idx']))
        for name,data in [('molecules',summaries),('conformers',conformers)]:
            table=pa.Table.from_pylist(data)
            if name=='conformers':table=table.set_column(table.schema.get_field_index('coordinates'),'coordinates',pa.array([r['coordinates'] for r in data],type=pa.list_(pa.list_(pa.float64(),3))))
            path=out/f'{name}_group{a.group}.parquet';pq.write_table(table,str(path)+'.pending',compression='zstd',row_group_size=4096);Path(str(path)+'.pending').replace(path)
        from rdkit import rdBase
        save(out/f'receipt_group{a.group}.json',{'job_id':os.environ['SLURM_JOB_ID'],'group':a.group,'molecules':2000,'conformers':len(conformers),'wall_seconds':time.monotonic()-start,'workers':a.workers,'science_cpu_seconds':sum(m['elapsed_seconds'] for m in summaries),'sci_reused':sum(r['sci_reused'] for r in summaries),'baseline_receipt':receipt,'source_sha256':sha(science.__file__),'recovery_source_sha256':sha(__file__),'rdkit_version':rdBase.rdkitVersion,'scratch_removed':str(scratch),'references':[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in [out/f'molecules_group{a.group}.parquet',out/f'conformers_group{a.group}.parquet']]})
    finally:shutil.rmtree(scratch)

if __name__=='__main__':main()
