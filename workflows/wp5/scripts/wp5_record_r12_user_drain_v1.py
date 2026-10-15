"""Root records actual new user approval and invokes the existing no-new-claims flag."""
import hashlib,json,os,socket,time,uuid
from pathlib import Path
B=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def save_new(p,j):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(j,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    contract=ref(B/'configs/production_contract_v5.json');plan=ref(B/'submission/recovery_attempt_v12/prepared_plan_v12.json')
    assert contract['sha256']=='a04ee67742ce6ebce095063cd9e69eab311c766b9c76a4cf4c92b66b77c33851'
    assert plan['sha256']=='a35419a90a24503310f56f416bba63c240537400e406f7fd60d5291b8210d990'
    decision=B/'submission/recovery_attempt_v12/user_approved_drain_and_one_phase_v1.json'
    approval={'schema':'WP5_R12_DRAIN_AND_ONE_PHASE_USER_DECISION_V1','status':'USER_APPROVED','recorded_epoch':time.time(),
       'source':'Actual user reply to request_user_input_async','question_item_id':'["request_user_input_async","call_e92f4936799142f49105fe45329daf89",0]',
       'user_answer':'允许正常退出并一次性续算（建议）','server':'zixiao@202.38.247.57:22','project':str(B.parent.parent),
       'production_contract':contract,'prepared_plan':plan,'reviewable_plan':ref(B/'reports/next_formal_72plus6_reviewable_plan_v2.md'),
       'normal_drain_authorized':True,'scancel_authorized':False,'authorized_main_jobs':72,'authorized_cleanup_jobs':6,
       'single_phase':True,'future_additional_phases_authorized':False,'scientific_configuration_changed':False,'final200_required':True,
       'required_before_formal':['all229_old_jobs_terminal','full_SCI_reconciliation_verified','pure_export_closed','production_bootstrap_verified','G0_closed']}
    if decision.exists():
        old=json.loads(decision.read_text());assert old['question_item_id']==approval['question_item_id'] and old['prepared_plan']==plan and old['production_contract']==contract
    else:save_new(decision,approval)
    stop=B/'STOP_NEW_MOLECULES.json';body={'time':time.time(),'reason':'USER_APPROVED_R12_SOFTWARE_RECOVERY_NORMAL_DRAIN',
        'job_id':None,'details':{'user_decision':ref(decision),'normal_exit_only':True,'keep_current_whole_molecule':True,'new_phase_not_yet_submitted':True}}
    if stop.exists():
        body=json.loads(stop.read_text());status='EXISTING_STOP_PRESERVED'
    else:
        temp=stop.with_name(stop.name+'.'+uuid.uuid4().hex+'.pending');save_new(temp,body)
        try:os.link(temp,stop);status='USER_APPROVED_STOP_NEW_CLAIMS_WRITTEN'
        finally:temp.unlink(missing_ok=True)
    report={'status':status,'time':time.time(),'decision':ref(decision),'stop':ref(stop),'stop_body':body,'no_job_signals_sent':True,'queue_opened':False,'QM_started':False}
    out=B/'reports/r12_user_normal_drain_actual_v1.json'
    if not out.exists():save_new(out,report)
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
