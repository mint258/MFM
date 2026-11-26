"""Place the existing final bootstrap on CPU nodes after GPU readouts finish."""
from cpu_ssh_runtime import execution_handle,execution_backend
import argparse,json,os,socket,subprocess,time
from pathlib import Path
from execution_ledger import C,locked_ledger,read,write

REPO=Path(__file__).resolve().parents[2]
WAITING='GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS'
CPU_NODES=['compute-0-'+str(i) for i in (10,16,8,17,9,11,12,13,15,19)]


def admit(configuration):
 """Check the actual CPU host, filesystems, memory and current UID quotas."""
 import runpy
 if configuration.get('budget_curve'):
  from budget_curve import admit_storage
  admit_storage(configuration)
 else:
  from budget_curve import admit_joint_storage
  admit_joint_storage()
 if socket.gethostname().split('.')[0] not in {'compute-0-'+str(i) for i in range(8,20)}:
  raise RuntimeError('Final statistics require a CPU node8..19')
 if os.environ.get('CUDA_VISIBLE_DEVICES'):
  raise RuntimeError('CPU statistics must have no visible CUDA device')
 d=runpy.run_path(str(REPO/'tools/model_v3/v2_diagnosis_disk.py'));m=d['m']
 m.require_capacity(m.filesystem_status('/'),0,2000)
 _,remaining=d['model_growth_forecast']()
 m.require_capacity(m.filesystem_status(configuration['output']),max(8388608,remaining),10000)
 nfs_future=max(67108864,configuration.get('nfs_future_bytes',67108864))
 m.require_capacity(m.filesystem_status(C),nfs_future,1000)
 m.quota_headroom(d['CONTROL']/'lustre_quota_available_v2_20261107.json','/lfshome',
                  max(8388608,remaining),d['remaining_d6']()+6000000000)
 m.quota_headroom(d['CONTROL']/'share_quota_available_v3.json','/share',nfs_future,d['remaining_nfs_other']())
 memory={line.split(':',1)[0]:int(line.split()[1])*1024
         for line in Path('/proc/meminfo').read_text().splitlines()
         if line.startswith(('MemTotal:','MemAvailable:'))}
 if memory['MemAvailable']<12*1024**3+int(.15*memory['MemTotal']):
  raise RuntimeError('CPU statistics memory allowance is unavailable')


def finalize(configuration):
 """Consume predictions once; never extract features or fit another probe."""
 c=configuration
 if c.get('statistics_backend')!='slurm_cpu':raise ValueError('Not a deferred-statistics run')
 admit(c)
 from evaluate import score
 output=Path(c['output']);summary=read(output/'summary.json')
 if summary.get('status') not in (WAITING,'COMPLETE'):
  raise ValueError('GPU training and readouts are not complete')
 if summary.get('samples')!=c['samples']:raise ValueError('Training budget is incomplete')
 started=time.monotonic();scored=[]
 for samples in c.get('evaluation_samples',[c['samples']]):
  path=output/('readout' if samples==c['samples'] else 'readout_'+str(samples))
  predictions=path/'predictions.json';manifest=read(predictions)
  if manifest['run']!=c['run'] or manifest['samples']!=samples:
   raise ValueError('Readout identity/budget mismatch')
  target=path/'scores.json'
  if not target.is_file():
   score(predictions,
         '/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/reference_C1_0/predictions.json',
         REPO/'results/p_recipe/scores.csv')
   scored.append(samples)
  result=read(target)
  if not all(result.get(key,{}).get('complete') and
             result[key].get('bootstrap_samples')==1000 and
             result[key].get('bootstrap_defined')==1000 for key in ('R1','R3')):
   raise ValueError('Original R1/R3 bootstrap is incomplete; preserve its output')
 elapsed=time.monotonic()-started
 summary.update(status='COMPLETE',statistics_complete=True,
   statistics_backend=execution_backend(),statistics_node=socket.gethostname().split('.')[0],
   statistics_job_id=execution_handle(),
   statistics_cpu_seconds=summary.get('statistics_cpu_seconds',0.)+elapsed)
 summary['training_and_evaluation_seconds']=summary['training_and_gpu_readout_seconds']+summary['statistics_cpu_seconds']
 if c.get('budget_curve'):summary['statistics_completed_at']=time.time()
 write(output/'summary.json',summary)
 return dict(run=c['run'],status='COMPLETE',newly_scored_samples=scored,
             statistics_job_id=summary['statistics_job_id'])


def cpu_destination():
 """Request one real CPU; if all are occupied, queue within the CPU-only set."""
 for node in CPU_NODES:
  text=subprocess.check_output(['scontrol','show','node',node,'-o'],text=True,timeout=15)
  values=dict(part.split('=',1) for part in text.split() if '=' in part)
  states=set(values.get('State','').split('+'))
  if (states<={'IDLE','MIXED','ALLOCATED'} and
      'cpu' in values.get('Partitions','').split(',') and
      int(values.get('CPUTot',0))-int(values.get('CPUAlloc',0))>=1 and
      int(values.get('FreeMem',0))>=12288+int(.15*int(values.get('RealMemory',0)))):
   return node
 return None


def queue(plan):
 """The monitor calls this after actual execution collection, not before it."""
 submitted=[]
 with locked_ledger() as ledger:
  jobs=ledger.setdefault('cpu_statistics',{})
  for filename in plan['configurations']:
   c=read(filename);record=ledger['runs'].get(c['run'],{})
   if c.get('statistics_backend')!='slurm_cpu' or c['run'] in jobs:continue
   if record.get('state')!='COMPLETED' or record.get('exit_code') not in (0,'0:0'):continue
   summary=Path(c['output'])/'summary.json'
   if not summary.is_file() or read(summary).get('status')!=WAITING:continue
   node=cpu_destination()
   command=['sbatch','--parsable','--job-name='+c['run']+'_cpu_statistics',
            '--partition=cpu','--nodes=1','--cpus-per-task=1',
            '--output='+str(C/(c['run']+'_cpu_statistics_%j.log')),
            str(REPO/'tools/p_recipe/cpu_statistics.sbatch'),str(Path(filename).resolve())]
   command.insert(4,'--nodelist='+node if node else '--exclude=compute-0-[0-7,14,18,20-22]')
   jobs[c['run']]=dict(backend='Slurm_CPU',configuration=filename,node_constraint=node or CPU_NODES,
      cpus=1,exclusive=False,submitted_at=time.time(),state='SUBMITTING',purpose='Original final R1/R3 bootstrap; no new probes')
   write(C/'study_execution.json',ledger)
   try:job=int(subprocess.check_output(command,cwd=REPO,text=True,timeout=30).strip().split(';')[0])
   except (OSError,ValueError,subprocess.SubprocessError) as error:
    jobs[c['run']].update(state='SUBMISSION_OBSERVATION_UNCERTAIN',observation_error=str(error))
    write(C/'study_execution.json',ledger);continue
   jobs[c['run']].update(job_id=job,state='SUBMITTED')
   write(C/'study_execution.json',ledger)
   submitted.append(dict(run=c['run'],**jobs[c['run']]))
 return submitted


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 mode=parser.add_mutually_exclusive_group(required=True)
 mode.add_argument('--plan');mode.add_argument('--finalize-configuration')
 args=parser.parse_args()
 result=queue(read(args.plan)) if args.plan else finalize(read(args.finalize_configuration))
 print(json.dumps(result),flush=True)
