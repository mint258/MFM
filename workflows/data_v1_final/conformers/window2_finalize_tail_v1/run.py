"""Finish final D7 only; retain existing Common/D5/first2/maps without rerunning."""
from __future__ import annotations
import argparse
import collections
import concurrent.futures as cf
import json
import multiprocessing as mp
import os
from pathlib import Path
import time
from workflows.data_v1_final.conformers.window2_population_v1 import finalize as original
from workflows.data_v1_final.conformers.window2_population_v1 import d7 as engine
from workflows.data_v1_final.conformers.window2_source_cache_v1.keep_source_map import install_native_reader


def initialize(science_path):
    engine.initialize(science_path)
    install_native_reader(engine,os.environ.get('DATA_V1_COMPLETED_SOURCE_CACHE_PLAN'))


def project_coordinates(db,source_alias,new_source,mids,table):
    """Original kept baseline plus new rows, strictly limited to needed MIDs."""
    import pyarrow as pa
    db.register('tail_needed_mids',pa.table({'molecule_id':mids}))
    db.execute('CREATE TABLE '+table+''' AS SELECT u.* FROM '''+source_alias+'''.uff u
        JOIN keep k USING(molecule_id,sprime_conf_idx)
        WHERE EXISTS(SELECT 1 FROM tail_needed_mids m WHERE m.molecule_id=u.molecule_id)''')
    if new_source:
        db.execute('INSERT INTO '+table+''' SELECT molecule_id,sprime_conf_idx,NULL,coordinates,uff_energy_kcal_mol
            FROM '''+new_source+''' n WHERE EXISTS(SELECT 1 FROM tail_needed_mids m WHERE m.molecule_id=n.molecule_id)''')
    db.unregister('tail_needed_mids')


def batch_tasks(db,mids,table):
    """Same original anchor selection and selected coordinate query/order."""
    import pyarrow as pa
    db.register('batch',pa.table({'molecule_id':mids}))
    anchors=db.execute('SELECT f.* FROM formal f JOIN batch USING(molecule_id) QUALIFY row_number() OVER(PARTITION BY molecule_id ORDER BY record_id)=1').fetch_arrow_table().to_pylist()
    coordinates=db.execute('SELECT f.* FROM '+table+' f JOIN batch USING(molecule_id)').fetch_arrow_table().to_pylist()
    byid=collections.defaultdict(list)
    for row in coordinates:byid[row['molecule_id']].append(row)
    jobs=[{'molecule_id':row['molecule_id'],'anchor':row,'uff':byid[row['molecule_id']]} for row in anchors]
    db.unregister('batch')
    return jobs


def refresh_batches(mids,closed,load,calculate,publish,batch_size=1024):
    """Only persisted closed batches are skipped; in-memory work is not closed."""
    for offset in range(0,len(mids),batch_size):
        ordinal=offset//batch_size
        if ordinal in closed:continue
        jobs=load(mids[offset:offset+batch_size])
        result=list(calculate(jobs))
        reference=publish(ordinal,result)
        closed[ordinal]=reference
    return [closed[index] for index in sorted(closed)]


def updated_row(source,state,common,refreshed):
    # Exact field updates from original refresh_final_orders, without whole-table JSON materialization.
    row=dict(source);row['common_population']=common
    if state.get('final_unique_count') is not None:
        row['uff_sprime_count']=row['uff_sprime_unique']=state['final_unique_count']
        if row['molecule_id'] in refreshed:row['sprime_orders_json']=refreshed[row['molecule_id']]
        row['sprime_unique_ids_json']=json.dumps(json.loads(row['sprime_orders_json'])['fixed_random']) if row.get('sprime_orders_json') else '[]'
    return row


def atomic_checkpoint(path,state):
    temporary=path.with_name('checkpoint.next.json')
    temporary.write_text(json.dumps(state),encoding='utf-8');os.replace(temporary,path)


