"""Full D7 and original three orders from closed source geometry, one producer."""
from __future__ import annotations
import argparse
import collections
import concurrent.futures as cf
import gzip
import importlib.util
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import pickle
import sys

from .run import read, info, save
from workflows.data_v1_final.conformers.selection import conformer_orders, stable_key

SCIENCE = None
HANDLES = collections.OrderedDict()


def initialize(science_path):
    global SCIENCE
    os.environ['OMP_NUM_THREADS'] = '1'
    os.environ['OPENBLAS_NUM_THREADS'] = '1'
    os.environ['MKL_NUM_THREADS'] = '1'
    sys.path.insert(0, str(Path(science_path).parent))
    spec = importlib.util.spec_from_file_location('_window2_original_sprime', science_path)
    SCIENCE = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(SCIENCE)
    SCIENCE.worker_init()


def native(row):
    """Read declared source once; alignment is checked using actual graph/arrays."""
    import lmdb
    path = row['source_path']
    if not path.startswith('/'):
        path = '/share/home/zixiao/descriptor_analysis/' + path
    if path not in HANDLES:
        if len(HANDLES) >= 4:
            HANDLES.popitem(last=False)[1].close()
        HANDLES[path] = lmdb.open(path, subdir=False, readonly=True, lock=False,
            create=False, readahead=False, max_readers=1024)
    handle = HANDLES.pop(path)
    HANDLES[path] = handle
    with handle.begin() as transaction:
        value = transaction.get(('%09d' % row['real_index']).encode())
    if value is None:
        raise ValueError('NATIVE_GEOMETRY_RECORD_MISSING:' + row['record_id'])
    return pickle.loads(value)


def count_unique(rows, order, distance, threshold=0.5):
    byid = {row['conformer_id']:row for row in rows}
    if len(byid) != len(rows) or set(order) != set(byid) or len(order) != len(rows):
        raise ValueError('D7_CONFORMER_ID_PERMUTATION')
    selected = []
    for key in order:
        values = [distance(byid[key], byid[old]) for old in selected]
        if not all(math.isfinite(value) and value >= 0 for value in values):
            raise ValueError('D7_NONFINITE_RMSD')
        if all(value >= threshold for value in values):
            selected.append(key)
    return selected


def source_orders(rows, distance, mid, source):
    if all(row['energy'] is not None for row in rows):
        return conformer_orders(rows, distance, mid, source, 20261025)
    return {'fixed_random':sorted((row['conformer_id'] for row in rows),
        key=lambda key:(stable_key(20261025,mid,source,key),str(key))),
        'energy':None,'diversity':None}


