"""Continue explicitly registered model jobs after the original disk guard admits them."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

ROOT = Path('/share/home/zixiao/descriptor_analysis')
REPO = ROOT / 'MFM_model_v3'
WRAPPER = str(REPO / 'tools/model_v3/v2_run_development.sbatch')
TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'PREEMPTED'}


def owned_controller(entry, text):
    for line in text.splitlines():
        fields = dict(word.split('=', 1) for word in line.split() if '=' in word)
        if fields.get('JobId') != str(entry['job']):
            continue
        if fields.get('UserId') != 'zixiao(1278)':
            raise ValueError('Controller owner differs')
        if not fields.get('JobState'):
            raise ValueError('Controller state is missing')
        if fields['JobState'] in TERMINAL:
            return fields
        if fields.get('NodeList') != entry['node'] or fields.get('Restarts') != str(entry['restarts']):
            raise ValueError('Controller allocation or restart count differs')
        match = re.search(r'(?:^|\s)Command=(.*?)(?=\sWorkDir=|\sStdErr=|\sStdOut=|$)', line)
        expected = [WRAPPER, entry['mode'], entry['configuration'], entry['gpu'], entry['python']]
        if not match or shlex.split(match.group(1)) != expected:
            raise ValueError('Controller command differs from the registered execution')
        return fields
    return None


def recover_one(entry, controller_text, guard, *, admit, observe_again, send_cont):
    before = owned_controller(entry, controller_text)
    if before is None:
        return {'status': 'CONTROLLER_UNAVAILABLE'}
    state = before['JobState']
    if state in TERMINAL:
        return {'status': 'FINISHED', 'slurm_state': state}
    if state != 'STOPPED':
        return {'status': 'OBSERVING', 'slurm_state': state}
    if guard.get('status') != 'DISK_PAUSED':
        return {'status': 'STOPPED_OUTSIDE_DISK_GUARD', 'slurm_state': state}
    if guard.get('jobs') != [entry['job']] or guard.get('node') != entry['node']:
        raise ValueError('Disk guard belongs to another allocation')
    admission = admit(entry)
    current = owned_controller(entry, observe_again(entry))
    if current is None or current['JobState'] != 'STOPPED':
        return {'status': 'STATE_CHANGED_NO_SIGNAL', 'slurm_state': None if current is None else current['JobState']}
    send_cont(entry)
    return {'status': 'CONT_SENT', 'slurm_state_before': state, 'admission': admission}


def command(argv):
    return subprocess.run(argv, text=True, capture_output=True, check=True, timeout=60)


def controller(entry):
    result = subprocess.run(['scontrol', 'show', 'job', str(entry['job']), '-o'],
                            text=True, capture_output=True, timeout=30)
    return result.stdout


def accounting_terminal(entry):
    result = command(['sacct', '-j', str(entry['job']), '-n', '-P',
                      '--format=JobIDRaw,User,State,NodeList'])
    for line in result.stdout.splitlines():
        values = line.split('|')
        if len(values) >= 4 and values[0] == str(entry['job']):
            state = values[2].split()[0]
            if values[1] == 'zixiao' and values[3] == entry['node'] and state in TERMINAL:
                return state
    return None


def admit(entry):
    argv = [entry['python'], '-B', str(REPO / 'tools/model_v3/v2_diagnosis_disk.py'),
            '--once', '--output', entry['output'], '--node', entry['node'],
            '--job', str(entry['job']), '--state', '/dev/null']
    result = command(['ssh', '-n', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                      entry['node'], shlex.join(argv)])
    return json.loads(result.stdout)


def send_cont(entry):
    command(['scancel', '--signal=CONT', '--full', '--user=zixiao',
             '--nodelist='+entry['node'], str(entry['job'])])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True, type=Path)
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if os.getuid() != 1278:
        raise ValueError('Actual model account required')
    lock = Path(str(args.state)+'.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    started = time.time()
    while True:
        configuration = json.loads(args.configuration.read_text())
        rows = []
        for entry in configuration['jobs'] if configuration['enabled'] else []:
            try:
                text = controller(entry)
                guard_path = ROOT / 'runs/model_v31_20261105' / f"M3_controlled_{entry['job']}.state.json"
                guard = json.loads(guard_path.read_text()) if guard_path.exists() else {}
                row = recover_one(entry, text, guard, admit=admit,
                                  observe_again=controller, send_cont=send_cont)
                if row['status'] == 'CONTROLLER_UNAVAILABLE':
                    terminal = accounting_terminal(entry)
                    if terminal is not None:
                        row = {'status': 'FINISHED', 'slurm_state': terminal, 'state_source': 'accounting_fallback'}
                if row['status'] == 'CONT_SENT':
                    print(json.dumps(dict(event='ORIGINAL_JOB_CONTINUED', job=entry['job'], **row)), flush=True)
            except Exception as error:
                row = {'status': 'OBSERVATION_OR_ADMISSION_UNAVAILABLE', 'reason': str(error)}
            rows.append(dict(job=entry['job'], node=entry['node'], **row))
        finished = bool(rows) and all(row['status'] == 'FINISHED' for row in rows)
        value = dict(pid=os.getpid(), uid=os.getuid(), started_at=started, observed_at=time.time(),
                     status='DISABLED' if not configuration['enabled'] else 'FINISHED' if finished else 'WATCHING', jobs=rows)
        temporary = Path(str(args.state)+'.next')
        temporary.write_text(json.dumps(value)+'\n')
        temporary.replace(args.state)
        if args.once or finished or not configuration['enabled']:
            return
        time.sleep(configuration['interval_seconds'])


if __name__ == '__main__':
    main()
