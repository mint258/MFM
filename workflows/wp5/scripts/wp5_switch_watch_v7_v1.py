"""Root-only prepared watch4 to watch7 service switch; no Slurm, QM or queue mutation."""
import argparse, ast, fcntl, hashlib, json, os, signal, socket, subprocess, sys, time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
OLD=ROOT/'scripts/wp5_recovery_hourly_watch_v6.py'
NEW=ROOT/'scripts/wp5_recovery_hourly_watch_v7.py'
OBSERVER=ROOT/'scripts/wp5_hourly_observe_v6.py'
EXPECTED={str(OLD):'98ac7e33eb1d6a2aebff5c8d1a43f26a5d744ef28a54becaee5f5916b85ce4f7',
          str(NEW):'3e7d4cc746f030f671974c0c52306d08a827150d5ad3f72f6e32ea0e64e0af8a',
          str(OBSERVER):'7cc2bffce68f7eedb329295c2bf2615a62b4a71c6698d4ddc512155440bda8e5'}
def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def alive(identity,source):
    pid=int(identity['pid']); proc=Path('/proc')/str(pid)
    if not proc.exists():return False
    stat=proc.joinpath('stat').read_text().rsplit(')',1)[1].split()
    if stat[0]=='Z':return False
    uid=int(next(line.split()[1] for line in proc.joinpath('status').read_text().splitlines() if line.startswith('Uid:')))
    cmd=proc.joinpath('cmdline').read_bytes().split(b'\0')
    if uid!=1278 or str(identity.get('start_ticks'))!=stat[19] or identity.get('source_path')!=str(source) or identity.get('source_sha256')!=EXPECTED[str(source)] or str(source).encode() not in cmd:
        raise ValueError('WATCH_PROCESS_IDENTITY_MISMATCH: '+str(pid))
    return True
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true');p.add_argument('--switch',action='store_true')
    p.add_argument('--first-hour',type=int,default=1);p.add_argument('--hours-limit',type=float,default=192)
    a=p.parse_args()
    if a.check:
        ast.parse(Path(__file__).read_text());print('WATCH_SWITCH_AST_PASS_NOT_STARTED');return
    for path,expected in EXPECTED.items():
        if sha(path)!=expected:raise ValueError('FROZEN_WATCH_SOURCE_DIFFERS: '+path)
    old_path=ROOT/'reports/recovery_hourly_watch_v6_identity.json'
    new_path=ROOT/'reports/recovery_hourly_watch_v7_identity.json'
    old=read(old_path)
    old_live=alive(old,OLD)
    existing=read(new_path) if new_path.is_file() else None
    new_live=alive(existing,NEW) if existing else False
    from wp5_hourly_observe_v6 import effective_jobs
    selected=effective_jobs()
    plan={'status':'PREPARED_NOT_STARTED','old_identity':old,'old_alive':old_live,
          'new_alive':new_live,'new_source':{'path':str(NEW),'sha256':EXPECTED[str(NEW)]},
          'actual_CONTINUATION14_receipt_closed':selected['ready'],
          'actual_cost_unique_jobs':len(selected['actual_cost_job_ids']),
          'actual_latest_logical_jobs':len(selected['effective_job_ids']),
          'apply_original_stop_conditions':old.get('STOP_flag_only') is True,
          'QM_started':False,'Slurm_submitted':False,'queue_written':False,
          'STOP_removed':False,'STOP_rules_changed':False}
    if not a.switch:print(json.dumps(plan,indent=2));return
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='sonmi':
        raise ValueError('ROOT_COORDINATOR_ZIXIAO_UID1278_ON_SONMI_REQUIRED')
    if not selected['ready'] or len(selected['actual_cost_job_ids'])!=385 or len(selected['effective_job_ids'])!=78:
        raise ValueError('WAIT_FOR_ACTUAL_CONTINUATION14_72_PLUS6_RECEIPT')
    with (ROOT/'reports/watch6_to_watch7_switch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if new_live:
            child_identity=existing
        else:
            cmd=[sys.executable,str(NEW),'--first-hour',str(a.first_hour),'--hours-limit',str(a.hours_limit)]
            if old.get('STOP_flag_only') is True:cmd.append('--apply-stop')
            log_path=ROOT/'logs'/('recovery_hourly_watch_v7_root_switch_'+str(int(time.time()))+'.log')
            with log_path.open('ab',buffering=0) as log:
                child=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                                       cwd=str(ROOT),start_new_session=True,close_fds=True)
            child_identity=None
            for _ in range(50):
                if child.poll() is not None:raise ValueError('WATCH7_START_FAILED: '+str(log_path))
                if new_path.is_file():
                    observed=read(new_path)
                    if observed.get('pid')==child.pid and alive(observed,NEW):
                        child_identity=observed;break
                time.sleep(0.1)
            if child_identity is None:
                child.terminate()
                raise ValueError('WATCH7_START_IDENTITY_NOT_VERIFIED: '+str(log_path))
        # Only retire the exact old metadata monitor after new watcher identity is verified.
        if old_live and alive(old,OLD):os.kill(int(old['pid']),signal.SIGTERM)
        result={**plan,'status':'WATCH7_STARTED_OLD_WATCH6_RETIRED' if old_live else 'WATCH7_STARTED',
                'new_identity':child_identity,'old_SIGTERM_sent':old_live,'time':time.time()}
        out=ROOT/'reports'/('watch6_to_watch7_switch_'+str(time.time_ns())+'.json')
        with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
        print(json.dumps({'status':result['status'],'report':str(out),'sha256':sha(out),'new_pid':child_identity['pid']}))
if __name__=='__main__':main()
