import json,os,signal,socket,time
from pathlib import Path
from prepare import ROOT,save,sha
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
review_path=ROOT/'formal_s/metadata_scheduling_v3_validation.json';review=json.loads(review_path.read_text())
assert review['status']=='PURE_METADATA_SCHEDULING_WORK_CONSERVATION_AND_UNCHANGED_SUBMISSION_GUARDS_PASS'
assert sha(ROOT/'scripts/s_convergence_root_v3.py')==review['new_controller_source_sha256']
b=json.loads((ROOT/'formal_s/controller_binding_v2.json').read_text())
for ref in b['sources']+b['configurations']:assert sha(ref['path'])==ref['sha256']
assert b['run_plan_sha256']==sha(ROOT/'formal_s/run_plan_v2.json')
b['sources']+= [{'path':str(ROOT/'scripts/s_convergence_root_v3.py'),'sha256':sha(ROOT/'scripts/s_convergence_root_v3.py'),'bytes':(ROOT/'scripts/s_convergence_root_v3.py').stat().st_size},{'path':str(review_path),'sha256':sha(review_path),'bytes':review_path.stat().st_size}]
b['metadata_scheduling']={'status':'ROOT_REVIEWED_METADATA_ONLY','node_preference':['compute-0-21','compute-0-20','compute-0-22'],'node21_prefers_long_B3':'observed faster actual throughput; other eligible nodes prefer pending B1','work_conserving':True,'current_scientific_jobs_continue':True,'scientific_sources_or_configs_changed':False,'review_path':str(review_path),'review_sha256':sha(review_path)}
path=ROOT/'formal_s/controller_binding_v3.json';assert not path.exists();save(path,b)
i=json.loads((ROOT/'formal_s/root_coordinator_v1_identity.json').read_text())
assert i['pid']==4078932 and i['uid']==os.getuid() and i['controller_implementation']=='s_convergence_root_v2'
p=Path('/proc')/str(i['pid']);assert p.stat().st_uid==i['uid']
assert (p/'stat').read_text().split()[21]==i['proc_start_ticks']
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==i['boot_id']
assert b's_convergence_root_v2.py' in (p/'cmdline').read_bytes()
archive=ROOT/'formal_s/retired_root_v2_scheduling_identity.json';assert not archive.exists()
save(archive,{'identity':i,'timestamp':time.time(),'action':'SIGTERM_VERIFIED_OWN_METADATA_ROOT_ONLY','scientific_jobs_continue':True})
os.kill(i['pid'],signal.SIGTERM)
print('METADATA_ROOT_V3_BOUND_AND_OWN_ROOT_V2_RETIRED_ONLY')
