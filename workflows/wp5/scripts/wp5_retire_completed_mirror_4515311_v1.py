import pathlib,json,os,stat,hashlib,time
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
assert os.getuid()==1278 and os.uname().nodename=='compute-0-17'
manifest_path=ROOT/'reports/terminal_queue_mirror_copy_v2_job_4515311/manifest.json'
manifest=json.loads(manifest_path.read_text());base=pathlib.Path(manifest['local_directory'])
assert base==pathlib.Path('/tmp/wp5_queue_mirror_4515311') and base.parent==pathlib.Path('/tmp') and not base.is_symlink() and base.stat().st_uid==1278
assert manifest['status']=='VERIFIED_LOCAL_MIRROR' and manifest['actual_registered_job_count']==463
for path,status in [(ROOT/'reports/actual463_apply_v10_job_4515313/report.json','APPLIED_AND_VERIFIED'),(ROOT/'gates/g3/phase16_remaining_storage_job_4515314.json','REMAINING_STORAGE_ESTIMATE_CLOSED'),(ROOT/'reports/terminal_export_repair_v8_job_4515315/report.json','TERMINAL_EXPORT_SCOPE_COMPLETE')]:
 assert json.loads(path.read_text())['status']==status
assert json.loads((ROOT/'gates/g0_ready_for_recovery_v16.json').read_text())['status']=='READY_FOR_ONE_PHASE_FORMAL_SUBMISSION'
files=[]
for path in base.iterdir():
 s=path.lstat();expected=manifest['local_fingerprints_after'].get(path.name)
 assert path.name in {'pending.sqlite','pending.sqlite-journal','pending.sqlite-wal','pending.sqlite-shm'} and expected is not None
 assert stat.S_ISREG(s.st_mode) and not path.is_symlink() and s.st_uid==1278 and s.st_nlink==1
 assert (s.st_dev,s.st_ino,s.st_uid,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==tuple(expected[k] for k in ('device','inode','uid','bytes','mtime_ns','ctime_ns'))
 files.append({'path':str(path),'bytes':s.st_size,'inode':s.st_ino,'uid':s.st_uid})
assert files and sum(x['bytes'] for x in files)>10000000000
readers=[];transport=[]
for proc in pathlib.Path('/proc').iterdir():
 if not proc.name.isdigit() or int(proc.name)==os.getpid():continue
 try:
  if proc.stat().st_uid!=1278:continue
  args=[x.decode(errors='replace') for x in (proc/'cmdline').read_bytes().split(b'\0') if x];comm=(proc/'comm').read_text().strip()
  if (args==['(sd-pam)'] and comm=='(sd-pam)') or (args==['sshd: zixiao@notty'] and comm=='sshd'):
   transport.append({'pid':proc.name,'argv':args});continue
  for fd in (proc/'fd').iterdir():
   try:
    target=os.readlink(fd)
    if target==str(base) or target.startswith(str(base)+'/'):readers.append({'pid':proc.name,'fd':fd.name,'target':target})
   except (FileNotFoundError,ProcessLookupError):pass
 except (FileNotFoundError,ProcessLookupError):pass
assert not readers,readers
for row in files:pathlib.Path(row['path']).unlink()
base.rmdir()
report={'status':'COMPLETED_PRIVATE_LOCAL_MIRROR_REMOVED','time':time.time(),'node':os.uname().nodename,'uid':os.getuid(),'target':str(base),'targets':files,'freed_bytes':sum(x['bytes'] for x in files),'open_readers':readers,'excluded_own_ssh_auth_transport':transport,'permanent_mirror_manifest_preserved':{'path':str(manifest_path),'sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest()},'formal_data_deleted':False,'source_queue_changed':False,'science_signalled':False}
p=ROOT/'reports/phase16_completed_local_mirror_cleanup_root_v1.json'
with p.open('x') as f:json.dump(report,f,indent=2)
print(json.dumps({'status':report['status'],'freed_bytes':report['freed_bytes'],'receipt':str(p)}))