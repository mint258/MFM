"""Original PPE D3 using already-bound atom maps; no second XYZ graph recovery."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import time
import pyarrow as pa
import pyarrow.parquet as pq
from .reference_d3 import SCALARS,frames,initialize
from .reference_mapping import model_graph,restore_atom_values
from .downstream_science import geometry_descriptors
from .pprime_queue import capacity


def one(frame):
    binding=frame['binding']
    result={'record_id':frame['record_id'],'source_reference':frame['source_reference'],
        'source_reference_row':frame['source_reference_row'],'model_smiles':binding['model_smiles'],
        'model_to_reference':binding['model_to_reference'],'SASA_atom_A2':None,
        'D3_valid_mask':[False]*7,'issues':binding['issues'],'state':'REFERENCE_MAPPING_UNRESOLVED',
        **{key:None for key in SCALARS}}
    if binding['model_to_reference'] is None:return result
    try:
        ordered,mol=model_graph(binding['model_smiles']);mapping=binding['model_to_reference']
        if ordered!=binding['model_smiles']:raise ValueError('Bound model SMILES atom order changed')
        if sorted(mapping)!=list(range(len(frame['atomic_numbers']))):raise ValueError('Incomplete source reference map')
        z=[a.GetAtomicNum() for a in mol.GetAtoms()]
        if z!=[frame['atomic_numbers'][i] for i in mapping]:raise ValueError('Source reference atom identity changed')
        coordinates=[frame['coordinates_A'][i] for i in mapping]
        d3,issues=geometry_descriptors(ordered,mol,z,coordinates,frame['D20'])
        result.update({key:d3.get(key) for key in SCALARS})
        result.update(SASA_atom_A2=restore_atom_values(d3.get('SASA_atom_A2'),mapping),issues=issues)
        valid=[result[k] is not None and math.isfinite(result[k]) for k in SCALARS]+[result['SASA_atom_A2'] is not None]
        result.update(D3_valid_mask=valid,state='D3_READY' if all(valid) else 'D3_PARTIAL_PROPERTIES')
    except Exception as exc:result.update(state='D3_PROPERTY_OR_BINDING_FAILED',issues=[type(exc).__name__+':'+str(exc)])
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--domain-manifest',type=Path,required=True);p.add_argument('--D20',type=Path,required=True)
    p.add_argument('--quota-snapshot',type=Path,required=True);p.add_argument('--attempt',required=True)
    p.add_argument('--workers',type=int,default=2);a=p.parse_args()
    if os.environ.get('SLURM_JOB_PARTITION')!='cpu' or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers:
        raise RuntimeError('Actual CPU allocation required')
    def safe():
        waiting=False
        while True:
            try:capacity(a.root,a.quota_snapshot,67108864);return
            except (OSError,ValueError,KeyError,RuntimeError) as exc:
                if not waiting:print('PPE_D3_DISK_WAIT',repr(exc),flush=True)
                waiting=True;time.sleep(2)
    safe();out=a.root/'labels/reference_D3'/a.attempt;out.mkdir(parents=True,exist_ok=False)
    domain=json.loads(a.domain_manifest.read_text())
    binding={row['record_id']:row for row in pq.read_table(domain['reference_bindings']).to_pylist()}
    reference=Path(domain['reference_geometry_source'])
    def inputs():
        for frame in frames(domain['records'],reference,a.D20,'PPE1694'):
            frame['binding']=binding[frame['record_id']]
            if frame['D20'] is None:raise ValueError('Closed PPE D20 source is missing')
            yield frame
    schema=pa.schema([('record_id',pa.string()),('source_reference',pa.string()),('source_reference_row',pa.int64()),
        ('model_smiles',pa.string()),('model_to_reference',pa.list_(pa.int32())),
        *[pa.field(k,pa.float64()) for k in SCALARS],('SASA_atom_A2',pa.list_(pa.float64())),
        ('D3_valid_mask',pa.list_(pa.bool_())),('issues',pa.list_(pa.string())),('state',pa.string())])
    states=Counter();buffer=[];rows=0;target=out/'PPE1694.parquet'
    with ProcessPoolExecutor(max_workers=a.workers,mp_context=mp.get_context('spawn'),initializer=initialize) as pool:
        with pq.ParquetWriter(target,schema,compression='zstd') as writer:
            for row in pool.map(one,inputs(),chunksize=8):
                buffer.append(row);states[row['state']]+=1;rows+=1
                if len(buffer)>=128:
                    safe();writer.write_table(pa.Table.from_pylist(buffer,schema=schema));buffer.clear()
            if buffer:safe();writer.write_table(pa.Table.from_pylist(buffer,schema=schema))
    report={'status':'REFERENCE_D3_CLOSED_WITH_EXPLICIT_FAILURES','dataset':'PPE1694','rows':rows,'states':dict(states),
        'records':str(target),'domain_manifest':str(a.domain_manifest),'D20_source':str(a.D20),
        'reference_bindings_source':domain['reference_bindings'],'reference_geometry_regenerated':False,
        'graph_recovery_repeated':False,'D20_recomputed':False,'original_D3_parameters_unchanged':True,
        'atomic_SASA_restored_to_reference_order':True,'independent_numeric_readback':False,'new_data_content_hashes':False}
    safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PPE_REFERENCE_D3_CLOSED',report,flush=True)

if __name__=='__main__':main()