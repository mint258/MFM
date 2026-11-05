import json,pathlib,hashlib,subprocess,datetime,xml.etree.ElementTree as ET
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
out=N/'Native_B_closed028029_SDK_Root_closure_actual_v1.json';assert not out.exists()
def ref(p):
 p=pathlib.Path(p);assert p.suffix not in {'.wandb','.jsonl','.npz','.pt','.pth','.lmdb'}
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def read(r):
 assert ref(r['path'])==r
 return json.loads(pathlib.Path(r['path']).read_bytes())
def counts(p,n):
 suites=ET.parse(p).getroot().iter('testsuite')
 c={k:0 for k in ('tests','failures','errors','skipped')}
 for x in suites:
  for k in c:c[k]+=int(x.get(k,0))
 assert c==dict(tests=n,failures=0,errors=0,skipped=0),(p,c)
 return dict(XML=ref(p),counts=c)
GPU={'2wh2cs0m':('028','4525078'),'dp8xtsi9':('029','4525109')}
ids=[x[1] for x in GPU.values()]+['4525137','4525138']
a=subprocess.run(['sacct','-X','-n','-P','-j',','.join(ids),'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],capture_output=True,text=True,check=True)
rows={line.split('|')[0]:line.split('|') for line in a.stdout.splitlines() if line}
assert set(rows)==set(ids) and all(r[1:4]==['zixiao','COMPLETED','0:0'] and r[5]=='16' and int(r[4])>0 for r in rows.values())
batches=[];runs=[];supervisors=[]
for pair,av,aj,sj in [('028029','v1','4525137','4525138')]:
 au=N/('native_closed'+pair+'_SDK_audit_actual_'+av);sy=N/('native_closed'+pair+'_sync_actual_v1')
 ab=read(ref(au/'BATCH_RESULT.json'));sr=read(ref(sy/'RESULT.json'))
 assert ab['status']=='CLOSED_SEGMENT_LOGS_MATCHED_PENDING_CPU_OUTER_C0' and ab['returncode']==0 and ab['failure'] is None and ab['actual_job_id']==aj
 assert sr['status']=='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0' and sr['failure'] is None and sr['job_id']==sj
 assert sr['source_hashes_before']==sr['source_hashes_after'] and sr['original_SDKs_retained'] is True
 for root,job in [(au,aj),(sy,sj)]:
  r=ref(pathlib.Path(str(root)+'.supervisor.json'));su=read(r)
  assert su['status']=='COMPLETED' and su['job_id']==job and su['exit_code']==0 and su['first_failure'] is None and not su['remaining']
  supervisors.append(r)
 qa=[counts(au/'metadata.xml',28),counts(sy/'metadata4.xml',4)]
 batches.append(dict(audit=ref(au/'BATCH_RESULT.json'),sync=ref(sy/'RESULT.json'),metadata_QA=qa,fixture_accounting_selfchecks=ref(sy/'fixture_accounting_selfchecks.json')))
 assert len(ab['verifications'])==len(sr['records'])==2
 for vr,transport in zip(ab['verifications'],sr['records']):
  v=read(vr);key=v['run_id'];slot,gjob=GPU[key]
  assert transport['run_id']==key
  assert v['schema']=='native_S_long_segment_full_log_comparison_v1' and v['status']=='ALL_SAVED_SCIENTIFIC_LOG_FIELDS_MATCHED'
  assert v['full_config_summary_typed_exact'] and v['raw_before_after_binding_closed']
  hi=v['history'];assert hi['clean_eof'] and hi['native_closed'] and hi['decode_error'] is None and hi['sdk_exit_codes']==[0] and hi['sdk_run_ids']==[key]
  assert hi['history_rows']==v['last_global_cursor']-v['first_global_cursor']+1
  one=read(transport['result'])
  assert one['status']=='SOURCE_AND_REMOTE_METADATA_VERIFIED' and one['action']=='SYNCED_EXACT_COPY_AND_API_VERIFIED' and one['failure'] is None and one['native_exit_code']==0
  assert one['original_source']==v['sdk'] and one['source_hash_before_after_equal'] and one['original_sync_marker_unchanged'] and not one['original_SDK_repaired_or_deleted']
  assert one['staged_SDK']['sha256']==v['sdk']['sha256'] and one['staged_SDK']['bytes']==v['sdk']['bytes']
  expected=dict(entity='mint_leaf258',project='mfm_model_v3_development',run_id=key,state='finished',history_rows=hi['history_rows'],first_step=v['first_global_cursor'],last_step=v['last_global_cursor'])
  assert one['actual_remote_metadata']==one['expected_remote_metadata']==transport['actual_remote_metadata']==expected
  assert one['official_core_command']['returncode']==0 and one['official_core_command']['timeout'] is False
  assert pathlib.Path(v['sdk']['path']).stat().st_size==v['sdk']['bytes']
  runs.append(dict(slot=slot,run_id=key,GPU_job_id=gjob,history_rows=hi['history_rows'],first_step=v['first_global_cursor'],last_step=v['last_global_cursor'],verification=vr,sync_result=transport['result']))
record=dict(schema='model_v3_native_B_closed_segment_SDK_Root_closure_v1',status='TWO_CLOSED_SEGMENTS_NATIVE_LOG_MATCH_AND_OFFICIAL_SYNC_CLOUD_READBACK_CLOSED',
captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),actual_sacct=dict(argv=a.args,returncode=a.returncode,stdout=a.stdout,stderr=a.stderr),
CPU_supervisors=supervisors,batches=batches,runs=runs,Root_SDK_checkpoint_or_scientific_array_payload_read=False,global_online_registry_recounted=False,original_SDKs_retained=True,
active_or_later_slots_audited=False,whole_B_four_curves_acceptance=False,preserved_failed_grouped_audit_parent='4524980',
preserved_failed_grouped_first_pair_output=str(N/'native_closed024025_SDK_audit_actual_v1'))
assert len(runs)==2 and {r['run_id'] for r in runs}==set(GPU)
pub=N/'R1five_Native028029_methods_publication_20261029_v1/PUBLICATION.json'
p=read(ref(pub))
assert p['public_code_sha']=='fa7821c8caf5105ec7c5a295bf234cc57c586a06' and p['UTF8_raw_byte_readbacks']==53 and p['public_Git_API_tree_readback_verified'] is True
audit_source=N/'native_closed028029_sdk_audit_v1_source/source_pins.json'
sync_source=N/'native_closed028029_long_sync_v1_source/source_pins.json'
fixture_source=N/'native_closed028029_long_sync_fixture_v1_source/source_pins.json'
assert ref(audit_source)['sha256']=='cb01961b0b8289191f9430b27039dc4dfaf8ad9f3f51cb188d15e2f270fa5f61'
assert ref(sync_source)['sha256']=='ffd3a5b543c2a386a94591c8ba192037ea4c0810e81d82d0aae9094a24857317'
assert ref(fixture_source)['sha256']=='0ad06d435c57f0f11e92f3da214e539a73f60b76bbcc817fa2139aa0802520ae'
assert ab['source_pins']==ref(audit_source)
proof=read(ref(sy/'fixture_accounting_selfchecks.json'))
assert len(proof['checks'])==6
for rr in runs:
 vr=read(rr['verification']);cr=vr['closed_metadata_refs']['closure'];read(cr)
 assert cr['path']==str(N/('native_S_B20k_v3/slots/slot_'+rr['slot']+'/management/ROOT_LONG_SEGMENT_CLOSURE.json'))
 rr['original_segment_Root_closure']=cr
record.update(published_exact_method=ref(pub),audit_source_pins=ref(audit_source),sync_source_pins=ref(sync_source),fixture_source_pins=ref(fixture_source),source_handoff=ref(N/'native_closed028029_SDK_source_handoff_v1.json'),original_science_code='3d9b1cc0c580dacc9398a5570b0c2fff3e257618',only_new_actual_closed_difference_slots=[28,29],remote_metric_values_independently_recompared=False,all_previous_SDK_closures_retained=True)
out.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(dict(status=record['status'],runs=len(runs),receipt=ref(out))))

