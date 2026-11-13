"""Resource routing for the user's three hybrid nodes; no exclusive requests."""
import re

def node_capacity(text):
 values=dict(re.findall(r'(\w+)=([^\s]+)',text))
 state=values['State'].upper()
 if any(word in state for word in ('DRAIN','DOWN','FAIL','MAINT','REBOOT','UNKNOWN')):
  raise ValueError('Node is not available for new work: '+state)
 return max(0,int(values['CPUTot'])-int(values['CPUAlloc']))

def requested_cpus(configuration,policy):
 return int(configuration['workers'])+int(policy['cpu_overhead'])

def route(free_cpus,required_cpus,used_mib,total_mib,policy):
 if total_mib<=0 or used_mib<0 or used_mib/total_mib>policy['maximum_existing_gpu_memory_fraction']:
  return 'WAIT_GPU'
 if total_mib-used_mib<policy.get('minimum_free_gpu_mib',0):return 'WAIT_GPU'
 return 'Slurm' if free_cpus>=required_cpus else 'native_with_standby'

def gpu_rank(name,policy):
 return next((i for i,value in enumerate(policy['gpu_preference']) if value in name),len(policy['gpu_preference']))
