"""One user-approved wall-clock hour per molecule, enforced outside native code."""
import contextlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

LIMIT_SECONDS = 3600
_METADATA = (
    'molecule_id', 'seed', 'D20', 'atomic_numbers', 'stereo_assigned',
    'assigned_isomeric_smiles', 'n_assigned_tetrahedral',
    'n_assigned_double_bond', 'stereo_draw_index', 'assigned_CIP_counts',
    'assigned_EZ_counts', 'stereo_assignment_complete',
    'normalized_removed_stereo_elements', 'stereo_draws',
)


def failed_packet(source, state, error, metadata=None):
    from .kernel import molecule_id
    from . import stereo
    from ..uff3_candidate_v1.core import seed_for
    mid = molecule_id(source)
    packet = dict(source=source, molecule_id=mid, seed=seed_for(mid), D20=None,
        atomic_numbers=[], conformers=[], candidates=[], attempts=[],
        requested_conformers=3, orders={'fixed_random': [], 'energy': [], 'diversity': []},
        state=state, error=error, cache_complete=False, native_all_failed=False,
        candidate_cache_sha256=None, atom_order_sha256=None,
        insufficient_conformers=True, generation_count_unknown=True,
        generation_order=[], worker_wall_seconds=None, worker_CPU_seconds=None,
        **stereo.defaults())
    metadata = metadata or {}
    if metadata.get('molecule_id', mid) != mid:
        raise ValueError('DEADLINE_CHECKPOINT_MOLECULE_DIFFERS')
    packet.update({k: metadata[k] for k in _METADATA if k in metadata})
    # A deadline is an interrupted native call, not evidence that all candidates
    # failed. Never enable another stereo draw or invent partial 3D delivery.
    packet.update(state=state, error=error, native_all_failed=False)
    history = list(packet.get('stereo_draws', []))
    if packet.get('stereo_assigned') and (
            not history or history[-1]['stereo_draw_index'] != packet['stereo_draw_index']):
        history.append({**{k: packet[k] for k in stereo.FIELDS},
            'state': state, 'error': error, 'native_all_failed': False,
            'attempts': [], 'assigned_CIP_counts': packet['assigned_CIP_counts'],
            'assigned_EZ_counts': packet['assigned_EZ_counts']})
    packet['stereo_draws'] = history
    return packet


def _cpu_children():
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


def generate_limited(source, config, *, command=None):
    """Supervise one isolated child across every candidate and stereo draw."""
    seconds = float(config.get('molecule_timeout_seconds', LIMIT_SECONDS))
    if not 0 < seconds <= LIMIT_SECONDS:
        raise ValueError('MOLECULE_DEADLINE_MUST_BE_AT_MOST_3600_SECONDS')
    from .kernel import molecule_id
    mid = molecule_id(source)
    root = str(Path(__file__).resolve().parents[3])
    if command is None:
        bootstrap = ("import runpy,sys;sys.path.insert(0,%r);"
                     "runpy.run_module('workflows.expansion.window3_v2.deadline',"
                     "run_name='__main__')" % root)
        command = [sys.executable, '-B', '-I', '-c', bootstrap]
    began, cpu = time.monotonic(), _cpu_children()
    process = subprocess.Popen(command, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding='utf-8', errors='replace', start_new_session=True)
    expired = False
    try:
        output, errors = process.communicate(json.dumps(
            {'source': source, 'config': config}) + '\n',
            timeout=max(0, seconds - (time.monotonic() - began)))
    except subprocess.TimeoutExpired:
        expired = True
        # A new session belongs only to this child; native C/C++ cannot defer
        # this signal as it could a Python signal handler.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        output, errors = process.communicate()
    metadata, result = {}, None
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get('event') == 'checkpoint':
            item = event['metadata']
            if item.get('molecule_id', mid) != mid:
                raise ValueError('DEADLINE_CHECKPOINT_MOLECULE_DIFFERS')
            for key in _METADATA:
                if key in item and (key != 'D20' or item[key] is not None):
                    metadata[key] = item[key]
        elif event.get('event') == 'result':
            result = event['packet']
    if expired:
        packet = failed_packet(source, 'UFF_TIMEOUT',
            'USER_MOLECULE_WALL_LIMIT: %g seconds across all stereo draws' % seconds,
            metadata)
    elif process.returncode or result is None:
        packet = failed_packet(source, 'TECHNICAL_UNKNOWN',
            'NATIVE_CHILD_EXIT: %s; %s' % (process.returncode, errors[-1000:]), metadata)
    else:
        if result['molecule_id'] != mid:
            raise ValueError('DEADLINE_RESULT_MOLECULE_DIFFERS')
        packet = result
    packet['worker_wall_seconds'] = time.monotonic() - began
    packet['worker_CPU_seconds'] = _cpu_children() - cpu
    packet['molecule_timeout_seconds'] = seconds
    packet['molecule_timed_out'] = expired
    packet['native_child_exit_code'] = process.returncode
    return packet


def child_main():
    request = json.loads(sys.stdin.readline())
    source, config = request['source'], request['config']
    channel = sys.stdout

    def checkpoint(stage, packet):
        item = {k: packet[k] for k in _METADATA if k in packet}
        channel.write(json.dumps({'event': 'checkpoint', 'stage': stage,
                                 'metadata': item}, allow_nan=False) + '\n')
        channel.flush()

    with contextlib.redirect_stdout(sys.stderr):
        from . import producer
        from .kernel import generate
        producer.init(config)
        producer.KERNEL.deadline_progress = checkpoint
        packet = generate(source, producer.KERNEL,
            reuse_d20=bool(config.get('stereo_supplement')), progress=checkpoint)
    channel.write(json.dumps({'event': 'result', 'packet': packet},
                             allow_nan=False) + '\n')
    channel.flush()


if __name__ == '__main__':
    child_main()
