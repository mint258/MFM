"""Focused tests for atomic checkpoint publication and exact continuation."""
from copy import deepcopy
import importlib.util,json,sys
from pathlib import Path
import numpy as np
import pytest
import torch
from phychem_mfm.phase1 import p_recipe_handoff as h

def scheduling_module():
 path=Path(__file__).resolve().parents[2]/'tools/p_recipe/scheduling.py'
 spec=importlib.util.spec_from_file_location('scheduling_under_test',path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def test_cpu_route_is_based_on_required_count_and_gpu_threshold():
 s=scheduling_module();policy=dict(cpu_overhead=2,maximum_existing_gpu_memory_fraction=.30,gpu_preference=['5090','4090','3090'])
 needed=s.requested_cpus(dict(workers=14),policy)
 assert needed==16
 for state in ('ALLOCATED','MIXED'):
  free=s.node_capacity('State='+state+' CPUAlloc=104 CPUTot=104')
  assert s.route(free,needed,0,32000,policy)=='native_with_standby'
  assert s.route(free,needed,9600,32000,policy)=='native_with_standby'
 assert s.route(15,needed,0,32000,policy)=='native_with_standby'
 assert s.route(16,needed,9600,32000,policy)=='Slurm'
 assert s.route(52,needed,9601,32000,policy)=='WAIT_GPU'
 assert s.route(52,needed,0,0,policy)=='WAIT_GPU'
 completing=s.node_capacity('State=IDLE+COMPLETING CPUAlloc=0 CPUTot=104')
 assert s.route(completing,needed,0,32000,policy)=='native_with_standby'
 assert s.route(52,needed,7000,24000,dict(policy,minimum_free_gpu_mib=18432))=='WAIT_GPU'
 with pytest.raises(ValueError):s.node_capacity('State=MIXED+DRAIN CPUAlloc=1 CPUTot=104')
 assert [s.gpu_rank(name,policy) for name in ('RTX5090','RTX4090','RTX3090')]==[0,1,2]

def test_failed_save_never_publishes_final_checkpoint_or_ack(tmp_path,monkeypatch):
 def interrupted(payload,path):
  Path(path).write_bytes(b'incomplete');raise OSError('simulated interrupted writer')
 monkeypatch.setattr(h,'save_checkpoint',interrupted)
 final=tmp_path/'samples_128.pt'
 with pytest.raises(OSError):h.publish_checkpoint({},final)
 assert not final.exists()
 assert not (tmp_path/'ack.json').exists()
 assert list(tmp_path.glob('*.writing.*'))

def test_publication_is_complete_and_immutable_before_ack(tmp_path):
 c=dict(run='A',handoff_request=str(tmp_path/'request.json'),handoff_ack=str(tmp_path/'ack.json'))
 request=dict(action='SAVE_AND_EXIT',run='A',request_id='once',job_id=123)
 h.atomic_json(c['handoff_request'],request)
 assert h.read_request(c)==request
 final=tmp_path/'samples_128.pt';clock=dict(samples_consumed=128,optimizer_updates=1)
 h.publish_checkpoint(dict(model={'w':torch.arange(8)},clock=clock),final)
 assert torch.equal(torch.load(final,weights_only=True)['model']['w'],torch.arange(8))
 assert not list(tmp_path.glob('*.writing.*'))
 h.publish_ack(c,request,final,clock)
 assert json.loads(Path(c['handoff_ack']).read_text())['clock']==clock
 with pytest.raises(FileExistsError):h.publish_checkpoint({},final)
 h.atomic_json(c['handoff_request'],dict(request,run='different'))
 with pytest.raises(ValueError):h.read_request(c)

def test_optimizer_clock_rng_and_next_samples_continue_exactly(tmp_path):
 def initialize():
  torch.manual_seed(31);model=torch.nn.Sequential(torch.nn.Linear(3,4),torch.nn.Dropout(.25),torch.nn.Linear(4,1)).double()
  optimizer=torch.optim.AdamW(model.parameters(),lr=.002)
  return model,optimizer,np.random.default_rng(71)
 def update(model,optimizer,rng,step):
  indices=rng.integers(0,9,size=3);x=torch.tensor(indices[:,None]+np.arange(3),dtype=torch.float64)/10
  optimizer.param_groups[0]['lr']=.002*(10-step)/10
  optimizer.zero_grad();loss=(model(x)-.3).square().mean();loss.backward();optimizer.step();return indices.tolist()
 reference,opt,rng=initialize();expected=[update(reference,opt,rng,i) for i in range(10)]
 expected_optimizer=deepcopy(opt.state_dict());expected_rng=torch.get_rng_state()
 model,opt,rng=initialize();actual=[update(model,opt,rng,i) for i in range(4)]
 path=tmp_path/'samples_12.pt';clock=dict(samples_consumed=12,optimizer_updates=4)
 h.publish_checkpoint(dict(model=model.state_dict(),optimizer=opt.state_dict(),clock=clock,rng=rng.bit_generator.state,torch_rng=torch.get_rng_state()),path)
 resumed,opt,rng=initialize();cp=torch.load(path,weights_only=True)
 resumed.load_state_dict(cp['model']);opt.load_state_dict(cp['optimizer']);rng.bit_generator.state=cp['rng'];torch.set_rng_state(cp['torch_rng'])
 actual += [update(resumed,opt,rng,i) for i in range(cp['clock']['optimizer_updates'],10)]
 assert actual==expected and cp['clock']['samples_consumed']==12
 assert all(torch.equal(a,b) for a,b in zip(reference.parameters(),resumed.parameters()))
 assert torch.equal(torch.get_rng_state(),expected_rng)
 for key,state in expected_optimizer['state'].items():
  assert all(torch.equal(value,opt.state_dict()['state'][key][name]) for name,value in state.items())

def test_cooperative_worker_exits_before_handoff_returns(tmp_path,monkeypatch):
 """A real CPU worker saves/acknowledges; a delayed wrapper records its exit."""
 import os,subprocess,threading,time
 tools=Path(__file__).resolve().parents[2]/'tools/p_recipe'
 monkeypatch.syspath_prepend(str(tools))
 from scheduled_run import handoff
 from native_run import identity
 c=dict(run='cpu_protocol_test',output=str(tmp_path),samples=1000000,
  handoff_request=str(tmp_path/'request.json'),handoff_ack=str(tmp_path/'ack.json'))
 configuration=tmp_path/'configuration.json';h.atomic_json(configuration,c)
 source='''import json,sys,time,torch
from pathlib import Path
from phychem_mfm.phase1.p_recipe_handoff import read_request,publish_checkpoint,finish_handoff
c=json.loads(Path(sys.argv[1]).read_text())
for update in range(1,c['samples']):
 request=read_request(c)
 if request:
  clock=dict(samples_consumed=update,optimizer_updates=update)
  checkpoint=Path(c['output'])/('samples_'+str(update)+'.pt')
  publish_checkpoint(dict(model={'weight':torch.tensor(update)},clock=clock),checkpoint)
  result=finish_handoff(c,request,checkpoint,clock)
  assert result['status']=='HANDOFF_SAVED' and result['run']==c['run']
  break
 time.sleep(.01)
'''
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
 process=subprocess.Popen([sys.executable,'-B','-c',source,str(configuration)],env=env,start_new_session=True)
 state_path=tmp_path/'native.json';started=time.time()
 state=dict(identity(process.pid),status='RUNNING',started_at=started)
 h.atomic_json(state_path,state)
 def finish():
  code=process.wait();time.sleep(2)
  h.atomic_json(state_path,dict(state,exit_code=code,elapsed_seconds=time.time()-started,ended_at=time.time()))
 wrapper=threading.Thread(target=finish);wrapper.start()
 try:
  result=handoff(dict(configuration=str(configuration),native_state=str(state_path),handoff_state=str(tmp_path/'handoff.json')),314159)
  assert process.poll()==0
  original,native,ack=result
  saved=torch.load(ack['checkpoint'],weights_only=True)
  assert saved['model']['weight'].item()==ack['clock']['optimizer_updates']
  assert ack['job_id']==314159 and native['exit_code']==0
 finally:
  if process.poll() is None:process.terminate()
  wrapper.join(timeout=15)

@pytest.mark.parametrize('free,backend',[(6,'Slurm'),(5,'native_SSH')])
def test_launcher_submits_only_needed_cpus_and_native_twin(tmp_path,monkeypatch,free,backend):
 tools=Path(__file__).resolve().parents[2]/'tools/p_recipe';monkeypatch.syspath_prepend(str(tools))
 import launch_plan as launch
 monkeypatch.setattr(launch,'C',tmp_path)
 h.atomic_json(tmp_path/'batch_gpu_inventory.json',[dict(node='compute-0-22',gpus=[['GPU-test']])])
 configuration=tmp_path/'A.json'
 h.atomic_json(configuration,dict(run='A',workers=4,output=str(tmp_path/'output'),stage=2,round=1,batch_size=128))
 monkeypatch.setattr(launch,'observe',lambda node:[dict(node=node,gpu_uuid='GPU-test',used_mib=100,total_mib=32000,gpu_name='RTX5090',free_cpus=free)] if node=='compute-0-22' else [])
 monkeypatch.setattr(launch,'own_gpu_busy',lambda gpu,node=None:False)
 calls=[]
 def execute(command,**kwargs):
  calls.append(command);return '4321\n' if command[0]=='ssh' else '12345\n'
 monkeypatch.setattr(launch.subprocess,'check_output',execute)
 ledger=launch.launch_locked(dict(configurations=[str(configuration)]),dict(runs={}))
 record=ledger['runs']['A'];assert record['backend']==backend
 submissions=[cmd for cmd in calls if cmd[0]=='sbatch']
 assert len(submissions)==1 and '--cpus-per-task=6' in submissions[0]
 assert not any('exclusive' in argument for argument in submissions[0])
 if backend=='native_SSH':
  assert calls[0][0]=='ssh' and record['wrapper_pid']==4321 and record['standby_job_id']==12345
  assert ledger['reservations']['A_standby']['job_id']==12345
  assert 'job_id' not in record and json.loads(configuration.read_text())['handoff_request']
 else:
  assert len(calls)==1 and record['job_id']==12345
  assert not ledger.get('reservations')
