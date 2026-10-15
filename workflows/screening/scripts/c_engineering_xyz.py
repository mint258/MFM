"""C5 real-source xyz roundtrip and ordered geometry analysis Parquet.

Original LMDB readonly/create=False; no molecular computation or lmdb_1 write.
Data problems produce one explicit issue row and scanning continues. Only an
attempt to write original data or a manifest count mismatch stops the scan.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
import concurrent.futures
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import pickle
import socket
import sys
import tempfile
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
AUDIT=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2')
sys.path[:0]=[str(AUDIT/'deps'),str(AUDIT/'scripts/deps')]
HANDLES={};SOURCES=None

def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):value.update(block)
    return value.hexdigest()

def save(path,value):
    pending=Path(str(path)+'.pending');pending.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');pending.replace(path)

def array(raw,name):
    value=raw.get(name) if isinstance(raw,dict) else getattr(raw,name,None)
    if hasattr(value,'detach'):value=value.detach().cpu().numpy()
    return value

def init(sources,barrier):
    global SOURCES
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    import torch,pyarrow as pa
    torch.set_num_threads(1);pa.set_cpu_count(1);pa.set_io_thread_count(1)
    SOURCES=sources;barrier.wait(timeout=180)

def read(row):
    import lmdb
    sid=int(row['shard_id']);index=int(row['real_index']);source=SOURCES[sid]['path']
    if row.get('source_path') and row['source_path']!=source:raise ValueError('SOURCE_PATH_MISMATCH')
    if sid not in HANDLES:HANDLES[sid]=lmdb.open(source,subdir=False,readonly=True,lock=False,create=False,readahead=False,meminit=False,max_readers=512)
    with HANDLES[sid].begin(buffers=False) as transaction:payload=transaction.get(f'{index:09d}'.encode())
    if payload is None:raise ValueError('SOURCE_RECORD_MISSING')
    if hashlib.sha256(payload).hexdigest()!=row['record_payload_sha256']:raise ValueError('SOURCE_PAYLOAD_SHA_MISMATCH')
    return pickle.loads(payload),payload

def one(row):
    import numpy as np
    from rdkit import Chem
    result={'record_id':row['record_id'],'molecule_id':row['molecule_id'],'conformer_id':row.get('conformer_id'),
        'size_stratum':row['size_stratum'],'heavy_atoms':row.get('heavy_atoms'),'source_path':SOURCES[int(row['shard_id'])]['path'],
        'real_index':int(row['real_index']),'source_payload_sha256':row['record_payload_sha256'],
        'atomic_numbers':None,'elements':None,'positions_A':None,'bond_pairs_zero_based':None,'bond_order_codes':None,
        'native_atom_order_sha256':None,'native_coordinates_sha256':None,'stored_bond_graph_sha256':None,
        'xyz_sha256':None,'xyz_max_error_A':None,'xyz_atom_order_equal':None,'xyz_roundtrip_status':'ERROR',
        'bond_graph_source':'original rdkit_bond_index + rdkit_bond_order; undirected pairs normalized only for analysis',
        'error':None,'bond_graph_error':None,'worker_pid':os.getpid()}
    try:
        raw,payload=read(row);x=np.asarray(array(raw,'x'))
        if not np.isfinite(x).all() or not np.equal(x,np.floor(x)).all():raise ValueError('NONINTEGER_NATIVE_ATOMS')
        z=x.reshape(-1).astype(np.int64)+1;positions=np.asarray(array(raw,'pos'),dtype=np.float64)
        if positions.shape!=(len(z),3) or not np.isfinite(positions).all() or not ((z>=1)&(z<=118)).all():raise ValueError('NATIVE_GEOMETRY_SHAPE_OR_FINITE_ERROR')
        elements=[Chem.GetPeriodicTable().GetElementSymbol(int(item)) for item in z]
        result.update(atomic_numbers=z.tolist(),elements=elements,positions_A=positions.tolist(),
            native_atom_order_sha256=hashlib.sha256(z.astype('<i8').tobytes()).hexdigest(),
            native_coordinates_sha256=hashlib.sha256(positions.astype('<f8').tobytes()).hexdigest())
        text=str(len(z))+'\nC5 native ordered geometry; '+row['record_id']+'\n'
        text+='\n'.join(f'{element} {point[0]:.12f} {point[1]:.12f} {point[2]:.12f}' for element,point in zip(elements,positions))+'\n'
        with tempfile.TemporaryDirectory(prefix='c5xyz_'+str(os.getuid())+'_'+os.environ['SLURM_JOB_ID']+'_',dir='/tmp') as scratch:
            path=Path(scratch)/'native.xyz'
            with path.open('w') as handle:handle.write(text);handle.flush();os.fsync(handle.fileno())
            actual=path.read_text();lines=actual.splitlines();n=int(lines[0]);tokens=[line.split() for line in lines[2:]]
            if n!=len(z) or len(tokens)!=len(z) or any(len(token)!=4 for token in tokens):raise ValueError('XYZ_ROW_COUNT_OR_FORMAT')
            parsed_z=np.asarray([Chem.GetPeriodicTable().GetAtomicNumber(token[0]) for token in tokens],dtype=np.int64)
            reread=np.asarray([[float(value) for value in token[1:]] for token in tokens],dtype=np.float64)
            error=float(np.max(np.abs(reread-positions)));same=bool(np.array_equal(z,parsed_z))
            result.update(xyz_sha256=hashlib.sha256(actual.encode()).hexdigest(),xyz_max_error_A=error,
                xyz_atom_order_equal=same,xyz_roundtrip_status='PASS' if error<1e-6 and same else 'FAIL')
        try:
            indices=np.asarray(array(raw,'rdkit_bond_index'));orders=np.asarray(array(raw,'rdkit_bond_order')).reshape(-1)
            if indices.ndim!=2 or indices.shape[0]!=2 or indices.shape[1]!=len(orders):raise ValueError('STORED_BOND_SHAPE')
            if not np.isfinite(indices).all() or not np.equal(indices,np.floor(indices)).all() or not ((indices>=0)&(indices<len(z))).all():raise ValueError('STORED_BOND_INDICES')
            if not np.isfinite(orders).all() or not np.equal(orders,np.floor(orders)).all():raise ValueError('STORED_BOND_ORDER_CODES')
            indices=indices.astype(np.int64);orders=orders.astype(np.int64)
            result['stored_bond_graph_sha256']=hashlib.sha256(indices.astype('<i8').tobytes()+orders.astype('<i8').tobytes()).hexdigest()
            graph={}
            for (i,j),order in zip(indices.T,orders):
                pair=tuple(sorted((int(i),int(j))))
                if i==j or int(order) not in range(1,6):raise ValueError('STORED_BOND_SELF_OR_ORDER')
                if pair in graph and graph[pair]!=int(order):raise ValueError('STORED_BOND_DUPLICATE_CONFLICT')
                graph[pair]=int(order)
            pairs=sorted(graph);result['bond_pairs_zero_based']=[list(pair) for pair in pairs];result['bond_order_codes']=[graph[pair] for pair in pairs]
        except Exception as exc:result['bond_graph_error']=type(exc).__name__+': '+str(exc)
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
    return result

def schema(pa):
    strings=('record_id','molecule_id','size_stratum','source_path','source_payload_sha256','native_atom_order_sha256',
        'native_coordinates_sha256','stored_bond_graph_sha256','xyz_sha256','xyz_roundtrip_status','bond_graph_source','error','bond_graph_error')
    return pa.schema([(name,pa.string()) for name in strings]+[(name,pa.int64()) for name in ('conformer_id','heavy_atoms','real_index','worker_pid')]+
        [('atomic_numbers',pa.list_(pa.int64())),('elements',pa.list_(pa.string())),('positions_A',pa.list_(pa.list_(pa.float64()))),
        ('bond_pairs_zero_based',pa.list_(pa.list_(pa.int64()))),('bond_order_codes',pa.list_(pa.int64())),
        ('xyz_max_error_A',pa.float64()),('xyz_atom_order_equal',pa.bool_())])

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workers',type=int,default=16)
    parser.add_argument('--panel',default=str(OLD/'wp4_native_panel/pilot_panel.parquet'))
    parser.add_argument('--panel-manifest',default=str(OLD/'wp4_native_panel/pilot_panel_manifest.json'))
    parser.add_argument('--output',default=str(ROOT/'c_engineering/xyz'));parser.add_argument('--check',action='store_true');args=parser.parse_args()
    if args.check:
        ast.parse(Path(__file__).read_text());print(json.dumps({'status':'AST_PASS','LMDB_opened':False,'QM_started':False}));return 0
    if args.workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<args.workers:raise ValueError('16 effective allocated workers required')
    import pyarrow as pa,pyarrow.parquet as pq
    panel=pq.read_table(args.panel).to_pylist();manifest=json.loads(Path(args.panel_manifest).read_text())
    if len(panel)!=manifest['actual_records'] or len({row['record_id'] for row in panel})!=len(panel):raise ValueError('MANIFEST_COUNT_MISMATCH')
    if len(panel)<10000:raise ValueError('MANIFEST_COUNT_LESS_THAN_C5_10000')
    output=Path(args.output).absolute()
    if output.exists() or not output.is_relative_to(ROOT/'c_engineering'):raise ValueError('Fresh analysis-only C5 output required')
    output.mkdir(parents=True);plan=json.loads((AUDIT/'plan.json').read_text());start=time.monotonic()
    context=multiprocessing.get_context('spawn');barrier=context.Barrier(args.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,initializer=init,initargs=(plan['sources'],barrier)) as pool:
        rows=list(pool.map(one,panel,chunksize=4))
    if len(rows)!=len(panel):raise ValueError('MANIFEST_COUNT_MISMATCH')
    path=output/'analysis_geometry.parquet';pq.write_table(pa.Table.from_pylist(rows,schema=schema(pa)),path,compression='zstd')
    counts=Counter(row['xyz_roundtrip_status'] for row in rows);pids=sorted({row['worker_pid'] for row in rows})
    if len(pids)<16:raise ValueError('FEWER_THAN_16_ACTUAL_C5_WORKERS')
    errors=[row['xyz_max_error_A'] for row in rows if row['xyz_max_error_A'] is not None]
    report={'status':'C5_REAL_SOURCE_SCAN_CLOSED','records':len(rows),'molecules':len({row['molecule_id'] for row in rows}),
        'job_id':os.environ['SLURM_JOB_ID'],'hostname':socket.gethostname(),'actual_worker_pids':pids,'statuses':dict(counts),
        'xyz_max_error_A':max(errors) if errors else None,'atom_order_equal_records':sum(row['xyz_atom_order_equal'] is True for row in rows),
        'source_bond_graph_available_records':sum(row['bond_pairs_zero_based'] is not None for row in rows),
        'output':{'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path)},
        'source_panel':{'path':args.panel,'sha256':sha(args.panel)},'source_manifest':{'path':args.panel_manifest,'sha256':sha(args.panel_manifest)},
        'script_sha256':sha(__file__),'seconds':time.monotonic()-start,
        'issues':[{'record_id':row['record_id'],'error':row['error'],'bond_graph_error':row['bond_graph_error'],'xyz_roundtrip_status':row['xyz_roundtrip_status']}
            for row in rows if row['error'] or row['bond_graph_error'] or row['xyz_roundtrip_status']!='PASS'],
        'old_pilot_evidence':'Old native source independently reread xyz positions only, not symbol order; this scan explicitly validates both, using the same .12f wire format.',
        'LMDB_options':{'readonly':True,'lock':False,'create':False},'original_data_written':False,'lmdb_1_created':False,
        'scratch_xyz_deleted':True,'source_geometry_changed':False}
    save(output/'xyz_report.json',report);print(json.dumps({key:report[key] for key in ('status','records','statuses','xyz_max_error_A','atom_order_equal_records')}));return 0

if __name__=='__main__':raise SystemExit(main())
