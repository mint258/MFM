#!/usr/bin/env python3
"""Root actual small checks of handed-off new-policy interfaces; never QM/submission."""
import hashlib,json,os,pathlib,socket,subprocess,time
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
PYTHON='/share/home/zixiao/.conda/envs/chemprop/bin/python'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    checks=[
      ('scf_v2','wp5_scf_metadata_v2.py',['--check'],'565c55a2b63ce0de7a7c84302b69cccc0bffe5afb2516cb0df4013bbbf54d64a'),
      ('registry_coverage','wp5_registry_coverage.py',['--check'],'ec98cc853677dc083fbb623f6da86de8921f22eb57deba24121efad11e6f0cf8'),
      ('new_policy_prototype','wp5_storage_new_policy_benchmark_v1.py',['--check'],'64fa5fc47e78d63cb86843aaf7992b4bdf7f0bedf49d104b7c306eae841b4090'),
      ('new_policy_budget','wp5_storage_budget_v10.py',['--check'],'dd355f74b05e02fa7c18876bc8757b8a47040df395584492be87735304ad901b'),
      ('reproduction50','wp5_reproduction50_v2.py',['plan','--check'],'45e470baf9d250b9912996181258810571563fd593a536385f5b9b467f7e67ad'),
      ('bulk7','wp5_submit_formal_v7.py',['--check'],'eb953f627446dee2e4b3b939308283f79d7ed468f0745ef2eab70b44b9e101c0'),
      ('g4checker4','wp5_g4_freeze_v4.py',['--check'],'bee252c576e5ba7dec9176c2019a25e76288402db070829cb6e92e5fce1aa328'),
      ('prototype_batch','wp5_storage_new_policy_benchmark_v1.sbatch',[],'8d54a9da9635a4208a63751e80500ebb0b39839f293a978fcc8cc6bb10c1e941'),
      ('budget_batch','wp5_storage_budget_v10.sbatch',[],'f1f8ed8b38e4fb5eccc43b0f5b601061d5b2f101f61c4170ddf88e732ad26ff3'),
      ('reproduction50_batch','wp5_reproduction50_v2.sbatch',[],'976f10a24e845faaa85de2c807d999e3e591e7dab4c140f365ee67cbdddab52d'),
      ('g4_batch','wp5_g4_freeze_v4.sbatch',[],'199ab3ce39555e5d4bc7bc36c18bd008f1efe11e8695ac0da8ceb7403182e415')]
    report={'schema':'WP5_ROOT_NEW_POLICY_PREPARED_CHECKS_V1','created_epoch':time.time(),'uid':os.getuid(),'hostname':socket.gethostname(),'checks':[]}
    for name,filename,args,expected in checks:
        path=ROOT/'scripts'/filename
        result={'name':name,'path':str(path),'expected_sha256':expected,'actual_sha256':sha(path)}
        if result['actual_sha256']!=expected:result.update(status='HANDOFF_SHA_DIFFERENCE',returncode=None)
        else:
            argv=['bash','-n',str(path)] if path.suffix=='.sbatch' else [PYTHON,'-B',str(path),*args]
            if path.suffix=='.sbatch' and b'\r' in path.read_bytes():result.update(status='CR_REJECTED',returncode=None)
            else:
                done=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60)
                result.update(argv=argv,returncode=done.returncode,stdout=done.stdout,stderr=done.stderr,
                              status='PASS' if done.returncode==0 and sha(path)==expected else 'NOT_PASS')
        report['checks'].append(result)
        print(name,result['status'],result.get('returncode'),flush=True)
    report['status']='PASS' if all(r['status']=='PASS' for r in report['checks']) else 'NOT_PASS'
    out=ROOT/'reports/root_new_policy_prepared_actual_checks_v1.json'
    with out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(report['status'],str(out))
    raise SystemExit(0 if report['status']=='PASS' else 1)
if __name__=='__main__':main()
