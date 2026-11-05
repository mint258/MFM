"""Strict model-owned CPU metadata adapter; no model or numeric shadow operations."""
from __future__ import annotations
import hashlib


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_capture_accounting(accounting, job_id):
    """Validate all original sacct rows without filtering or rewriting raw evidence."""
    _require(type(job_id) is str and job_id.isascii() and job_id.isdecimal(), 'Exact decimal parent job required')
    expected = ['sacct', '-n', '-P', '-j', job_id,
                '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS']
    _require(accounting['argv'] == expected and type(accounting['returncode']) is int
             and accounting['returncode'] == 0, 'Exact successful Root sacct invocation required')
    stdout = accounting['stdout']
    _require(type(stdout) is str and hashlib.sha256(stdout.encode()).hexdigest()
             == accounting['stdout_sha256'], 'Original complete raw stdout SHA differs')
    rows = [line.split('|') for line in stdout.splitlines() if line.strip()]
    expected_ids = {job_id, job_id+'.batch', job_id+'.extern'}
    _require(len(rows) == 3 and all(len(row) == 6 for row in rows)
             and {row[0] for row in rows} == expected_ids,
             'Exactly one parent, one named batch and one named extern row required')
    by_id = {row[0]: row for row in rows}
    parent = by_id[job_id]
    _require(parent[:4] == [job_id, 'zixiao', 'COMPLETED', '0:0'] and parent[5] == '16',
             'Unique actual parent must be zixiao/COMPLETED/0:0/16CPU')
    for row in rows:
        _require(row[4].isascii() and row[4].isdecimal(), 'Nonnegative integer ElapsedRaw required')
    elapsed = int(parent[4])
    for suffix in ('.batch', '.extern'):
        step = by_id[job_id+suffix]
        _require(step[:4] == [job_id+suffix, '', 'COMPLETED', '0:0']
                 and step[5] == '16' and int(step[4]) <= elapsed,
                 'Named step must have empty User, C0, 16CPU and bounded elapsed time')
    return {'schema': 'model_v3_fixed_h0_capture_accounting_validation_v3',
            'raw_stdout_sha256': accounting['stdout_sha256'], 'original_row_count': 3,
            'original_row_order': [row[0] for row in rows], 'parent': parent,
            'steps': [by_id[job_id+'.batch'], by_id[job_id+'.extern']],
            'raw_stdout_filtered_or_rewritten': False}


def metadata_selfcheck():
    """Synthetic parser controls only; these do not assert any actual job succeeded."""
    job = '71'
    stdout = '71|zixiao|COMPLETED|0:0|48|16\n71.batch||COMPLETED|0:0|48|16\n71.extern||COMPLETED|0:0|48|16\n'
    def sample(text=stdout):
        return {'argv': ['sacct', '-n', '-P', '-j', job,
                        '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS'],
                'returncode': 0, 'stdout': text,
                'stdout_sha256': hashlib.sha256(text.encode()).hexdigest()}
    good = sample()
    _require(validate_capture_accounting(good, job)['original_row_count'] == 3, 'Three-row positive control failed')
    bad = []
    changed = sample(); changed['stdout_sha256'] = '0'*64; bad.append(changed)
    changed = sample(); changed['returncode'] = 1; bad.append(changed)
    changed = sample(); changed['returncode'] = False; bad.append(changed)
    changed = sample(); changed['argv'][3:3] = ['-X']; bad.append(changed)
    for text in (stdout.splitlines()[0]+'\n',
                 stdout.replace('71.extern', '71.batch'),
                 stdout.replace('71.extern', '71.0'),
                 stdout.replace('71|zixiao', '72|zixiao'),
                 stdout.replace('71|zixiao', '71|foreign'),
                 stdout.replace('71.batch||', '71.batch|zixiao|'),
                 stdout.replace('71.extern||COMPLETED|0:0', '71.extern||FAILED|1:0'),
                 stdout.replace('71.batch||COMPLETED|0:0|48|16', '71.batch||COMPLETED|0:0|48|8'),
                 stdout.replace('71.extern||COMPLETED|0:0|48|16', '71.extern||COMPLETED|0:0|49|16'),
                 stdout.replace('|48|16', '|-1|16'),
                 stdout.replace('|48|16', '|48|16|extra')):
        bad.append(sample(text))
    for index, observation in enumerate(bad):
        try:
            validate_capture_accounting(observation, job)
        except ValueError:
            pass
        else:
            raise ValueError('Metadata negative control accepted: '+str(index))
    return {'scope': 'SYNTHETIC_METADATA_PARSER_CONTROLS_ONLY', 'positive_controls': 1,
            'rejected_negative_controls': len(bad), 'actual_job_claim': False}
