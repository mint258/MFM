import json, subprocess, socket, os
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
commands={
'identity':['id'], 'queue':['squeue','-u','zixiao','-o','%.20i %.12P %.55j %.10T %.12M %.6C %.12m %.30N'],
'nodes':['sinfo','--Node','-o','%N %P %t %c %m %C %l'],
'partitions':['scontrol','show','partition'], 'quota':['quota','-v','-u','zixiao'],
'disk':['df','-h',str(root)], 'inodes':['df','-i',str(root)],
'node20':['scontrol','show','node','compute-0-20'],
'compute_ssh':['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','compute-0-20','hostname'],
}
out={'hostname':socket.gethostname(),'uid':os.getuid(),'commands':{}}
for name,argv in commands.items():
 try:
  p=subprocess.run(argv,capture_output=True,text=True,timeout=35,stdin=subprocess.DEVNULL)
  out['commands'][name]={'argv':argv,'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 except Exception as e: out['commands'][name]={'error':str(e)}
(root/'preflight.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))