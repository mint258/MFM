"""Bind the ONE actual CPU readiness parent without inventing per-component jobs."""
import hashlib,json,pathlib,subprocess,xml.etree.ElementTree as ET
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';D=N/'native_S_readiness_actual_v2';O=N/'native_S_readiness_1405_terminal_v1';O.mkdir()
def ref(p):
 p=pathlib.Path(p);raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(p):return json.loads(pathlib.Path(p).read_bytes())
def write(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
 return ref(p)
def capture(argv):
 p=subprocess.run(argv,capture_output=True,text=True,check=True,timeout=30);return dict(argv=argv,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
raw=capture(['sacct','-X','-n','-P','-j','4521405','--format=JobIDRaw,State,ExitCode']);assert raw['stdout'].strip()=='4521405|COMPLETED|0:0';r=write(O/'raw_sacct.json',raw)
own=capture(['sacct','-X','-n','-P','-j','4521405','--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']);row=own['stdout'].strip().split('|');assert row[:4]==['4521405','zixiao','COMPLETED','0:0'] and row[5:]==['16','compute-0-13'];write(O/'owned_parent_sacct.json',own)
result=read(D/'READINESS_RESULT.json');sup=read(pathlib.Path(str(D)+'.supervisor.json'));index=read(D/'COMPONENT_INDEX.json')
assert result['status']=='READINESS_CHILD_COMPLETE_PENDING_ACTUAL_CPU_C0' and result['failure'] is None and result['returncode']==0 and result['job_id']=='4521405'
assert len(result['stages'])==9 and all(x['returncode']==0 and not x['stage_timeout'] and x['job_id']=='4521405' for x in result['stages'])
assert sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None and sup['retirement'] is None and sup['remaining']==[] and sup['private_storage']['first_sampling_failure'] is None
for xml,expected in [(D/'SDK_readback/metadata29.xml',29),(D/'inventory_metadata4.xml',4)]:
 c={k:0 for k in ('tests','failures','errors','skipped')}
 for suite in ET.parse(xml).getroot().iter('testsuite'):
  for k in c:c[k]+=int(suite.attrib.get(k,0))
 assert c==dict(tests=expected,failures=0,errors=0,skipped=0)
assert len(index['sdk']['profiles'])==len(index['future_state'])==2 and len(index['metadata_observations'])==4
projection=write(O/'terminal.json',dict(schema='native_S_actual_terminal_projection_v2',job_id='4521405',status='COMPLETED',exit_code=0,exit_code_raw='0:0',raw_sacct=r,supervisor=ref(pathlib.Path(str(D)+'.supervisor.json')),readiness_result=ref(D/'READINESS_RESULT.json'),component_index=ref(D/'COMPONENT_INDEX.json'),same_actual_parent_for_all_components=True,scientific_acceptance=False))
print(json.dumps(dict(status='ACTUAL_READINESS_CPU_C0_CLOSED',terminal=projection,SDK_QA=29,CP_QA=4,stages=9)))