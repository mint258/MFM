"""Bounded Root metadata coordinator: finish pilot reporting, never launch the full run."""
import fcntl, json, os, signal, socket, subprocess, time
from pathlib import Path
from prepare import ROOT, PROJECT, save, sha

TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL', 'DEADLINE', 'REVOKED'}

def accounting(ids):
    p = subprocess.run(['sacct', '-j', ','.join(ids), '-n', '-P',
        '--format=JobIDRaw,User,State,ExitCode,JobName'], stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise RuntimeError({'sacct_rc': p.returncode, 'stderr': p.stderr})
    rows = {}
    for line in p.stdout.splitlines():
        cols = line.split('|')
        if cols[0] in ids:
            assert cols[1] == 'zixiao' and cols[4].startswith('sprime_')
            rows[cols[0]] = {'state': cols[2].split()[0], 'exit_code': cols[3], 'job_name': cols[4]}
    assert set(rows) == set(ids), rows
    return rows

def main():
    assert os.getuid() == 1278 and socket.gethostname().split('.')[0] == 'sonmi'
    lock = (ROOT / 'submission/pilot_close_watch.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    script = ROOT / 'scripts/summarize_pilot_v6.sbatch'
    pinned = {str(p): sha(p) for p in [script, ROOT / 'scripts/summarize_pilot.py',
        ROOT / 'scripts/reproduce100_v6_independent.py', ROOT / 'scripts/sprime_v6.py']}
    ids = [json.loads((ROOT / f'submission/pilot_v6_group{g}.json').read_text())['job_id'] for g in range(1, 6)]
    ids.append(json.loads((ROOT / 'submission/reproduce100_independent_v6.json').read_text())['job_id'])
    identity = {'pid': os.getpid(), 'uid': os.getuid(), 'hostname': socket.gethostname(),
        'started_epoch': time.time(), 'script_sha256': sha(__file__), 'watched_job_ids': ids,
        'pinned_sources': pinned, 'poll_interval_seconds': 600, 'maximum_hours': 10,
        'full_run_submission_enabled': False}
    save(ROOT / 'reports/pilot_close_watch_identity.json', identity)
    wake = False
    def wakeup(signum, frame):
        nonlocal wake
        wake = True
    signal.signal(signal.SIGUSR1, wakeup)
    deadline = time.monotonic() + 10 * 3600
    receipt_path = ROOT / 'submission/summarize_pilot_v6.json'
    while time.monotonic() < deadline:
        try:
            assert all(sha(p) == expected for p, expected in pinned.items()), 'Pinned source changed'
            rows = accounting(ids)
            state = {'epoch': time.time(), 'jobs': rows, 'status': 'WAITING_FOR_PILOT_AND_RERUN'}
            if all(r['state'] in TERMINAL for r in rows.values()):
                if any(r['state'] != 'COMPLETED' or r['exit_code'] != '0:0' for r in rows.values()):
                    state['status'] = 'PILOT_OR_RERUN_TERMINAL_ERROR'
                    save(ROOT / 'reports/pilot_close_watch_status.json', state)
                    print(json.dumps(state), flush=True)
                    return
                if not receipt_path.exists():
                    p = subprocess.run(['python', str(ROOT / 'scripts/collect_accounting.py'), '--stage', 'pilot_v6'],
                        stdin=subprocess.DEVNULL, cwd=PROJECT, capture_output=True, text=True, timeout=60)
                    assert p.returncode == 0, (p.returncode, p.stderr)
                    p = subprocess.run(['python', str(ROOT / 'scripts/submit.py'), str(script),
                        '--node', 'compute-0-2', '--cpus', '16', '--mem-gib', '32'], stdin=subprocess.DEVNULL,
                        cwd=PROJECT, capture_output=True, text=True, timeout=60)
                    save(ROOT / 'reports/pilot_summary_submission_from_watch.json',
                        {'epoch': time.time(), 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
                    if p.returncode:
                        raise RuntimeError('Report submission unavailable; exact reason saved')
                report_id = json.loads(receipt_path.read_text())['job_id']
                report = accounting([report_id])[report_id]
                state.update(status='REPORT_SUBMITTED', report_job_id=report_id, report_job=report)
                if report['state'] in TERMINAL:
                    state['status'] = 'REPORT_READY' if report['state'] == 'COMPLETED' and report['exit_code'] == '0:0' else 'REPORT_TERMINAL_ERROR'
                    if state['status'] == 'REPORT_READY':
                        state['pilot_result'] = json.loads((ROOT / 'reports/pilot_summary.json').read_text())['status']
                        state['reproduction100'] = json.loads((ROOT / 'reports/pilot_reproduction100.json').read_text())['status']
                    save(ROOT / 'reports/pilot_close_watch_status.json', state)
                    print(json.dumps(state), flush=True)
                    return
            save(ROOT / 'reports/pilot_close_watch_status.json', state)
            print(json.dumps(state), flush=True)
        except Exception as exc:
            save(ROOT / 'reports/pilot_close_watch_error.json', {'epoch': time.time(), 'error': repr(exc)})
            print('METADATA_ERROR ' + repr(exc), flush=True)
        until = time.monotonic() + 600
        while time.monotonic() < until and time.monotonic() < deadline and not wake:
            time.sleep(min(5, max(.1, until - time.monotonic())))
        wake = False
    save(ROOT / 'reports/pilot_close_watch_status.json', {'status': 'BOUNDED_WATCH_EXPIRED', 'epoch': time.time()})

if __name__ == '__main__':
    main()
