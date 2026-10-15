from pathlib import Path
import os,json,signal,subprocess,time,hashlib
R=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
assert os.getuid()==1278
old_pid=3429748;old_ticks='8054049243'
old_source=R/'scripts/wp5_recovery_hourly_watch_v3.py'
new_source=R/'scripts/wp5_recovery_hourly_watch_v4.py'
assert hashlib.sha256(old_source.read_bytes()).hexdigest()=='7f0911d40d55f361fc3d6569d0c88bcc97622ab1b54a3fed3cc559c908cf39d2'
assert hashlib.sha256(new_source.read_bytes()).hexdigest()=='43a055e5e51152f74dcb3f762a04cd4e75c09c20e82ae3af3c29446345fb3ca9'
def identity(pid):
    p=Path('/proc')/str(pid)
    status=p.joinpath('status').read_text()
    assert 'Uid:\t1278\t1278\t1278\t1278' in status
    return {'pid':pid,'start_ticks':p.joinpath('stat').read_text().rsplit(')',1)[1].split()[19],
            'cmdline':p.joinpath('cmdline').read_bytes().replace(b'\0',b' ').decode()}
before=identity(old_pid)
assert before['start_ticks']==old_ticks and str(old_source) in before['cmdline']
existing=R/'reports/recovery_hourly_watch_v4_identity.json'
if existing.exists():
    d=json.loads(existing.read_text())
    if (Path('/proc')/str(d['pid'])).exists():raise RuntimeError('Existing v4 watcher must be reviewed')
log=(R/'reports/recovery_hourly_watch_v4.log').open('ab',buffering=0)
env=dict(os.environ,PYTHONPATH=str(R/'scripts'))
child=subprocess.Popen(['/share/home/zixiao/.conda/envs/chemprop/bin/python','-B','-u',str(new_source),'--first-hour','4','--hours-limit','192','--apply-stop'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
for _ in range(50):
    if child.poll() is not None:raise RuntimeError('New watcher exited '+str(child.returncode))
    if existing.exists():
        d=json.loads(existing.read_text())
        if d.get('pid')==child.pid:break
    time.sleep(.1)
else:raise RuntimeError('No actual new identity after 5 seconds')
after=identity(child.pid)
assert str(new_source) in after['cmdline']
again=identity(old_pid)
assert again['start_ticks']==old_ticks and again['cmdline']==before['cmdline']
os.kill(old_pid,signal.SIGTERM)
proof={'schema':'WP5_OWN_GUIDE_WATCH_REPLACEMENT_V2','time':time.time(),'old':before,'new':after,'new_identity':d,'old_owned_watcher_TERM':True,'science_jobs_changed':False,'phase_submitted':False,'last_actual_observer_hour':3,'next_hour':4}
(R/'reports/recovery_hourly_watch_replacement_actual_v2.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'new_pid':child.pid,'new_start_ticks':after['start_ticks'],'old_owned_watcher_terminated':old_pid,'science_jobs_changed':False}))
