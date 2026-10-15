"""Record the job's own cgroup memory peak and GNU time measurements."""
import argparse, json, os, re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--time-log',required=True);p.add_argument('--output',required=True)
a=p.parse_args();job=os.environ['SLURM_JOB_ID']
result={'job_id':job,'slurm_cpus':int(os.environ['SLURM_CPUS_PER_TASK']),
    'time_log':a.time_log,'own_cgroup_memory_peak_bytes':None,'cgroup_measurements':[]}
text=Path(a.time_log).read_text(errors='replace') if Path(a.time_log).exists() else ''
for title,key in [('Maximum resident set size (kbytes)','maximum_process_rss_kib'),
                  ('User time (seconds)','user_seconds'),('System time (seconds)','system_seconds')]:
    match=re.search(re.escape(title)+r':\s*([0-9.]+)',text)
    result[key]=float(match[1]) if match else None
for line in Path('/proc/self/cgroup').read_text().splitlines():
    _,controllers,relative=line.split(':',2)
    if f'job_{job}' not in relative.split('/') or '..' in relative.split('/'):
        continue
    if not controllers:
        candidate=Path('/sys/fs/cgroup')/relative.lstrip('/')/'memory.peak'
    elif 'memory' in controllers.split(','):
        candidate=Path('/sys/fs/cgroup/memory')/relative.lstrip('/')/'memory.max_usage_in_bytes'
    else:continue
    if candidate.is_file():
        try:
            value=int(candidate.read_text().strip())
            result['cgroup_measurements'].append({'path':str(candidate),'peak_bytes':value})
        except (OSError,ValueError):pass
if result['cgroup_measurements']:
    result['own_cgroup_memory_peak_bytes']=max(x['peak_bytes'] for x in result['cgroup_measurements'])
result['rss_scope']='GNU time maximum process RSS across the reaped tree; not summed simultaneous worker RSS'
Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
