"""Once-only full actual UFF D3/SASA F64 cache, shared by D6 and statistics."""
import argparse,concurrent.futures as cf,importlib,json,math,multiprocessing as mp,os,pickle,sqlite3,sys
from pathlib import Path
from . import physical as G,identities as A
from ...labels.window2_normalization_v1 import io as I
from ...labels.normalization_compact_runtime_v3 import codec as K
from ...labels.payload_audit_v1.payload import evaluate
from ...labels.size_cpu_v2.aggregate import pair_keys
STATE={}


def init(plan,index):
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    import torch
    torch.set_num_threads(1)
    if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    fields=I.load_data(I.load(plan['coverage'])['field_map_reference']);fields=[f for f in fields if f['task']=='D3']
    parent=Path(__file__).absolute().parents[2]/'labels';sys.path.insert(0,str(parent))
    try:common=importlib.import_module('common');masks=importlib.import_module('pilot_masks')
    finally:sys.path.pop(0)
    if Path(common.__file__).parent!=parent or Path(masks.__file__).parent!=parent:raise ValueError('ORIGINAL_MASK_MODULE_BINDING')
    STATE.update(plan=plan,index=index,fields=fields,common=common,masks=masks,reused_database=plan.get('reused_database'))


def work(task):
    number,mids=task;root=Path(STATE['plan']['uff_d3_cache_root']);path=root/('part_%06d.sqlite'%number);marker=path.with_suffix('.json')
    if marker.is_file():return I.load(marker)
    src=sqlite3.connect('file:'+A.database_path(STATE['index'])+'?mode=ro',uri=True);out=sqlite3.connect(path)
    out.executescript('CREATE TABLE IF NOT EXISTS molecules(mid TEXT PRIMARY KEY,newly_masked INTEGER); CREATE TABLE IF NOT EXISTS graphs(anchor TEXT PRIMARY KEY,z BLOB,bonds BLOB,codes BLOB); CREATE TABLE IF NOT EXISTS labels(mid TEXT,conf INTEGER,gid TEXT PRIMARY KEY,anchor TEXT,atomic_numbers BLOB,entries BLOB,issues TEXT,ordinary_sprime INTEGER,diagnostic_only INTEGER,excluded_from_all_training INTEGER); CREATE INDEX IF NOT EXISTS label_mid ON labels(mid);')
    count=0;invalid=0
    reused=sqlite3.connect('file:'+STATE['reused_database']+'?mode=ro',uri=True) if STATE.get('reused_database') else None
    try:
        for mid in mids:
            prior=out.execute('SELECT 1 FROM molecules WHERE mid=?',(mid,)).fetchone()
            expected=src.execute("SELECT count(*) FROM geometries WHERE mid=? AND src='uff_sprime'",(mid,)).fetchone()[0]
            if reused is not None:
                expected=sum(reused.execute('SELECT 1 FROM reused WHERE gid=?',(gid,)).fetchone() is None for gid, in src.execute("SELECT gid FROM geometries WHERE mid=? AND src='uff_sprime'",(mid,)))
            if expected==0:continue
            present=out.execute('SELECT count(*) FROM labels WHERE mid=?',(mid,)).fetchone()[0]
            if prior and expected==present:continue
            if prior or present:raise ValueError('PARTIAL_MID_COMMIT_IN_UFF_D3_CACHE')
            invalid_before=invalid;native_cache={}
            for storage,gid,ordinary,pointer in src.execute("SELECT physical,gid,ordinary,pointer FROM geometries WHERE mid=? AND src='uff_sprime' ORDER BY physical",(mid,)):
                if reused is not None and reused.execute('SELECT 1 FROM reused WHERE gid=?',(gid,)).fetchone():continue
                pointer=json.loads(pointer);actual,xyz=G.physical(pointer)
                anchor=pointer.get('native_anchor_record_id') or actual.get('native_anchor_record_id') or actual.get('source_record_id')
                if not isinstance(anchor,str) or not anchor:raise ValueError('EXPLICIT_UFF_NATIVE_ANCHOR_REQUIRED:'+gid)
                if anchor not in native_cache:
                    hit=src.execute("SELECT pointer FROM geometries WHERE mid=? AND src='pm7' AND physical=?",(mid,anchor)).fetchone()
                    if hit is None:raise ValueError('ACTUAL_UFF_NATIVE_ANCHOR_POINTER_MISSING:'+anchor)
                    raw=G.native(json.loads(hit[0]));z=(G.array(G.field(raw,'x')).reshape(-1)+1).astype('int64').tolist()
                    bonds=G.array(G.field(raw,'rdkit_bond_index')).T.tolist();codes=G.array(G.field(raw,'rdkit_bond_order')).reshape(-1).tolist()
                    native_cache[anchor]=(raw,z,bonds,codes)
                    out.execute('INSERT OR IGNORE INTO graphs VALUES(?,?,?,?)',(anchor,pickle.dumps(z,protocol=5),pickle.dumps(bonds,protocol=5),pickle.dumps(codes,protocol=5)))
                raw,z,bonds,codes=native_cache[anchor]
                if actual.get('atomic_numbers') is not None and list(actual['atomic_numbers'])!=z:raise ValueError('ACTUAL_UFF_AND_NATIVE_GRAPH_ATOM_ORDER_ALIGNMENT')
                actual_anchor=actual.get('native_anchor_record_id') or actual.get('source_record_id')
                if actual_anchor and actual_anchor!=anchor:raise ValueError('ACTUAL_UFF_NATIVE_ANCHOR_WITNESS_DIFFERS')
                try:d3,issues=G.uff_d3(raw,xyz)
                except Exception as exc:d3={};issues=['ORIGINAL_D3_FAILED:'+repr(exc)]
                finite=lambda v:isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
                missing=[n for n in ('PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2') if not finite(d3.get(n))]
                atomic=d3.get('SASA_atom_A2');array_ok=atomic is not None and len(atomic)==len(z) and all(finite(v) for v in atomic)
                row=dict(d3,record_id=gid,molecule_id=mid,total_atoms=len(z),calc_type='D3',status='SUCCESS' if not missing and array_ok else 'PROPERTY_FAILED',issues=issues)
                entries,*_=evaluate(row,'D3',STATE['fields'],STATE['common'],STATE['masks'],pair_keys,{})
                for e in entries:e['field']=next(f for f in STATE['fields'] if f['field_id']==e['field_id'])
                out.execute('INSERT INTO labels VALUES(?,?,?,?,?,?,?,?,?,?)',(mid,int(pointer['sprime_conf_idx']),gid,anchor,pickle.dumps(z,protocol=5),pickle.dumps(K.pack_entries(entries),protocol=5),json.dumps(issues),ordinary,bool(pointer.get('diagnostic_only')),bool(pointer.get('excluded_from_all_training'))))
                count+=1;invalid+=int(any(any(a and not b for a,b in zip(e['source_value_mask'],e['value_mask'])) for e in entries))
            out.execute('INSERT INTO molecules VALUES(?,?)',(mid,invalid-invalid_before));out.commit()
        count=out.execute('SELECT count(*) FROM labels').fetchone()[0];invalid=out.execute('SELECT coalesce(sum(newly_masked),0) FROM molecules').fetchone()[0]
    finally:
        if reused is not None:reused.close()
        src.close();out.close()
    result={'path':str(path),'bytes':path.stat().st_size,'records':count,'newly_masked_records':invalid,'part':number}
    I.save(marker,result);return result

