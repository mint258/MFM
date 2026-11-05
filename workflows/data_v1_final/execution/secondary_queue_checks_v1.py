"""Two actual Alpha CPU metadata-only fixtures, no scientific data or producer calls."""
import hashlib,json,os,socket,subprocess,sys,time,unittest
from pathlib import Path

def main():
 root=Path('/gfshome/alpha/codex_data_v1_20261026');jid=os.environ.get('SLURM_JOB_ID','');node=os.environ.get('SLURMD_NODENAME') or socket.gethostname().split('.')[0]
 assert os.getuid()==1264 and jid.isdecimal() and node in {'compute-0-1','compute-0-3','compute-0-4','compute-0-5','compute-0-6','sonmi1'}
 assert os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('CUDA_VISIBLE_DEVICES')==''
 frame=subprocess.run(['scontrol','show','job','-o',jid],check=True,text=True,capture_output=True).stdout
 from secondary_cpu_queue_v1.common import fields
 job=fields(frame);assert job['UserId']=='alpha(1264)' and job['NumCPUs']=='16' and job['NodeList']==node and job['JobState']=='RUNNING' and job['Partition']=='cpu'
 s=os.statvfs(root);assert s.f_bavail*s.f_frsize>=200000000000+(1<<20)
 from secondary_cpu_queue_v1.test_metadata import MetadataBoundaries
 suite=unittest.TestLoader().loadTestsFromTestCase(MetadataBoundaries);assert suite.countTestCases()==2
 started=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(suite)
 sources=[]
 for p in [Path(__file__).absolute(),*sorted((root/'code/secondary_cpu_queue_v1').glob('*.py'))]:
  raw=p.read_bytes();sources.append({'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
 x={'schema':'ACTUAL_SECONDARY_QUEUE_METADATA_FIXTURES_V1','status':'TWO_METADATA_FIXTURES_PASSED' if result.wasSuccessful() and result.testsRun==2 and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses else 'METADATA_FIXTURES_FAILED','endpoint':'218.192.171.238:22','uid':1264,'job_id':jid,'node':node,'actual_slurm_job_text':frame,'sources':sources,'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'elapsed_test_seconds':time.monotonic()-started,'allocated_cpus':16,'memory_requested':False,'actual_slurm_memory_environment':{k:os.environ.get(k) for k in ('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU')},'dataset_records_read':0,'UFF_calls':0,'QM_calls':0,'compatibility_or_data_generation_accepted':False,'forced_signals_sent':False}
 out=root/('secondary_queue_metadata_'+jid+'.json')
 with out.open('x') as f:json.dump(x,f,indent=2)
 print(json.dumps({'status':x['status'],'output':str(out),'test_count':x['tests_run']}))
 return 0 if x['status']=='TWO_METADATA_FIXTURES_PASSED' else 1
if __name__=='__main__':raise SystemExit(main())