def one(task):
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    meta, records, uff = task['meta'], task['records'], task['uff']
    mid = meta['molecule_id']
    prior = task.get('prior_packet')
    prior_cache = None
    if prior:
        with gzip.open(prior,'rt',encoding='utf-8') as stream:
            packet = json.load(stream)
        cache, d7 = packet.get('cache',{}), packet.get('d7')
        if cache.get('status','').startswith('PM7_GEOMETRY_CACHE_COMPLETE'):
            prior_cache = cache
        if packet.get('molecule_id') != mid:
            raise ValueError('CLOSED_PACKET_MOLECULE_ALIGNMENT')
        if cache.get('status','').startswith('PM7_GEOMETRY_CACHE_COMPLETE') and (d7 or not uff):
            result = {'molecule_id':mid, 'pm7_count':cache['pm7_count'],
                'pm7_unique':cache['pm7_unique'],'uff_sprime_count':d7['uff_sprime_count'] if d7 else 0,
                'uff_sprime_unique':d7['uff_sprime_unique'] if d7 else 0,
                'heavy_atoms':cache['heavy_atoms'],'rotatable_bonds':cache['rotatable_bonds'],
                'effective_role':meta['effective_role'],'common_population':meta['common_population'],
                'pm7_orders_json':json.dumps(cache['orders']),
                'sprime_orders_json':json.dumps(d7['orders']['uff_sprime']) if d7 else None,
                'pm7_unique_ids_json':json.dumps(cache['unique_representatives']),
                'sprime_unique_ids_json':json.dumps(d7['unique_representatives']['uff_sprime']) if d7 else None,
                'reused_closed_result':True,'status':'COMPLETE','error':None}
            return result
    mol, numbers, signature = None, None, None
    pm7 = []
    for row in sorted(records,key=lambda value:value['record_id']):
        if prior_cache and pm7:
            break
        raw = native(row)
        other, z, xyz = SCIENCE.graph(raw)
        if mol is None:
            mol,numbers,signature = other,z,SCIENCE.ordered_graph(other)
        if len(z) != row['total_atoms'] or not np.array_equal(z,numbers) or SCIENCE.ordered_graph(other) != signature:
            raise ValueError('NATIVE_ATOM_GRAPH_GEOMETRY_ALIGNMENT:' + mid)
        value = json.loads(row['value_json']) if row.get('value_json') and not row.get('duplicate') else None
        energy = value['value_kcal_mol'] if value and value.get('valid') else None
        pm7.append({'conformer_id':row['record_id'],'coordinates':xyz,'energy':energy})
    if prior_cache:
        if set(prior_cache['record_ids']) != {row['record_id'] for row in records} or prior_cache['atomic_numbers'] != numbers.tolist():
            raise ValueError('REUSED_PM7_SOURCE_ALIGNMENT:' + mid)
        pm7 = prior_cache['pm7']
    if len(pm7) != meta['S_conformers']:
        raise ValueError('WHOLE_PM7_MOLECULE_COUNT_ALIGNMENT:' + mid)
    sprime = []
    for row in uff:
        xyz = np.asarray(row['coordinates'],dtype=np.float64)
        if xyz.shape != (len(numbers),3) or not np.isfinite(xyz).all():
            raise ValueError('SPRIME_ATOM_GEOMETRY_ALIGNMENT:' + mid)
        energy = float(row['uff_energy_kcal_mol'])
        if not math.isfinite(energy):
            raise ValueError('SPRIME_ENERGY_NOT_FINITE:' + mid)
        sprime.append({'conformer_id':row['sprime_conf_idx'],'coordinates':xyz,'energy':energy})
    if len(sprime) != meta['merged_uff_count']:
        raise ValueError('WHOLE_SPRIME_MOLECULE_COUNT_ALIGNMENT:' + mid)
    distance = lambda left,right: SCIENCE.rmsd(mol,left['coordinates'],right['coordinates'])
    porders = prior_cache['orders'] if prior_cache else source_orders(pm7,distance,mid,'pm7')
    uorders = source_orders(sprime,distance,mid,'uff_sprime')
    puniq = prior_cache['unique_representatives'] if prior_cache else count_unique(pm7,porders['fixed_random'],distance)
    uuniq = count_unique(sprime,uorders['fixed_random'],distance)
    return {'molecule_id':mid,'pm7_count':len(pm7),'pm7_unique':len(puniq),
        'uff_sprime_count':len(sprime),'uff_sprime_unique':len(uuniq),
        'heavy_atoms':int(np.count_nonzero(numbers!=1)),
        'rotatable_bonds':int(rdMolDescriptors.CalcNumRotatableBonds(Chem.RemoveHs(mol))),
        'effective_role':meta['effective_role'],'common_population':meta['common_population'],
        'pm7_orders_json':json.dumps(porders),'sprime_orders_json':json.dumps(uorders),
        'pm7_unique_ids_json':json.dumps(puniq),'sprime_unique_ids_json':json.dumps(uuniq),
        'reused_closed_result':False,'status':'COMPLETE','error':None}


def safe_one(task):
    try:
        return one(task)
    except Exception as exc:
        return {'molecule_id':task['meta']['molecule_id'],'status':'SOURCE_OR_COMPUTATION_FAILED',
            'error':repr(exc),'effective_role':task['meta']['effective_role'],
            'common_population':task['meta']['common_population'],
            'pm7_count':None,'pm7_unique':None,'uff_sprime_count':None,'uff_sprime_unique':None,
            'heavy_atoms':None,'rotatable_bonds':None,'pm7_orders_json':None,'sprime_orders_json':None,
            'pm7_unique_ids_json':None,'sprime_unique_ids_json':None,'reused_closed_result':False}


