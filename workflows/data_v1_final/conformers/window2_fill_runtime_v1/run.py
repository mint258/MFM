"""Omit unused formal/HOF/coordinate I/O for already-complete closed D7 rows."""
from __future__ import annotations
import argparse
import collections
import concurrent.futures as cf
import json
import multiprocessing as mp
import os
from pathlib import Path
import time
from workflows.data_v1_final.conformers.window2_population_v1 import fill as original
from workflows.data_v1_final.conformers.window2_population_v1.fill import d7, read, info, save


def already_complete(meta,statistics):
    """The original early-return guard, restricted to an already closed D7 row."""
    try:
        if statistics['status']!='COMPLETE':return False
        kept=json.loads(statistics['sprime_unique_ids_json']) if statistics.get('sprime_unique_ids_json') else []
        return len(kept)>=int(meta['S_conformers'])
    except (KeyError,TypeError,ValueError):
        # Malformed/unknown inputs follow the original safe_fill error handling.
        return False


def part_values(db,metas,statistics,bounds,pool):
    """Preserve output order; materialize full science input only for slow rows."""
    byid={row['molecule_id']:row for row in statistics}
    values={};remaining=[]
    for meta in metas:
        mid=meta['molecule_id'];stats=byid[mid]
        if already_complete(meta,stats):
            # Original fill_one reads no SCIENCE method/records/uff before this
            # early return. Original safe_fill preserves every state field and
            # UFF_UNSUPPORTED precedence; no state/scientific code is copied.
            stub={'meta':meta,'d7':stats,'records':[],'uff':[],
                'max_original_attempt_idx':bounds.get(mid,-1)}
            values[mid]=original.safe_fill(stub)
        else:remaining.append(meta)
    if remaining:
        jobs=original.d7.tasks(db,remaining)
        for job in jobs:
            mid=job['meta']['molecule_id']
            job['d7']=byid[mid]
            job['max_original_attempt_idx']=bounds.get(mid,-1)
        for job,value in zip(jobs,pool.map(original.safe_fill,jobs,chunksize=4)):
            values[job['meta']['molecule_id']]=value
    return [values[meta['molecule_id']] for meta in metas]


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
                values=part_values(db,metas,statistics,bounds,pool)
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