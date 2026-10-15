"""Read-only scheduler accounting and small result summaries for this task."""
import json, subprocess, sys, time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
out={'time_UTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'jobs':{}}
for value in sys.argv[1:]:
    if not value.isdecimal():raise ValueError('Numeric job IDs required')
    p=subprocess.run(['sacct','-j',value,'-o','JobID,JobName,State,ExitCode,AllocCPUS,ElapsedRaw,MaxRSS','-P'],capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=30)
    out['jobs'][value]={'sacct_exit_code':p.returncode,'sacct_stdout':p.stdout,'sacct_stderr':p.stderr}
path=ROOT/'reports'/('accounting_'+'_'.join(sys.argv[1:])+'.json')
path.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