def quote(value):
    return "'" + str(value).replace("'","''") + "'"


def parquet_sql(references):
    return 'read_parquet([' + ','.join(quote(r['path']) for r in references) + '],union_by_name=true)'


def prepare(plan, workspace):
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    common = read(plan['common'])
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    ready = workspace/'ready.json'
    db = duckdb.connect(str(workspace/'d7.duckdb'))
    db.execute('SET threads=' + str(plan['workers']))
    if ready.exists():
        if read(ready)['plan'] != plan:
            raise ValueError('RESUME_INPUT_PLAN_CHANGED')
        return db,common
    db.execute('CREATE TABLE members AS SELECT * FROM ' + parquet_sql(common['membership_tables']))
    db.execute('CREATE TABLE formal AS SELECT record_id,molecule_id,source_path,real_index,total_atoms FROM read_parquet(' + quote(plan['formal_index']) + ')')
    db.execute('ATTACH '+quote(plan['closed_hof_db'])+' AS original_hof (READ_ONLY)')
    db.execute('CREATE TABLE hof AS SELECT * FROM original_hof.hof')
    db.execute('DETACH original_hof')
    umaps=[r for r in common['physical_geometry_tables'] if Path(r['path']).name.startswith('uff_sprime-')]
    db.execute('CREATE TABLE umaps AS SELECT * FROM ' + parquet_sql(umaps))
    originals=read(common['old_sprime_manifest'])
    sources=[r for r in originals['references'] if r.get('kind')=='conformers']
    paths=','.join(quote(r['path']) for r in sources)
    # Project actual accepted coordinates once into node scratch, never shared
    # derived copies or a second validation pass.
    db.execute(('CREATE TABLE baseline AS SELECT molecule_id,sprime_conf_idx,coordinates,uff_energy_kcal_mol,status,converged,filename,file_row_number FROM read_parquet([PATHS],filename=true,file_row_number=true)').replace('PATHS',paths))
    db.execute('''CREATE TABLE uff AS SELECT r.molecule_id,coalesce(m.sprime_conf_idx,r.sprime_conf_idx) AS sprime_conf_idx,m.geometry_id,
        r.coordinates,r.uff_energy_kcal_mol FROM baseline r LEFT JOIN umaps m
        ON r.filename=m.source_path AND r.file_row_number=m.source_row_index AND m.source_format='parquet'
        WHERE r.status='SUCCESS' AND r.converged IS TRUE''')
    generated=db.execute("SELECT molecule_id,sprime_conf_idx,geometry_id,source_path,source_row_index FROM umaps WHERE source_format<>'parquet' ORDER BY source_path,source_row_index").fetch_arrow_table().to_pylist()
    rows=[]
    for source,group in __import__('itertools').groupby(generated,key=lambda row:row['source_path']):
        with gzip.open(source,'rt',encoding='utf-8') as stream:
            packet=json.load(stream)
        for m in group:
            row=packet['conformers'][m['source_row_index']]
            if row['molecule_id']!=m['molecule_id']:
                raise ValueError('GENERATED_PHYSICAL_ROW_MID_ALIGNMENT')
            rows.append({key:m[key] for key in ('molecule_id','sprime_conf_idx','geometry_id')} |
                {'coordinates':row['coordinates'],'uff_energy_kcal_mol':row['uff_energy_kcal_mol']})
        if len(rows)>=4096:
            db.register('part',pa.Table.from_pylist(rows));db.execute('INSERT INTO uff SELECT * FROM part');db.unregister('part');rows=[]
    if rows:
        db.register('part',pa.Table.from_pylist(rows));db.execute('INSERT INTO uff SELECT * FROM part');db.unregister('part')
    # Include partial/unsupported/non-Common molecules in the full S-prime
    # descriptive denominator, preserving canonical append indices and real count.
    outside=dict(db.execute('SELECT molecule_id,S_conformers FROM members WHERE NOT common_population').fetchall())
    bounds=dict(db.execute('SELECT molecule_id,max(sprime_conf_idx) FROM baseline GROUP BY molecule_id').fetchall())
    index=read(common['completion_index'])
    outcomes=read(index['outcomes'])
    rows=[]
    for outcome in outcomes:
        mid=outcome['molecule_id']
        if mid not in outside or not outcome['science_result_observed']:
            continue
        with gzip.open(outcome['package_reference']['path'],'rt',encoding='utf-8') as stream:
            packet=json.load(stream)
        new=[row for row in packet['conformers'] if row['origin']!='accepted_sprime']
        start=max(bounds.get(mid,-1),outside[mid]-1)+1
        for ordinal,row in enumerate(new):
            rows.append({'molecule_id':mid,'sprime_conf_idx':start+ordinal,'geometry_id':None,
                'coordinates':row['coordinates'],'uff_energy_kcal_mol':row['uff_energy_kcal_mol']})
        if len(rows)>=4096:
            db.register('part',pa.Table.from_pylist(rows));db.execute('INSERT INTO uff SELECT * FROM part');db.unregister('part');rows=[]
    if rows:
        db.register('part',pa.Table.from_pylist(rows));db.execute('INSERT INTO uff SELECT * FROM part');db.unregister('part')
    db.execute('CREATE INDEX fmid ON formal(molecule_id)')
    db.execute('CREATE INDEX umid ON uff(molecule_id)')
    db.execute('CREATE INDEX hrid ON hof(record_id)')
    db.execute('CREATE TABLE prior(molecule_id VARCHAR PRIMARY KEY,packet_path VARCHAR)')
    prior={}
    for reference in plan.get('closed_ordinary_catalogs',[]):
        for batch in pq.ParquetFile(reference['path']).iter_batches(batch_size=4096):
            for row in batch.to_pylist():
                if row.get('status')=='DURABLE_READONLY_MOLECULE_RESULT':
                    path=row['packet_reference']['path']
                    if row['molecule_id'] in prior and prior[row['molecule_id']]!=path:
                        raise ValueError('CONFLICTING_CLOSED_D7_RESULTS')
                    prior[row['molecule_id']]=path
    for source in plan.get('closed_ordinary_orphan_manifests',[]):
        for item in read(source)['closed_orphans']:
            row = item['catalog_row']
            if row['status'] == 'DURABLE_READONLY_MOLECULE_RESULT':
                prior[row['molecule_id']] = row['packet_reference']['path']
    if prior:
        db.register('part',pa.table({'molecule_id':list(prior),'packet_path':list(prior.values())}))
        db.execute('INSERT INTO prior SELECT * FROM part');db.unregister('part')
    db.execute('CHECKPOINT')
    save(ready,{'plan':plan,'closed_prior_molecules':len(prior)})
    return db,common


