"""Close existing recovery evidence; metadata only, no submission or queue mutation."""
import hashlib,json,os,socket,sqlite3,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p),'bytes':Path(p).stat().st_size}
def write(p,x):
 t=p.with_name(p.name+'.pending');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(t,p)
def main():
 assert socket.gethostname().split('.')[0]=='compute-0-20' and os.getuid()==1278
 out=R/'reports/recovery_ready_v11_20261011';out.mkdir(exist_ok=False)
 pub=read(R/'reports/observation_latest.json');age=time.time()-pub['time'];assert 0<=age<=180
 original=R/'submission/submitted_jobs.json';jobs=read(original)
 ids=[str(x['job_id']) for x in jobs['main']+jobs['cleanup']]
 states={j:pub['registered_job_states'][j] for j in ids}
 assert len(ids)==78 and all(s in {'COMPLETED','FAILED'} for s in states.values())
 assert (R/'STOP_NEW_MOLECULES.json').exists()
 plan=R/'reports/terminal_reconciliation_plan_v2_job_4514064/plan.json'
 apply=R/'reports/terminal_reconciliation_apply_v2_20261011/report.json'
 export=R/'reports/terminal_export_repair_v1_job_4514068/report.json'
 assert read(plan)['status']=='REVIEWABLE_PLAN_NO_QUEUE_WRITE' and not read(plan)['conflicts']
 assert read(apply)['status']=='METADATA_ONLY_RECONCILIATION_COMPLETE'
 assert read(export)['status']=='EXACT_TWO_ROOT_EXPORT_REPAIR_COMPLETE'
 db=sqlite3.connect('file:'+str(R/'queue/pending.sqlite')+'?mode=ro',uri=True,timeout=10)
 db.row_factory=sqlite3.Row;db.execute('BEGIN')
 counts=[dict(x) for x in db.execute('SELECT state,count(*) molecules,sum(record_count) records FROM molecules GROUP BY state')]
 unexported=db.execute("SELECT count(*) FROM molecules WHERE state='COMPLETE' AND export_json IS NULL").fetchone()[0]
 db.rollback();db.close()
 expected={'COMPLETE':(61967,612960),'PENDING':(1158484,10618748),'RETRY_PENDING':(15,146)}
 assert {x['state']:(x['molecules'],x['records']) for x in counts}==expected and unexported==0
 snap=read(R/'reports/formal_hour7_queue_snapshot_v1.json')
 assert snap['population_closed'] and snap['task_denominators_closed']
 assert sum(x['molecules'] for x in counts)==1220466 and sum(x['records'] for x in counts)==11231854
 materialized=read(R/'reports/formal_materialized_permanent_bytes_v1.json')
 assert not materialized['missing']
 for x in materialized['refs']:assert Path(x['path']).stat().st_size==x['bytes']
 credit=materialized['permanent_bytes'];assert credit==sum(x['bytes'] for x in materialized['refs'])
 g3=read(R/'gates/g3_current_scope_closed_v12.json');free=pub['quota_parsed']['remaining_bytes']
 remaining_peak=g3['writeback_peak_bytes']-credit;head=free-remaining_peak
 assert head>=g3['required_headroom_bytes'] and free>=g3['runtime_stop_remaining_bytes']
 contract=R/'configs/production_contract_v4.json';con=read(contract)
 prepared=R/'submission/recovery_attempt_v11/prepared_plan_v11.json';prepared_data=read(prepared)
 assert prepared_data['production_contract']['sha256']==sha(contract)
 pressure=R/'gates/metadata_queue_fixture/queue_fix_v11_20261011_run1/report.json'
 bridge=R/'reports/wp5_queue_runtime_science_bridge_v1.json'
 assert read(pressure)['status']=='METADATA_ONLY_STRESS_PASS'
 report={'schema':'WP5_TERMINAL_QUEUE_RECONCILIATION_CLOSED_V1','status':'PASS_QUEUE_RECONCILIATION','created_epoch':time.time(),
  'source':ref(__file__),'plan':ref(plan),'applied':ref(apply),'terminal_export_repair':ref(export),
  'original_submission':ref(original),'original_job_states':states,'observation_epoch':pub['time'],'publisher_age_seconds':age,
  'queue_states':counts,'unexported_COMPLETE_molecules':unexported,'formal_records':11231854,'formal_molecules':1220466,
  'remaining_molecules':1158499,'remaining_records':10618894,'task_denominators_snapshot':ref(R/'reports/formal_hour7_queue_snapshot_v1.json'),
  'full_SCI_validation_already_performed_by_4514064':True,'pure_export_already_performed_by_4514068':True,
  'scientific_recomputation_started':False,'queue_mutated':False,'ordinary_outputs_policy_unchanged':True,
  'metadata_pressure':ref(pressure),'scientific_unchanged_bridge':ref(bridge),'production_contract':ref(contract),
  'current_storage':{'source_G3':ref(R/'gates/g3_current_scope_closed_v12.json'),'materialized_permanent_refs':ref(R/'reports/formal_materialized_permanent_bytes_v1.json'),
   'frozen_total_writeback_peak_bytes':g3['writeback_peak_bytes'],'already_materialized_permanent_bytes':credit,
   'remaining_writeback_peak_bytes':remaining_peak,'quota_remaining_bytes':free,'peak_headroom_bytes':head,'required_peak_headroom_bytes':200000000000,
   'future_float32_reserve_bytes':400000000000,'method':'Total frozen output peak less unique permanent outputs already charged to current quota; no repeated charge for existing files.'},
  'guide_step3_5_user_instruction_pending':True,'STOP_retained':True,'formal_submission_started':False,'final200_still_required':True}
 report_path=out/'report.json';write(report_path,report)
 old=read(R/'gates/g0_ready_for_formal.json');g0=dict(old)
 g0.update(schema='WP5_G0_RECOVERY_READY_V11',created_at_epoch=time.time(),production_contract={'path':str(contract),'sha256':sha(contract)},
  prepared_plan={'path':str(prepared),'sha256':sha(prepared)},submission_authority_pending=True,queue_reconciliation_report=ref(report_path),
  current_quota_validation=report['current_storage'],scientific_protocol_and_parser_unchanged_since_original_gates=True,
  scientific_evidence_transfer=ref(bridge),stop_retained_pending_user_recovery_instruction=True)
 g0['gates']=dict(old['gates']);g4=R/'gates/g4_frozen_manifest_v5.json'
 assert read(g4)['status']=='PASS';g0['gates']['G4']={'status':'PASS',**ref(g4)}
 replacements={old['production_contract']['path']:contract,old['prepared_plan']['path']:prepared,
  old['gates']['G4']['path']:g4,
  str(R/'configs/current_code_chain_user_override_v4.json'):R/'configs/current_code_chain_user_override_v5.json',
  str(R/'reproduction_package/supplement_job_4513971/manifest.json'):Path(con['reproduction_package']['path'])}
 paths=[]
 for x in old['bindings']:paths.append(replacements.get(x['path'],Path(x['path'])))
 paths.extend([report_path,bridge,pressure,plan,apply,export,R/'reports/formal_materialized_permanent_bytes_v1.json'])
 g0['bindings']=[{'path':str(p),'sha256':sha(p)} for p in dict.fromkeys(paths)]
 for x in g0['gates'].values():assert sha(x['path'])==x['sha256']
 write(R/'gates/g0_ready_for_recovery_v11.json',g0)
 print(json.dumps({'status':report['status'],'remaining_molecules':1158499,'remaining_records':10618894,'permanent_bytes':credit,
  'quota_remaining_bytes':free,'remaining_peak_bytes':remaining_peak,'peak_headroom_bytes':head,'g0_status':g0['status'],'submission_authority_pending':True}))
if __name__=='__main__':main()