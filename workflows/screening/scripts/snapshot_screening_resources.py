"""Read-only scheduler, account quota and logical environment metadata."""
import datetime, importlib.metadata, json, os, socket, subprocess
from pathlib import Path

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')

def query(argv):
    result=subprocess.run(argv,capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=45)
    return {'argv':argv,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}

report={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'host':socket.gethostname(),'uid':os.getuid(),'cwd':str(Path.cwd()),
    'sinfo':query(['sinfo','--Node','-h','-o','%N|%P|%t|%C|%m|%e']),
    'partitions':query(['scontrol','show','partition']),
    'own_queue':query(['squeue','-u','zixiao','-h','-o','%i|%j|%T|%M|%C|%N|%R']),
    'quota':query(['quota','-v','-u','zixiao']),
    'nodes':{f'compute-0-{number}':query(['scontrol','show','node',f'compute-0-{number}'])
             for number in range(10,21)},
    'packages':{name:importlib.metadata.version(name) for name in ('numpy','torch','rdkit','lmdb')}}
path=ROOT/'reports/resource_snapshot.json'
path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'UTC':report['UTC'],'host':report['host'],'uid':report['uid'],
    'sinfo':report['sinfo']['stdout'],'own_queue':report['own_queue']['stdout'],
    'quota':report['quota']['stdout'],'snapshot':str(path)}))
