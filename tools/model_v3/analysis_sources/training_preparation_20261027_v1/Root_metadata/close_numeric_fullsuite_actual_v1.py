import hashlib,json,pathlib,subprocess,sys,xml.etree.ElementTree as ET
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';O=B/'runs/model_v3_20261025';S=N/'numeric_full_regression_v1_source';sys.path.insert(0,str(S))
import regression_control_v4 as c
P=O/'numeric_stability_fullsuite_v1_control_v1.json';ps=c.file_sha(P);plan,assignment=c.verify_frozen_plan(P,ps)
rp=O/'numeric_stability_fullsuite_v1_part0_submission_v1.json';r=c.json_file(rp);job=r['job_id'];assert job=='4521421'
summary_path=O/f'integration_tests_{job}/summary.json';supervisor_path=O/f'integration_supervisor_{job}.json';summary=c.json_file(summary_path);sup=c.json_file(supervisor_path)
original=plan['contract']['scheduler_script'];submitted=pathlib.Path(r['argv'][-1]);assert submitted==O/'run_numeric_full_regression_v1.sbatch'
assert c.file_sha(submitted)==r['script_sha256']==original['sha256']
assert submitted.read_bytes()==pathlib.Path(original['path']).read_bytes()
# The existing Root submit helper admits scripts only under OLD. Verify this
# single exact raw-copy relocation explicitly, preserve the actual receipt,
# then exercise every frozen metadata check with that one path projection.
projected={**r,'argv':[*r['argv'][:-1],original['path']]}
index=c.validate_submission_metadata(plan,ps,projected,summary,sup,assignment);assert index==0
c.validate_partition_union([summary]);argv=['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'];raw=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45,check=True);acct=c.validate_accounting(raw.stdout,[job])
counts=dict(tests=0,failures=0,errors=0,skipped=0)
for sh in summary['shards']:
 xml=O/f'integration_tests_{job}/shard_{sh["shard"]:02d}.xml';root=ET.fromstring(xml.read_bytes());suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'));got={k:sum(int(x.attrib.get(k,0)) for x in suites) for k in counts};assert got==sh['counts'];counts={k:counts[k]+got[k] for k in counts}
assert counts==summary['counts']==dict(tests=2639,failures=0,errors=0,skipped=3)
def ref(p):
 p=pathlib.Path(p);d=p.read_bytes();return dict(path=str(p),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())
out=N/'numeric_full_regression_4521421_actual_closure_v1.json';report=dict(schema='model_v3_numeric_fullsuite_Root_actual_closure_v1',status='ACTUAL_C0_FULL_REGRESSION_VERIFIED',job_id=job,actual_accounting=dict(argv=argv,stdout=raw.stdout,stderr=raw.stderr,returncode=raw.returncode),summary=ref(summary_path),supervisor=ref(supervisor_path),actual_submission=ref(rp),frozen_plan=ref(P),assignment=ref(plan['contract']['assignment']['path']),actual_script=ref(submitted),frozen_script=original,script_path_scope='exact-byte relocation to OLD required by existing Root submission helper; original receipt and frozen plan unchanged',metadata_validation='all frozen checks passed using one explicit script-path projection only; raw actual argv retained',test_counts=counts,passed=2636,test_files=113,pytest_children=4,sources_before_after_equal=summary['sources_before']==summary['sources_after'],current_frozen_runtime_verified=True,original_48_scientific_matrix_pending=True,scientific_adoption=False)
with out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=ref(out),counts=counts,passed=2636,status=report['status'])))