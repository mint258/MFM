"""Install hash-verified offline software in the new secondary environment only."""
import hashlib,json,os,pathlib,shutil,socket,stat,subprocess,sys,time
ROOT=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
PREFIX=ROOT/'chemprop_compatible_v2'
MANIFEST_SHA='2940cfbc45c61736da45e0dae21180beba592ebb5a3d56d5ac9e9713ff82ba56'
def need(ok,msg):
    if not ok:raise RuntimeError(msg)
def main():
    jid=os.environ.get('SLURM_JOB_ID','');node=socket.gethostname().split('.')[0]
    need(os.getuid()==1264 and jid.isdecimal() and node in {'compute-0-1','compute-0-3','compute-0-4','compute-0-5','compute-0-6','sonmi1'},'SECONDARY_UID_CPU_NODE')
    need(os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('CUDA_VISIBLE_DEVICES')=='','ACTUAL_CPU16_ONLY')
    started=time.monotonic()
    with (ROOT/'offline_install_single_attempt_v1.json').open('x') as f:json.dump({'job_id':jid,'uid':os.getuid()},f)
    wheelroot=ROOT/'wheelhouse_v1';mp=wheelroot/'manifest.json';raw=mp.read_bytes()
    need(len(raw)<2**20 and hashlib.sha256(raw).hexdigest()==MANIFEST_SHA,'EXACT_SOFTWARE_MANIFEST')
    manifest=json.loads(raw);need(len(manifest['files'])==32 and manifest['total_bytes']==284466710,'EXACT32_WHEELS')
    seen=set();total=0
    for row in manifest['files']:
        name=row['name'];need(pathlib.Path(name).name==name and name.endswith('.whl') and name not in seen,'LITERAL_UNIQUE_WHEEL');seen.add(name)
        p=wheelroot/name;s=p.lstat();need(stat.S_ISREG(s.st_mode) and s.st_uid==1264 and s.st_size==row['bytes'],'OWN_EXACT_WHEEL')
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(2**20),b''):h.update(b)
        need(h.hexdigest()==row['sha256'],'TRANSFERRED_WHEEL_SHA_CHANGED');total+=s.st_size
    need(total==manifest['total_bytes'] and shutil.disk_usage(ROOT).free>200000000000+10*1024**3,'SOFTWARE_AND200GB_STORAGE')
    python=PREFIX/'bin/python';need(python.exists() and PREFIX.lstat().st_uid==1264,'ONLY_OWN_PREPARED_PREFIX')
    env={k:v for k,v in os.environ.items() if not k.startswith('PIP_') and k not in {'PYTHONPATH','PYTHONHOME'}}
    env.update(PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',PIP_CONFIG_FILE=os.devnull,PIP_NO_INDEX='1',LD_LIBRARY_PATH=str(PREFIX/'lib'))
    argv=[str(python),'-B','-m','pip','install','--no-index','--no-input','--disable-pip-version-check','--find-links',str(wheelroot),'--prefix',str(PREFIX),'--force-reinstall','numpy==2.2.6','scipy==1.15.3','lmdb==1.7.5','pyarrow==17.0.0','torch==2.5.1+cpu','torch-geometric==2.7.0']
    with (ROOT/('offline_pip_'+jid+'.out')).open('xb') as log:
        result=subprocess.run(argv,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
    need(result.returncode==0,'OFFLINE_SOFTWARE_INSTALL_FAILED')
    check=subprocess.run([str(python),'-B','-m','pip','check'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True)
    need(check.returncode==0,'SOFTWARE_DEPENDENCY_CHECK_FAILED')
    code="""import json,platform,sys,pickle
import rdkit,numpy as np,scipy,pyarrow,lmdb,torch,torch_geometric
from rdkit import Chem
from rdkit.Chem import AllChem
from torch_geometric.data import Data
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
assert platform.python_version()=='3.11.14'
assert rdkit.__version__=='2025.09.5'
assert np.__version__=='2.2.6' and scipy.__version__=='1.15.3'
assert torch.__version__=='2.5.1+cpu' and torch.version.cuda is None
assert torch_geometric.__version__=='2.7.0'
values=np.array([[1.25,-2.0,3.5],[0.0,4.25,6.0]],dtype=np.float64)
roundtrip=pickle.loads(pickle.dumps(Data(pos=torch.tensor(values,dtype=torch.float64))))
assert np.array_equal(roundtrip.pos.detach().cpu().numpy(),values)
assert Chem.MolFromSmiles('CCO').GetNumAtoms()==3
u,s,vt=np.linalg.svd(np.eye(3));assert np.array_equal(s,np.ones(3))
print(json.dumps({'python':platform.python_version(),'executable':sys.executable,'rdkit':rdkit.__version__,'numpy':np.__version__,'scipy':scipy.__version__,'pyarrow':pyarrow.__version__,'lmdb':lmdb.__version__,'torch':torch.__version__,'torch_geometric':torch_geometric.__version__,'torch_cuda_build':torch.version.cuda,'toy_pickle_tensor_PyG_float64_exact':True,'toy_rdkit_parse_atoms':3,'toy_numpy_svd_passed':True}))
"""
    tested=subprocess.run([str(python),'-B','-c',code],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True)
    need(len(tested.stdout.encode())+len(tested.stderr.encode())<2**20,'SMALL_VALIDATION_OUTPUT')
    with (ROOT/('offline_validation_'+jid+'.out')).open('x') as f:f.write(tested.stdout+'\n'+tested.stderr)
    need(tested.returncode==0,'ACTUAL_NATIVE_ENVIRONMENT_IMPORT_OR_TOY_CHECK_FAILED')
    versions=json.loads(tested.stdout)
    result={'schema':'SECONDARY_OFFLINE_ENVIRONMENT_VALIDATION_V1','status':'READY_FOR_GOLDEN16_COMPATIBILITY_TEST','endpoint':'218.192.171.238:22','user':'alpha','uid':os.getuid(),'node':node,'job_id':jid,'cpus':16,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'source_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'python_path':str(python),'software_prefix':str(PREFIX),'versions':versions,'software_manifest_sha256':MANIFEST_SHA,'verified_wheel_files':32,'verified_wheel_bytes':total,'dependency_check_stdout':check.stdout,'memory_requested':False,'actual_memory_environment':{k:os.environ.get(k) for k in ('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU')},'elapsed_seconds':time.monotonic()-started,'dataset_records_read':0,'UFF_calls':0,'QM_calls':0,'golden_compatibility_accepted':False,'formal_generation_authorized':False,'torch_matches_main_build_claimed':False,'version_difference_note':'Torch CPU2.5.1 and Arrow17 are explicitly different from main; actual original-data golden replay is still required. RDKit2025.09.5 and NumPy2.2.6 remain fixed.','forced_signals_sent':False}
    payload=(json.dumps(result,indent=2,sort_keys=True)+'\n').encode()
    with (ROOT/('offline_environment_'+jid+'.json')).open('xb') as f:f.write(payload)
    print(json.dumps({'job_id':jid,'status':result['status'],'result_sha256':hashlib.sha256(payload).hexdigest()}))
if __name__=='__main__':main()
