"""Compute-node readonly metadata probe; no chemistry, payloads or proof writes."""
import argparse,json,os,re,socket,time
from pathlib import Path
from .common import UID,need,load,ref,sha,canonical,source_review,storage_observation,query


def process(pid):
    path=Path('/proc')/str(pid);before=(path/'stat').read_text();fields=before[before.rfind(')')+2:].split()
    argv_raw=(path/'cmdline').read_bytes();cgroup=(path/'cgroup').read_bytes();status=(path/'status').read_text()
    need(len(argv_raw)<=128*1024 and len(cgroup)<=128*1024,'BOUNDED_GATE_PROCESS_METADATA_REQUIRED')
    uid=next(line.split()[1:] for line in status.splitlines() if line.startswith('Uid:'))
    need(len(uid)==4 and all(int(value)==UID for value in uid),'EXACT_GATE_PROCESS_UID_REQUIRED')
    env_raw=(path/'environ').read_bytes();need(len(env_raw)<=2*1024**2,'BOUNDED_GATE_ENVIRONMENT_REQUIRED')
    env={}
    names={'SLURM_JOB_ID','SLURM_CPUS_PER_TASK','SLURM_JOB_PARTITION','CUDA_VISIBLE_DEVICES',
           'SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU',
           'OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'}
    for item in env_raw.split(b'\0'):
        if b'=' in item:
            key,value=item.split(b'=',1)
            if key.decode(errors='replace') in names:env[key.decode()]=value.decode()
    after=(path/'stat').read_text();tail=after[after.rfind(')')+2:].split()
    need((fields[19],fields[2],fields[3])==(tail[19],tail[2],tail[3]),'GATE_PROCESS_LIFETIME_CHANGED_DURING_PROBE')
    return {'pid':pid,'uid':UID,'start_ticks':int(fields[19]),'pgid':int(fields[2]),'sid':int(fields[3]),
        'argv':[part.decode() for part in argv_raw.rstrip(b'\0').split(b'\0')],
        'argv_sha256':sha(argv_raw),'cgroup':cgroup.decode(),'cgroup_sha256':sha(cgroup),'selected_environment':env}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',type=Path,required=True);parser.add_argument('--job-id',required=True)
    args=parser.parse_args();request=load(args.request)
    need(os.getuid()==UID and args.job_id.isdecimal() and socket.gethostname().split('.')[0]==request['node'],
         'ACTUAL_ALPHA_TARGET_METADATA_IDENTITY_REQUIRED')
    source_review(request['controller_review_reference']['path'])
    matches=[]
    for item in Path('/proc').iterdir():
        if not item.name.isdecimal():continue
        try:
            if item.stat().st_uid!=UID:continue
            raw=(item/'cmdline').read_bytes()
            if raw.rstrip(b'\0').split(b'\0')!=[part.encode() for part in request['gate_argv']]:continue
            candidate=process(int(item.name));env=candidate['selected_environment']
            need(env.get('SLURM_JOB_ID')==args.job_id and env.get('SLURM_CPUS_PER_TASK')=='16' and
                 env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('CUDA_VISIBLE_DEVICES')=='',
                 'ACTUAL_GATE_SLURM_ENVIRONMENT_DIFFERS')
            if re.search(r'(?:^|/)job_'+re.escape(args.job_id)+r'(?:/|\n|$)',candidate['cgroup']):
                candidate['actual_slurm_membership_basis']='EXACT_JOB_ID_IN_ACTUAL_CGROUP'
            else:
                listing=query(['scontrol','listpids',args.job_id],emit=False)
                rows=[line.split() for line in listing['stdout'].splitlines()]
                own=[row for row in rows if len(row)>=2 and row[0]==str(candidate['pid']) and row[1]==args.job_id]
                need(len(own)==1,'ACTUAL_SLURM_LISTPIDS_GATE_MEMBERSHIP_REQUIRED')
                candidate['actual_slurm_membership_basis']='EXACT_PID_AND_JOB_IN_ACTUAL_NODE_SCONTROL_LISTPIDS'
                candidate['actual_slurm_listpids_query']=listing
            matches.append(candidate)
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    need(len(matches)==1,'EXACT_ONE_ACTUAL_OWN_WAITING_GATE_PROCESS_REQUIRED')
    storage=storage_observation(quiet=True)
    result={'schema':'SECONDARY_CPU_ACTUAL_TARGET_METADATA_V1','uid':UID,'node':request['node'],
        'hostname':socket.gethostname().split('.')[0],'job_id':args.job_id,
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'observed_unix_seconds':time.time(),'queue_request_reference':ref(args.request),
        'gate_process':matches[0],'actual_memory_environment':{key:matches[0]['selected_environment'].get(key)
            for key in ('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU')},'storage':storage,
        'scientific_data_or_chemistry_read':False,'proof_written_by_probe':False}
    print(canonical(result).decode(),flush=True)


if __name__=='__main__':main()
