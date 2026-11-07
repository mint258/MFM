"""Both actual Alpha parents plus actual Main export; stop-new only at2x cost."""
import csv,io,time
from . import contract as C,runtime as R


def group(proof,plan):
    reference=proof['request']['aggregate_cost_group_reference'];value=C.load(reference)
    C.need(reference['path']==plan['aggregate_cost_group_path'] and value['reviewer']=='root' and value['status']=='APPROVED'
        and value['schema']=='ROOT_ACTUAL_N1_ALPHA_FINITE_COST_GROUP_V1'
        and value['assignment_manifest_reference']==plan['assignment_manifest_reference']
        and value['molecules']==plan['whole_remaining_count'] and value['comparable_core_seconds_per_molecule']==45
        and str(value['actual_export_job_id'])==str(plan['actual_export_job_id'])
        and value['pair_registered_before_any_startup_proof']is True and value['no_science_or_C0_claimed_by_pair_registration']is True
        and value['stop_new_multiplier']==2 and value['no_signal_to_science']is True,'EXACT_ROOT_ACTUAL_NATIVE_COST_GROUP')
    parents=value['native_parents'];C.need(len(parents)==2 and {r['cpus'] for r in parents}=={16,64}
        and all(str(r['job_id']).isdecimal() and r['uid']==1264 for r in parents)
        and any(str(r['job_id'])==str(proof['job_id']) and r['cpus']==plan['cpus'] for r in parents),'REAL_TWO_NATIVE_PARENTS_NOT_REQUESTED_CORE_FORECAST')
    for parent in parents:
        peer=C.load(parent['run_plan_reference']);C.review(peer)
        C.need(peer['role']=='run' and peer['endpoint']['id']=='alpha' and peer['cpus']==parent['cpus']
            and peer['shard_id']==parent['shard_id'] and peer['assignment_manifest_reference']==plan['assignment_manifest_reference'],
            'BOTH_ACTUAL_PARENT_PLANS_BELONG_TO_THIS_FINITE_ASSIGNMENT_NOT_PUBCHEM')
        parent['expected_job_name']=peer['job_name'];parent['expected_script_path']=peer['script_path']
    def target(ref):
        result=plan['locator_map'].get(ref['path'],ref);C.need(result['bytes']==ref['bytes'] and result['sha256']==ref['sha256'],'COST_EVIDENCE_COPY_SAME_BYTES');return result
    account=C.load(target(value['actual_export_accounting_reference']));raw=C.verify(target(account['raw_sacct_reference']),2<<20).read_text()
    jid=str(value['actual_export_job_id']);rows=[r for r in csv.DictReader(io.StringIO(raw),delimiter='|') if r.get('JobIDRaw',r.get('JobID'))==jid]
    if account['schema']=='ROOT_ACTUAL_SLURM_PARENT_ACCOUNTING_V1':
        names=('JobIDRaw','JobName','State','ExitCode','NodeList','AllocCPUS','ElapsedRaw','Start','End','User')
        cells=list(csv.reader(io.StringIO(raw),delimiter='|'));C.need(len(cells)==1 and len(cells[0])==10,'REAL_TEN_COLUMN_EXPORT_COST')
        row=dict(zip(names,cells[0]));C.need(all(str(account[k])==row[k] for k in names),'EXPORT_RAW_FIELDS_MATCH');rows=[row]
    else:
        C.need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
            and account['query_returncode']==0 and len(rows)==1 and rows[0]['UID']=='1278','ACTUAL_CANONICAL_MAIN_EXPORT_QUERY_AND_RAW_UID')
    C.need(account['endpoint']=='202.38.247.57:22' and account['uid']==1278 and len(rows)==1
        and rows[0]['JobIDRaw']==jid and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0'
        and int(rows[0]['AllocCPUS'])==16,'ACTUAL_MAIN_EXPORT_COST_NOT_ESTIMATE')
    value['actual_export_core_seconds']=int(rows[0]['AllocCPUS'])*int(rows[0]['ElapsedRaw'])
    return value


def observe(value):
    from secondary_cpu_queue_v1 import common as Q
    total=value['actual_export_core_seconds'];evidence=[]
    for parent in value['native_parents']:
        observed=Q.query(['scontrol','show','job','-o',str(parent['job_id'])],allow_failure=True)
        if observed['returncode']!=0:
            closed=Q.query(['sacct','-j',str(parent['job_id']),'--parsable2','--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS,UID'])
            rows=[r for r in csv.DictReader(io.StringIO(closed['stdout']),delimiter='|') if r['JobIDRaw']==str(parent['job_id'])]
            C.need(len(rows)==1 and rows[0]['UID']=='1264' and int(rows[0]['AllocCPUS'])==parent['cpus']
                and rows[0]['State'].split()[0]in C.TERMINAL,'ACTUAL_TERMINAL_COST_AFTER_SCONTROL_PURGE')
            seconds=int(rows[0]['ElapsedRaw']);C.need(seconds>=0,'NONNEGATIVE_TERMINAL_COST');total+=seconds*parent['cpus']
            evidence.append({'job_id':str(parent['job_id']),'actual_scontrol_failure':observed,'actual_terminal_sacct':closed,'actual_core_seconds':seconds*parent['cpus']});continue
        j=R.fields(observed['stdout'])
        C.need(j['JobId']==str(parent['job_id']) and j['UserId']=='alpha(1264)' and int(j['NumCPUs'])==parent['cpus']
            and j['Partition']=='cpu' and j['JobName']==parent['expected_job_name'] and j['Command']==parent['expected_script_path']
            and j['JobState']in({'RUNNING','PENDING','COMPLETING'}|C.TERMINAL),'REAL_OWN_SCHEDULER_PARENT_COST')
        seconds=R.duration(j['RunTime']);C.need(seconds>=0,'NONNEGATIVE_ALLOCATED_RUNTIME')
        total+=seconds*parent['cpus'];evidence.append({'job_id':str(parent['job_id']),'actual_scontrol':observed,'actual_core_seconds':seconds*parent['cpus']})
    threshold=2*45*value['molecules']
    return {'unix':time.time(),'actual_aggregate_allocated_core_seconds':total,'two_times_comparable_core_seconds':threshold,
        'descriptive_comparable_is_not_tail_bound':True,'includes_Main_export_and_both_Alpha_parents':True,'parents':evidence,
        'stop_new':total>=threshold,'no_signals_or_retry':True}
