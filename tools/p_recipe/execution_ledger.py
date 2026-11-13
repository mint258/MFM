"""Serialize the submitter, observer, and Slurm handoff ledger mutations."""
from contextlib import contextmanager
import fcntl,json,os
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/p_recipe_20261113')

def read(path):return json.loads(Path(path).read_text())

def write(path,value):
 path=Path(path);tmp=path.with_name(path.name+'.tmp.'+str(os.getpid()))
 with tmp.open('x') as stream:
  stream.write(json.dumps(value,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
 os.replace(tmp,path)

@contextmanager
def locked_ledger():
 with (C/'study_execution.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  path=C/'study_execution.json';ledger=read(path) if path.is_file() else dict(runs={})
  yield ledger
  write(path,ledger)
