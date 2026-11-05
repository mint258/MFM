"""Rejudge saved arrays only. No model, Torch, new forward, or candidate adoption."""
from __future__ import annotations
import argparse,csv,hashlib,json,os,re,socket,time,zipfile
from pathlib import Path

def need(ok,msg):
    if not ok:raise ValueError(msg)
def read(path):
    p=Path(path);need(p.is_absolute() and p.is_file() and not p.is_symlink() and p.stat().st_size<=2<<20,'Small ordinary JSON only')
    return json.loads(p.read_bytes(),parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
def at(value,keys):
    for key in keys:value=value[key]
    return value

def metrics(actual,reference,kind):
    import numpy as np
    need(actual.shape==reference.shape and actual.ndim==2 and actual.size>0,'Corresponding nonempty matrices required')
    finite=bool(np.isfinite(actual).all() and np.isfinite(reference).all())
    if not finite:return dict(elements=int(actual.size),failed_elements=int(actual.size),passed=False,finite=False,maxabs=None,max_scaled_error=None,infinite_scaled_error=False,zero_reference_nonzero_delta=None,actual_at_worst=None,reference_at_worst=None,threshold_at_worst=None,row=None,component=None)
    delta=np.abs(actual-reference);tol=(1e-6+1e-4*np.abs(reference)) if kind=='fp32_terminals' else 1e-9*np.abs(reference)
    failed=delta>tol;zero_bad=(reference==0)&(delta!=0)
    scaled=np.zeros_like(delta);np.divide(delta,tol,out=scaled,where=tol!=0)
    infmask=(tol==0)&(delta!=0);scaled[infmask]=np.inf
    flat=int(scaled.reshape(-1).argmax());row,col=divmod(flat,actual.shape[1]);worst=float(scaled[row,col])
    return dict(elements=int(actual.size),failed_elements=int(failed.sum()),passed=not bool(failed.any()),finite=True,maxabs=float(delta.max()),max_scaled_error=None if not np.isfinite(worst) else worst,infinite_scaled_error=not np.isfinite(worst),zero_reference_nonzero_delta=int(zero_bad.sum()),actual_at_worst=float(actual[row,col]),reference_at_worst=float(reference[row,col]),threshold_at_worst=float(tol[row,col]),row=row,component=col)

def archive(raw,kind):
    import numpy as np
    p=Path(raw['path']);limit=512<<10 if kind=='fp32_terminals' else 4<<20
    need(p.is_absolute() and p.is_file() and not p.is_symlink() and p.stat().st_uid==1278 and p.stat().st_nlink==1 and p.stat().st_size==raw['bytes']<=limit,'Bounded owned saved NPZ only')
    before=p.stat();need(hashlib.sha256(p.read_bytes()).hexdigest()==raw['sha256'],'Existing saved archive raw SHA differs')
    with zipfile.ZipFile(p) as z:
        items=z.infolist();need(len(items)==(52 if kind=='fp32_terminals' else 4) and all(i.filename.endswith('.npy') and '/' not in i.filename and i.file_size<=2<<20 for i in items) and sum(i.file_size for i in items)<=2<<20,'Bounded numeric archive entries')
    with np.load(p,allow_pickle=False) as z:values={key:z[key] for key in z.files}
    after=p.stat();need((before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),'Saved archive changed')
    return values

FIELDS={'PD/p_extensive':'invariant','PD/p_intensive':'invariant','PD/d_intensive':'invariant','PD/d_binary':'invariant','PD/d_atom':'invariant','PD/p_pair':'invariant','PD/p_gradient':'vector','PD/p_dipole':'vector','PD/p_dipole_magnitude':'invariant','S/noise':'vector','S/coordinate':'coordinate','S/element_logits':'invariant','S/clean_bond_logits':'invariant'}
TRANSFORMS=['general_rotation','translation_only','other_rotation_and_translation']

def fp32_case(entry,path):
    import numpy as np
    record=read(path);m=at(record,entry['measurement_path']);case_id=m['case_id'];raw=m['actual_terminal_output_artifact']
    need(raw is not None and raw.get('contains_native_data') is False and raw.get('contains_parameter_weights') is False,'Saved synthetic terminal arrays required')
    values=archive(raw,'fp32_terminals');want={prefix+'__'+field.replace('/','__') for prefix in ('original','transform0','transform1','transform2') for field in FIELDS}
    need(set(values)==set(raw['arrays'])==want and len(m['measurements'])==3 and m['complete_terminal_count']==13,'Complete original52/all13/all3 coverage')
    need(all(a.dtype==np.float32 and a.ndim==2 and list(a.shape)==raw['arrays'][k]['shape'] and raw['arrays'][k]['dtype']=='float32' for k,a in values.items()),'Saved true FP32 terminal header/dtype')
    need(sum(a.nbytes for a in values.values())<=320<<10,'Original numeric array bound')
    domain=m['domain']['domain_pass'];need(type(domain) is bool,'Recorded domain boolean')
    out=[]
    for ti,t in enumerate(m['measurements']):
        tr=t['transform'];need(tr['name']==TRANSFORMS[ti] and tr['row_vector_rule']=='x @ R + t','Original exact transform/order/convention')
        rotation=np.asarray(tr['rotation_float64'],dtype=np.float64);shift=np.asarray(tr['translation_A'],dtype=np.float64)
        need(rotation.shape==(3,3) and shift.shape==(3,) and np.isfinite(rotation).all() and np.isfinite(shift).all(),'Recorded finite rigid transform')
        old={f['field']:f for f in t['fields']};need(set(old)==set(FIELDS) and type(t['vector_edges_unchanged']) is bool,'Original field/domain coverage')
        for field,law in FIELDS.items():
            f=old[field];need(f['law']==law,'Original field covariance law')
            base=values['original__'+field.replace('/','__')].astype(np.float64);actual=values['transform'+str(ti)+'__'+field.replace('/','__')].astype(np.float64)
            reference=base if law=='invariant' else base@rotation
            if law=='coordinate':reference=reference+shift
            result=metrics(actual,reference,'fp32_terminals')
            floor=f['nonzero_norm_floor'];need(type(floor) in (int,float) and floor>=0,'Original nonzero-domain floor')
            nonzero=(float(np.linalg.norm(base,axis=-1).max())>floor and float(np.linalg.norm(actual,axis=-1).max())>floor) if f['nonzero_required'] else True
            eligible=domain and t['vector_edges_unchanged'] and nonzero
            out.append(dict(cohort=entry['name'],case_id=case_id,precision_scope='FP32_saved_terminals',transform=tr['name'],field=field,law=law,unit=f['unit'],historical_domain_eligible=eligible,v2_with_existing_domain_pass=bool(result['passed'] and eligible),**result))
    return case_id,out,bool(m['passed'])

def h0_case(entry,path):
    import numpy as np
    m=read(path);raw=m['FP64_clean_H0']['file'];values=archive(raw,'fp64_h0');need(set(values)=={'role0_clean_H0','role1_clean_H0','role2_clean_H0','role3_clean_H0'},'Four complete saved FP64 H0 roles')
    need(all(a.dtype==np.float64 and a.shape==(44,512) for a in values.values()),'Actual saved FP64 clean H0 shape')
    rows=[];base=values['role0_clean_H0']
    for i,name in enumerate(TRANSFORMS):
        result=metrics(values['role%d_clean_H0'%(i+1)],base,'fp64_h0')
        rows.append(dict(cohort=entry['name'],case_id=m['case_id'],precision_scope='FP64_H0_only_original_inputs_generated_in_FP32_then_promoted',transform=name,field='H0_clean44',law='invariant',unit='embedding',historical_domain_eligible=True,v2_with_existing_domain_pass=result['passed'],**result))
    return m['case_id'],rows,None

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID','').isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16 and os.environ.get('CUDA_VISIBLE_DEVICES')=='','Actual owned CPU>=16 Slurm with CUDA hidden required')
    node=socket.gethostname().split('.')[0];need(node==os.environ['MODEL_V3_EXPECTED_NODE'] and re.fullmatch(r'compute-0-(?:2|[89]|1[0-9])',node),'Actual authorized expected CPU node')
    need(re.search(r'(?:job[_/-])'+re.escape(os.environ['SLURM_JOB_ID'])+r'(?:/|\n|$)',Path('/proc/self/cgroup').read_text()) is not None,'Own job cgroup')
    req=read(a.request);need(req['schema']=='saved_equivariance_v2_rejudge_request_v1' and req['fp32_atol']==1e-6 and req['fp32_rtol']==1e-4 and req['fp64_rtol']==1e-9,'Explicit new rule, no epsilon')
    need(not a.output.exists() and a.output.parent.resolve()==a.output.parent,'Fresh output only');a.output.mkdir(mode=0o700)
    expected=set(req['expected_case_ids']);need(len(expected)==48,'Complete frozen48 identities');all_rows=[];summaries=[];started=time.monotonic()
    for entry in req['cohorts']:
        seen=set();cases=[];errors=[]
        for path in entry['case_json_paths']:
            try:
                need(time.monotonic()-started<req['worker_deadline_seconds'],'Finite worker deadline')
                cid,rows,old=(fp32_case if entry['kind']=='fp32_terminals' else h0_case)(entry,path)
                need(cid in expected and cid not in seen,'Exact unique original case identity');seen.add(cid);all_rows.extend(rows)
                cases.append(dict(case_id=cid,old_recorded_passed=old,v2_error_pass=all(r['passed'] for r in rows),v2_with_original_domain_pass=all(r['v2_with_existing_domain_pass'] for r in rows),failed_elements=sum(r['failed_elements'] for r in rows)))
            except Exception as e:errors.append(dict(case_json=path,type=type(e).__name__,reason=str(e)))
        complete=seen==expected and not errors
        summaries.append(dict(name=entry['name'],kind=entry['kind'],original_job=entry['job_id'],available_cases=len(seen),expected_cases=48,complete=complete,case_pass=sum(r['v2_error_pass'] for r in cases),case_fail=sum(not r['v2_error_pass'] for r in cases),cases=cases,errors=errors,compensation_adoption='NOT_ADOPTED_ARCHIVE_ONLY' if entry.get('compensation_history') else 'NO_ADOPTION_DECISION_BY_REJUDGE',FP64_terminal_status='UNPROVEN_TERMINAL_REFERENCE_ARRAYS_NOT_SAVED' if entry['kind']=='fp64_h0' else None,pure_FP64_math_claimed=False))
    columns=['cohort','case_id','precision_scope','transform','field','law','unit','elements','failed_elements','passed','finite','maxabs','max_scaled_error','infinite_scaled_error','zero_reference_nonzero_delta','row','component','actual_at_worst','reference_at_worst','threshold_at_worst','historical_domain_eligible','v2_with_existing_domain_pass']
    with (a.output/'field_results.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(all_rows)
    result=dict(schema='saved_equivariance_v2_rejudge_summary_v1',status='REJUDGED_AVAILABLE_SAVED_ARRAYS' if all(r['complete'] for r in summaries) else 'INCOMPLETE_SAVED_INPUTS_HOLD',rules=dict(FP32='abs(actual-reference)<=1e-6+1e-4*abs(reference)',FP64='abs(actual-reference)<=1e-9*abs(reference); zero reference requires exact zero delta; no epsilon'),reference='Original field law from 0c49: invariant base; vector base@recorded_R64; coordinate base@recorded_R64+recorded_t64, all comparisons FP64',CSV_rows=len(all_rows),cohorts=summaries,known_unprovable=req['known_unprovable'],new_model_or_forward_or_matrix_run=False,compensation_adopted=False,old_results_unchanged=True,actual_job_id=os.environ['SLURM_JOB_ID'],seconds=time.monotonic()-started)
    with (a.output/'summary.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
    need((a.output/'field_results.csv').stat().st_size+(a.output/'summary.json').stat().st_size<=128<<20,'Bounded report output')
    print(json.dumps(dict(status=result['status'],cohorts=len(summaries),rows=len(all_rows),summary=str(a.output/'summary.json'))));return int(result['status']!='REJUDGED_AVAILABLE_SAVED_ARRAYS')
if __name__=='__main__':raise SystemExit(main())