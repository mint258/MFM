import hashlib,json,pathlib,subprocess,xml.etree.ElementTree as ET
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';A=N/'native_closed028029_SDK_audit_actual_v1'
def ref(p):
 raw=pathlib.Path(p).read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
a=json.loads((A/'BATCH_RESULT.json').read_bytes());s=json.loads(pathlib.Path(str(A)+'.supervisor.json').read_bytes())
job=a['actual_job_id'];assert job==json.loads((N/'Native028029_exact_two_SDK_audit_CPU_control_v1/SUBMITTED.json').read_bytes())['job_id']
assert a['status']=='CLOSED_SEGMENT_LOGS_MATCHED_PENDING_CPU_OUTER_C0' and a['returncode']==0 and a['failure'] is None and len(a['verifications'])==2
assert s['status']=='COMPLETED' and s['job_id']==job and s['exit_code']==0 and s['first_failure'] is None and not s['remaining']
c={k:0 for k in ('tests','failures','errors','skipped')}
for q in ET.parse(A/'metadata.xml').getroot().iter('testsuite'):
 for k in c:c[k]+=int(q.get(k,0))
assert c==dict(tests=28,failures=0,errors=0,skipped=0)
acct=['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
r=subprocess.run(acct,capture_output=True,text=True,check=True)
row=r.stdout.strip().split('|');assert row[:4]==[job,'zixiao','COMPLETED','0:0'] and int(row[4])>0 and row[5:]==['16','compute-0-19'] and r.stderr==''
py=B/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
argv=[str(py),'-B',str(N/'native_closed028029_long_sync_v1_source/prepare.py')]
for vr in a['verifications']:
 assert ref(vr['path'])==vr;v=json.loads(pathlib.Path(vr['path']).read_bytes())
 assert v['status']=='ALL_SAVED_SCIENTIFIC_LOG_FIELDS_MATCHED'
 argv+=['--entry',vr['path'],str(A/'BATCH_RESULT.json'),str(A)+'.supervisor.json']
argv+=['--pins-sha256','ffd3a5b543c2a386a94591c8ba192037ea4c0810e81d82d0aae9094a24857317','--output',str(N/'native_closed028029_sync_plan_v1'),'--job-output',str(N/'native_closed028029_sync_actual_v1')]
out=N/'native_closed028029_sync_prepare_actual_v1.json';assert not out.exists()
run=subprocess.run(argv,capture_output=True,text=True,timeout=180)
body=dict(schema='NATIVE_CLOSED028029_SYNC_PREPARE_ACTUAL_V1',actual_audit_C0=dict(argv=acct,stdout=r.stdout,stderr=r.stderr,returncode=r.returncode),metadata_QA=dict(XML=ref(A/'metadata.xml'),counts=c),audit=ref(A/'BATCH_RESULT.json'),audit_supervisor=ref(pathlib.Path(str(A)+'.supervisor.json')),preparation=dict(argv=argv,returncode=run.returncode,stdout=run.stdout,stderr=run.stderr),SDK_payload_read=False,online_action=False,author_handoff_path_placeholders_materialized_as_single_absolute_argv_elements=True)
out.write_text(json.dumps(body,indent=2)+'\n')
print(json.dumps(dict(returncode=run.returncode,receipt=ref(out),stdout=run.stdout,stderr=run.stderr),sort_keys=True));assert run.returncode==0
