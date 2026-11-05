"""Actual terminal identity contract; no scheduler or chemistry call."""
def actual_c0(account,job):
    parents=account.get('actual_parents') or [account.get('actual_parent',{})]
    matches=[p for p in parents if str(p.get('JobIDRaw',p.get('job_id')))==str(job)]
    if len(matches)!=1:raise ValueError('Exactly one actual original audit parent required')
    p=matches[0]
    if not (p.get('State',p.get('state'))=='COMPLETED' and p.get('ExitCode',p.get('exit_code'))=='0:0'
      and str(p.get('UID',p.get('uid')))=='1264' and p.get('endpoint',account.get('endpoint'))=='218.192.171.238:22'):
        raise ValueError('Actual original Alpha audit C0 required; no running/Main identity')
    return p