def run(plan):
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    out=Path(plan['output'])
    # Already producer-closed upstream references are consumed, not rebuilt/QA'd.
    common=original.read(out/'manifest.json')
    first2=common['Pprime_first2_scope_reference']
    fill=original.read(plan['fill']);d7=original.read(plan['d7'])
    root=out/'D7_tail_resume_v1';root.mkdir(parents=True,exist_ok=True)
    checkpoint=root/'checkpoint.json'
    inputs={key:plan[key] for key in ('output','workspace','coordinate_db','fill','d7','science_path')}
    state=original.read(checkpoint) if checkpoint.exists() else {'inputs':inputs,'batches':[]}
    if state['inputs']!=inputs:raise ValueError('TAIL_RESUME_INPUTS_CHANGED')
    if (out/'D7.json').exists():
        report=original.read(out/'D7.json')
        return finish_delivery(out,common,first2,report['order_tables'])
    states={}
    for part in fill['parts']:
        for row in pq.read_table(part['states']['path'],columns=['molecule_id','final_unique_count','optimized_candidates']).to_pylist():
            states[row['molecule_id']]=row
    changed=[]
    for reference in d7['order_tables']:
        for row in pq.read_table(reference['path'],columns=['molecule_id','uff_sprime_count']).to_pylist():
            status=states[row['molecule_id']]
            if status.get('final_unique_count') is not None and (row['uff_sprime_count']!=status['final_unique_count'] or status.get('optimized_candidates',0)>0):
                changed.append(row['molecule_id'])
    mids=sorted(set(changed));closed={row['batch']:row for row in state['batches']}
    pending=[mid for index,mid in enumerate(mids) if index//1024 not in closed]
    db=duckdb.connect(str(Path(plan['workspace'])/'final_population.duckdb'))
    db.execute('SET threads='+str(plan['workers']))
    if pending and not state.get('projection'):
        source_alias=None
        for name,path in db.execute('SELECT database_name,path FROM duckdb_databases()').fetchall():
            if path==plan['coordinate_db']:source_alias='"'+name.replace('"','""')+'"';break
        if source_alias is None:
            source_alias='tail_source_coordinates_v1'
            db.execute('ATTACH '+original.quote(plan['coordinate_db'])+' AS '+source_alias+' (READ_ONLY)')
        table='tail_coordinates_'+str(os.getpid())+'_'+str(time.time_ns())
        newrefs=[part['new_geometry'] for part in fill['parts'] if part['new_geometry']]
        project_coordinates(db,source_alias,original.parquet_sql(newrefs) if newrefs else None,pending,table)
        state['projection']={'table':table,'molecules':len(pending)}
        atomic_checkpoint(checkpoint,state)
    if pending:
        table=state['projection']['table']
        with cf.ProcessPoolExecutor(max_workers=plan['workers'],mp_context=mp.get_context('spawn'),
            initializer=initialize,initargs=(plan['science_path'],)) as pool:
            def publish(ordinal,result):
                path=root/('refreshed-%06d-%d.parquet'%(ordinal,time.time_ns()))
                values=[{'molecule_id':mid,'sprime_orders_json':orders} for mid,orders in result]
                pq.write_table(pa.Table.from_pylist(values),path,compression='zstd')
                reference=dict(original.info(path,len(values)),batch=ordinal)
                state['batches']=sorted([*state['batches'],reference],key=lambda row:row['batch'])
                atomic_checkpoint(checkpoint,state)
                print(json.dumps({'stage':'final_D7_tail','closed_batches':len(state['batches']),'batch':ordinal}),flush=True)
                return reference
            refresh_batches(mids,closed,lambda batch:batch_tasks(db,batch,table),
                lambda jobs:pool.map(original.refreshed_orders,jobs,chunksize=4),publish)
    refreshed={}
    for reference in state['batches']:
        for row in pq.read_table(reference['path']).to_pylist():refreshed[row['molecule_id']]=row['sprime_orders_json']
    actual_common=dict(db.execute('SELECT molecule_id,common_population FROM members').fetchall())
    parts=[];buffer=[];summary=[]
    unused_json={'pm7_orders_json','sprime_orders_json','pm7_unique_ids_json','sprime_unique_ids_json'}
    def write_rows(rows):
        path=root/('final_orders-%06d-%d.parquet'%(len(parts),time.time_ns()))
        pq.write_table(pa.Table.from_pylist(rows),path,compression='zstd')
        parts.append(original.info(path,len(rows)))
    # Preserve original global input row order and original8192-row output grouping.
    for reference in d7['order_tables']:
        for batch in pq.ParquetFile(reference['path']).iter_batches(batch_size=8192):
            for source in batch.to_pylist():
                mid=source['molecule_id'];row=updated_row(source,states[mid],actual_common[mid],refreshed)
                buffer.append(row);summary.append({key:value for key,value in row.items() if key not in unused_json})
                if len(buffer)==8192:write_rows(buffer);buffer=[]
    if buffer:write_rows(buffer)
    report=original.summarize(summary)
    report.update(status='COMPLETE' if fill['status']=='COMPLETE' and d7['status']=='COMPLETE' else 'PARTIAL_WITH_EXPLICIT_FAILURES',
        original_D7_reference=plan['d7'],source_sprime_closure=plan['fill'],order_tables=parts,Sprime_orders_require_new_geometry_merge=False)
    original.save(out/'D7.json',report)
    finish_delivery(out,common,first2,parts)
    db.close()


def finish_delivery(out,common,first2,parts):
    path=out/'delivery_manifest.json'
    if path.exists():return original.info(path)
    return original.save(path,{'files':[*common['membership_tables'],*common['full_source_physical_geometry_tables'],
        *common.get('diagnostic_addressable_geometry_tables',[]),original.info(out/'manifest.json'),
        original.info(out/'D5'/'manifest.json'),first2,original.info(out/'D7.json')]})


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True)
    args=parser.parse_args();run(original.read(args.plan))


if __name__=='__main__':main()