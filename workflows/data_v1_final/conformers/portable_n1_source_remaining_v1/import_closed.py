"""Main allocated CPU: preserve foreign ownership/once and all N1 F64 results."""
import argparse,csv,importlib,io,json,pathlib
from . import contract as C,runtime as R,io as I


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=pathlib.Path);p.add_argument('--startup-proof',required=True,type=pathlib.Path);a=p.parse_args()
    plan,proof=R.admit(a.plan,a.startup_proof,'import');C.need(plan['endpoint']['id']=='main','ACTUAL_MAIN_CPU_IMPORT')
    def target(ref):
        r=plan['locator_map'].get(ref['path'],ref);C.need(r['bytes']==ref['bytes'] and r['sha256']==ref['sha256'],'EXACT_FOREIGN_COPY_BYTES');return r
    out=C.literal(plan['output_directory']);C.need(not out.exists(),'NEW_IMPORT_OUTPUT');out.mkdir(parents=True);budget=R.Budget(plan,proof,out);budget.check()
    manifest=C.load(plan['assignment_manifest_reference']);by={}
    for shard in manifest['shards']:
        for member in C.load(shard['members_reference'],C.ADMIN):
            C.need(member['task_key']not in by,'UNIQUE_GLOBAL_FINITE_ASSIGNMENT');by[member['task_key']]=member
    # Main common.geometry_sha is the original callable; no graph/UFF/QM init.
    geometry=importlib.import_module('workflows.data_v1_final.conformers.common').geometry_sha
    rows=[];parents=[];seen=set();parent_seen=set()
    for entry in plan['closed_native_parents']:
        budget.check();receipt=C.load(target(entry['receipt_reference']),C.ADMIN);jid=str(receipt['actual_parent_job_id'])
        C.need(jid not in parent_seen,'PARENT_ACCOUNTED_ONCE');parent_seen.add(jid)
        account=C.load(target(entry['actual_accounting_reference']));raw=C.verify(target(account['raw_sacct_reference']),2<<20).read_text()
        C.need(account['endpoint']=='218.192.171.238:22' and account['uid']==1264 and account['query_returncode']==0,'REAL_FOREIGN_ACCOUNTING_ENDPOINT_UID')
        found=[r for r in csv.DictReader(io.StringIO(raw),delimiter='|') if r['JobIDRaw']==jid]
        C.need(len(found)==1 and found[0]['UID']=='1264' and found[0]['State'].split()[0]in C.TERMINAL
            and int(found[0]['AllocCPUS'])==receipt['cpus'] and found[0]['NodeList']==receipt['node'],'ACTUAL_FOREIGN_TERMINAL_PARENT_NOT_FAKE_MAIN_JOB')
        actual=found[0];parents.append({'job_id':jid,'endpoint':'218.192.171.238:22','actual':actual,
            'allocated_core_seconds':int(actual['AllocCPUS'])*int(actual['ElapsedRaw']),'actual_accounting_reference':entry['actual_accounting_reference']})
        C.need(receipt['schema']=='N1_FOREIGN_FINITE_SHARD_RECEIPT_V1' and receipt['all_started_native_tasks_drained']is True
            and receipt['assignment_manifest_reference']==plan['assignment_manifest_reference'] and receipt['signals_sent']is False
            and receipt['automatic_retry']is False,'TRUE_DRAINED_FINITE_N1_RECEIPT')
        for index in receipt['result_index_references']:
            path=C.verify(target(index),check=budget.check)
            with path.open() as stream:
                for line in stream:
                    result=json.loads(line);key=result['task_key'];C.need(key in by and key not in seen,'NO_RECOUNT_OR_OUTSIDE_NATIVE_RESULT');seen.add(key)
                    member=by[key];reserved=member['original_Main_assignment_claim_reference']
                    C.need(C.ref(C.MAIN_LEDGER/(key+'.json'))==reserved,'ORIGINAL_MAIN_ASSIGNMENT_RESERVATION_UNCHANGED')
                    owner=C.load(reserved);C.need(owner['schema']=='N1_FOREIGN_ASSIGNMENT_RESERVED_V1' and owner['scientific_attempt_started']is False
                        and owner['task_key']==key and owner['seed']==C.proposed_seed(member['molecule_id']),'EXPLICIT_ASSIGNMENT_NOT_FAKE_NATIVE_START')
                    task=C.load(owner['original_task_reference'],8<<20);C.need(C.value_sha(task)==member['task_sha256'],'ORIGINAL_EXACT_TASK_SHA')
                    packet=I.packet(target(result['packet_reference']),task,receipt['endpoint'],jid,geometry)
                    start=C.load(target(result['worker_start_reference']));native=C.load(target(result['native_claim_reference']))
                    C.need(start['runtime']==result['runtime']==packet['runtime'] and start['task_key']==native['task_key']==key
                        and native['actual_parent_job_id']==jid and native['uid']==1264
                        and native['original_Main_assignment_claim_reference']==reserved
                        and native['assignment_manifest_reference']==plan['assignment_manifest_reference'],'ACTUAL_FOREIGN_START_CLAIM_PACKET_OWNER_AND_SOURCE')
                    rows.append({'task_key':key,'molecule_id':member['molecule_id'],'seed':member['seed'],
                        'original_task_reference':owner['original_task_reference'],'original_Main_assignment_claim_reference':reserved,
                        'native_claim_origin_reference':result['native_claim_reference'],'native_start_origin_reference':result['worker_start_reference'],
                        'native_packet_origin_reference':result['packet_reference'],'actual_Main_packet_copy_reference':target(result['packet_reference']),
                        'native_endpoint':receipt['endpoint'],'native_parent_job_id':jid,'summary':packet['summary'],
                        'all_F64_event_and_real_second_SHA_readback':True,'new_SCI_calls':0})
    index=budget.write(out/'foreign_N1_closed_result_index.jsonl',b''.join(C.canonical(r)+b'\n' for r in rows))
    budget.write(out/'import.json',C.canonical({'schema':'N1_FINITE_FOREIGN_IMPORT_V1','status':'CLOSED_SOURCE_RESULTS_IMPORTED_NO_COMMON_RELEASE',
        'assignment_manifest_reference':plan['assignment_manifest_reference'],'result_index_reference':index,'results':len(rows),
        'actual_native_parents':parents,'new_SCI_calls':0,'canonical_Main_assignment_claims_rewritten':False,
        'UNKNOWN_and_unstarted_not_retried':True,'common_or_extra_physical_id_release':False})+b'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
