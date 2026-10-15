"""B5 array complement: permutation-invariant molecule summaries, size ICC."""
from __future__ import annotations
import argparse,collections,concurrent.futures,json,math,multiprocessing,os,sys,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011');OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
sys.path.insert(0,str(ROOT/'scripts'));import b_pilot_analysis as base
import b5_size_conditioned as size
WANTED={}
def init(wanted,barrier):
    global WANTED
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);WANTED=wanted;barrier.wait(timeout=120)
def summaries(value,path):
    import numpy as np
    if base.finite(value):return {'scalar':float(value)}
    if path.endswith('molecular_quadrupole_traceless_au') or path.endswith('dipole_Debye'):
        return size.invariant_feature(value,path,None)
    if isinstance(value,list) and value and all(isinstance(x,dict) for x in value):
        columns=collections.defaultdict(list)
        for row in value:
            for key,x in row.items():
                if key in ('i','j','atom_index','atom_i','atom_j','basis_i','basis_j'):continue
                if base.finite(x):columns[key].append(float(x))
                elif isinstance(x,list) and all(base.finite(y) for y in x):
                    for j,y in enumerate(x):columns[key+':'+str(j)].append(float(y))
    else:
        try:a=np.asarray(value,dtype=float)
        except (ValueError,TypeError):return {}
        if not a.size or not np.isfinite(a).all():return {}
        if a.ndim==2 and a.shape[1] in (3,):columns={str(j):a[:,j].tolist() for j in range(a.shape[1])}
        else:columns={'all':a.ravel().tolist()}
    result={}
    for name,values in columns.items():
        a=np.asarray(values,float)
        if not len(a):continue
        result.update({name+':mean':float(a.mean()),name+':RMS':float(np.sqrt(np.mean(a*a))),name+':minimum':float(a.min()),name+':maximum':float(a.max())})
    return result

def scan(path):
    import numpy as np,pyarrow.parquet as pq
    receipt=json.loads(Path(path).read_text());groups=collections.defaultdict(list);s=None;count=0
    for row in pq.read_table(receipt['parquet']['path'],columns=['task','size_stratum','details_json'],use_threads=False).to_pylist():
        count+=1;s=row['size_stratum'];task=row['task'];d=json.loads(row['details_json']);valid=d.get('status')=='SUCCESS' or (task=='pm7_B' and d.get('B_base_success'))
        if not valid:continue
        for path_,value in base.fields(d.get('values',{})):
            if (task,path_) not in WANTED or not base.present(value):continue
            for key,x in summaries(value,path_).items():groups[(task,path_,key)].append(x)
    stats=[]
    for (task,path_,feature),values in groups.items():
        if len(values)<2:continue
        a=np.asarray(values,float);stats.append((task,path_,feature,len(a),float(a.mean()),float(((a-a.mean())**2).sum())))
    return {'molecule_id':receipt['molecule_id'],'size_stratum':s,'stats':stats,'worker_pid':os.getpid(),'source_rows':count}
def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=16);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:
        import ast;ast.parse(Path(__file__).read_text());print('AST_PASS_NO_QM_NO_LMDB');return
    if not os.environ.get('SLURM_JOB_ID') or not 16<=a.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK',0)):raise ValueError('SLURM_16_WORKERS_REQUIRED')
    import pyarrow as pa,pyarrow.parquet as pq
    start=time.monotonic();out=ROOT/'b_quantum/analysis/B5_molecule_invariants';out.mkdir(parents=True,exist_ok=False)
    registry=json.loads((ROOT/'reports/label_registry_v2.json').read_text())['entries'];wanted={(e['task'],e['source_path']):e for e in registry if e['classification']=='physical_label' and not e['excluded'] and (e['task'].startswith('xtb_') or e['task'] in ('pm7_cation','pm7_anion','pm7_water','pm7_octanol') or 'derived_from_same_geometry' in e['source_path'])}
    paths=sorted((OLD/'wp4_native_full_v4').glob('bucket_*/molecules/*/receipt.json'))
    if len(paths)!=1441:raise ValueError('MANIFEST_MOLECULE_COUNT_MISMATCH')
    context=multiprocessing.get_context('spawn');barrier=context.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=context,initializer=init,initargs=(wanted,barrier)) as pool:results=list(pool.map(scan,[str(p) for p in paths],chunksize=1))
    if sum(r['source_rows'] for r in results)!=131701:raise ValueError('MANIFEST_NATIVE_SLOT_MISMATCH')
    groups=collections.defaultdict(list)
    for r in results:
        for task,path_,feature,n,mean,ss in r['stats']:
            for s in ('all',r['size_stratum']):groups[(s,task,path_,feature)].append((n,mean,ss))
    rows=[]
    for (s,t,p,f),items in groups.items():
        estimate=size.compute(items)
        if estimate:rows.append({'size_stratum':s,'task':t,'source_path':p,'feature':f,'unit':wanted[(t,p)]['unit'],**estimate})
    pq.write_table(pa.Table.from_pylist(rows),out/'molecule_summary_ICC.parquet',compression='zstd')
    report={'status':'B5_MOLECULE_SUMMARY_CLOSED','job_id':os.environ['SLURM_JOB_ID'],'seconds':time.monotonic()-start,'actual_worker_pids':sorted({r['worker_pid'] for r in results}),'source_records':10020,'source_molecules':1441,'labels':rows,'definition':'One-way unbalanced ANOVA between actual molecules, evaluated on permutation-invariant molecular mean/RMS/extrema of each array channel. Vector dipole uses magnitude; quadrupole uses true3x3 invariant metrics. Sparse pair distributions use present entries only; varying cutoff membership is part of that scalar summary, not an imputed zero.','relation_to_site_analysis':'Companion native-site within-conformer SD is meaningful because1441/1441 source atom graphs match. Cross-molecule same-index site ICC is exploratory and depends on source atom order/types; it cannot alone determine array-label coverage. Molecular summaries provide actual between-molecule invariants but can miss redistributions that preserve moments. Both views retained, no unsupported all-vector claim.','not_estimable_labels':[{'task':t,'source_path':p} for (t,p) in wanted if not any(r['task']==t and r['source_path']==p for r in rows)],'perturbed_geometry_note':'Noise-seeded PERT forces include perturbation variability as well as conformer variability; not pure native conformer ICC.','new_QM_calls':0,'LMDB_opened_or_written':False}
    base.save(out/'report.json',report);print(json.dumps({k:report[k] for k in ('status','job_id','seconds')}))
if __name__=='__main__':main()
