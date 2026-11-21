"""Same-condition recovery from actual terminal handles, preserving all attempts."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path

from checkpoint_binding import validate_resume
from collect import accounting, TERMINAL
from dispatch import ledger, read
from runtime import CONTROL, capacity, write


def retry_configuration(current, saved, *, checkpoint=None, resume_samples=None,
                        acceptance_source=None):
    validate_resume(current, saved)
    c = deepcopy(current)
    for key in ('gpu_uuid', 'node', 'handoff_request', 'handoff_ack', 'resume', 'resume_samples'):
        c.pop(key, None)
    c['execution_attempt'] = current.get('execution_attempt', 1)+1
    if checkpoint:
        c.update(resume=str(checkpoint), resume_samples=resume_samples)
    else:
        if (c['arm'], c['seed']) != ('S-B0', 0):
            raise ValueError('This zero-state recovery is only for the failed baseline')
        if not saved.get('baseline_acceptance') or not acceptance_source:
            raise ValueError('Keep the original sole baseline acceptance before restarting')
        c['baseline_acceptance'] = saved['baseline_acceptance']
        c['baseline_acceptance_reference'] = str(acceptance_source)
    return c


def prepare(configuration, from_initialization=False):
    from s_statistics import cpu_only
    cpu_only()
    capacity()
    path = Path(configuration)
    c = read(path)
    with ledger() as state:
        record = state['runs'][c['run']]
        actual = accounting([record['job_id']]).get(record['job_id'])
        task = read(record['task'])
        process = read(task['state_path'])
        if not actual or actual['state'] not in TERMINAL or 'exit_code' not in process:
            raise ValueError('Recovery requires an actual terminal job and recorded process exit')
        if process['uid'] != os.getuid() or process['run'] != c['run']:
            raise ValueError('Recovery process owner/run does not match')
        output = Path(c['output'])
        owned = (CONTROL/'training').resolve()
        if output.is_symlink() or output.resolve().parent != owned:
            raise ValueError('Recovery output must be an owned direct S training directory')
        saved = read(output/'configuration.json')
        validate_resume(c, saved)
        prior = dict(record, slurm=actual, process=process, configuration_snapshot=c,
                     task_snapshot=task, output_before_recovery=str(output))
        if from_initialization:
            if actual['state'] != 'FAILED' or process['exit_code'] == 0:
                raise ValueError('Zero-state recovery requires the actual failed attempt')
            if list(output.glob('samples_*.pt')):
                raise ValueError('A closed checkpoint exists; do not discard recoverable progress')
            archive = CONTROL/'attempt_archive'/(c['run']+'_job'+str(record['job_id']))
            if (archive.exists() or not archive.resolve().is_relative_to(CONTROL.resolve())
                    or output.stat().st_uid != os.getuid()):
                raise ValueError('Inspect the owned archive target before moving failed outputs')
            new = retry_configuration(c, saved,
                                      acceptance_source=archive/'configuration.json')
            archive.parent.mkdir(parents=True, exist_ok=True)
            output.rename(archive)  # Same-filesystem rename; all failed files remain intact.
            prior.update(archived_output=str(archive), lost_updates_reason='No closed checkpoint before1M')
        else:
            request, ack = read(c['handoff_request']), read(c['handoff_ack'])
            checkpoint = Path(ack['checkpoint'])
            if (actual['state'] != 'COMPLETED' or process['exit_code'] != 0
                    or ack['run'] != c['run'] or request['request_id'] != ack['request_id']
                    or checkpoint.is_symlink() or checkpoint.resolve().parent != output.resolve()
                    or not checkpoint.is_file()
                    or not 0 < ack['clock']['samples_consumed'] < c['samples']):
                raise ValueError('Handoff must identify a closed partial checkpoint from this run')
            new = retry_configuration(c, saved, checkpoint=checkpoint,
                                      resume_samples=ack['clock']['samples_consumed'])
            prior['handoff_ack'] = ack
        state.setdefault('attempt_history', {}).setdefault(c['run'], []).append(prior)
        write(path, new)
        # Canonical scientific run/output remains unchanged; the next dispatcher
        # may start exactly one new execution handle with fresh control paths.
        del state['runs'][c['run']]
        return dict(status='RECOVERY_PREPARED', run=c['run'], configuration=str(path),
                    execution_attempt=new['execution_attempt'], resume=new.get('resume'),
                    jobs_submitted=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--configuration', type=Path, required=True)
    p.add_argument('--from-initialization', action='store_true')
    a = p.parse_args()
    print(json.dumps(prepare(a.configuration, a.from_initialization)), flush=True)
