"""Freeze a permanent WP5 reproduction package: code/binaries/params/recipes/environment."""
from __future__ import annotations
import argparse,ast,concurrent.futures,hashlib,importlib.metadata,json,os,shutil,socket,subprocess,sys,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
OVERRIDE_SHA='b368187eb93d0641c0628fc33ed447192cf0e260bcfb0e01230812c49ba72b2c'
NODES={'compute-0-'+str(n) for n in (12,13,14,17,18,19)}
_ENV=('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','XTBPATH','PYTHONPATH','LD_LIBRARY_PATH')
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8<<20),b''):h.update(block)
    return h.hexdigest()
def save(path,data):
    path=Path(path)
    if path.exists():raise FileExistsError(path)
    with path.open('x') as stream:json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
def asset(arg):
    item,out=arg;source=Path(item['path'])
    if source.suffix=='.lmdb' or any(part.endswith('.lmdb') for part in source.parts):raise ValueError('NO_DATASET_COPY_IN_REPRODUCTION_PACKAGE')
    first=source.stat();actual=sha(source)
    if item.get('sha256') and actual!=item['sha256']:raise ValueError('ACTUAL_SOURCE_SHA_CHANGED:'+str(source))
    destination=Path(out)/'assets'/item['role']/(actual+'_'+source.name);destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,destination)
    if sha(destination)!=actual or source.stat().st_mtime_ns!=first.st_mtime_ns:raise ValueError('PACKAGE_COPY_OR_SOURCE_STABILITY_FAILED')
    return {'role':item['role'],'source_path':str(source),'path':str(destination),'sha256':actual,'bytes':first.st_size,'source_uid':first.st_uid,'mode':first.st_mode &0o777,'worker_pid':os.getpid()}
