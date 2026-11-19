"""Original D20 on source reference graphs; never generate or replace geometries."""
import argparse
from collections import Counter
import json
import time
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem
from .pprime_queue import capacity
from .downstream_science import graph_descriptors,identities
from .shared_reader import SharedB0Reader


def original_d20(smiles):
    params=Chem.SmilesParserParams();params.removeHs=False
    mol=Chem.MolFromSmiles(smiles,params)
    if mol is None:raise ValueError('Previously bound source graph is not parseable')
    return graph_descriptors(Chem.RemoveHs(mol))


def reuse_descriptors(paths):
    cache={}
    for source in paths:
        for batch in pq.ParquetFile(source).iter_batches(batch_size=256):
            for row in batch.to_pylist():
                if row['D20_values'] is None:continue
                cache.setdefault(row['model_smiles'],({'names':row['D20_names'],'values':row['D20_values'],
                    'valid_mask':row['D20_valid_mask'],'issues':row['issues']},'CLOSED_REFERENCE_D20:'+str(source),row['state']))
    return cache


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--input',action='append',required=True,help='Dataset=closed_domain_parquet')
    p.add_argument('--attempt',required=True);p.add_argument('--quota-snapshot',type=Path,required=True)
    p.add_argument('--reuse-D20',action='append',type=Path,default=[])
    a=p.parse_args();root=a.root;g=json.loads((root/'geometry/shared_v1/queue.manifest.json').read_text())
    def safe(needed):
        waiting=False
        while True:
            try:capacity(root,a.quota_snapshot,needed);return
            except (OSError,ValueError,KeyError,RuntimeError) as exc:
                if not waiting:print('REFERENCE_D20_DISK_WAIT',repr(exc),flush=True)
                waiting=True;time.sleep(2)
    safe(134217728);out=root/'labels/reference_D20'/a.attempt;out.mkdir(parents=True,exist_ok=False)
    cache=reuse_descriptors(a.reuse_D20);reports=[]
    schema=pa.schema([('dataset',pa.string()),('record_id',pa.string()),('model_smiles',pa.string()),
        ('shared_molecule_id',pa.string()),('D20_names',pa.list_(pa.string())),('D20_values',pa.list_(pa.float64())),
        ('D20_valid_mask',pa.list_(pa.bool_())),('issues',pa.list_(pa.string())),('state',pa.string()),
        ('D20_origin',pa.string())])
    with SharedB0Reader(g['queue']) as shared:
        for specification in a.input:
            dataset,source=specification.split('=',1);target=out/(dataset+'.parquet')
            counts=Counter();buffer=[]
            with pq.ParquetWriter(target,schema,compression='zstd') as writer:
                for batch in pq.ParquetFile(source).iter_batches(batch_size=256,
                        columns=['record_id','model_smiles','domain_eligible']):
                    for row in batch.to_pylist():
                        if not row['domain_eligible']:continue
                        smiles=row['model_smiles'];mid,_=identities(smiles)
                        if smiles not in cache:
                            existing=shared.db.execute('SELECT state,result FROM tasks WHERE mid=?',(mid,)).fetchone()
                            if existing:
                                if existing[1] is not None:
                                    import zlib
                                    result=json.loads(zlib.decompress(existing[1]));d20=result.get('D20')
                                    cache[smiles]=(d20,'SHARED_GEOMETRY_PRODUCER',existing[0])
                                else:cache[smiles]=(None,'SHARED_GEOMETRY_PRODUCER_PENDING',existing[0])
                            else:cache[smiles]=(original_d20(smiles),'ORIGINAL_D20_FUNCTIONS_ON_REFERENCE_GRAPH','D20_COMPUTED')
                        d20,origin,source_state=cache[smiles]
                        state='D20_READY' if d20 and all(d20['valid_mask']) else 'D20_PARTIAL' if d20 else 'D20_SOURCE_UNAVAILABLE'
                        counts[state]+=1
                        buffer.append({'dataset':dataset,'record_id':row['record_id'],'model_smiles':smiles,
                            'shared_molecule_id':mid,'D20_names':d20['names'] if d20 else None,
                            'D20_values':d20['values'] if d20 else None,'D20_valid_mask':d20['valid_mask'] if d20 else None,
                            'issues':d20['issues'] if d20 else [source_state],'state':state,'D20_origin':origin})
                    safe(134217728)
                    if buffer:writer.write_table(pa.Table.from_pylist(buffer,schema=schema));buffer.clear()
            reports.append({'dataset':dataset,'source':source,'records':str(target),'counts':dict(counts)})
            print('REFERENCE_D20_CLOSED',dataset,dict(counts),flush=True)
    report={'status':'D20_REFERENCE_GRAPHS_CLOSED_D3_P_PENDING','groups':reports,
        'unique_ordered_graphs_seen':len(cache),'reused_closed_D20_sources':[str(v) for v in a.reuse_D20],'source_geometry_regenerated':False,
        'D20_source':'Unchanged pretraining 20 descriptor function objects and order',
        'D3_ready':False,'P_ready':False,'Pprime_ready':False,'independent_numeric_readback':False,
        'actual_label_consumer_reuses_shared_results':True,'no_local_database_copy':True}
    safe(1048576);(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
