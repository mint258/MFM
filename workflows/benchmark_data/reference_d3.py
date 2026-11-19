"""Original D3 over fixed dataset reference geometries, with explicit atom maps."""
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
from workflows.data_v1_final.labels.common import D20_NAMES
from .downstream_science import geometry_descriptors
from .pprime_queue import capacity
from .reference_mapping import map_reference,restore_atom_values,MAPPING_MAX_ITERATIONS

SCALARS=['PMI1','PMI2','PMI3','PBF','volume_A3','SASA_total_A2']


def one(frame):
    result={'record_id':frame['record_id'],'source_reference':frame['source_reference'],
        'source_reference_row':frame['source_reference_row'],'total_atoms':len(frame['atomic_numbers']),
        'model_smiles':None,'model_to_reference':None,'reference_bond_pairs':None,
        'SASA_atom_A2':None,'issues':[],'state':'REFERENCE_MAPPING_UNRESOLVED',
        **{key:None for key in SCALARS},'D3_valid_mask':[False]*7}
    try:
        bound=map_reference(frame['smiles'],frame['atomic_numbers'],frame['coordinates_A'])
        d20=frame.get('D20') or {'names':D20_NAMES,'values':[float('nan')]*20,'valid_mask':[False]*20,'issues':['D20_SOURCE_PENDING']}
        d3,issues=geometry_descriptors(bound['model_smiles'],bound['model_mol'],bound['model_atomic_numbers'],
            bound['model_coordinates_A'],d20)
        result.update({key:d3.get(key) for key in SCALARS})
        result.update(model_smiles=bound['model_smiles'],model_to_reference=bound['model_to_reference'],
            reference_bond_pairs=bound['reference_bond_pairs'],
            SASA_atom_A2=restore_atom_values(d3.get('SASA_atom_A2'),bound['model_to_reference']),issues=issues)
        valid=[result[key] is not None and math.isfinite(result[key]) for key in SCALARS]
        valid.append(result['SASA_atom_A2'] is not None)
        result['D3_valid_mask']=valid
        result['state']='D3_READY' if all(valid) else 'D3_PARTIAL_PROPERTIES'
    except Exception as exc:result['issues']=[type(exc).__name__+':'+str(exc)]
    return result


def configuration(root,group,ppe_domain=None):
    d20=root/'labels/reference_D20/job_4536481'/(group+'.parquet')
    if group=='C7H10O2':
        return root/'reference/C7H10O2/job_4536463/all_rows.parquet',root/'reference/C7H10O2/job_4536463/reference.parquet',d20
    if group in ('NMRShiftDB2_13C','NMRShiftDB2_1H'):
        name='carbon.parquet' if group.endswith('13C') else 'hydrogen.parquet'
        return root/'domain/NMRShiftDB2/job_4536470'/name,root/'reference/NMRShiftDB2/job_4536439'/name,d20
    if group=='PPE1694' and ppe_domain is not None:
        manifest=json.loads(Path(ppe_domain).read_text())
        return Path(manifest['records']),root/'reference/PPE1694/job_4536464/reference.parquet',d20
    raise ValueError('Explicit closed source domain is required for this reference group')


def frames(domain,reference,d20,group):
    domains=pq.read_table(domain,columns=['record_id','source_row','model_smiles','domain_eligible']).to_pylist()
    by_key={}
    for row in domains:
        if row['domain_eligible']:
            key=row['source_row'] if group.startswith('NMRShiftDB2_') else row['record_id']
            if key in by_key:raise ValueError('Reference/domain identity is not unique')
            by_key[key]=row
    descriptors={}
    if d20.is_file():
        for row in pq.read_table(d20).to_pylist():
            if row['D20_values'] is not None:
                descriptors[row['record_id']]={'names':row['D20_names'],'values':row['D20_values'],
                    'valid_mask':row['D20_valid_mask'],'issues':row['issues']}
    key_column='source_row' if group.startswith('NMRShiftDB2_') else 'record_id'
    columns=[key_column,'atomic_numbers','coordinates_A'];seen=set();ordinal=0
    for batch in pq.ParquetFile(reference).iter_batches(batch_size=64,columns=columns):
        for ref in batch.to_pylist():
            index=ordinal;ordinal+=1;key=ref[key_column]
            if key not in by_key:continue
            row=by_key[key]
            if key in seen:raise ValueError('Reference row identity repeated')
            seen.add(key)
            yield {'record_id':row['record_id'],'smiles':row['model_smiles'],'source_reference':str(reference),
                'source_reference_row':index,'atomic_numbers':ref['atomic_numbers'],'coordinates_A':ref['coordinates_A'],
                'D20':descriptors.get(row['record_id'])}
    if seen!=set(by_key):raise ValueError('Accepted source domain has missing reference geometries')


