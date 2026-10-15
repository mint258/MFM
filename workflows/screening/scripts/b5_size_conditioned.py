"""B5 supplement: size-conditioned ICC and correct invariant quadrupole metrics."""
from __future__ import annotations
import argparse,collections,concurrent.futures,importlib.util,json,multiprocessing,os,sys,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
sys.path.insert(0,str(ROOT/'scripts'));import b_pilot_analysis as base
_original_feature=base.feature

def invariant_feature(value,path,geom):
    import numpy as np
    if path.endswith('molecular_quadrupole_traceless_au') and isinstance(value,list) and len(value)==6:
        xx,xy,yy,xz,yz,zz=value;matrix=np.asarray([[xx,xy,xz],[xy,yy,yz],[xz,yz,zz]],float)
        return {'frobenius':float(np.linalg.norm(matrix)),**{'eigenvalue'+str(i):float(x) for i,x in enumerate(np.linalg.eigvalsh(matrix))}}
    return _original_feature(value,path,geom)
base.feature=invariant_feature

def scan(arg):
    result=base.scan(arg);receipt=json.loads(Path(arg[0]).read_text());r=next(iter(base.GEOMS[result['molecule_id']].values()))
    return {'molecule_id':result['molecule_id'],'size_stratum':r['size_stratum'],'icc':result['icc'],'worker_pid':result['worker_pid'],'aligned':result['atom_graph_alignment_assessed']}

def compute(items):
    import numpy as np
    ns=np.asarray([r[0] for r in items],float);means=np.asarray([r[1] for r in items]);N=ns.sum();k=len(items)
    if k<2:return None
    mean=float((ns*means).sum()/N);within=sum(r[2] for r in items)/(N-k);betweenMS=float((ns*(means-mean)**2).sum()/(k-1));n0=float((N-(ns*ns).sum()/N)/(k-1));between=(betweenMS-within)/n0;positive=max(between,0.)
    return {'molecules':k,'records':int(N),'within_variance':float(within),'within_sd':float(within**.5),'between_variance_raw':float(between),'between_variance_nonnegative':float(positive),'ICC':float(positive/(positive+within)) if positive+within else None,'within_fraction':float(within/(positive+within)) if positive+within else None,'within_over_between':float(within/positive) if positive else None,'median_molecule_within_sd':float(np.median([(r[2]/(r[0]-1))**.5 for r in items])),'p90_molecule_within_sd':float(np.quantile([(r[2]/(r[0]-1))**.5 for r in items],.9))}

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=32);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:
        import ast;ast.parse(Path(__file__).read_text());print('AST_PASS_NO_QM_NO_LMDB');return
    if not os.environ.get('SLURM_JOB_ID') or not 16<=a.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK',0)):raise ValueError('SLURM_16_WORKERS_REQUIRED')
    import pyarrow as pa,pyarrow.parquet as pq
    start=time.monotonic();out=ROOT/'b_quantum/analysis/B5_size_conditioned';out.mkdir(parents=True,exist_ok=False)
    geometry=pq.read_table(ROOT/'c_engineering/xyz/analysis_geometry.parquet').to_pylist();geoms={}
    for r in geometry:geoms.setdefault(r['molecule_id'],{})[r['record_id']]=r
    paths=sorted((OLD/'wp4_native_full_v4').glob('bucket_*/molecules/*/receipt.json'))
    if len(paths)!=1441 or len(geometry)!=10020:raise ValueError('MANIFEST_GEOMETRY_NATIVE_COUNTS_MISMATCH')
    context=multiprocessing.get_context('spawn');barrier=context.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=context,initializer=base.init,initargs=(geoms,[],barrier)) as pool:results=list(pool.map(scan,[(str(p),None) for p in paths],chunksize=1))
    registry=json.loads((ROOT/'reports/label_registry.json').read_text())['entries'];wanted={(e['task'],e['source_path']):e for e in registry if e['classification']=='physical_label' and (e['task'].startswith('xtb_') or e['task'] in ('pm7_water','pm7_octanol','pm7_cation','pm7_anion') or 'derived_from_same_geometry' in e['source_path'])}
    accum=collections.defaultdict(list)
    for r in results:
        for t,p,site,n,mean,ss in r['icc']:
            if (t,p) not in wanted:continue
            accum[('all',t,p,site)].append((n,mean,ss));accum[(r['size_stratum'],t,p,site)].append((n,mean,ss))
    components=[]
    for (s,t,p,site),items in accum.items():
        value=compute(items)
        if value:components.append({'size_stratum':s,'task':t,'source_path':p,'component':site,**value})
    pq.write_table(pa.Table.from_pylist(components),out/'ICC_components.parquet',compression='zstd')
    grouped=collections.defaultdict(list)
    for r in components:grouped[(r['size_stratum'],r['task'],r['source_path'])].append(r)
    summaries=[]
    for (s,t,p),rows in sorted(grouped.items()):
        summaries.append({'size_stratum':s,'task':t,'source_path':p,'components':len(rows),'components_with_within_fraction_gt10pct':sum(r['within_fraction'] is not None and r['within_fraction']>.1 for r in rows),'within_fraction':base.stats([r['within_fraction'] for r in rows]),'within_sd':base.stats([r['within_sd'] for r in rows]),'molecule_within_sd_median':base.stats([r['median_molecule_within_sd'] for r in rows]),'minimum_molecules':min(r['molecules'] for r in rows),'unit':wanted[(t,p)]['unit']})
    report={'status':'B5_SIZE_CONDITIONED_CLOSED','job_id':os.environ['SLURM_JOB_ID'],'seconds':time.monotonic()-start,'actual_worker_pids':sorted({r['worker_pid'] for r in results}),'aligned_molecules':sum(r['aligned'] for r in results),'labels':summaries,'not_estimable_from_pilot':[{'task':t,'source_path':p} for t,p in wanted if not any(k[1:]==(t,p) for k in grouped)],'ICC_definition':'Same unbalanced one-way ANOVA as base B5, evaluated globally and within each heavy-atom stratum. Arrays reported per common native site; unsupported or absent sites never zero.','quadrupole_definition':'Official xTB six-vector xx,xy,yy,xz,yz,zz converted to symmetric3x3; Frobenius norm and eigenvalues invariant under rigid rotation. This supersedes base component_norm_proxy for quadrupole.','dipole_definition':'Dipole magnitude; component-direction sensitivity and charged-molecule origin effects not assessed. Low norm ICC variation cannot prove full vector direction is conformer-insensitive.','coverage_interpretation':'A small global within/between ratio can follow the large size range; decisions should use within-size ICC and within-molecule SD in physical units. Pilot1441 molecules contain minimum-only Hessian and sparse labels; lack of repeated Hessian modes is not zero sensitivity.','documentation':'https://xtb-docs.readthedocs.io/en/latest/properties.html'}
    base.save(out/'report.json',report);print(json.dumps({k:report[k] for k in ('status','job_id','seconds','aligned_molecules')}))
if __name__=='__main__':main()
