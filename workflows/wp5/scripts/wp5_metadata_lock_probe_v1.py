import json,os,socket
from pathlib import Path
f=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/gates/metadata_queue_production_shape/production_shape_r12_v3_20261012_run4_production_budget/fixture.sqlite.metadata_v12.lock')
assert os.getuid()==1278
s=f.stat();answer={'node':socket.gethostname(),'inode':s.st_ino,'locks':[]}
for line in Path('/proc/locks').read_text().splitlines():
    fields=line.split();index=6 if len(fields)>1 and fields[1]=='->' else 5
    if len(fields)<=index:continue
    try:inode=int(fields[index].rsplit(':',1)[1])
    except (ValueError,IndexError):continue
    if inode!=s.st_ino:continue
    pid=int(fields[index-1]);row={'raw':line,'pid':pid}
    if pid>0:
        proc=Path('/proc')/str(pid)
        try:
            uid=proc.stat().st_uid;row['uid']=uid
            if uid==1278:
                row['cmdline']=proc.joinpath('cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')[:500]
                row['cgroup']=proc.joinpath('cgroup').read_text()[:500]
        except FileNotFoundError:row['exited']=True
    answer['locks'].append(row)
print(json.dumps(answer))
