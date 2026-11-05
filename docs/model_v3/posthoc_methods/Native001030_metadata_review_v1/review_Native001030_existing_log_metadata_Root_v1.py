"""Root metadata-only verification of existing Native001030 evidence; no SDK scan."""
import csv,datetime,hashlib,io,json,os,pathlib,stat
N=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026');P=N/'Native_B_slots001_030_log_coverage_20261029_v1'
assert os.getuid()==1278 and not os.environ.get('SLURM_JOB_ID')
def ref(p):
 p=pathlib.Path(p);a=p.lstat();assert p.suffix in ('.json','.py','.md','.csv') and stat.S_ISREG(a.st_mode) and a.st_uid==1278 and a.st_size<=2<<20
 raw=p.read_bytes();z=p.lstat();assert (a.st_ino,a.st_size,a.st_mtime_ns)==(z.st_ino,z.st_size,z.st_mtime_ns)
 return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(p):return json.loads(pathlib.Path(p).read_bytes())
def bound(r):assert ref(r['path'])==r;return read(r['path'])
assert ref(P/'COVERAGE.json')['sha256']=='2ca5f3c3dc09345f623c21714aa5f7911ad3b232b1ec398e107205ea563a3aa1'
assert ref(P/'COVERAGE.csv')['sha256']=='aa48a171dc51a2c9be028798f80a40dd55780012f612f07b01257f3985c36bc4'
j=read(P/'COVERAGE.json');assert j['row_count']==30 and j['full_typed_successful_segment_rows']==29 and j['legacy_failed_saved_stream_rows']==1 and j['B_four_member_acceptance'] is False
assert [x['slot'] for x in j['rows']]==['%03d'%i for i in range(1,31)]
assert len(j['metadata_refs'])==263 and len({r['path'] for r in j['metadata_refs']})==263
for r in j['metadata_refs']:assert pathlib.Path(r['path']).suffix in ('.json','.py') and ref(r['path'])==r
for r in j['rows'][1:]:
 assert all(r[k] is True for k in ('full_config_summary_typed_exact','raw_before_after_binding_closed','clean_eof','official_sync_and_remote_metadata_match','audit_C0','sync_C0','source_sdk_SHA_matches_sync','certificate_matches_actual_configuration_and_submission','CPU_parent_identity_matches_sup_refs','framing_CRC_evidence_closed'))
 assert r['native_exit_code']==0 and r['cloud_state']=='finished' and r['history_rows']==r['cloud_history_rows'] and r['first_step']==r['cloud_first_step'] and r['last_step']==r['cloud_last_step']
 refs=r['source_refs'];v=bound(refs['full_native_verification']);sync=bound(refs['sync_per_run_result']);h=v['history']
 assert v['run_id']==r['run_id'] and v['full_config_summary_typed_exact'] is v['raw_before_after_binding_closed'] is True
 assert h['status']=='VERIFIED_COMMITTED_HISTORY' and h['clean_eof'] is h['native_closed'] is True and h['decode_error'] is None and h['uncommitted_native_requests']==0 and h['sdk_exit_codes']==[0] and h['sdk_run_ids']==[r['run_id']]
 assert h['history_rows']==r['history_rows'] and h['first_explicit_step']==r['first_step'] and h['last_explicit_step']==r['last_step']
 assert v['closed_metadata_refs']['configuration']==refs['configuration'] and v['closed_metadata_refs']['submission']==refs['submission']
 remote=dict(entity=r['cloud_entity'],project=r['cloud_project'],run_id=r['run_id'],state='finished',history_rows=r['cloud_history_rows'],first_step=r['cloud_first_step'],last_step=r['cloud_last_step'])
 assert sync['status']=='SOURCE_AND_REMOTE_METADATA_VERIFIED' and sync['native_exit_code']==0 and sync['failure'] is None
 assert sync['actual_remote_metadata']==sync['expected_remote_metadata']==remote
 assert sync['original_source']==v['sdk'] and sync['source_hash_before_after_equal'] is sync['original_sync_marker_unchanged'] is True and sync['original_SDK_repaired_or_deleted'] is False
 for key,job in [('audit_supervisor',r['audit_job_id']),('sync_supervisor',r['sync_job_id'])]:
  s=bound(refs[key]);assert s['status']=='COMPLETED' and str(s['job_id'])==job and s['exit_code']==0 and s['first_failure'] is None and not s['remaining']
 assert r['certificate_has_standalone_CRC_boolean'] is False
bad=j['rows'][0];assert bad['run_id']=='jumhvnta' and bad['native_exit_code']==1 and bad['history_rows']==725 and bad['cloud_state']=='failed' and bad['full_config_summary_typed_exact'] is False and bad['checkpoint_or_recovery_claimed'] is False
record=dict(schema='model_v3_Native001030_existing_log_evidence_Root_metadata_review_v1',captured_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),coverage_source=ref(P/'COVERAGE.json'),original_CSV=ref(P/'COVERAGE.csv'),original_README=ref(P/'README.md'),actual_bounded_metadata_source_rawrefs_verified=263,successful_native_and_official_sync_rows=29,legacy_failed_saved_stream_rows=1,failed001_typed_semantics_and_normalized_SHA_remain_unproven=True,no_new_CRC_boolean_or_SDK_scan_claim=True,Root_SDK_steps_resource_journal_weights_or_array_body_read=False,new_audit_or_sync_or_model_execution=False,full_B_precision_acceptance=False,D5_authority=False)
out=P/'ROOT_METADATA_REVIEW.json';assert not out.exists();out.write_text(json.dumps(record,indent=2)+'\n')
rows=list(csv.DictReader(io.StringIO((P/'COVERAGE.csv').read_text())));assert len(rows)==30
keys=['slot','run_id','model_job','audit_job','sync_job','rows','native_exit','cloud_state','full_config_summary_typed']
lines=['# Existing Native B log coverage: actual slots001-030','','Root verified263 bounded metadata/source byte references and independently matched the29 successful full native certificates, official per-run remote readbacks and audit/sync supervisors. No original SDK/history/resource journal/model or array was read.','','001 remains an original failed run:725 saved rows,steps0..724,native exit1,cloud failed; full config/summary semantics and normalized history SHA remain unproven. No checkpoint or recovery qualification is granted.002-030 have complete existing typed/native/official-sync evidence; this table grants no B numerical or D5 acceptance.','','| '+' | '.join(keys)+' |','| '+' | '.join(['---']*len(keys))+' |']
for r in rows:lines.append('| '+' | '.join(r[k].replace('|','\\|').replace('\n',' ') for k in keys)+' |')
lines+=['','CRC/framing evidence is the actual audit C0 plus its exact pinned producer/installed-decoder execution path; certificates have no separate CRC boolean. No current rescan is claimed. Cloud route/state/count/cursors were checked; remote metric values were not independently recompared.','','Full references and scope are in COVERAGE.json and ROOT_METADATA_REVIEW.json. The original thirty-row source CSV remains at its bound N path and is not a standard experiment CSV publication.']
md=P/'COVERAGE.md';assert not md.exists();md.write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(status='EXISTING_29_POSITIVE_AND_ONE_ORIGINAL_FAILED_LOG_SCOPES_VERIFIED',Root_review=ref(out),Markdown=ref(md)),sort_keys=True))
