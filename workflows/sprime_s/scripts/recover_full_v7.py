"""Recover only terminal registered owners; keep valid complete molecules, preserve leftovers."""
import json,os,hashlib,time
from pathlib import Path
import numpy as np
import pyarrow as pa,pyarrow.parquet as pq
from prepare import ROOT,POP,save,sha
import full_dataset_v7 as coord

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    import duckdb
    plan=json.loads((ROOT/'reports/full_recovery_plan.json').read_text())
    assert time.time()-plan['timestamp']<1800
    terminal=plan['terminal_registered_jobs'];assert terminal
    prepared=json.loads((coord.FULL/'prepared.json').read_text())
    assert prepared['source_sha256']==sha(coord.science.__file__)
    db=coord.database();rows=db.execute("SELECT id,file_group,lo,hi,molecules,owner,job_id,receipt FROM chunks WHERE state='RUNNING'").fetchall();db.close()
    result=[];dd=duckdb.connect();dd.execute('SET threads=16');dd.execute("SET memory_limit='20GB'")
    pilot_ids=set(pq.read_table(ROOT/'prepared/pilot_molecules.parquet',columns=['molecule_id']).column(0).to_pylist())
    for cid,group,lo,hi,expected,owner,jid,old in rows:
        if jid not in terminal:continue
        assert owner==f"{terminal[jid]['node']}:{jid}" and terminal[jid]['user']=='zixiao'
        prior=json.loads(old) if old else {'segments':[],'molecules':0};seq=len(prior['segments']);base=f'g{group}_c{cid:04d}_s{seq:02d}_j{jid}'
        paths={kind:coord.FULL/'parts'/(base+'_'+kind+'.parquet') for kind in ['molecules','conformers']}
        tables={};notes=[]
        for kind,path in paths.items():
            candidate=path if path.exists() else Path(str(path)+'.pending')
            if candidate.exists():
                try:tables[kind]=pq.read_table(candidate)
                except Exception as exc:notes.append({'path':str(candidate),'error':repr(exc),'action':'PRESERVED_UNREADABLE_NO_SCI_REUSE'})
        recovered=0;previous_ids=set()
        for ref in prior.get('references',[]):
            assert sha(ref['path'])==ref['sha256']
            if ref['kind']=='molecules':
                ids=pq.read_table(ref['path'],columns=['molecule_id']).column(0).to_pylist();assert not previous_ids.intersection(ids);previous_ids.update(ids)
        assert len(previous_ids)==prior['molecules']
        if 'molecules' in tables:
            ms=tables['molecules'].to_pylist();cs=tables['conformers'].to_pylist() if 'conformers' in tables else []
            assert len({m['molecule_id'] for m in ms})==len(ms)
            assert len({(c['molecule_id'],c['sprime_conf_idx']) for c in cs})==len(cs)
            expected_rows=dd.execute(f"SELECT molecule_id,records,max_total_atoms FROM read_parquet('{POP/'molecule_index.parquet'}') WHERE file_group=? AND molecule_id BETWEEN ? AND ?",[group,lo,hi]).fetchall();expected_map={m:(n,a) for m,n,a in expected_rows}
            by_id={m['molecule_id']:[] for m in ms}
            for c in cs:
                assert c['molecule_id'] in by_id,'Orphan conformer in recoverable footer'
                by_id[c['molecule_id']].append(c)
            complete=[];selected=[]
            for m in ms:
                mid=m['molecule_id'];assert mid in expected_map and mid not in previous_ids and mid not in pilot_ids and m['expected_conformers']==expected_map[mid][0] and m['file_group']==group
                seed=max(1,int.from_bytes(hashlib.sha256(('sprime-ETKDGv3-v1:'+mid).encode()).digest()[:4],'big')&0x7fffffff)
                assert m['seed']==seed and 0<=m['generated_conformers']<=m['expected_conformers']
                children=sorted(by_id[mid],key=lambda c:c['sprime_conf_idx'])
                if len(children)!=m['generated_conformers']:continue
                assert [c['sprime_conf_idx'] for c in children]==list(range(len(children)))
                for c in children:
                    xyz=np.asarray(c['coordinates'],dtype=np.float64)
                    assert xyz.shape==(expected_map[mid][1],3) and np.isfinite(xyz).all() and c['seed']==seed and c['atom_order_sha256']==m['atom_order_sha256']
                complete.append(m);selected.extend(children)
            if complete:
                # New files avoid touching or claiming the interrupted bytes as a complete segment.
                refs=[]
                for kind,data in [('molecules',complete),('conformers',selected)]:
                    schema=pa.ipc.read_schema(pa.BufferReader((coord.FULL/(kind+'.schema')).read_bytes()))
                    dest=coord.FULL/'parts'/(base+'_recovered_j'+os.environ['SLURM_JOB_ID']+'_'+kind+'.parquet');assert not dest.exists()
                    pq.write_table(pa.Table.from_pylist(data,schema=schema),dest,compression='zstd')
                    refs.append({'path':str(dest),'bytes':dest.stat().st_size,'sha256':sha(dest),'kind':kind})
                segment={'chunk_id':cid,'segment_index':seq,'group':group,'job_id':jid,'recovery_job_id':os.environ['SLURM_JOB_ID'],'owner':owner,'molecules':len(complete),'conformers':len(selected),'source_sha256':prepared['source_sha256'],'references':refs}
                coord.finish(cid,owner,segment);recovered=len(complete)
        if not recovered:
            queue=coord.database();cur=queue.execute("UPDATE chunks SET state='PENDING',owner=NULL,job_id=NULL WHERE id=? AND owner=? AND job_id=? AND state='RUNNING'",(cid,owner,jid));assert cur.rowcount==1;queue.commit();queue.close()
        result.append({'chunk_id':cid,'terminal_owner_job':jid,'recovered_complete_molecules':recovered,'original_partial_files_preserved':True,'notes':notes})
    dd.close();save(ROOT/'reports'/('full_recovery_'+os.environ['SLURM_JOB_ID']+'.json'),{'status':'RECOVERED','job_id':os.environ['SLURM_JOB_ID'],'chunks':result,'scientific_generation_calls':0,'original_lmdb_written':False})
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
