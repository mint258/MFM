"""Query every actual owned submission; preserve all failed/timeout parent costs."""
import argparse,csv,io,re
from pathlib import Path
from ..queue_v1.shared import ROOT,REPO,load,pin,write_new,query,on_login,need,now

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True);a=p.parse_args();on_login()
    need(re.fullmatch(r'[a-z0-9_]+',a.tag),'SAFE_NEW_TAG')
    output=ROOT/'control'/('owned_accounting_'+a.tag+'.json')
    rawpath=ROOT/'control'/('owned_sacct_'+a.tag+'.txt')
    need(not output.exists() and not rawpath.exists(),'NEW_ACCOUNTING_SNAPSHOT_REQUIRED')
    receipts={}
    for path in sorted((ROOT/'control/submissions').glob('*.json')):
        obj=load(path)
        if not isinstance(obj,dict) or not (obj.get('job_id') and obj.get('request') and obj.get('sbatch_returncode')==0):continue
        jid=str(obj['job_id']);need(jid.isdecimal() and jid not in receipts and obj.get('uid')==1278,'UNIQUE_ACTUAL_OWN_RECEIPT')
        receipts[jid]={'receipt_reference':pin(path),'job_name':obj['request'].get('job_name',path.stem)}
    need(receipts,'ACTUAL_RECEIPTS_REQUIRED')
    previous=load(ROOT/'control/owned_accounting_v7.json')
    need({v['JobIDRaw'] for v in previous['actual_parents']}<=set(receipts),'PRESERVE_EVERY_OLD_PARENT')
    argv=['sacct','-j',','.join(sorted(receipts,key=int)),'--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,Partition','-P']
    raw=query(argv)
    with rawpath.open('x',encoding='utf-8',newline='\n') as f:f.write(raw)
    rows=[];steps=[]
    for row in csv.DictReader(io.StringIO(raw),delimiter='|'):
        jid=row['JobIDRaw']
        if not jid.isdecimal():steps.append(row);continue
        need(jid in receipts,'UNEXPECTED_PARENT');row.update(receipts[jid]);row['allocated_core_seconds_observed']=int(row['ElapsedRaw'])*int(row['AllocCPUS']);rows.append(row)
    need(len(rows)==len(receipts) and {r['JobIDRaw'] for r in rows}==set(receipts),'EXACT_COMPLETE_PARENT_SET')
    terminal={'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED','SPECIAL_EXIT'}
    total=sum(r['allocated_core_seconds_observed'] for r in rows)
    evidence={'schema':'DATA_V1_OWNED_ACCOUNTING_POINT_IN_TIME_V2','observed_at':now(),'command_argv':argv,'query_returncode':0,'raw_sacct_reference':pin(rawpath),'actual_parents':rows,'steps_preserved_not_added_to_parent_cost':steps,'active_parent_job_ids':[r['JobIDRaw'] for r in rows if r['State'].split()[0] not in terminal],'allocated_core_seconds_observed':total,'allocated_core_hours_observed':total/3600,'cost_basis':'Actual parent ElapsedRaw integer seconds times AllocCPUS; every FAILED/TIMEOUT included; steps are preserved without double charging.','zero_elapsed_interpretation':'Scheduler integer-second floor, not proof of zero physical cost.','resource_policy_authority':pin(REPO/'configs/data_v1/user_cpu_auto_memory_20261026_v1.json'),'scheduler_memory_requested_by_new_policy':False,'source_reference':pin(Path(__file__).absolute()),'data_bodies_read':False}
    write_new(output,evidence);print({'snapshot':pin(output),'parents':len(rows),'active':evidence['active_parent_job_ids'],'allocated_core_hours_observed':total/3600})

if __name__=='__main__':main()
