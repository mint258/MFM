"""Full2.5M exact ranked typed source→UFF JSONL and augmentation FP projection."""
import argparse
import os
from pathlib import Path
import uuid
from ..common import load,reference,dump_new,require
from ..portable_sources_v1.transport import verify,bind_plan,provenance
from ..uff3_alpha_runtime_v1 import ordered_contract as Current
from .engine import RECIPE,WIDTH
from .sql_runtime import SqlGuard,configure


def run(plan_path):
    import duckdb
    from ..uff3_candidate_v1 import core as C
    plan=load(plan_path);require(plan.get('schema')=='PUBCHEM_TYPED_ORDERED_UFF_SOURCE_PLAN_V1','Wrong ordered source plan schema')
    bind_plan(plan)
    rank=load(verify(plan['ranking_receipt']));filtered=load(verify(rank['filtered_pool']));novelty=load(verify(rank['novelty_receipt']))
    candidate_refs=Current.complete(rank,filtered,novelty);Current.completed_rank(plan,rank)
    candidates=[verify(ref)for ref in candidate_refs];batch=verify(rank['batch1'])
    origin=Current.origin(plan,filtered)
    root=Path(plan['output_directory']);require(root.is_absolute() and not root.is_symlink(),'Absolute source output required')
    root.mkdir(parents=True,exist_ok=True);guard=SqlGuard(plan,root)
    import fcntl
    lock=(root/'parent.lock').open('a+b');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    require(not (root/'source_manifest.json').exists(),'Closed source manifest exists; reuse exact source')
    out=root/('attempt_'+uuid.uuid4().hex);out.mkdir();db=duckdb.connect(':memory:')
    parts=[];counts={'R':0,'N':0};projected=out/'augmentation_projection.jsonl';part=None;part_rows=0
    try:
        configure(db,plan,out/'spill');guard.start(db)
        db.read_parquet([str(path)for path in candidates],union_by_name=False).create_view('candidates');db.read_parquet(str(batch)).create_view('batch1')
        require(db.execute('SELECT count(*),count(DISTINCT full_key),count(DISTINCT cid) FROM batch1').fetchone()==(2500000,2500000,2500000),
            'Exactly2.5M unique first-batch molecules required')
        require(db.execute('SELECT stream,count(*),min(stream_rank),max(stream_rank),count(DISTINCT stream_rank) FROM batch1 GROUP BY stream ORDER BY stream').fetchall()
            ==[('N',1250000,1,1250000,1250000),('R',1250000,1,1250000,1250000)],'Full original R/N rank domains required')
        require(db.execute('SELECT count(*) FROM batch1 ANTI JOIN candidates USING(cid,full_key)').fetchone()[0]==0,'A ranked identity lacks its actual source graph')
        db.execute('''CREATE TABLE selected AS SELECT b.stream,b.stream_rank,c.cid,c.full_key,c.source_smiles,c.isomeric_smiles,
            c.ecfp4_2048_hex,c.generic_murcko,c.generic_ring_systems FROM batch1 b JOIN candidates c USING(cid,full_key)''')
        require(db.execute('SELECT count(*) FROM selected').fetchone()[0]==2500000,'Ranked source join amplified or lost identities')
        cursor=db.execute('SELECT * FROM selected ORDER BY stream,stream_rank');names=[c[0] for c in cursor.description]
        with projected.open('x',encoding='utf-8') as fp:
            while True:
                batch_rows=cursor.fetchmany(1000)
                if not batch_rows:break
                for values in batch_rows:
                    row=dict(zip(names,values));stream=row['stream']
                    source={'pubchem_version':origin['pubchem_version'],'cid':int(row['cid']),'full_key':row['full_key'],
                        'source_smiles':row['source_smiles'],'isomeric_smiles':row['isomeric_smiles'],'stream':stream,'stream_rank':int(row['stream_rank'])}
                    C.source_identity(source);counts[stream]+=1
                    if part is None:
                        part_path=out/('source_'+str(len(parts)).zfill(4)+'.jsonl');part=part_path.open('x',encoding='utf-8');part_rows=0
                    part.write(C.canonical(source).decode()+'\n');part_rows+=1
                    raw=bytes.fromhex(row['ecfp4_2048_hex']);require(len(raw)==WIDTH,'Ranked original fingerprint width differs')
                    fp.write(C.canonical({'molecule_id':C.molecule_id(source),'full_key':source['full_key'],
                        'ecfp4_2048_hex':row['ecfp4_2048_hex'],'generic_murcko':row['generic_murcko'],'generic_ring_systems':row['generic_ring_systems']}).decode()+'\n')
                    if part_rows==10000:
                        part.flush();os.fsync(part.fileno());part.close();part=None;parts.append({**reference(part_path),'rows':part_rows})
                fp.flush();guard.check()
            fp.flush();os.fsync(fp.fileno())
        if part is not None:
            part.flush();os.fsync(part.fileno());part.close();part=None;parts.append({**reference(part_path),'rows':part_rows})
        require(counts=={'R':1250000,'N':1250000} and sum(p['rows'] for p in parts)==2500000,'Exact whole ordered source census differs')
    finally:
        if part is not None:part.close()
        guard.done.set()
        if hasattr(guard,'thread'):guard.thread.join()
        db.close();lock.close()
    guard.close()
    for ref in candidate_refs:verify(ref)
    verify(rank['batch1'])
    manifest={'schema':'PUBCHEM_UFF3_ORDERED_SOURCE_MANIFEST_V1','status':'ALL2500000_ORDERED_SOURCE_GRAPHS_PROJECTED_NO_UFF',
        'molecules':2500000,'molecules_by_stream':counts,'ranking_receipt':plan['ranking_receipt'],'source_parts':parts,
        'source_origin':origin,'pubchem_version':origin['pubchem_version'],
        'typed_filtered_pool':rank['filtered_pool'],'resource_plan':reference(plan_path),'new_UFF_QM_calls':0}
    manifest.update(population_version=filtered['population_version'],source_pool_receipt=filtered['source_pool_receipt'])
    manifest['actual_parent']={'job_id':os.environ['SLURM_JOB_ID'],'uid':os.getuid()}
    manifest['endpoint_execution']=provenance(plan)
    dump_new(root/'source_manifest.json',manifest)
    reference_projection={'schema':'EXPANSION_ORDERED_RN_REFERENCE_PROJECTION_V1','status':'COMPLETE',
        'fingerprint_recipe':RECIPE,'targets_present':False,'downstream_features_present':False,
        'source_manifest':reference(root/'source_manifest.json'),'ranking_receipt':plan['ranking_receipt'],
        'projection':{**reference(projected),'rows':2500000},'original_source_fingerprints_reused_without_new_perception':True}
    dump_new(root/'augmentation_manifest.json',reference_projection);return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);run(p.parse_args().plan)


if __name__=='__main__':main()