def environment():
    allowed={name:os.environ.get(name) for name in _ENV}
    versions={}
    for name in ('numpy','pyarrow','duckdb','rdkit','torch','torch-geometric','lmdb','zstandard'):
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    conda=[]
    for path in sorted((Path(sys.prefix)/'conda-meta').glob('*.json')):
        raw=json.loads(path.read_text())
        # No channel auth URLs, shell history, arbitrary environment, passwords or keys.
        conda.append({key:raw.get(key) for key in ('name','version','build','build_number','subdir','fn','md5','sha256')})
    return {'python_executable':sys.executable,'python_executable_sha256':sha(sys.executable),'python_version':sys.version,
        'conda_prefix':sys.prefix,'conda_package_lock':conda,'packages':versions,'selected_environment_variables':allowed,
        'platform':{'kernel':os.uname().release,'machine':os.uname().machine,'system':os.uname().sysname},
        'same_environment_rule':'Use the frozen prefix/interpreter, binary/parameter SHA and one-thread variables. Each run binds this package SHA; source/binary changes reject execution.'}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--chain',type=Path,help='Final current source inventory JSON; no provisional code is silently frozen')
    p.add_argument('--protocol',type=Path,default=ROOT/'configs/protocol.json');p.add_argument('--g4-reference',type=Path,default=ROOT/'gates/G4_freeze/job_4513932/report.json')
    p.add_argument('--authority',type=Path,default=ROOT/'configs/user_raw_retention_override_20261011_v1.json')
    p.add_argument('--audit-membership',type=Path);p.add_argument('--out',type=Path);p.add_argument('--workers',type=int,default=24);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('REPRODUCTION_PACKAGE_AST_PASS_NO_EXPORT_NO_HASH_NO_QM');return
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0] not in NODES or a.workers<24 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers:raise ValueError('Actual authorized24+ allocation required')
    if sha(a.authority)!=OVERRIDE_SHA:raise ValueError('Actual user raw-retention override changed')
    if not a.chain or not a.audit_membership:raise ValueError('Final frozen current chain and actual audit membership required')
    chain=json.loads(a.chain.read_text());protocol=json.loads(a.protocol.read_text());old=json.loads(a.g4_reference.read_text());audit=json.loads(a.audit_membership.read_text())
    if old['status']!='PASS' or audit['status']!='AUDIT_MEMBERSHIP_CLOSED':raise ValueError('Actual prior binary evidence and current record audit must close')
    if chain.get('status')!='CURRENT_CODE_READY_TO_FREEZE':raise ValueError('Do not package provisional/mutating sources')
    out=a.out or ROOT/'reproduction_package'/('job_'+os.environ['SLURM_JOB_ID'])
    if not out.resolve().is_relative_to(ROOT):raise ValueError('Package output only inside current root')
    out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();items=list(chain['files']);items.append({'path':str(a.chain),'role':'current_chain_inventory','sha256':sha(a.chain)})
    items.extend([{'path':str(a.authority),'role':'user_override','sha256':OVERRIDE_SHA},{'path':str(a.protocol),'role':'protocol','sha256':sha(a.protocol)},
        {'path':protocol['registry']['path'],'role':'registry','sha256':protocol['registry']['sha256']},
        {'path':str(a.audit_membership),'role':'audit_membership','sha256':sha(a.audit_membership)},
        {'path':audit['selected_records']['path'],'role':'audit_selected_records','sha256':audit['selected_records']['sha256']}])
    for family in ('mopac','xtb'):
        entry=old['context']['software'][family]
        if protocol[family+'_executable']!=entry['path']:raise ValueError('Binary absolute entry changed:'+family)
        items.append({'path':entry['path'],'role':'binary_'+family,'sha256':entry['expected_sha256']})
    for entry in protocol['frozen_dependencies'].values():items.append({'path':entry['path'],'role':'scientific_dependency','sha256':entry['sha256']})
    for entry in protocol.get('mulliken_official_references',{}).values():items.append({'path':entry['path'],'role':'mulliken_reference','sha256':entry['sha256']})
    # The actual prior G4 hashes explicitly include every XTB parameter file.
    parameter_prefix=Path(protocol['xtb_environment']['XTBPATH']).resolve()
    for entry in old['bindings']:
        path=Path(entry['path'])
        if path.resolve().is_relative_to(parameter_prefix):items.append({'path':str(path),'role':'xtb_parameter','sha256':entry['sha256']})
    unique={}
    for item in items:
        if item['path'] in unique and unique[item['path']]['sha256']!=item['sha256']:raise ValueError('Conflicting frozen source declarations')
        unique.setdefault(item['path'],item)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:assets=list(pool.map(asset,((item,str(out)) for item in unique.values()),chunksize=1))
    env=environment();save(out/'environment_lock.json',env)
    recipes={'protocol_seed':protocol['seed'],'perturbation_sigma_A':protocol['perturb_sigma_A'],'pair_cutoff_A':protocol['pair_cutoff_A'],'timeout_seconds':protocol['timeout_seconds'],
        'audit_seed':20261010,'audit_selection':audit['selection'],'tasks':protocol['tasks'],
        'seed_rule':"PERT seed =1+int(SHA256(str(protocol_seed)+'|'+record_id)[:16],16)%2147483646; NumPy default_rng(seed).normal(0,perturb_sigma_A,coords.shape), add to a coordinate copy; no job/time dependent seed",
        'input_file_sha256_rule':'Per actual original rendered input filename and SHA256 of original bytes; names are relative basenames, ordered canonical by name. No per-record input file/body is saved.',
        'input_bundle_sha256_rule':'SHA256 of original WP5BUNDLE1 canonical envelope A4.bundle(sorted original render_inputs members with role=input)); exact A4.bundle source is packaged. Supplementary, never replaces per-file typed hashes.',
        'renderer_source_files':[entry for entry in assets if Path(entry['source_path']).name in {'wp5_engine_v2.py','wp4_native_pilot_v4.py'}]}
    save(out/'recipes_and_seed_rules.json',recipes)
    source_assets={entry['source_path']:entry for entry in assets}
    software={}
    for sid,family in ((1,'mopac'),(2,'xtb')):
        reference=old['context']['software'][family];copied=source_assets[reference['path']]
        software[family]={'software_version_id':sid,'version':reference['version'],'executable':reference['path'],'sha256':reference['expected_sha256'],'copied_binary':copied['path'],
            'protect_original_entry':'At worker initialization reject original executable/parameter/source SHA changes relative to this permanent package'}
    manifest={'schema':'WP5_REPRODUCTION_PACKAGE_V1','status':'REPRODUCTION_PACKAGE_CLOSED','job_id':os.environ['SLURM_JOB_ID'],'software_versions':software,
        'assets':assets,'asset_bytes':sum(entry['bytes'] for entry in assets),'environment':{'path':str(out/'environment_lock.json'),'sha256':sha(out/'environment_lock.json')},
        'recipes':{'path':str(out/'recipes_and_seed_rules.json'),'sha256':sha(out/'recipes_and_seed_rules.json')},
        'protocol':{'path':str(a.protocol),'sha256':sha(a.protocol)},'registry':protocol['registry'],
        'audit_membership':{'path':str(a.audit_membership),'sha256':sha(a.audit_membership)},
        'authority':{'path':str(a.authority),'sha256':OVERRIDE_SHA},
        'source_input_reconstruction':'Final native base z/float64 positions +record_id+frozen recipe/renderer/seed recreate inputs; source payload pointers/SHA remain in formal population. No saved per-record input bytes.',
        'permanent':True,'source_assets_unchanged':True,'new_QM_calls':0,'original_data_written':False,'dataset_copied':False,'seconds':time.monotonic()-started,
        'script_sha256':sha(__file__),'precision_rule':'Only original per-field parser declaration; unknown precision is strict, never a widened universal epsilon.'}
    save(out/'manifest.json',manifest);print(json.dumps({'package':str(out/'manifest.json'),'assets':len(assets),'bytes':manifest['asset_bytes']}))
if __name__=='__main__':main()
