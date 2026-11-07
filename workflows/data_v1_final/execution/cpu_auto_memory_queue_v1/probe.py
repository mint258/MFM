"""Target-node identity and optional actual memory observation; never a limit."""
import datetime,json,os,socket,time
from pathlib import Path


def observation():
    epoch=time.time();result={'uid':os.getuid(),'node':socket.gethostname().split('.')[0],
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'observed_unix_seconds':epoch,
        'observed_at':datetime.datetime.fromtimestamp(epoch,datetime.timezone.utc).isoformat(),
        'memory_observation_only':True,'memory_admission_evaluated':False}
    try:
        info={line.split()[0].rstrip(':'):int(line.split()[1])*1024 for line in
              Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))}
        result.update(total_bytes=info['MemTotal'],available_bytes=info['MemAvailable'],
                      used_bytes=info['MemTotal']-info['MemAvailable'],memory_error=None)
    except (OSError,KeyError,ValueError) as exc:
        result.update(total_bytes=None,available_bytes=None,used_bytes=None,memory_error=repr(exc))
    return result


if __name__=='__main__':print(json.dumps(observation()))
