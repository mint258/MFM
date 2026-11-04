"""Append actual closed prior224 IDs without repeating the physical QA."""
import fcntl,hashlib,json,os,pathlib,subprocess,time
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
CONTROL=ROOT/'control/n1_prior224_current_actual_20261105_v1'
OUTPUT=ROOT/'artifacts/conformers/n1_current_canonical_physical_qa_v1/prior224_current_v1'
REGISTRY=ROOT/'control/n1_current_canonical_registry_v1/current.json'
JID='4525895'

def load(path):return json.loads(pathlib.Path(path).read_bytes())
def ref(path):
 path=pathlib.Path(path);raw=path.read_bytes()
 return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def save(path,value):
 raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
 if path.exists():assert path.read_bytes()==raw
 else:
  with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 return ref(path)
def replace(path,value):
 temp=path.with_name('.'+path.name+'.prior224.pending');save(temp,value);os.replace(temp,path)

def main():
 argv=['sacct','-j',JID,'-X','--parsable2','--format=JobIDRaw,State,ExitCode,ElapsedRaw,User,UID,AllocCPUS,NodeList']
 result=subprocess.run(argv,capture_output=True,text=True,check=True,timeout=30)
 rows=[r.split('|') for r in result.stdout.splitlines() if r.strip()];assert len(rows)==2
 parent=dict(zip(rows[0],rows[1]))
 assert all(parent[k]==v for k,v in dict(JobIDRaw=JID,State='COMPLETED',ExitCode='0:0',User='zixiao',UID='1278',AllocCPUS='16',NodeList='compute-0-18').items()),parent
 receipt=load(OUTPUT/'receipt.json');scope=receipt['identity_scope']
 assert receipt['schema']=='N1_PRIOR_MAIN224_CURRENT_PHYSICAL_QA_RECEIPT_V1' and receipt['job_id']==JID
 assert receipt['uid']==1278 and receipt['status']=='PHYSICAL_ID_SIDECAR_PENDING_ROOT_D6_INTEGRATION'
 assert all(receipt[k]==224 for k in ('registered_source_states','source_packets_closed','real_second_source_packets','independent_QA_passed','accepted_extra_count'))
 assert receipt['new_UFF_calls']==receipt['new_QM_calls']==0 and receipt['source_was_Alpha_import5249'] is False
 assert receipt['original_Main_generation_parent_ids']==['4521418','4521476','4521479','4521481']
 assert receipt['historical_noncanonical_coverage']=='UNKNOWN'
 for key in ('accepted_extra_index','extra_geometry_table','Pprime_two_conformer_order_sidecar'):
  assert pathlib.Path(receipt[key]['path']).stat().st_size==receipt[key]['bytes']
 account_path=CONTROL/('actual_'+JID+'_accounting.json')
 if account_path.exists():assert load(account_path)['parent']==parent
 else:
  raw=CONTROL/('actual_'+JID+'.sacct.psv')
  with raw.open('x') as f:f.write(result.stdout)
  save(account_path,dict(schema='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1',status='ACTUAL_PARENT_ACCOUNTING_CLOSED',
   endpoint='202.38.247.57:22',uid=1278,query_returncode=0,query_argv=argv,raw_sacct_reference=ref(raw),
   observed_unix_seconds=time.time(),parent=parent))
 account_ref=ref(account_path);receipt_ref=ref(OUTPUT/'receipt.json')
 member=dict(actual_parent_job_id=JID,actual_parent_accounting_reference=account_ref,publisher_receipt_reference=receipt_ref,
  accepted_extra_index_reference=receipt['accepted_extra_index'],registered_identity_table_reference=receipt['extra_geometry_table'],
  accepted_extra_count=224,Pprime_two_conformer_order_reference=receipt['Pprime_two_conformer_order_sidecar'])
 with (REGISTRY.parent/'current.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);registry=load(REGISTRY)
  assert registry['identity_scope']==scope and any(m['actual_parent_job_id']=='4525894' and m['accepted_extra_count']==4400 for m in registry['members'])
  old=[m for m in registry['members'] if m['actual_parent_job_id']==JID]
  if old:assert old==[member]
  else:
   history=REGISTRY.parent/'snapshots';previous=history/(registry['registry_snapshot_id']+'.json')
   if previous.exists():assert previous.read_bytes()==REGISTRY.read_bytes()
   else:
    with previous.open('xb') as f:f.write(REGISTRY.read_bytes())
   registry.update(previous_registry_snapshot_reference=ref(previous),members=registry['members']+[member],
    registry_snapshot_id='v1-final-candidate-N1-4624-4525895-20261105')
   registry['current_registered_extra_count']=sum(m['accepted_extra_count'] for m in registry['members'])
   assert registry['current_registered_extra_count']==4624
   save(history/(registry['registry_snapshot_id']+'.json'),registry);replace(REGISTRY,registry)
  accepted=dict(schema='N1_CURRENT_CANONICAL_PRIOR224_PHYSICAL_ACCEPTANCE_V1',status='CURRENT_RELEASE_REGISTERED_PHYSICAL_COMPONENT',
   identity_scope=scope,actual_parent_job_id=JID,actual_parent_accounting_reference=account_ref,
   publisher_receipt_reference=receipt_ref,accepted_extra_count=224,total_current_registered_extra_count=4624,
   current_registry_reference=ref(REGISTRY),registry_snapshot_id=registry['registry_snapshot_id'],
   registered_scope='Alpha original4407 plus four prior Main origins224; not all Common N1',
   original_Alpha_failed_or_no_second_states_preserved=7,existing4400_repeated_QA=False,
   historical_noncanonical_coverage='UNKNOWN',all_global_registered_extra_identity_tables_included=False,
   original_source_history_and_IDs_preserved=True,ordinary_N_and_D5_unchanged=True,new_QM_calls=0,new_UFF_calls=0,
   final_Common_D6_training_release=False,**{k:receipt[k] for k in ('accepted_extra_index','extra_geometry_table','Pprime_two_conformer_order_sidecar','all224_states_reference')})
 accepted_ref=save(CONTROL/'accepted_current_release_4525895.json',accepted)
 with (ROOT/'control/current_work_state.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);path=ROOT/'control/current_work_state.json';state=load(path)
  state['N1_prior224_current_release_actual_20261105']=dict(accepted,acceptance_reference=accepted_ref);replace(path,state)
 with (ROOT/'control/root_current_all_future_ledger_v1.lock').open('rb') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);path=ROOT/'control/root_current_all_future_ledger_v1.json';ledger=load(path)
  entry=ledger['entries']['n1_prior224_current_physical_qa_20261105_v1'];assert entry['job_id']==JID
  entry.update(status='ACTUAL_C0_PRIOR224_REGISTERED_PHYSICAL_COMPONENT',future_reserved_bytes=0,
   actual_parent_accounting_reference=account_ref,acceptance_reference=accepted_ref,actual_used_bytes_not_refunded=True)
  total=sum(e['future_reserved_bytes'] for e in ledger['entries'].values())
  ledger.update(known_future_reserved_bytes=total,total_future_reserved_bytes=total,entries_observed_unix_seconds=time.time());replace(path,ledger)
 print('PRIOR224_REGISTERED_TOTAL_CURRENT4624_OLD4400_RETAINED_NEW_QM_UFF0')
if __name__=='__main__':main()