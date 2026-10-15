#!/usr/bin/env python3
"""Read completed pilot, diagnose ESP and select B1/B3 matched samples."""
from __future__ import annotations
import argparse
import collections
import concurrent.futures as futures
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import sys
import time
sys.dont_write_bytecode=True
OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
NEW=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
sys.path[:0]=[str(OLD/'docs/deps'),'/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps']
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_name(path.name+'.pending');pending.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n');pending.replace(path)
def reason(detail):
    text=' '.join(detail.get('diagnostic_lines',[]))+str(detail.get('failure_reason',''))
    if detail['status']=='TIMEOUT':return 'TIMEOUT'
    if 'd' in text and 'ESP method does not work' in text:return 'D_ORBITAL_UNSUPPORTED'
    if 'SURFAC' in text or 'VAN DER WAALS' in text:return 'SURFACE_GRID_FAILED'
    if 'keyword' in text.lower():return 'KEYWORD_CONFLICT'
    if 'converg' in text.lower() or 'SCF' in text:return 'SCF_FAILED'
    if detail.get('failure_code')=='NUMERIC_PROPERTY_MISSING':return 'MISSING_ESP_OUTPUT'
    return detail.get('failure_code') or detail['status']
def scan(path):
    import pyarrow.parquet as pq
    path=Path(path);receipt=json.loads(path.read_text());ref=receipt['parquet']
    if sha(ref['path'])!=ref['sha256']:raise ValueError('MANIFEST_PARQUET_SHA_MISMATCH')
    table=pq.read_table(ref['path'],columns=['record_id','molecule_id','task','status','details_json'],use_threads=False)
    esp=[];hess=[];pm7={}
    for row in table.to_pylist():
        if row['task'] not in ('pm7_ESP','xtb_hessian','pm7_B'):continue
        detail=json.loads(row['details_json']);detail['pilot_parquet_reference']=ref
        if row['task']=='pm7_ESP':
            esp.append({'record_id':row['record_id'],'molecule_id':row['molecule_id'],'status':row['status'],
              'reason':reason(detail),'elapsed_seconds':detail['elapsed_seconds'],'detail':detail})
        elif row['task']=='xtb_hessian':
            freq=detail.get('values',{}).get('frequencies_cm_inverse')
            usable=row['status']=='SUCCESS' and isinstance(freq,list) and all(math.isfinite(float(x)) for x in freq)
            hess.append({'record_id':row['record_id'],'molecule_id':row['molecule_id'],'status':row['status'],
              'frequencies_cm_inverse':freq if usable else None,'detail':detail,
              'mode_files_retained':[x['name'] for x in detail.get('archived_files',[]) if x['name'] in ('g98.out','hessian','normal_modes','vib_normal_modes')]})
        else:
            pm7[row['record_id']]={'gradient_norm':detail.get('values',{}).get('gradient_norm_kcal_mol_A'),
                                  'HOF':detail.get('values',{}).get('heat_of_formation_kcal_mol')}
    return {'molecule_id':receipt['molecule_id'],'esp':esp,'hess':hess,'pm7':pm7,'worker_pid':os.getpid()}
