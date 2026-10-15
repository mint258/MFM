"""Replace only the verified Root-owned read-only observer service."""
import ast, hashlib, json, os, signal, socket, subprocess, time
from pathlib import Path
PROJECT=Path('/share/home/zixiao/descriptor_analysis');R=PROJECT/'runs/phase1_wp5_20261011'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def identity(pid):
    proc=Path('/proc')/str(pid);status=proc.joinpath('status').read_text()
    uid=int(next(x for x in status.splitlines() if x.startswith('Uid:')).split()[1])
    ticks=proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]
    args=proc.joinpath('cmdline').read_bytes().decode().split('\0')[:-1]
    cwd=proc.joinpath('cwd').resolve()
    paths=[str((cwd/arg).resolve()) for arg in args if arg.endswith('.py')]
    return {'pid':pid,'uid':uid,'start_ticks':ticks,'argv':args,'cwd':str(cwd),'python_source_paths':paths}
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
assert json.loads((R/'reports/startup_replacement_initial_observer_v3_stdout.json').read_text())['effective_selection_ready']
assert (R/'reports/startup_replacement_initial_observer_v3.exitcode').read_text().strip()=='0'
for file,expected in [('wp5_hourly_observe_v3.py','a70d048dbd49b40efce6aab94410f124cbd62e15d2e4e8eb2dbfb2cd46c548c9'),('wp5_recovery_hourly_watch_v3.py','7f0911d40d55f361fc3d6569d0c88bcc97622ab1b54a3fed3cc559c908cf39d2')]:
    p=R/'scripts'/file;assert sha(p)==expected;ast.parse(p.read_text())
report={'time':time.time(),'uid':os.getuid(),'old_pid':3424328,'new_watch_source':str(R/'scripts/wp5_recovery_hourly_watch_v3.py')}
oldpath=R/'scripts/wp5_recovery_hourly_watch_v1.py'
oldref=json.loads((R/'reports/recovery_hourly_watch_v1_identity.json').read_text())
assert oldref['pid']==3424328
try:
    old=identity(3424328);report['old_actual_identity']=old
    assert old['uid']==1278 and old['start_ticks']=='8053769462'
    assert str(oldpath) in old['python_source_paths']
    assert sha(oldpath)==oldref.get('script_sha256',oldref.get('source_sha256'))
    os.kill(3424328,signal.SIGTERM);report['old_action']='SIGTERM_OWN_VERIFIED_READONLY_SERVICE'
except FileNotFoundError:report['old_action']='ALREADY_EXITED_NO_SIGNAL'
newsource=R/'scripts/wp5_recovery_hourly_watch_v3.py';pidfile=R/'reports/recovery_hourly_watch_v3.pid'
assert not pidfile.exists(),'New watcher already registered; do not launch a duplicate'
command=['/share/home/zixiao/.conda/envs/chemprop/bin/python','-B',str(newsource),'--hours-limit','192','--first-hour','1']
with (R/'reports/recovery_hourly_watch_v3.log').open('x') as log:
    p=subprocess.Popen(command,cwd=PROJECT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
report['command']=command;report['new_pid']=p.pid
for _ in range(100):
    if pidfile.exists():break
    if p.poll() is not None:raise RuntimeError('New watcher exited '+str(p.returncode))
    time.sleep(.1)
ref=json.loads((R/'reports/recovery_hourly_watch_v3_identity.json').read_text())
actual=identity(p.pid);assert ref['pid']==p.pid and actual['uid']==1278 and actual['start_ticks']==ref['start_ticks']
assert str(newsource) in actual['python_source_paths'] and ref['source_sha256']==sha(newsource)
report.update(status='OWN_READONLY_WATCH_REPLACED_AND_VERIFIED',new_actual_identity=actual,new_service_identity=ref)
(R/'reports/recovery_hourly_watch_replacement_actual_v1.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'old_pid':report['old_pid'],'new_pid':p.pid,'start_ticks':actual['start_ticks'],'hours_limit':ref['hours_limit']}))
