import json,os,stat,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
cache=root/'scripts/__pycache__';removed=[]
if cache.exists():
 if cache.is_symlink() or cache.stat().st_uid!=os.getuid():raise RuntimeError('Unexpected cache ownership')
 for path in cache.iterdir():
  info=path.lstat()
  if path.suffix!='.pyc' or not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid():continue
  removed.append({'path':str(path),'bytes':info.st_size});path.unlink()
 if not any(cache.iterdir()):cache.rmdir()
report={'time_UTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
 'removed_reconstructible_bytecode':removed,
 'probe_scratch':'All scratch removed by per-calculation finally; original outputs retained for property verification',
 'installer_cache_bytes_previously_removed':452392879}
(root/'reports/cleanup.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'removed_files':len(removed),'bytes':sum(x['bytes'] for x in removed)}))
