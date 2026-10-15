"""Independent same-seed rerun and strict float64 coordinate-byte comparison."""
import argparse,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,time
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from prepare import ROOT,save,sha
import sprime_v6 as science

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',default='pilot_v6');a=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    stage=ROOT/a.stage;metas=[];expected_m={};expected_c={}
    for group in range(1,6):
        rows=pq.read_table(stage/f'molecules_group{group}.parquet').to_pylist()
        chosen=sorted(rows,key=lambda r:hashlib.sha256(('sprime-reproduce100:'+r['molecule_id']).encode()).digest())[:20]
        for r in chosen:metas.append(r);expected_m[r['molecule_id']]=r;expected_c[r['molecule_id']]=[]
        ids={r['molecule_id'] for r in chosen}
        for c in pq.read_table(stage/f'conformers_group{group}.parquet',filters=[('molecule_id','in',sorted(ids))]).to_pylist():expected_c[c['molecule_id']].append(c)
    assert len(metas)==100 and len(expected_m)==100
    rows=pq.read_table(ROOT/'prepared/pilot_records.parquet',filters=[('molecule_id','in',sorted(expected_m))],columns=['record_id','molecule_id','source_path','real_index','record_payload_sha256','total_atoms','energy_raw','smiles','QC_molecule_chirality_conflict','QC_molecule_ez_conflict']).to_pylist()
    indexed={m:[] for m in expected_m}
    for r in rows:indexed[r['molecule_id']].append(r)
    tasks=[(indexed[m['molecule_id']],{'molecule_id':m['molecule_id'],'file_group':m['file_group'],'max_heavy_atoms':m['max_heavy_atoms']}) for m in metas]
    results=[]
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=science.worker_init) as pool:
        for actual,confs in pool.map(science.process,tasks):
            mid=actual['molecule_id'];old=expected_m[mid];old_confs=sorted(expected_c[mid],key=lambda c:c['sprime_conf_idx'])
            same_status=actual['status']==old['status'];same_count=len(confs)==len(old_confs)
            checks=[]
            if same_count:
                for new,previous in zip(confs,old_confs):
                    new_xyz=np.asarray(new['coordinates'],dtype='<f8');old_xyz=np.asarray(previous['coordinates'],dtype='<f8')
                    checks.append({'index':new['sprime_conf_idx'],'shape_equal':new_xyz.shape==old_xyz.shape,'coordinate_bytes_equal':new_xyz.tobytes()==old_xyz.tobytes(),'new_sha256':hashlib.sha256(new_xyz.tobytes()).hexdigest(),'old_sha256':hashlib.sha256(old_xyz.tobytes()).hexdigest(),'seed_equal':new['seed']==previous['seed']})
            passed=same_status and same_count and all(c['shape_equal'] and c['coordinate_bytes_equal'] and c['seed_equal'] for c in checks)
            results.append({'molecule_id':mid,'passed':passed,'same_status':same_status,'same_count':same_count,'coordinates_tested':len(checks),'checks':checks,'actual_status':actual['status'],'expected_status':old['status']})
    result={'status':'PASS' if all(r['passed'] for r in results) else 'FAIL','job_id':os.environ['SLURM_JOB_ID'],'molecules':100,'molecules_with_coordinates':sum(r['coordinates_tested']>0 for r in results),'conformers_tested':sum(r['coordinates_tested'] for r in results),'source_sha256':sha(science.__file__),'criterion':'Strict float64 coordinate bytes, seed, count and status; no numerical tolerance','results':results}
    save(ROOT/'reports/pilot_reproduction100.json',result);print(json.dumps({k:v for k,v in result.items() if k!='results'}),flush=True)
    if result['status']!='PASS':raise RuntimeError('SAME_SEED_COORDINATE_REPRODUCTION_FAILED')

if __name__=='__main__':main()
