"""Pack full true Common and exact prefix-preserving R/N augmentation references."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from ..common import load,reference,require,dump_new,wp5_key
from ..portable_sources_v1.transport import verify,bind_plan,provenance
from .engine import RECIPE,WIDTH,file_frame
from .run import Guard
from .coverage import validate_reference


def run(plan_path):
    plan=load(plan_path);require(plan.get('schema')=='PUBCHEM_EXACT_REFERENCE_PACK_PLAN_V1','Wrong reference pack plan')
    bind_plan(plan)
    import socket
    if not plan.get('runtime_profile_reference'):
        require(socket.gethostname().split('.')[0].startswith('compute-0-') and os.environ.get('SLURM_JOB_ID'),
            'Allocated Main compute node required for full reference packing')
    root=Path(plan['output_directory']);require(root.is_absolute() and not root.exists(),'Fresh absolute packed reference directory required')
    root.mkdir(parents=True);guard=Guard(plan,root);guard.poll(True,32<<20)
    role=plan['reference_role'];before=role=='before';require(role in ('before','after'),'Explicit reference role required')
    source_path=verify(plan['input_manifest']);source=load(source_path)
    if before:
        require(source.get('schema')=='expansion_common_v1_structure_projection_v1' and source.get('fingerprint_recipe')==RECIPE
            and source.get('targets_present') is False and source.get('population_roles')==['TRAIN','VAL']
            and source.get('one_row_per_common_molecule') is True,'Actual full Common projection required')
        verify(source['actual_full_receipt_reference']);review=load(verify(source['final_Root_graph_review_reference']))
        require(review.get('reviewer')=='root' and review.get('status')=='APPROVED_EXACT_COMMON_REFERENCE_PROJECTION',
            'Actual full Common final graph authority required')
        verify(source['common_population_manifest']);expected=source['common_molecules'];base_count=0
    else:
        base_path=verify(plan['base_reference_manifest']);base=validate_reference(base_path,'before');base_count=base['molecules']
        require(source.get('schema')=='EXPANSION_ORDERED_RN_REFERENCE_PROJECTION_V1' and source.get('status')=='COMPLETE'
            and source.get('fingerprint_recipe')==RECIPE and source.get('targets_present') is False
            and source['projection']['rows']==2500000,'Actual full2.5M ordered fingerprint augmentation required')
        source_manifest=load(verify(source['source_manifest']))
        require(source_manifest['molecules']==2500000 and source_manifest['molecules_by_stream']=={'R':1250000,'N':1250000},'Whole R/N source census required')
        expected=2500000
        require(sum(base[k]['bytes'] for k in ('fingerprints','keys','counts'))+(32<<20)<=plan['output_cap_bytes'],
            'Declared augmentation output must cover the whole immutable base copy')
        shutil.copyfile(verify(base['fingerprints']),root/'fingerprints.bin');shutil.copyfile(verify(base['keys']),root/'keys.ascii')
        original=sqlite3.connect(verify(base['counts']).as_uri()+'?mode=ro',uri=True)
        copy=sqlite3.connect(root/'counts.sqlite')
        try:original.backup(copy)
        finally:original.close();copy.close()
    projection=verify(source['projection']);frame=file_frame(projection);db=sqlite3.connect(root/'counts.sqlite')
    db.executescript('''CREATE TABLE IF NOT EXISTS ids(molecule_id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS scaffolds(key TEXT PRIMARY KEY,n INTEGER);
        CREATE TABLE IF NOT EXISTS rings(key TEXT PRIMARY KEY,n INTEGER);
        CREATE TABLE IF NOT EXISTS identities(full_key TEXT PRIMARY KEY,n INTEGER);''')
    if not before and db.execute('SELECT count(*) FROM identities').fetchone()[0]==0:
        with (root/'keys.ascii').open('rb') as stream:
            for line in stream:
                require(len(line)==28,'Original key width differs');key=line[:-1].decode('ascii');wp5_key(key)
                db.execute('INSERT INTO identities VALUES(?,1) ON CONFLICT(full_key) DO UPDATE SET n=n+1',(key,))
        db.commit()
    count=0;window=0;digest=hashlib.sha256();mode='xb' if before else 'ab'
    try:
        with projection.open('rb') as stream,(root/'fingerprints.bin').open(mode) as out,(root/'keys.ascii').open(mode) as keys:
            for line in stream:
                require(len(line)<=1<<20,'Bounded projection row required');digest.update(line);row=json.loads(line)
                require(set(row)=={'molecule_id','full_key','ecfp4_2048_hex','generic_murcko','generic_ring_systems'},'Reference projection contains unexpected features/targets')
                key=row['full_key'];wp5_key(key);raw=bytes.fromhex(row['ecfp4_2048_hex'])
                require(len(raw)==WIDTH and isinstance(row['molecule_id'],str) and row['molecule_id'],'Exact reference bytes and original MID required')
                require(isinstance(row['generic_murcko'],str) and isinstance(row['generic_ring_systems'],list)
                    and all(isinstance(v,str) for v in row['generic_ring_systems']),'Exact source scaffold/ring projection required')
                if not before:require(db.execute('SELECT 1 FROM identities WHERE full_key=?',(key,)).fetchone() is None,'Augmentation repeats an original/new reference full identity')
                db.execute('INSERT INTO ids VALUES(?)',(row['molecule_id'],))
                db.execute('INSERT INTO identities VALUES(?,1) ON CONFLICT(full_key) DO UPDATE SET n=n+1',(key,))
                db.execute('INSERT INTO scaffolds VALUES(?,1) ON CONFLICT(key) DO UPDATE SET n=n+1',(row['generic_murcko'],))
                for ring in set(row['generic_ring_systems']):db.execute('INSERT INTO rings VALUES(?,1) ON CONFLICT(key) DO UPDATE SET n=n+1',(ring,))
                out.write(raw);keys.write(key.encode('ascii')+b'\n');count+=1
                window+=len(line)+4096
                if window>=8<<20:db.commit();out.flush();keys.flush();guard.poll(True,32<<20);window=0
            for handle in (out,keys):handle.flush();os.fsync(handle.fileno())
        require(count==expected==source['projection']['rows'] and digest.hexdigest()==source['projection']['sha256']
            and file_frame(projection)==frame,'Every original projection row and SHA must match')
        db.commit();require(db.execute('SELECT count(*) FROM ids').fetchone()[0]==base_count+count,'All reference molecular ordinals retained')
    finally:db.close()
    guard.poll(True)
    result={'schema':'expansion_exact_ecfp4_reference_v1' if before else 'EXPANSION_EXACT_AUGMENTED_REFERENCE_V1',
        'status':'COMPLETE','fingerprint_recipe':RECIPE,'targets_present':False,'input_manifest':plan['input_manifest'],
        'molecules':base_count+count,'bytes_per_fingerprint':WIDTH,'bytes_per_identity':28,
        'fingerprints':reference(root/'fingerprints.bin'),'keys':reference(root/'keys.ascii'),'counts':reference(root/'counts.sqlite'),
        'resource_plan':reference(plan_path),'all_reference_rows_preserved':True}
    result['endpoint_execution']=provenance(plan)
    if not before:result.update(base_reference_manifest=plan['base_reference_manifest'],added_molecules=count,
        added_source_manifest=source['source_manifest'],addition_projection_manifest=plan['input_manifest'],
        original_reference_ordinals_preserved_as_exact_prefix=True)
    dump_new(root/'manifest.json',result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);run(p.parse_args().plan)


if __name__=='__main__':main()
