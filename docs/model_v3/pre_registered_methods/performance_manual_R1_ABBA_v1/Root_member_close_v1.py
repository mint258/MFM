"""Root closes one actual standalone R1 ABBA member using metadata and stat only."""
import argparse,hashlib,json,stat,subprocess,time
from pathlib import Path
B=Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';O=B/'runs/model_v3_20261025'
CODE='9e16d4c5a15c558051499d3dc0c55c9bd3787734';PUBLIC='8147f44baa1ea1ecc3822af7affd0a95401ed248';SERIES='A00_manual_R1_C35_9e16_v1'
def read(p):return json.loads(Path(p).read_bytes())
def ref(p):
 p=Path(p);assert p.suffix not in ('.jsonl','.wandb','.npz','.pt','.lmdb')
 raw=p.read_bytes();assert len(raw)<=2<<20
 return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--position',type=int,choices=(1,2,3,4),required=True);args=p.parse_args()
position=args.position;role=('reference','candidate','candidate','reference')[position-1];F=N/'performance_manual_R1_ABBA_v1'/('member_'+str(position));D=F/'child';C=F/'control'
target=C/'Root_closure_actual_v1.json';assert not target.exists()
submission=C/'Root_submission_actual_v1.json';attempt=read(submission);job=attempt['job_id']
assert attempt['status']=='SUBMITTED' and type(job) is str and job.isdigit()
actual_argv=['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
actual=subprocess.run(actual_argv,capture_output=True,text=True,timeout=30);rows=[x.split('|') for x in actual.stdout.splitlines() if x.split('|')[0]==job]
assert actual.returncode==0 and len(rows)==1 and rows[0][1:4]==['zixiao','COMPLETED','0:0'] and rows[0][5:]==['16','compute-0-21']
paths=dict(configuration=D/'configuration.json',summary=D/'summary.json',run_status=D/'run_status.json',supervisor=F/'supervisor.json')
cfg=read(paths['configuration']);summary=read(paths['summary']);status=read(paths['run_status']);sup=read(paths['supervisor'])
assert sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None and str(sup['job_id'])==job
assert sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[] and sup['foreign_gpu_processes_signalled'] is False
assert status['status']=='STANDALONE_TIMING_COMPLETED' and status['failure'] is None and status['cleanup_errors']==[] and status['stream_cleanup']['errors']==[]
assert summary['status']=='STANDALONE_TIMING_COMPLETED' and summary['measured_updates']==20 and summary['warmup_updates']==2
assert summary['role']==cfg['role']==role and summary['abba_position']==cfg['abba_position']==position and summary['series_id']==cfg['series_id']==SERIES
assert cfg['code_sha']==summary['code_sha']==CODE and cfg['prereg_sha']==summary['prereg_sha']==PUBLIC and cfg['seed']==summary['seed']==0
assert cfg['input']==summary['input']=='native_s' and cfg['smoke'] is summary['smoke'] is False and summary['tracking_mode']=='offline'
projection={k:v for k,v in cfg.items() if k!='configuration_sha256'}
digest=hashlib.sha256(json.dumps(projection,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
assert digest==cfg['configuration_sha256']==summary['configuration_sha256']
pins=N/'performance_manual_R1_ABBA_GPU_v1_source/source_pins.json';source_package=ref(pins);assert source_package['sha256']=='51a5d9c0d8aa5ab708bea6b04d33044e7a555d41e16492dc0e1e0857777aad89'
for row in read(pins)['files']:assert ref(row['path'])==row
for name,sha in read(N/'performance_packaging_CPU_4523705_Root_closure_v1.json')['full_current_source_map'].items():assert ref(name)['sha256']==sha
G=O/'cpu_git_tools_v1/bin/git';W=B/'MFM_model_v3_performance_integration_v1'
assert subprocess.check_output([str(G),'-C',str(W),'rev-parse','HEAD']).decode().strip()==CODE
assert subprocess.check_output([str(G),'-C',str(W),'status','--porcelain=v1'])==b''
run_id=summary['tracking_run_id'];assert type(run_id) is str and len(run_id)==8
sdk,=list((D/'wandb').glob('offline-run-*-'+run_id+'/run-'+run_id+'.wandb'))
assert sdk.is_file() and not sdk.is_symlink() and 0<sdk.stat().st_size<=128<<20
journal=D/'steps.jsonl';assert journal.is_file() and not journal.is_symlink() and 0<journal.stat().st_size<=32<<20
seen=set();physical=0
for item in F.rglob('*'):
 info=item.lstat();identity=(info.st_dev,info.st_ino)
 if stat.S_ISREG(info.st_mode) and identity not in seen:physical+=info.st_size;seen.add(identity)
assert physical+(2<<20)<=2<<30
result=dict(schema='model_v3_Root_single_R1_ABBA_member_closure_v1',status='ACTUAL_C0_SOURCE_INPUT_22_UPDATES_TRAINER_SDK_FINISHED',actual_unix=time.time(),position=position,role=role,series_id=SERIES,job_id=job,source_package=source_package,submission=ref(submission),actual_sacct=dict(argv=actual_argv,returncode=actual.returncode,stdout=actual.stdout,stderr=actual.stderr),**{name:ref(path) for name,path in paths.items()},tracking_run_id=run_id,SDK=dict(path=str(sdk),bytes=sdk.stat().st_size),step_journal=dict(path=str(journal),bytes=journal.stat().st_size),measured_updates=20,warmup_updates=2,input_configuration_and_source_matched=True,trainer_SDK_finish_completed=True,SDK_native_stream_independent_audit_pending=True,step_journal_body_independent_audit_pending=True,Root_SDK_journal_or_model_payload_opened=False,physical_unique_family_stat_bytes=physical,capacity_or_ABBA_speed_acceptance_granted=False,scientific_acceptance=False)
raw=(json.dumps(result,indent=2)+'\n').encode()
with target.open('xb') as f:f.write(raw);f.flush()
print(json.dumps(dict(closure=ref(target),job_id=job,position=position,role=role,independent_SDK_audit_still_pending=True)))
