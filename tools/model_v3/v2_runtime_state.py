"""Resolve current Slurm control state before delayed accounting observations."""


def observed_job_state(job, accounting, controller_text, *, owner_uid=1278):
    """Keep historical fallback explicit; never relabel a foreign allocation."""
    for line in controller_text.splitlines():
        fields = dict(word.split('=', 1) for word in line.split() if '=' in word)
        if fields.get('JobId') != str(job):
            continue
        if not fields.get('UserId', '').endswith('(' + str(owner_uid) + ')'):
            raise ValueError('Controller record ownership differs from the model account')
        if not fields.get('JobState'):
            raise ValueError('Controller record lacks its current job state')
        return fields['JobState'], 'slurm_controller'
    return accounting.get(str(job), 'UNKNOWN'), 'accounting_fallback'
