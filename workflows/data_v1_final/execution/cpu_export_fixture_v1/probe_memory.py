"""Tiny read-only /proc memory observation; never opens project data."""
import datetime,json,os,pathlib,socket,time
CPU_NODES={f'compute-0-{n}' for n in (2,*range(8,20))}
def sample():
    node=socket.gethostname().split('.')[0]
    if node not in CPU_NODES or os.getuid()!=1278:raise ValueError('AUTHORIZED_CPU_NODE_AND_UID_REQUIRED')
    values={line.split(':',1)[0]:int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))}
    if set(values)!={'MemTotal','MemAvailable'} or not 0<values['MemAvailable']<=values['MemTotal']:raise ValueError('INVALID_REAL_MEMORY_OBSERVATION')
    return {'schema':'CPU_READONLY_MEMORY_OBSERVATION_V1','node':node,'uid':os.getuid(),'observed_unix_seconds':time.time(),'observed_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'total_bytes':values['MemTotal'],'available_bytes':values['MemAvailable'],'used_bytes':values['MemTotal']-values['MemAvailable']}
if __name__=='__main__':print(json.dumps(sample()))
