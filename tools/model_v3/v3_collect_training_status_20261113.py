"""Read current actual training plans; no launch or scientific computation."""
import csv,datetime,io,json,subprocess
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
h=json.loads((C/'MODEL_V3_HANDOFF_20261111.json').read_text())
plans=h.get('active_development_plans',[str(C/'LATENT_V3_20261111/plan.json')])
runs={}
for path in plans:
    for row in json.loads(Path(path).read_text())['runs']:
        runs[row['job']]=row
raw=subprocess.check_output(['squeue','-h','-u','zixiao','-o','%i|%T|%M|%N|%C|%R'],text=True)
states={row.split('|')[0]:row.split('|') for row in raw.splitlines()}
training=[]
for r in runs.values():
    if states.get(str(r['job']),['',''])[1]!='RUNNING':continue
    f=Path(r['output'])/'losses.csv';row=None
    if f.exists():
        with f.open('rb') as stream:
            header=stream.readline().decode();stream.seek(max(0,f.stat().st_size-65536))
            data=stream.read().decode();lines=data.splitlines()
        if not data.endswith('\n'):lines=lines[:-1]
        if lines:row=next(csv.DictReader(io.StringIO(header+lines[-1]+'\n')))
    g=C/('M3_controlled_'+str(r['job'])+'.state.json')
    guard=json.loads(g.read_text()) if g.exists() else None
    training.append(dict(job=r['job'],node=r['node'],stage=r['stage'],arm=r['arm'],
        condition=r['condition'],row=row,guard=guard))
nodes={}
for node in sorted({r['node'] for r in runs.values()}):
    observed=[subprocess.run(['ssh','-n',node,command],capture_output=True,text=True) for command in (
        'nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv,noheader,nounits',
        'df -B1 /','head -3 /proc/meminfo')]
    nodes[node]=dict(returncode=next((z.returncode for z in observed if z.returncode),0),
        stdout=''.join(z.stdout for z in observed),stderr=''.join(z.stderr for z in observed))
value=dict(observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    source_plans=plans,training=training,nodes=nodes,squeue=raw,cpu37_start='')
name=C/('MODEL_V3_root_check_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M')+'.json')
name.write_text(json.dumps(value,indent=2)+'\n')
(C/'MODEL_V3_latest_root_path.txt').write_text(str(name)+'\n')
print(json.dumps(dict(path=str(name),training=[dict(job=r['job'],node=r['node'],
    stage=r['stage'],arm=r['arm'],condition=r['condition'],row=r['row'],
    guard_status=r['guard']['status'] if r['guard'] else None) for r in training])))