def tasks(db,metas):
    import pyarrow as pa
    db.register('batch',pa.table({'molecule_id':[row['molecule_id'] for row in metas]}))
    records=db.execute('SELECT f.*,h.value_json,h.duplicate FROM formal f JOIN batch USING(molecule_id) LEFT JOIN hof h USING(record_id) ORDER BY molecule_id,record_id').fetch_arrow_table().to_pylist()
    uff=db.execute('SELECT u.* FROM uff u JOIN batch USING(molecule_id) ORDER BY molecule_id,sprime_conf_idx').fetch_arrow_table().to_pylist()
    prior=dict(db.execute('SELECT p.* FROM prior p JOIN batch USING(molecule_id)').fetchall())
    byrecord=collections.defaultdict(list);byuff=collections.defaultdict(list)
    for row in records:byrecord[row['molecule_id']].append(row)
    for row in uff:byuff[row['molecule_id']].append(row)
    db.unregister('batch')
    return [{'meta':meta,'records':byrecord[meta['molecule_id']],
        'uff':byuff[meta['molecule_id']],'prior_packet':prior.get(meta['molecule_id'])} for meta in metas]


def summarize(rows):
    import numpy as np
    from scipy.stats import spearmanr
    complete=[row for row in rows if row['status']=='COMPLETE']
    result={'molecules':len(rows),'complete_molecules':len(complete),
        'failed_molecules':len(rows)-len(complete),'reused_closed_molecules':sum(row['reused_closed_result'] for row in rows),
        'dedup_threshold_A':0.5,'rmsd':'source heavy-atom order, proper-rotation Kabsch',
        'unique_counts':{},'correlations':{}}
    for source,count,unique in [('pm7','pm7_count','pm7_unique'),('uff_sprime','uff_sprime_count','uff_sprime_unique')]:
        subset=complete
        total=sum(row[count] for row in subset);n_unique=sum(row[unique] for row in subset)
        result['unique_counts'][source]={'histogram':dict(collections.Counter(str(row[unique]) for row in subset)),
            'molecules':len(subset),'total_conformers':total,'unique_conformers':n_unique,
            'duplicate_conformer_fraction':1-n_unique/total if total else None,
            'scope':'FULL_PM7_SOURCE' if source=='pm7' else 'FULL_SOURCE_ORDINARY_SPRIME_ACTUAL_ACCEPTED_COUNTS'}
        for feature in ('heavy_atoms','rotatable_bonds'):
            x=[row[feature] for row in subset];y=[row[unique] for row in subset]
            rho=float(spearmanr(x,y).statistic) if len(set(x))>1 and len(set(y))>1 else None
            result['correlations'][source+'_unique_vs_'+feature]={'spearman_rho':rho if rho is None or math.isfinite(rho) else None,'molecules':len(subset)}
    return result


