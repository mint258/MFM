"""Settle an unused owned standby once; no resource retirement or model work."""
import re


def settle(job, name, call, persist, progress=None):
    """Caller has already proved full-budget native exit and actual PID absence.

    A started standby is only observed. A zero-work pending standby is held and
    rechecked before one cancellation; accounting must confirm its final state.
    """
    progress = progress or {}

    def accounting():
        raw = call('/usr/bin/sacct', '-X', '-n', '-P', '-j', str(job),
                   '--format=User,JobName%128,State,ExitCode,ElapsedRaw')
        rows = [row.split('|') for row in raw.splitlines() if row.strip()]
        if len(rows) != 1 or rows[0][:2] != ['zixiao', name]:
            raise ValueError('Standby accounting must bind the exact own job')
        return rows[0], raw

    def controller():
        raw = call('/usr/bin/scontrol', 'show', 'job', '-o', str(job))
        info = dict(re.findall(r'(?:^| )(\w+)=([^ ]*)', raw))
        if info.get('UserId') != 'zixiao(1278)' or info.get('JobName') != name:
            raise ValueError('Standby controller identity differs')
        return info

    row, raw = accounting()
    if row[2:] == ['PENDING', '0:0', '0'] and not progress.get('cancel_requested'):
        before = controller()
        if before.get('JobState') != 'PENDING':
            return dict(settled=False, actual=raw, reason='STANDBY_STARTED')
        call('/usr/bin/scontrol', 'hold', str(job))
        held = controller()
        row, raw = accounting()
        if (held.get('JobState') != 'PENDING' or held.get('Reason') != 'JobHeldUser'
                or row[2:] != ['PENDING', '0:0', '0']):
            return dict(settled=False, actual=raw, reason='ZERO_WORK_BOUNDARY_CHANGED')
        progress = dict(cancel_requested=True, standby_job_id=job, job_name=name)
        persist(progress)
        call('/usr/bin/scancel', str(job))
        row, raw = accounting()
    settled = ((row[2] == 'COMPLETED' and row[3] == '0:0')
               or row[2:] == ['CANCELLED by 1278', '0:0', '0'])
    return dict(settled=settled, actual=raw,
                cancel_requested=bool(progress.get('cancel_requested')))
