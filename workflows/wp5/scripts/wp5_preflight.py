"""Read-only WP5 cluster/identity/quota and local-scratch metadata."""
import argparse,hashlib,json,os,re,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
PROJECT=ROOT.parent.parent
NODES=[f'compute-0-{i}' for i in range(14,20)]
SLOTS=[4,4,4,8,4,5]
def command(argv):
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60)
    return {'argv':argv,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.pending')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    os.replace(tmp,path)
def inspect():
    guide=PROJECT/'WP5 正式计算行动指南（Codex）.md'
    report={'observed_at':time.time(),'uid':os.getuid(),'username':os.environ.get('USER'),'hostname':os.uname().nodename,
            'project':str(PROJECT),'guide':str(guide),'guide_sha256':hashlib.sha256(guide.read_bytes()).hexdigest(),
            'partition':command(['scontrol','show','partition','cpu']),
            'node_summary':command(['sinfo','--Node','--nodes=compute-0-[14-19]','-o','%N|%P|%t|%C|%m']),
            'nodes':{},'quota':command(['quota','-v','-u','zixiao']),
            'slurm_config':command(['scontrol','show','config'])}
    for node,slots in zip(NODES,SLOTS):
        raw=command(['scontrol','show','node',node])
        fields=dict(re.findall(r'(\w+)=([^\s]+)',raw['stdout']))
        queue=command(['squeue','-w',node,'-h','-o','%i|%u|%j|%T|%C|%m|%N'])
        jobs=[]
        for row in queue['stdout'].splitlines():
            jid=row.split('|')[0]
            if jid: jobs.append(command(['scontrol','show','job','-o',jid]))
        scratch=command(['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',node,
            "hostname; findmnt -T /tmp -o TARGET,SOURCE,FSTYPE,OPTIONS; df -B1 /tmp; df -i /tmp"])
        report['nodes'][node]={'planned_slots':slots,'requested_cpu_per_slot':24,'requested_mem_gib_per_slot':32,
            'raw':raw,'fields':fields,'queue_all_users':queue,'jobs_all_users':jobs,'scratch_metadata':scratch}
    partition=report['partition']['stdout']
    report['G1']={'passed':report['partition']['returncode']==0 and 'MaxTime=UNLIMITED' in partition and
                 'compute-0-[2,8-19]' in partition,'partition':'cpu','walltime_hours':48,
                 'normal_pack_target_hours':40,'large_pack_target_hours':20}
    report['G2']={'state':'LOCAL_PATHS_CONFIRMED_PENDING_PILOT_MAX_TEMP_AND_G6_MEASUREMENT',
        'path':'/tmp','automatic_slurm_cleanup':False,
        'cleanup_evidence':'Epilog/EpilogSlurmctld=(null), explicit runner cleanup required; no claim about uninspected OS tmp cleaners.',
        'policy':'Whole-molecule private node scratch, cleanup in finally; compare pilot max transient bytes*10*slots against actual local capacity.'}
    quota=report['quota']
    lines=[x.split() for x in quota['stdout'].splitlines() if x.strip().startswith('/dev/')]
    if quota['returncode']==0 and len(lines)==1:
        parts=lines[0];used=int(parts[1]);limit=int(parts[3]);files=int(parts[4])
        report['quota_parsed']={'filesystem':parts[0],'used_kib':used,'hard_limit_kib':limit,
            'remaining_bytes':(limit-used)*1024,'files_reported':files,'quota_scope':'user quota, not filesystem df'}
    atomic(ROOT/'gates/g1_g2_initial.json',report)
    print(json.dumps({'report':str(ROOT/'gates/g1_g2_initial.json'),'G1':report['G1'],'quota':report.get('quota_parsed')},ensure_ascii=False))
if __name__=='__main__':inspect()
