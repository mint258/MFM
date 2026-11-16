"""Taskbook 2B: up to eight tight PM7 calls, reuse the original outputs.
Only runs exact original input/version witnesses produced by stage2B_lineage.
"""
import concurrent.futures as cf,hashlib,json,os,pathlib,signal,subprocess,sys,time
from stage0_cohort import R,O,load,save,guard
B=R/'MFM_p_data_information';ENGINE=R/'runs/phase1_wp5_20261011/scripts';sys.path.insert(0,str(ENGINE));import wp5_parser_v2 as parser
from wp5_scf_metadata_v2 import extract_scf

def one(item,root):
 guard();folder=root/(hashlib.sha256(json.dumps([item['molecule_id'],item['native_record_id']]).encode()).hexdigest()[:16]);folder.mkdir(exist_ok=False);original=(pathlib.Path(item['original_input_directory'])/'input.mop').read_bytes();head,body=original.split(b'\n',1);assert b'SCFCRT' not in head.upper();tight=head+b' SCFCRT=0.00001\n'+body;(folder/'input.mop').write_bytes(tight);assert tight.split(b'\n',1)[1]==body
 note=dict(molecule_id=item['molecule_id'],native_record_id=item['native_record_id'],directory=str(folder),original_input_sha256=hashlib.sha256(original).hexdigest(),tight_input_sha256=hashlib.sha256(tight).hexdigest(),changed_only_SCF_keyword=True,timeout_seconds=300,CPUs=1,attempt=1)
 env=dict(os.environ,**item['environment']);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='');started=time.time();process=None
 try:
  (folder/'call_started.json').write_text(json.dumps(dict(started_epoch=started,**note)));guard()
  with (folder/'process.out').open('wb') as output:
   process=subprocess.Popen([item['software']['executable'],'input.mop'],cwd=folder,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
   while process.poll() is None:
    guard()
    if time.time()-started>300:raise TimeoutError('300 second taskbook call limit')
    if sum(p.stat().st_size for p in folder.iterdir() if p.is_file())>256*1024**2:raise OSError('Declared per-call output allowance reached')
    time.sleep(.5)
  note['exit_code']=process.returncode
 except Exception as exc:
  note['failure']=repr(exc)
  if process is not None and process.poll() is None:
   os.killpg(process.pid,signal.SIGTERM)
   try:process.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
 note['elapsed_seconds']=time.time()-started;return note

def main():
 guard();lineage=load(O/'calibration_2B_lineage.json');ready=[p for p in lineage['cases'] if p['task']=='pm7_B' and p['ready']];assert len(ready)<=8 and len({(p['molecule_id'],p['native_record_id']) for p in ready})==len(ready);assert len({p['molecule_id'] for p in ready})<=4;root=O/'calibration_2B_tight';root.mkdir(exist_ok=False)
 configuration=dict(status='TRIGGERED_EXACT_PM7_INPUTS_RECOVERED',planned_new_calls=len(ready),max_new_calls=32,reused_original_outputs=len(ready),max_parallel_calls=4,CPU_per_call=1,timeout_seconds=300,max_CPU_minutes=160,geometry_optimization=False,original_SCFCRT_default=1e-4,tight_SCFCRT=1e-5,parameter_source='https://openmopac.net/Manual/scf_test.html',binary_version='23.0.3',xtb_calls=0,xtb_reason='Independent SCF-only 10x control not recovered; --acc not substituted',cases=[{k:p[k] for k in ['molecule_id','native_record_id','task','protocol_reference','reproduction_package_reference','software','original_input_directory','reconstructed_files','reconstructed_bundle_sha256','original_inputs_exact_hash_match','setting']} for p in ready],external_output_directory=str(root))
 save(B/'configs/p_data_information/calibration_2B.json',configuration);results=[]
 with cf.ThreadPoolExecutor(max_workers=4) as pool:
  futures={pool.submit(one,p,root):p for p in ready}
  for future in cf.as_completed(futures):
   result=future.result();item=futures[future]
   folder=pathlib.Path(result['directory']);files={n:(folder/n).read_bytes() for n in ['input.out','process.out','input.aux'] if (folder/n).exists()};result['SCF']=extract_scf('pm7_B',files)
   if result.get('exit_code')==0:
    try:
     values=parser.parse_mopac(folder,item['symbols']);result['tight_HOF_kcal_mol']=values.get('heat_of_formation_kcal_mol');result['parser_context']=parser.context()
    except Exception as exc:result['parse_failure']=repr(exc)
   results.append(result);save(O/'calibration_2B_actual_calls.json',dict(actual_new_calls=len(results),planned_total=len(ready),original_outputs_reused=True,retries=0,cases=results));print('CALIBRATION_CALL_DONE',len(results),len(ready),'EXIT',result.get('exit_code'),'SCF',result['SCF']['converged'],flush=True)
 configuration.update(actual_new_calls=len(results),status='EXECUTED_PM7_CASES_ONLY');save(B/'configs/p_data_information/calibration_2B.json',configuration);print('CALIBRATION_2B_DONE',len(results),flush=True)
if __name__=='__main__':main()