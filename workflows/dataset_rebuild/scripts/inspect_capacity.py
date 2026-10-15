import json,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
def run(argv):
 p=subprocess.run(argv,capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=30)
 return {'argv':argv,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
report={'time_UTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
 'nodes':{f'compute-0-{i}':run(['scontrol','show','node',f'compute-0-{i}']) for i in range(14,20)},
 'quota':run(['quota','-v','-u','zixiao']),
 'partitions':run(['scontrol','show','partition'])}
(ROOT/'reports'/'wp5_capacity_snapshot.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'capacity_snapshot':str(ROOT/'reports'/'wp5_capacity_snapshot.json')}))
