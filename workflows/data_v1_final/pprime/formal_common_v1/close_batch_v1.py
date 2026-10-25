"""Bind actual parent sacct cost, including failures; never submit another batch."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

from common_v1 import IO, load, pilot_review


def actual_parent(result, rows):
    matches=[row for row in rows if str(row.get('JobIDRaw',row.get('JobID')))==str(result['runtime']['job_id'])]
    if len(matches)!=1:raise ValueError('EXACTLY_ONE_ACTUAL_PARENT_ROW_REQUIRED_NO_BATCH_EXTERN_SUM')
    r=matches[0]
    if r['User']!='zixiao' or r['NodeList']!=result['runtime']['node'] or int(r['AllocCPUS'])!=16 or int(r['ElapsedRaw'])<0:
        raise ValueError('ACTUAL_PARENT_OWNER_NODE_CPU_BINDING_MISMATCH')
    state=r['State'].split()[0]
    if state not in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}:
        raise ValueError('ACTUAL_PARENT_MUST_BE_TERMINAL')
    return r,int(r['AllocCPUS'])*int(r['ElapsedRaw'])


def assess(result, rows, rate):
    parent,seconds=actual_parent(result,rows)
    estimate=rate*result['requested_new_records']
    gates={'terminal_parent_completed_zero':parent['State']=='COMPLETED' and parent['ExitCode']=='0:0',
       'compute_and_export_closed':result['status']=='PPRIME_FORMAL_BATCH_CLOSED_AWAITING_ACTUAL_PARENT_ACCOUNTING' and not result['failures'],
       'sixteen_workers_exited_joined':result['all_workers_joined'],
       'every_requested_new_record_closed':result['new_records']==result['requested_new_records'],
       'actual_allocated_cost_within_1_5x_pilot_estimate':seconds<=1.5*estimate}
    return {'schema':'PPRIME_FORMAL_BATCH_ACTUAL_CLOSURE_V1',
       'status':'PPRIME_FORMAL_BATCH_ACTUALLY_CLOSED' if all(gates.values()) else 'PPRIME_FORMAL_STOP_REPORT_ROOT_NO_FURTHER_DISPATCH',
       'gates':gates,'actual_parent':parent,'allocated_core_seconds':seconds,'allocated_core_hours':seconds/3600,
       'requested_new_records':result['requested_new_records'],'estimated_core_seconds':estimate,
       'actual_core_seconds_per_requested_new_conformer':seconds/result['requested_new_records'] if result['requested_new_records'] else None,
       'reused_pilot_cost_counted_again':False,'child_CPU_substituted_for_parent_allocation':False,
       'scientific_failure_outcomes_preserved':True,'next_job_submitted':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','result','raw-sacct','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();c,_=load(a.config);result=json.loads(a.result.read_text())
    plan=json.loads(IO.require_pin(result['plan']).read_text())
    _,_,gates=pilot_review(plan['pilot_review']['path'],c['pilot_config']['path'])
    rows=list(csv.DictReader(a.raw_sacct.read_text().splitlines(),delimiter='|'))
    report=assess(result,rows,gates['allocated_core_seconds_per_requested_conformer'])
    report.update(result=IO.reference(a.result),raw_sacct=IO.reference(a.raw_sacct),config=IO.reference(a.config))
    IO.write_json(a.output,report)


if __name__=='__main__':main()
