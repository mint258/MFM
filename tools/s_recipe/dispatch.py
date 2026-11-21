"""S-owned GPU dispatch using the existing node observation and handoff math."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

from runtime import CONTROL, REPO, ROOT, write

P_REPO = ROOT/'MFM_p_recipe'
OLD = '/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
NEW = str(ROOT/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python')


def read(path):
    return json.loads(Path(path).read_text())


@contextmanager
def ledger():
    with (CONTROL/'execution.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = CONTROL/'execution.json'
        state = read(path) if path.is_file() else dict(schema='S_RECIPE_EXECUTION_V1', runs={}, statistics={})
        try:
            yield state
        finally:
            write(path, state)


def gate():
    registration = read(REPO/'configs/s_recipe/preregistration.json')
    if registration.get('status') != 'FROZEN':
        return 'WAITING_S_PREREGISTRATION_FREEZE'
    plan_path = P_REPO/'configs/p_recipe/fixed_20261115/confirmation/plan.json'
    if not plan_path.is_file() or not read(plan_path).get('recipe_frozen'):
        return 'WAITING_P_RECIPE_FREEZE'
    plan = read(plan_path)
    configs = {read(path)['run']: read(path) for path in plan['configurations']}
    execution = read(ROOT/'runs/p_recipe_20261113/study_execution.json')
    if not any(name in configs and configs[name]['samples'] == 9000000 and
               record.get('job_id') and record.get('state') not in
               ('SUBMITTING', 'SUBMISSION_OBSERVATION_UNCERTAIN')
               for name, record in execution['runs'].items()):
        return 'WAITING_P_9M_SUBMISSION'
    return None


def authorized(c):
    """Only the initial six runs are unconditional taskbook work."""
    if c['samples'] == 9000000:
        best = read(REPO/'configs/s_recipe/CURRENT_BEST.json')
        if best.get('status') != 'FROZEN' or c['seed'] != 0:
            raise ValueError('9M requires the final frozen S recipe')
        if c['arm'] == 'S-B0':
            return
        if c['arm'] != 'S-final' or best['recipe'] == 'S-B0' or set(c['components']) != set(best['components']):
            raise ValueError('Only a distinct frozen S-final may accompany9M S-B0')
        return
    if c['arm'] == 'S-M1':
        proposal = read(REPO/'configs/s_recipe/merge_proposal.json')
        if set(c['components']) != set(proposal['components']) or not proposal['ready']:
            raise ValueError('Merge does not match the registered adopted components')
        return
    if c['seed'] == 1:
        decisions = read(REPO/'configs/s_recipe/seed0_decisions.json')['arms']
        triggers = [arm for arm, result in decisions.items()
                    if arm != 'S-G1' and result.get('status') == 'COMPLETE' and result['R3']['verdict'] == 'WIN']
        if c['arm'] not in triggers and not (c['arm'] == 'S-B0' and triggers):
            raise ValueError('Only a seed0 WIN authorizes seed1 and its one shared baseline')
        return
    if c['seed'] != 0 or c['arm'] not in ('S-B0', 'S-N1', 'S-N2', 'S-R1', 'S-R2', 'S-G1'):
        raise ValueError('Not a taskbook screening run')


def existing_scheduling():
    directory = REPO/'tools/p_recipe'
    sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location('s_reused_scheduler', directory/'launch_plan.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def submit(paths):
    blocked = gate()
    if blocked:
        return dict(status=blocked, submitted=[])
    scheduler = existing_scheduling()
    policy = dict(read(REPO/'configs/p_recipe/scheduling.json'))
    own_policy = REPO/'configs/s_recipe/execution_policy.json'
    if own_policy.is_file():
        policy['minimum_free_gpu_mib'] = read(own_policy)['minimum_free_gpu_mib']
    nodes = [node for node in policy['nodes'] if node != 'compute-0-21']
    cards, errors = [], {}
    with ThreadPoolExecutor(3) as pool:
        futures = {pool.submit(scheduler.observe, node): node for node in nodes}
        for future in as_completed(futures):
            try:
                cards.extend(future.result())
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                errors[futures[future]] = str(error)
    submitted = []
    with ledger() as execution:
        execution.update(last_observed_at=time.time(), node_errors=errors)
        execution['observed_cards'] = [dict(card) for card in cards]
        busy = {r['gpu_uuid'] for r in execution['runs'].values()
                if r.get('status') not in ('COMPLETED', 'FAILED', 'CANCELLED')}
        cards = [card for card in cards if card['gpu_uuid'] not in busy and
                 not scheduler.own_gpu_busy(card['gpu_uuid'], card['node'])]
        for filename in paths:
            c = read(filename)
            if c['run'] in execution['runs']:
                continue
            authorized(c)
            if not Path(c['initialization']).is_file():
                continue
            if c['noise'] == 'frad' and not (REPO/'configs/s_recipe/rotors.json').is_file():
                continue
            preferred = ('compute-0-20', 'compute-0-22') if c['samples'] > 3000000 else tuple('compute-0-'+str(i) for i in range(8))
            cards.sort(key=lambda card: (card['node'] not in preferred,
                scheduler.gpu_rank(card['gpu_name'], policy)))
            chosen = None
            cpus = c['workers']+2
            for card in cards:
                mode = scheduler.route(card['free_cpus'], cpus, card['used_mib'], card['total_mib'], policy)
                if mode == 'WAIT_GPU':
                    continue
                if card['node'] not in ('compute-0-20', 'compute-0-22') and (
                        mode != 'Slurm' or card.get('existing_compute_context')):
                    continue
                chosen = card, mode
                break
            if chosen is None:
                continue
            card, mode = chosen
            cards.remove(card)
            python = NEW if '5090' in card['gpu_name'] else OLD
            handle = c['run'] + ('_attempt'+str(c['execution_attempt'])
                                 if c.get('execution_attempt', 1) > 1 else '')
            c.update(gpu_uuid=card['gpu_uuid'], node=card['node'],
                     handoff_request=str(CONTROL/(handle+'_handoff_request.json')),
                     handoff_ack=str(CONTROL/(handle+'_handoff_ack.json')))
            if any(Path(c[key]).exists() for key in ('handoff_request', 'handoff_ack')):
                raise RuntimeError('Existing handoff controls require inspecting the original handle')
            write(filename, c)
            task = dict(run=c['run'], node=card['node'], gpu_uuid=card['gpu_uuid'],
                minimum_free_gpu_mib=policy['minimum_free_gpu_mib'], python=python,
                configuration=str(filename), cpus=cpus, mode=mode,
                state_path=str(CONTROL/(handle+'_process.json')),
                command=[python, '-B', '-u', 'tools/s_recipe/train.py', '--configuration', str(filename)])
            task_path = CONTROL/(handle+'_task.json')
            write(task_path, task)
            record = dict(status='SUBMITTING', mode=mode, submitted_at=time.time(),
                          configuration=str(filename), task=str(task_path), **card)
            execution['runs'][c['run']] = record
            write(CONTROL/'execution.json', execution)
            if mode == 'native_with_standby':
                command = [python, '-B', '-u', str(REPO/'tools/s_recipe/runtime.py'), '--configuration', str(task_path)]
                code = ('import subprocess;f=open('+repr(str(CONTROL/(c['run']+'_native.log')))+',"ab",buffering=0);'
                        'p=subprocess.Popen('+repr(command)+',stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print(p.pid)')
                try:
                    record['wrapper_pid'] = int(subprocess.check_output(['ssh', '-n', '-o', 'ConnectTimeout=10',
                        card['node'], shlex.join([python, '-B', '-c', code])], text=True, timeout=30).strip())
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    record.update(status='SUBMISSION_OBSERVATION_UNCERTAIN', error=str(error))
                    continue
            command = ['sbatch', '--parsable', '--partition=gpu', '--nodes=1', '--ntasks=1',
                '--nodelist='+card['node'], '--cpus-per-task='+str(cpus), '--job-name='+c['run'],
                '--output='+str(CONTROL/(c['run']+'_%j.log')),
                str(REPO/'tools/s_recipe/run.sbatch'), str(task_path)]
            try:
                record.update(job_id=int(subprocess.check_output(command, text=True, timeout=30).strip().split(';')[0]),
                              status='SUBMITTED')
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                record.update(status='SUBMISSION_OBSERVATION_UNCERTAIN', error=str(error))
            submitted.append(dict(run=c['run'], **record))
            write(CONTROL/'execution.json', execution)
    return dict(status='DISPATCH_OBSERVED', submitted=submitted)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--plan', type=Path, required=True)
    print(json.dumps(submit(read(p.parse_args().plan)['configurations'])), flush=True)
