"""Actual terminal Slurm/producer metadata; no manual per-job approval file."""
from ..alpha_runtime_v1 import common as Q

TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}


def raw_rows(text,job):
    header=None;result=[]
    for line in text.splitlines():
        fields=line.strip().split('|')
        if 'JobIDRaw'in fields and 'State'in fields and 'ExitCode'in fields:
            header={name:i for i,name in enumerate(fields)};continue
        if not fields:continue
        identifier=fields[header['JobIDRaw']]if header and len(fields)>header['JobIDRaw']else fields[0]
        if not(identifier==job or identifier.startswith(job+'.')):continue
        if header:
            get=lambda name:fields[header[name]]
            row=(get('JobIDRaw'),get('State'),get('ExitCode'))
        else:
            Q.need(len(fields)>=3,'Actual parseable Slurm job/state/exit fields')
            row=tuple(fields[:3])
        result.append((row[0],row[1].split()[0].rstrip('+'),row[2]))
    return result


def parent(runtime,account_ref,require_C0=True):
    a=Q.load(Q.verify(account_ref));raw=Q.verify(a['raw_sacct_reference']).read_text()
    job=str(runtime['job_id']);uid=runtime.get('uid',Q.UID)
    Q.need(runtime['endpoint']==a['endpoint']==Q.ENDPOINT and uid==a['uid']==Q.UID,
           'Actual Alpha producer/runtime/accounting endpoint and UID')
    matches=[p for p in a['actual_parents']if str(p['JobIDRaw'])==job]
    Q.need(len(matches)==1 and int(matches[0]['UID'])==Q.UID,'One actual same producer parent')
    p=matches[0];state=p['State'].split()[0].rstrip('+');rows=raw_rows(raw,job)
    main=[r for r in rows if r[0]==job];steps=[r for r in rows if r[0]!=job]
    Q.need(len(main)==1 and main[0][1:]==(state,p['ExitCode'])
        and state in TERMINAL and all(r[1]in TERMINAL for r in rows)
        and any(r[0]==job+'.batch'for r in steps),'Actual parent and recorded batch/steps all terminal; no live old job tree')
    if require_C0:Q.need(state=='COMPLETED'and p['ExitCode']=='0:0','Actual completed producer C0 required')
    return p