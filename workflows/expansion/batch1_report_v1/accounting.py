"""Terminal native parent allocation costs, without counting batch/extern twice."""
import csv
from decimal import Decimal, localcontext
import io
import re

TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}


def need(value,message):
    if not value:raise ValueError(message)


def cpu_seconds(value):
    if value in (None,'','Unknown','N/A'):return None
    match=re.fullmatch(r'(?:(\d+)-)?(\d+):(\d+(?:\.\d+)?)(?::(\d+(?:\.\d+)?))?',value)
    need(match is not None,'Native TotalCPU format')
    days,a,b,c=match.groups()
    if c is None:
        need(Decimal(b)<60,'Native TotalCPU seconds range')
        return Decimal(days or 0)*86400+Decimal(a)*60+Decimal(b)
    need(b.isdigit()and int(b)<60 and Decimal(c)<60,'Native TotalCPU minute/seconds range')
    return Decimal(days or 0)*86400+Decimal(a)*3600+Decimal(b)*60+Decimal(c)


def hours(seconds):
    with localcontext()as context:
        context.prec=50
        return format(Decimal(seconds)/Decimal(3600),'f')


def summarize(inventory,reader):
    need(inventory['inventory_complete_for_declared_goal_scope']is True and inventory['coverage_statement'],
         'Explicit complete goal accounting inventory, including failed/superseded parents')
    result=[];seen=set();documents={}
    for item in inventory['parents']:
        endpoint=item['endpoint'];uid=item['uid'];job=str(item['job_id']);key=(endpoint,uid,job)
        need(key not in seen and re.fullmatch(r'\d+(?:_\d+)?',job),'Each native parent exactly once, never batch/extern')
        seen.add(key);ref=item['accounting_reference'];token=reader.token(ref)
        if token not in documents:documents[token]=reader.json(ref)
        document=documents[token]
        need(document['endpoint']==endpoint and document['uid']==uid,'Accounting endpoint/UID provenance')
        raw=document.get('raw_sacct')
        if raw is None:raw=reader.bytes(document['raw_sacct_reference']).decode('utf-8')
        rows=list(csv.DictReader(io.StringIO(raw),delimiter='|'))
        fields={'JobIDRaw','State','ExitCode','UID','ElapsedRaw','AllocCPUS','TotalCPU'}
        need(bool(rows)and fields<=set(rows[0]),'Native accounting needs header and ElapsedRaw/AllocCPUS/TotalCPU')
        selected=[row for row in rows if row['JobIDRaw']==job]
        need(len(selected)==1,'Exactly one native allocation parent row')
        row=selected[0];state=row['State'].split()[0].rstrip('+')
        need(state in TERMINAL and int(row['UID'])==uid,'Actual terminal own native parent; running costs are not final')
        elapsed=int(row['ElapsedRaw']);cpus=int(row['AllocCPUS'])
        need(elapsed>=0 and cpus>=0 and isinstance(item['stage'],str)and item['stage']
             and item['disposition']in('adopted','failed','superseded','cancelled','diagnostic'),
             'Nonnegative actual allocation with explicit cost role/disposition')
        if item['disposition']=='adopted':need(state=='COMPLETED'and row['ExitCode']=='0:0','Adopted input must be native C0')
        total=cpu_seconds(row['TotalCPU'])
        result.append(dict(endpoint=endpoint,uid=uid,job_id=job,stage=item['stage'],disposition=item['disposition'],
            state=state,exit_code=row['ExitCode'],elapsed_raw_seconds=elapsed,allocated_CPUs=cpus,
            allocated_core_seconds=elapsed*cpus,allocated_core_hours=hours(elapsed*cpus),
            TotalCPU_seconds_decimal=None if total is None else str(total),accounting_reference=ref))
    need(bool(result),'No empty accounting inventory')
    groups={}
    for row in result:
        for kind,key in (('stage',row['stage']),('disposition',row['disposition']),('endpoint',row['endpoint'])):
            group=groups.setdefault((kind,key),dict(parents=0,allocated_core_seconds=0,TotalCPU_seconds=Decimal(0),TotalCPU_unavailable_parents=0))
            group['parents']+=1;group['allocated_core_seconds']+=row['allocated_core_seconds']
            if row['TotalCPU_seconds_decimal']is None:group['TotalCPU_unavailable_parents']+=1
            else:group['TotalCPU_seconds']+=Decimal(row['TotalCPU_seconds_decimal'])
    summaries=[]
    for(kind,key),value in sorted(groups.items()):
        summaries.append(dict(group_type=kind,group=key,parents=value['parents'],allocated_core_seconds=value['allocated_core_seconds'],
            allocated_core_hours=hours(value['allocated_core_seconds']),
            observed_TotalCPU_seconds_decimal=None if value['TotalCPU_unavailable_parents']==value['parents']else str(value['TotalCPU_seconds']),
            TotalCPU_unavailable_parents=value['TotalCPU_unavailable_parents']))
    return dict(parents=result,groups=summaries,allocated_core_seconds=sum(row['allocated_core_seconds']for row in result),
        allocated_core_hours=hours(sum(row['allocated_core_seconds']for row in result)),
        coverage_statement=inventory['coverage_statement'],parent_steps_not_double_counted=True,
        failed_superseded_diagnostic_costs_preserved=True,allocated_core_hours_are_not_TotalCPU_or_kernel_process_CPU=True)