def initialize():
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[key]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    from .downstream_science import load
    load()


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--groups',nargs='+',required=True);p.add_argument('--ppe-domain',type=Path)
    p.add_argument('--attempt',required=True);p.add_argument('--quota-snapshot',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    if os.environ.get('SLURM_JOB_PARTITION')!='cpu' or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers:
        raise RuntimeError('Actual CPU allocation required')
    def admit():
        waiting=False
        while True:
            try:
                capacity(a.root,a.quota_snapshot,134217728)
                if waiting:print('REFERENCE_D3_DISK_RESUMED',flush=True)
                return
            except (OSError,ValueError,KeyError,RuntimeError) as exc:
                if not waiting:print('REFERENCE_D3_DISK_WAIT',repr(exc),flush=True)
                waiting=True;time.sleep(2)
    admit();out=a.root/'labels/reference_D3'/a.attempt;out.mkdir(parents=True,exist_ok=False)
    schema=pa.schema([('record_id',pa.string()),('source_reference',pa.string()),('source_reference_row',pa.int64()),
        ('total_atoms',pa.int32()),('model_smiles',pa.string()),('model_to_reference',pa.list_(pa.int32())),
        ('reference_bond_pairs',pa.list_(pa.list_(pa.int32(),2))),
        *[pa.field(key,pa.float64()) for key in SCALARS],('SASA_atom_A2',pa.list_(pa.float64())),
        ('D3_valid_mask',pa.list_(pa.bool_())),('issues',pa.list_(pa.string())),('state',pa.string())])
    reports=[]
    with ProcessPoolExecutor(max_workers=a.workers,mp_context=mp.get_context('spawn'),initializer=initialize) as pool:
        for group in a.groups:
            domain,reference,d20=configuration(a.root,group,a.ppe_domain)
            states=Counter();buffer=[];count=0;path=out/(group+'.parquet')
            with pq.ParquetWriter(path,schema,compression='zstd') as writer:
                for row in pool.map(one,frames(domain,reference,d20,group),chunksize=8):
                    buffer.append(row);states[row['state']]+=1;count+=1
                    if len(buffer)>=256:
                        admit();writer.write_table(pa.Table.from_pylist(buffer,schema=schema));buffer.clear()
                    if count%4096==0:print('REFERENCE_D3_PROGRESS',group,count,dict(states),flush=True)
                if buffer:admit();writer.write_table(pa.Table.from_pylist(buffer,schema=schema))
            report={'dataset':group,'records':str(path),'rows':count,'states':dict(states),'source_domain':str(domain),
                'source_reference':str(reference),'D20_recomputed':False}
            reports.append(report);print('REFERENCE_D3_CLOSED',report,flush=True)
    report={'status':'REFERENCE_D3_ATTEMPTS_CLOSED_WITH_EXPLICIT_MAPPING_OR_PROPERTY_FAILURES','groups':reports,
        'original_D3_routine':'c_engineering_wire.corrected_base, unchanged parameters and units',
        'graph_mapping':'One RDKit2025.09.5 XYZ2mol pass with known template charge; full named chemical graph and specified stereo match',
        'graph_mapping_max_iterations':MAPPING_MAX_ITERATIONS,'alternative_graph_retries':False,
        'reference_geometries_regenerated':False,'reference_source_atom_order_preserved':True,
        'computation_boundary':'Temporary model-order coordinate gather; all per-atom SASA restored to original reference indices',
        'source_isotopes_without_XYZ_identity':'Explicit unresolved mapping, not guessed',
        'independent_numeric_readback':False,'new_data_content_hashes':False,'P_ready':False}
    admit();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