def produce(plan):
    index=A.prepare(plan,geometry_only=True);root=Path(plan['uff_d3_cache_root']);root.mkdir(parents=True,exist_ok=True);manifest=root/'manifest.json'
    if manifest.is_file():return I.load(manifest)
    existing=[];known=set();reuse_path=None
    if plan.get('reuse_uff_d3_caches'):
        reuse_path=root/'reused.sqlite';reuse_marker=root/'reused.json'
        for prior in plan['reuse_uff_d3_caches']:
            for ref in I.load(prior)['files']:
                if ref['path'] not in known:known.add(ref['path']);existing.append(ref)
        if not reuse_marker.is_file():
            reuse=sqlite3.connect(reuse_path);reuse.execute('CREATE TABLE IF NOT EXISTS reused(gid TEXT PRIMARY KEY)')
            try:
                for ref in existing:
                    source=sqlite3.connect('file:'+ref['path']+'?mode=ro',uri=True)
                    try:reuse.executemany('INSERT OR IGNORE INTO reused VALUES(?)',source.execute('SELECT gid FROM labels'))
                    finally:source.close()
                    reuse.commit()
            finally:reuse.close()
            I.save(reuse_marker,{'inputs':plan['reuse_uff_d3_caches'],'database':I.ref(reuse_path)})
        elif I.load(reuse_marker)['inputs']!=plan['reuse_uff_d3_caches']:raise ValueError('FROZEN_EXISTING_D3_CACHE_INPUTS_CHANGED')
        plan=dict(plan,reused_database=str(reuse_path))
    db=sqlite3.connect('file:'+A.database_path(index)+'?mode=ro',uri=True)
    if reuse_path:
        db.execute('ATTACH DATABASE ? AS prior',('file:'+str(reuse_path)+'?mode=ro',))
        missing={row[0] for row in db.execute("SELECT DISTINCT mid FROM geometries g WHERE src='uff_sprime' AND NOT EXISTS(SELECT 1 FROM prior.reused r WHERE r.gid=g.gid)")}
    else:missing=None
    mids=[mid for mid,role,common in db.execute('SELECT mid,role,common FROM members ORDER BY mid') if A.selected(role,common) and (missing is None or mid in missing)];db.close()
    width=int(plan.get('molecules_per_block',128));tasks=[(i//width,mids[i:i+width]) for i in range(0,len(mids),width)]
    with cf.ProcessPoolExecutor(max_workers=int(plan['workers']),mp_context=mp.get_context('spawn'),initializer=init,initargs=(plan,index)) as pool:
        added=[]
        for ref in pool.map(work,tasks):
            added.append(ref);print(json.dumps({'phase':'UFF_D3_CACHE','parts':len(added),'new_records':sum(r['records'] for r in added)}),flush=True)
    expected=sum(v for k,v in index['expected_conformers'].items() if k.endswith('_U'));files=existing+added
    if sum(r['records'] for r in files)!=expected:raise ValueError('ALL_ACTUAL_UFF_D3_RECORD_COUNTS_DIFFER')
    result={'schema':'FULL_ACTUAL_UFF_D3_FLOAT64_CACHE_V1','files':files,'inputs':index['inputs'],'records':expected,
        'original_corrected_base_calls_per_new_actual_geometry':1,'new_D3_calls':sum(r['records'] for r in added),
        'reused_D3_records':sum(r['records'] for r in existing),'D20_export_source':'original PM7 typed source shared once per M',
        'original_corrected_base_internal_HBA_preserved':True,'new_content_hashes':False,
        'new_masks_report_only':True,'source_F64_geometry_unchanged':True}
    I.save(manifest,result);return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);args=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise ValueError('REAL_CPU_SLURM_PRODUCER_REQUIRED')
    print(json.dumps(produce(I.load(args.plan))),flush=True)
if __name__=='__main__':main()