def sample_balanced(rows,keys,count,seed):
    groups=collections.defaultdict(list)
    for row in rows:groups[tuple(str(row.get(k)) for k in keys)].append(row)
    for key,group in groups.items():group.sort(key=lambda r:hashlib.sha256((str(seed)+'|'+r['record_id']).encode()).hexdigest())
    chosen=[];offsets=collections.Counter()
    while len(chosen)<count:
        progress=False
        for key in sorted(groups):
            offset=offsets[key]
            if offset<len(groups[key]):chosen.append(groups[key][offset]);offsets[key]+=1;progress=True
            if len(chosen)==count:break
        if not progress:raise ValueError('MANIFEST_SAMPLE_POPULATION_TOO_SMALL')
    weights=[{'stratum':list(key),'population':len(groups[key]),'selected':offsets[key],
              'weight':len(groups[key])/offsets[key] if offsets[key] else None} for key in sorted(groups)]
    return chosen,weights
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workers',type=int,default=16);p.add_argument('--seed',type=int,default=20261011)
    p.add_argument('--out',default=str(NEW/'b_quantum/plan'));p.add_argument('--check',action='store_true');args=p.parse_args()
    if args.check:
        import ast;ast.parse(Path(__file__).read_text());print('AST_PASS_NO_DATA_NO_QM');return 0
    if not os.environ.get('SLURM_JOB_ID') or not 16<=args.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK',0)):raise ValueError('SLURM_16_WORKERS_REQUIRED')
    import pyarrow as pa;import pyarrow.parquet as pq
    pa.set_cpu_count(args.workers);pa.set_io_thread_count(args.workers)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    panel_path=OLD/'wp4_native_panel/pilot_panel.parquet';panel=pq.read_table(panel_path).to_pylist();byid={r['record_id']:r for r in panel}
    paths=sorted((OLD/'wp4_native_full_v4').glob('bucket_*/molecules/*/receipt.json'))
    manifest=json.loads((OLD/'wp4_native_panel/pilot_panel_manifest.json').read_text())
    if len(panel)!=manifest['actual_records'] or len(paths)!=manifest['molecules']:raise ValueError('MANIFEST_POPULATION_MISMATCH')
    started=time.monotonic();results=[];errors=[]
    with futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=mp.get_context('spawn')) as pool:
        pending={pool.submit(scan,path):str(path) for path in paths}
        for future in futures.as_completed(pending):
            try:results.append(future.result())
            except Exception as exc:errors.append({'receipt':pending[future],'error':str(exc)})
    if errors:dump(out/'errors.json',errors);raise ValueError('MANIFEST_SCAN_NOT_CLOSED')
    esp=[r for result in results for r in result['esp']];hess=[r for result in results for r in result['hess']]
    if len(esp)!=len(panel) or len({r['record_id'] for r in esp})!=len(panel) or len(hess)!=len(paths):raise ValueError('MANIFEST_TASK_COUNTS_MISMATCH')
    failed=[]
    for item in esp:
        if item['status']=='SUCCESS':continue
        row={**byid[item['record_id']],'esp_failure_reason':item['reason'],'original_esp_status':item['status'],
             'original_esp_detail_json':json.dumps(item['detail'],separators=(',',':'))}
        failed.append(row)
    selected_esp,esp_weights=sample_balanced(failed,('esp_failure_reason','size_stratum'),200,args.seed)
    good_hess=[];pm7={key:value for result in results for key,value in result['pm7'].items()}
    bands=collections.Counter();mol_bands=collections.Counter();mode_known=0
    for item in hess:
        freq=item['frequencies_cm_inverse']
        if freq is None:continue
        nmoderate=sum(-100<=x<-20 for x in freq);ndeep=sum(x<-100 for x in freq)
        bands.update(moderate_20_to_100=nmoderate,below_minus_100=ndeep)
        mol_bands.update(moderate_20_to_100=int(nmoderate>0),below_minus_100=int(ndeep>0),any_imaginary=int(nmoderate+ndeep>0))
        mode_known+=bool(item['mode_files_retained'])
        row={**byid[item['record_id']],'original_imaginary_group':'imaginary' if nmoderate+ndeep else 'no_imaginary',
          'original_frequency_band':'below_minus_100' if ndeep else 'minus100_to_minus20' if nmoderate else 'none',
          'original_PM7_gradient_norm_kcal_mol_A':pm7.get(item['record_id'],{}).get('gradient_norm'),
          'original_hessian_detail_json':json.dumps(item['detail'],separators=(',',':'))}
        good_hess.append(row)
    selected_hess=[];hess_weights=[]
    for group in ('imaginary','no_imaginary'):
        members=[r for r in good_hess if r['original_imaginary_group']==group]
        chosen,weights=sample_balanced(members,('size_stratum','original_frequency_band'),50,args.seed+1)
        selected_hess.extend(chosen);hess_weights.append({'group':group,'strata':weights})
    if len({r['molecule_id'] for r in selected_hess})!=100:raise ValueError('MANIFEST_HESSIAN_NOT_ONE_DISTINCT_MOLECULE_EACH')
    pq.write_table(pa.Table.from_pylist(selected_esp),out/'esp_200.parquet',compression='zstd')
    pq.write_table(pa.Table.from_pylist(selected_hess),out/'hessian_100.parquet',compression='zstd')
    report={'scope':'B1_B3_NATIVE_PILOT_SAMPLING_PLAN','seed':args.seed,'job_id':os.environ['SLURM_JOB_ID'],
      'panel':{'path':str(panel_path),'sha256':sha(panel_path),'records':len(panel),'molecules':len(paths)},
      'source_script_sha256':sha(__file__),'actual_worker_pids':sorted({r['worker_pid'] for r in results}),
      'elapsed_seconds':time.monotonic()-started,'ESP':{'failed_population':len(failed),'reason_counts':dict(collections.Counter(r['esp_failure_reason'] for r in failed)),
        'sample':200,'sampling_weights':esp_weights,'original_call_already_separate':True},
      'hessian':{'successful_population':len(good_hess),'requested_population':len(hess),'frequency_mode_counts':dict(bands),
        'molecule_counts_by_band':dict(mol_bands),'sample':100,'group_counts':{'imaginary':50,'no_imaginary':50},'sampling_weights':hess_weights,
        'original_archived_mode_vector_cases':mode_known,'original_torsion_inference':'UNAVAILABLE_WITHOUT_NORMAL_MODE_VECTORS; frequency alone is insufficient.',
        'new_comparison_groups':['GFN2 --hess on unchanged PM7 coordinates','GFN2 --ohess independently optimized scratch geometry','PM7 FORCE LET NOREOR on unchanged PM7 coordinates']},
      'samples':{name:{'path':str(out/name),'sha256':sha(out/name)} for name in ('esp_200.parquet','hessian_100.parquet')},
      'QM_calls':0,'LMDB_opened':False,'original_outputs_modified':False}
    dump(out/'manifest.json',report);print(json.dumps({k:report[k] for k in ('job_id','elapsed_seconds','ESP','hessian')}))
    return 0
if __name__=='__main__':raise SystemExit(main())