def run(plan):
    import pyarrow as pa
    import pyarrow.parquet as pq
    out=Path(plan['output']);out.mkdir(parents=True,exist_ok=True)
    checkpoint=out/'checkpoint.json';done=read(checkpoint) if checkpoint.exists() else {'parts':[]}
    db,common=prepare(plan,plan['workspace'])
    metas=db.execute('SELECT * FROM members ORDER BY molecule_id').fetch_arrow_table().to_pylist()
    batch_size=plan.get('batch_molecules',2048)
    parts=list(done['parts']);completed={row['part'] for row in parts}
    with cf.ProcessPoolExecutor(max_workers=plan['workers'],mp_context=mp.get_context('spawn'),initializer=initialize,initargs=(plan['science_path'],)) as pool:
        for part,offset in enumerate(range(0,len(metas),batch_size)):
            if part in completed:continue
            batch=tasks(db,metas[offset:offset+batch_size])
            rows=list(pool.map(safe_one,batch,chunksize=4))
            path=out/('part-%06d.parquet'%part)
            pq.write_table(pa.Table.from_pylist(rows),path,compression='zstd',row_group_size=2048)
            parts.append({'part':part,**info(path,len(rows))})
            temporary=out/'checkpoint.next.json'
            temporary.write_text(json.dumps({'parts':parts}),encoding='utf-8')
            os.replace(temporary,checkpoint)
            print(json.dumps({'stage':'D7','completed_molecules':min(offset+batch_size,len(metas)),'total':len(metas)}),flush=True)
    db.close()
    # Summary consumes statistics generated in this producer, never source geometry.
    rows=[]
    for reference in parts:
        rows.extend(pq.read_table(reference['path']).to_pylist())
    summary=summarize(rows)
    summary.update(status='COMPLETE' if summary['failed_molecules']==0 and len(rows)==1220466 else 'PARTIAL_WITH_EXPLICIT_FAILURES',
        source_common=plan['common'],three_orders_from_original_algorithm=True,
        order_tables=parts,content_hashes_computed=False,new_QM_calls=0,new_UFF_calls=0)
    save(out/'manifest.json',summary)
    save(out/'delivery_manifest.json',{'files':parts})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True)
    args=parser.parse_args()
    run(read(args.plan))


if __name__=='__main__':main()