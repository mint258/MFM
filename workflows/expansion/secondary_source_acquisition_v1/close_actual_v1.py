"""Account a finished secondary download from that endpoint's actual sacct only."""
import argparse,csv,io,json,os,pathlib
from contracts import ENDPOINT,UID,need,load,pin,verify,write_new


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--receipt',type=pathlib.Path,required=True)
    p.add_argument('--accounting-evidence',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    receipt=load(a.receipt);evidence=load(a.accounting_evidence)
    need(receipt['endpoint']==evidence['endpoint']==ENDPOINT and receipt['uid']==evidence['uid']==UID,'DO_NOT_MIX_CLUSTER_IDENTITIES_OR_COSTS')
    need(evidence['query_returncode']==0 and evidence['command_argv'][0]=='sacct','ACTUAL_SECONDARY_SACCT_REQUIRED')
    raw=verify(evidence['raw_sacct_reference']).read_text();jid=receipt['job_id']
    rows=list(csv.DictReader(io.StringIO(raw),delimiter='|'));parents=[r for r in rows if r.get('JobIDRaw')==jid]
    need(len(parents)==1,'EXACT_UNIQUE_SECONDARY_PARENT_REQUIRED');parent=parents[0]
    need(parent['State'].split()[0] in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'}
        and int(parent['AllocCPUS'])==16 and int(parent['ElapsedRaw'])>=0,'ACTUAL_TERMINAL_CPU16_PARENT_REQUIRED')
    seconds=int(parent['ElapsedRaw'])*int(parent['AllocCPUS'])
    result={'schema':'SECONDARY_COCONUT_ACTUAL_PARENT_COST_V1','status':'SECONDARY_ACTUAL_TERMINAL_PARENT_ACCOUNTED',
        'endpoint':ENDPOINT,'uid':UID,'receipt':pin(a.receipt),'accounting_evidence':pin(a.accounting_evidence),
        'raw_sacct_reference':evidence['raw_sacct_reference'],'actual_parent':parent,'allocated_core_seconds':seconds,
        'allocated_core_hours':seconds/3600,'steps_not_double_counted':[r for r in rows if r.get('JobIDRaw','').startswith(jid+'.')],
        'elapsed_zero_is_integer_floor_not_true_zero':True,'costs_include_failures_and_startup':True,
        'monetary_compute_charge_claimed':False,'profile_or_payload_status':receipt['status'],
        'successful_profile_and_parent_complete':receipt['status']=='ACTUAL_CSV_ZIP_PROFILE_COMPLETE_NOT_IDENTITY_AUTHORITY'
          and parent['State']=='COMPLETED' and parent['ExitCode']=='0:0','identity_or_release_accepted':False}
    need(not a.output.exists(),'NEW_COST_CLOSURE_ONLY');write_new(a.output,result)
    print(json.dumps({'cost_closure':pin(a.output),'allocated_core_seconds':seconds,'endpoint':ENDPOINT}))
if __name__=='__main__':main()
