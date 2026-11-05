import ast,json,os,pathlib,re,subprocess,sys,time
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
def run(argv,env=None):
 r=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30,env=env)
 assert r.returncode==0,(argv,r.stderr[-1500:])
 return r.stdout
import argparse,shlex
a=argparse.ArgumentParser();a.add_argument('--old',choices=['4520405','4520486','4520411','4520456','4520549','4520438'],required=True);a.add_argument('--node',choices=['compute-0-2','compute-0-19'],required=True);a=a.parse_args()
P=N/('R1v3_old'+a.old+'_speed_report_CPU_submit_actual_v4');P.mkdir()
F=N/'performance_remaining_Av2_R1_ABBA_v3'/('cohort_'+a.old)
receipts=[json.loads((F/('member_'+str(i))/'control/Root_submission_actual_v1.json').read_text()) for i in range(1,5)]
assert all(r['status']=='SUBMITTED' and r['position']==i and r['cohort']==a.old for i,r in enumerate(receipts,1))
jobs=[r['job_id'] for r in receipts];assert len(set(jobs))==4
account_argv=['sacct','-X','-n','-P','-j',','.join(jobs),'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
account=run(account_argv);rows=[s.split('|') for s in account.splitlines() if s]
assert len(rows)==4 and {r[0] for r in rows}==set(jobs) and all(r[1:4]==['zixiao','COMPLETED','0:0'] and int(r[4])>0 and r[5]=='16' for r in rows)
with (P/'GPU_four_actual_C0.json').open('x') as f:json.dump(dict(argv=account_argv,returncode=0,stdout=account,stderr=''),f,indent=2)
WORKER=B/'MFM_model_v3_A_acceptance_v2_candidate_v1/tools/model_v3/a_speed_report.py'
SB=P/'run_original_speed_report.sbatch'
NODE=a.node
OUT=N/('R1v3_old'+a.old+'_speed_report_actual_v3')
assert not OUT.exists()
py=B/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
args=[str(py),'-u','-B',str(B/'runs/model_v3_20261025/run_cpu_supervised_v3.py'),'--output-root',str(OUT),'--record',str(OUT)+'.supervisor.json','--wall-seconds','240','--rss-limit-bytes','12884901888','--',str(py),'-u','-B',str(N/'run_original_R1_speed_report_fresh_dir_CPU_v1.py'),'--old',a.old]
SB.write_text('#!/bin/bash\n#SBATCH --job-name=R1v3_original_speed_report\n#SBATCH --partition=cpu\n#SBATCH --cpus-per-task=16\n#SBATCH --time=00:05:00\nset -euo pipefail\nexport CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1\nexec '+' '.join(shlex.quote(x) for x in args)+'\n')

assert os.getuid()==1278 and not os.environ.get('SLURM_JOB_ID')
assert not (P/'SUBMITTED.json').exists(),'No duplicate'
assert not re.search(r'^#SBATCH.*--(?:mem|exclusive)',SB.read_text(),re.M),'Automatic memory/no exclusive'
ast.parse(WORKER.read_text());run(['bash','-n',str(SB)])
node=run(['scontrol','show','node',NODE,'-o']);n=dict(re.findall(r'(CPUAlloc|CPUTot)=(\d+)',node))
assert int(n['CPUTot'])-int(n['CPUAlloc'])>=16
memory=run(['ssh','-n','-o','BatchMode=yes',NODE,"awk '/MemAvailable/ {print}' /proc/meminfo"])
assert int(re.search(r'MemAvailable:\s+(\d+) kB',memory)[1])>=32*1024**2
sys.path.insert(0,str(N/'native_s_profile_launch_v8'));import root_phase as rp
q=rp.actual_quota()
with rp.registry_lock(N/'native_S_profile_registered_reservations_v6.json'):
 reg=rp.registry_value(N/'native_S_profile_registered_reservations_v6.json')
 remaining=sum(row['remaining_bytes'] for row in reg['reservations'].values())
assert q['free_bytes']-remaining-(2<<30)>64<<30 and q['free_bytes']>200*10**9
env={k:v for k,v in os.environ.items() if not k.startswith('SBATCH_')}
env.update(MODEL_V3_EXPECTED_NODE=NODE)
# CPU_EXTRA_ENV_INSERT
argv=['sbatch','--parsable','--partition=cpu','--nodelist='+NODE,'--cpus-per-task=16','--output='+str(P/'slurm-%j.log'),str(SB)]
job=run(argv,env).strip();assert job.isdigit(),job
with (P/'SUBMITTED.json').open('x') as f:
 json.dump(dict(job_id=job,node=NODE,argv=argv,automatic_memory=True,actual_CPU_MemAvailable_kB=int(re.search(r'MemAvailable:\s+(\d+) kB',memory)[1]),submitted_unix=time.time()),f,indent=2);f.write('\n')
print('CPU_ACTUAL_JOB='+job)


