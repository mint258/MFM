"""Explicit Root-only old metadata stop/observation;never signal science jobs."""
import argparse,fcntl,os,pathlib,signal,stat,time
from . import contract as C,edge as E
from workflows.data_v1_final.execution.sprime_wave2_controller_v3 import controller as V,capacity_gate as CG
from workflows.data_v1_final.execution.sprime_resource_epoch_v1 import controller as OLD
def same_process(expected,actual):
    return all(actual[k]==expected[k] for k in ('pid','uid','start_ticks','boot_id','argv','cgroup'))
def no_live_old(expected):
    path=pathlib.Path('/proc',str(expected['pid']))
    if not path.exists():return True
    actual=V.process_identity(expected['pid']);return not same_process(expected,actual)
def old_identity(reference):
    expected=E.meta(reference);C.need(expected['uid']==1278 and expected['argv'][0:4]==[C.Q.PY,'-B','-m','workflows.data_v1_final.execution.sprime_resource_epoch_v1.controller']
        and expected['actual_primary']==str(OLD.E.HERE/'controller.py') and expected['node']=='sonmi'
        and expected['endpoint']=='202.38.247.57:22','ONLY_EXACT_OLD_MAIN_METADATA_CONTROLLER_NOT_SCIENCE_OR_OTHER_SOURCE')
    return expected
def locks():
    # Caller enters outer first. This order cannot race an in-flight old
    # metadata helper:its inherited outer fd stays locked until it exits.
    return CG.serialization_lock(C.Q.ROOT/'control'/CG.LOCK_NAME)
def main():
    C.Q.on_login();p=argparse.ArgumentParser(description=__doc__)
    for k in ('review','output'):p.add_argument('--'+k,type=pathlib.Path,required=True)
    p.add_argument('--root-stop-exact-old-metadata',action='store_true');a=p.parse_args();rr=C.ref(a.review);r=E.meta(rr)
    C.root(r,'ROOT_SPRIME_OLD_METADATA_CUTOVER_DECISION_V1','APPROVED_EXACT_METADATA_ONLY_CUTOVER')
    expected=old_identity(r['old_controller_reference']);C.need(r['old_latest_state_reference']==C.ref(r['old_latest_state_reference']['path'])
        and r['science_or_other_process_signals_authorized'] is False and r['old_history_mutation_authorized'] is False,'ACTUAL_LAST_STATE_NO_SCIENCE_SIGNALS')
    out=a.output;C.need(C.META in out.parents and not out.exists(),'FRESH_CUTOVER_EVIDENCE_ROOT');out.mkdir(parents=True)
    try:
        manager=locks();fd=manager.__enter__()
    except BlockingIOError:
        C.Q.write_new(out/'receipt.json',{'status':'WAIT_OLD_TRANSITION_LOCK_BUSY','transition_intents_created':0,'signals_sent':0});return 0
    sent=0
    try:
        if not no_live_old(expected):
            actual=V.process_identity(expected['pid']);C.need(same_process(expected,actual),'EXACT_UID_PID_START_BOOT_ARGV_CGROUP_BEFORE_METADATA_SIGNAL')
            if not a.root_stop_exact_old_metadata:
                C.Q.write_new(out/'receipt.json',{'status':'WAIT_OLD_METADATA_STILL_LIVE','old_controller_reference':r['old_controller_reference'],'signals_sent':0});return 0
            C.need(r['allow_single_SIGTERM_exact_old_metadata'] is True,'EXPLICIT_ROOT_METADATA_SIGNAL_ONLY_DECISION')
            children=pathlib.Path('/proc',str(expected['pid']),'task',str(expected['pid']),'children').read_text().split()
            C.need(not children,'OLD_METADATA_CHILD_STILL_LIVE_WAIT_NO_SIGNAL_OR_REISSUE')
            C.Q.write_new(out/'exact_metadata_signal_intent.json',{'review_reference':rr,'actual_old_process':actual,'signal':'SIGTERM','production_jobs_signalled':0})
            # Exactly one authorized metadata PID;no process group,scancel,
            # descendant signal,science signal or retry escalation is used.
            C.need(same_process(expected,V.process_identity(expected['pid'])),'OLD_PID_IDENTITY_CHANGED_BEFORE_SIGNAL')
            os.kill(expected['pid'],signal.SIGTERM);sent=1
            until=time.monotonic()+15
            while not no_live_old(expected) and time.monotonic()<until:time.sleep(.2)
        C.need(no_live_old(expected),'OLD_METADATA_NOT_STOPPED_HOLD_NO_ESCALATION')
        lockpath=V.BASE/'wave2_single_instance.lock';lockfd=os.open(lockpath,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            info=os.fstat(lockfd);C.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278 and info.st_nlink==1,'ORIGINAL_OWN_CONTROLLER_LOCK')
            fcntl.flock(lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            state=E.meta(r['old_latest_state_reference']);C.need(state['launch_identity_reference']==r['old_controller_reference'],'OLD_LATEST_STATE_ACTUAL_CONTROLLER_IDENTITY')
            rows=[]
            for bid,stages in state['stages'].items():
                C.need(bid in OLD.E.G.BATCHES,'ONLY_ORIGINAL179_BATCHES')
                for stage,row in stages.items():
                    if row.get('actual_registered_references'):rows.append({'batch_id':bid,'stage':stage,'job_id':row['job_id'],'registration':row['actual_registered_references']})
            C.Q.write_new(out/'receipt.json',{'schema':'ACTUAL_MAIN_SPRIME_MULTINODE_CUTOVER_V1','status':'OLD_METADATA_STOPPED_LOCKS_OBSERVED_ADOPTION_PENDING_ROOT',
                'old_controller_reference':r['old_controller_reference'],'old_latest_state_reference':r['old_latest_state_reference'],'root_cutover_review_reference':rr,
                'observed_old_registrations':rows,'outer_serialization_lock_observed':str(C.Q.ROOT/'control'/CG.LOCK_NAME),'original_controller_lock_observed':str(lockpath),
                'old_same_process_absent':True,'exact_old_metadata_SIGTERM_sent':sent,'production_jobs_signalled':0,'old_files_or_registrations_mutated':False,
                'all_current_paths_still_require_Root_adoption_reconciliation':True,'new_controller_or_science_launched':False})
        finally:os.close(lockfd)
    finally:manager.__exit__(None,None,None)
    return 0
if __name__=='__main__':raise SystemExit(main())
