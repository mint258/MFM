"""B6 additional physically motivated derivability checks, existing pilot only."""
import argparse,collections,concurrent.futures,json,multiprocessing,os,sys,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011');OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
sys.path.insert(0,str(ROOT/'scripts'));import b_pilot_analysis as base

ELEMENTS={}
def init(elements,barrier):
    global ELEMENTS
    ELEMENTS=elements
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);barrier.wait(timeout=120)
def scan(path):
    import numpy as np,pyarrow.parquet as pq
    from rdkit import Chem
    receipt=json.loads(Path(path).read_text());result=collections.defaultdict(list)
    for row in pq.read_table(receipt['parquet']['path'],columns=['task','status','details_json'],use_threads=False).to_pylist():
        d=json.loads(row['details_json']);v=d.get('values',{});task=row['task']
        if task=='xtb_fod' and base.finite(v.get('NFOD_e')) and v.get('FOD_atom_e'):
            result['NFOD_from_sum_atomic_FOD'].append((float(v['NFOD_e']),float(sum(v['FOD_atom_e']))))
        if task=='pm7_B':
            scalar=v.get('gradient_norm_kcal_mol_A');grad=v.get('gradient_kcal_mol_A')
            if base.finite(scalar) and grad:result['PM7_gradient_norm_from_vector'].append((float(scalar),float(np.linalg.norm(grad))))
            shells=v.get('atomic_shell_population_e');elements=ELEMENTS.get(d['record_id'])
            # Native details identify elements in input_geometry; no chemistry
            # guess or quantum recalculation is used for missing element maps.
            if not elements:elements=d.get('symbols')
            if shells and isinstance(elements,list) and len(shells)==len(elements):
                try:core=np.asarray([Chem.GetPeriodicTable().GetNOuterElecs(int(z)) for z in elements],float)
                except Exception:continue
                predicted=core-np.asarray([sum(x.values()) for x in shells])
                for field in ('net_charges_e','mulliken_charges_e'):
                    value=v.get(field)
                    if isinstance(value,list) and len(value)==len(predicted):result['PM7_'+field+'_from_atomic_shell_populations'].extend((float(x),float(y)) for x,y in zip(value,predicted))
        if task=='xtb_hessian':
            thermo=v.get('thermo_tot_H_cal_mol_Cp_cal_mol_K_S_cal_mol_K_S_J_mol_K')
            if isinstance(thermo,list) and len(thermo)==4 and all(base.finite(x) for x in thermo):result['thermo_entropy_J_from_cal_4_184'].append((float(thermo[3]),float(thermo[2])*4.184))
    return {key:value for key,value in result.items()},os.getpid()
def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=16);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:
        import ast;ast.parse(Path(__file__).read_text());print('AST_PASS_NO_QM_NO_LMDB');return
    if not os.environ.get('SLURM_JOB_ID') or not 16<=a.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK',0)):raise ValueError('SLURM_16_WORKERS_REQUIRED')
    import pyarrow.parquet as pq
    elements={r['record_id']:r['atomic_numbers'] for r in pq.read_table(ROOT/'c_engineering/xyz/analysis_geometry.parquet',columns=['record_id','atomic_numbers']).to_pylist()}
    start=time.monotonic();paths=sorted((OLD/'wp4_native_full_v4').glob('bucket_*/molecules/*/receipt.json'));context=multiprocessing.get_context('spawn');barrier=context.Barrier(a.workers)
    if len(paths)!=1441:raise ValueError('MANIFEST_NATIVE_MOLECULE_MISMATCH')
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=context,initializer=init,initargs=(elements,barrier)) as pool:results=list(pool.map(scan,[str(p) for p in paths],chunksize=1))
    groups=collections.defaultdict(list)
    for data,pid in results:
        for key,pairs in data.items():groups[key].extend(pairs)
    rows=[]
    for key,pairs in groups.items():
        x=[r[0] for r in pairs];y=[r[1] for r in pairs];errors=[abs(a-b) for a,b in pairs];r2=base.r_squared(x,y)
        rows.append({'relationship':key,'numeric_components':len(pairs),'R2':r2,'R2_gt0_9999':r2 is not None and r2>.9999,'absolute_error':base.stats(errors),'exact_float64_equality':all(error==0 for error in errors),'interpretation':'A highR2 alone does not authorize numerical replacement; printed rounding errors and max_abs_error remain explicit.'})
    report={'status':'B6_ADDITIONAL_RELATIONSHIPS_CLOSED','job_id':os.environ['SLURM_JOB_ID'],'actual_worker_pids':sorted({pid for data,pid in results}),'seconds':time.monotonic()-start,'relationships':rows,'atomic_population_note':'Element mapping comes from independently checked original native C5 atom sequence; unsupported map stays unassessed, no Mulliken/Coulson proxy substitution.','no_scientific_values_deleted':True,'POLAR_reinvestigated':False,'QM_calls':0,'LMDB_opened_or_written':False}
    base.save(ROOT/'b_quantum/analysis/B6_additional_relationships.json',report);print(json.dumps({k:report[k] for k in ('status','job_id','seconds')}))
if __name__=='__main__':main()
