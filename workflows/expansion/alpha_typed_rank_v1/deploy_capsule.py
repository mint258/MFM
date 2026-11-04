"""Root-executed Alpha metadata deployment helper; never compile, scan DATA or submit."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import stat
import subprocess
import sys
import zipfile

A=Path('/gfshome/alpha/codex_data_v1_20261026')
D=A/'control/pubchem_completion_environment_20261103'
PRIOR=D/'popcount_production_8cfcee1_actual_deployment.json'
PRIOR_SHA='c0da242418e9ff76b3af40beb09d19d4a8a69c2b737c178d3eae6f55ff3e20de'
PREFIX='workflows/expansion/alpha_typed_rank_v1/'
NAMES={'__init__.py','authority.py','budget.py','closed_N_audit.py','collect.py','entry.py','test_metadata.py','test_native_sql.py','README.md'}
ENTRY_SOURCE='''import sys,importlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
if __name__=="__main__":
 module=sys.argv.pop(1)
 if not module.startswith("workflows.expansion.alpha_typed_rank_v1."):raise RuntimeError("Explicit rank adapter module required")
 importlib.import_module(module).main()
'''
FIXTURE_SOURCE='''"""Root-submitted small source fixtures only; no full-pool admission claim."""
import argparse,importlib,io,os,unittest
import importlib.util
from pathlib import Path
from ..alpha_runtime_v1 import common as Q,profile
from ..alpha_runtime_v1.guard import Guard
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path);a=p.parse_args()
 plan=Q.load(a.plan);proof=Q.load(a.startup_proof);actual=profile.admit(plan,minimum_workers=16);request=proof['request']
 Q.need(plan['schema']=='ALPHA_TYPED_RANK_SOURCE_FIXTURE_PLAN_V1'and plan['scope_key']==request['scope_key']=='alpha_typed_rank_source_fixtures_v1'
  and request['producer_plan_reference']==Q.reference(a.plan)and request['execution_argv']==plan['execution_argv']
  and proof['uid']==actual['uid']==os.getuid()==1264 and proof['endpoint']==actual['endpoint']==Q.ENDPOINT
  and str(proof['job_id'])==actual['job_id']==os.environ['SLURM_JOB_ID']
  and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'Actual small source-fixture allocation required')
 Q.need(all(Q.reference(f)in request['source_references']for f in Path(__file__).parent.glob('*.py')),'All actual rank capsule sources pinned')
 guard=Guard(plan)
 try:
  modules=[(importlib.import_module(__package__+'.'+name),expected)for name,expected in (('test_metadata',4),('test_native_sql',2))]
  allowed={'workflows.expansion.uff3_candidate_v1.test_credit':5,'workflows.expansion.uff3_candidate_v1.test_credit_threads':2,
   'workflows.expansion.uff3_candidate_v1.test_ledger_epoch':None};seen=set()
  extra=plan.get('additional_fixture_suites',[]);Q.need(type(extra)is list,'Explicit additional suite list required')
  for spec in extra:
   name=spec['module'];expected=spec['expected_tests'];ref=spec['source_reference']
   Q.need(name in allowed and name not in seen and type(expected)is int and expected>0
    and(allowed[name]is None or expected==allowed[name]),'Only explicitly counted approved UFF ledger suites allowed')
   Q.need(0<ref['bytes']<=2<<20 and ref in plan['code_references']and ref in request['source_references'],'Additional suite source must be small and plan/startup pinned');Q.verify(ref)
   found=importlib.util.find_spec(name);Q.need(found is not None and Q.reference(found.origin)==ref,'Actual namespace must resolve declared suite source before import')
   module=importlib.import_module(name);Q.need(Q.reference(module.__file__)==ref,'Actual imported additional suite must retain exact source pin')
   modules.append((module,expected));seen.add(name)
  suites=[];suite_details=[]
  for module,expected in modules:
   ref=Q.reference(module.__file__);Q.need(ref in plan['code_references']and ref in request['source_references'],'Every actual fixture module source pinned')
   loaded=unittest.defaultTestLoader.loadTestsFromModule(module);Q.need(loaded.countTestCases()==expected,'Actual loaded suite count differs from Root explicit expected count')
   suites.append(loaded);suite_details.append(dict(module=module.__name__,source_reference=ref,expected_tests=expected,actual_loaded_tests=loaded.countTestCases()))
  expected_total=sum(row['expected_tests']for row in suite_details)
  suite=unittest.TestSuite(suites);log=io.StringIO();r=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
  out=Path(plan['output_directory']);out.mkdir(parents=True,exist_ok=False)
  Q.write(out/'receipt.json',dict(schema='ALPHA_TYPED_RANK_SMALL_SOURCE_FIXTURES_V1',status='FIXTURES_ONLY_PENDING_ACTUAL_C0',tests=r.testsRun,
   failures=len(r.failures),errors=len(r.errors),skips=len(r.skipped),transcript=log.getvalue(),suite_details=suite_details,expected_tests=expected_total,actual_parent=actual,
   plan_reference=Q.reference(a.plan),startup_proof_reference=Q.reference(a.startup_proof),runtime=guard.receipt(),fullpool_or_ranking_execution_claimed=False))
  Q.need(r.testsRun==expected_total and r.wasSuccessful()and not r.skipped,'All actual explicitly counted small source suites must pass');guard.sample();guard.check()
 finally:guard.close()
if __name__=='__main__':main()
'''


def need(value,message):
    if not value:raise ValueError(message)


def stamp(s):return tuple(getattr(s,k)for k in('st_dev','st_ino','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))


def pin(path,maximum=2<<20):
    path=Path(path).absolute();before=path.lstat()
    need(stat.S_ISREG(before.st_mode)and before.st_uid==os.getuid()and before.st_size<=maximum,'Small own regular source/metadata required')
    with path.open('rb')as stream:
        need(stamp(os.fstat(stream.fileno()))==stamp(before),'Same source FD required')
        raw=stream.read(maximum+1);after=os.fstat(stream.fileno())
    need(stamp(before)==stamp(after)==stamp(path.lstat())and len(raw)<=maximum,'Source changed during metadata read')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def verify(ref,maximum=2<<20):
    need(pin(ref['path'],maximum)=={k:ref[k]for k in('path','bytes','sha256')},'Declared actual source/metadata pin differs')
    return Path(ref['path'])


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n')as stream:json.dump(value,stream,sort_keys=True,separators=(',',':'));stream.write('\n')
    return pin(path)


def paths_from_source(path,default=None):
    tree=ast.parse(Path(path).read_text())
    values=[n.value for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='__path__'for t in n.targets)]
    if not values:
        need(default is not None,'Explicit inherited namespace source required');return [str(default)]
    need(len(values)==1,'Unambiguous inherited namespace assignment required');value=ast.literal_eval(values[0])
    need(isinstance(value,list)and all(isinstance(p,str)and Path(p).is_absolute()for p in value),'Literal actual namespace paths required')
    return value


def union(*groups):
    result={}
    for group in groups:
        for value in group:
            ref={k:value[k]for k in('path','bytes','sha256')}
            need(ref['path']not in result or result[ref['path']]==ref,'Conflicting source pins');result[ref['path']]=ref
    return list(result.values())


def unique(values):return list(dict.fromkeys(map(str,values)))


def namespace_source(values):return '__path__ = '+repr(values)+'\n'


def relative(name):
    p=PurePosixPath(name)
    need(not p.is_absolute()and '\\'not in name and '..'not in p.parts and str(p)==name,'Safe literal archive member path required')
    return p


def deploy(a):
    need(os.getuid()==1264 and sys.flags.isolated,'Root executes this helper only on isolated real Alpha UID1264')
    prior_ref=pin(a.prior_deployment)
    need(prior_ref['bytes']==93797 and prior_ref['sha256']==PRIOR_SHA,'Known actual CPP source deployment required')
    prior=read(verify(prior_ref));base=Path(prior['base_code_root'])
    need(Path.cwd().resolve()==base.resolve()and base.parent==A/'code'and not(base/'string.py').exists(),
      'Exact clean Alpha code cwd required; never run from home/string.py')
    capsule=a.capsule.absolute()
    need(capsule.parent==A/'code'and re.fullmatch('alpha_typed_rank_[A-Za-z0-9_]+',capsule.name)
      and not capsule.exists()and not a.output_metadata.exists(),'New real capsule and fresh deployment metadata required')
    need(a.output_metadata.absolute().parent==D,'Deployment metadata belongs to the actual Alpha environment control directory')
    prior_refs=prior['code_references']
    for value in prior_refs:verify(value)
    old_layer=Path(prior['entry_reference']['path']).parent
    wf_source=old_layer/'workflows/__init__.py';exp_source=old_layer/'workflows/expansion/__init__.py'
    wf_paths=paths_from_source(wf_source);exp_paths=paths_from_source(exp_source)
    old_ranks=[r for r in prior_refs if r['path'].endswith('/exact_nn_cached_v1/typed_rank.py')]
    need(len(old_ranks)==1,'One actual inherited original typed_rank source required')
    rank_origin=old_ranks[0];verify(rank_origin)
    sort_origin=pin(base/'workflows/expansion/external_sort.py')
    mref=pin(a.source_manifest);manifest=read(verify(mref));zref=pin(a.archive,2<<20)
    need(zref['sha256']==manifest['archive_sha256']and re.fullmatch('[0-9a-f]{40}',manifest['source_commit']),
      'Actual source archive SHA and execution commit required')
    declared={r['path']:r for r in manifest['files']}
    need(len(declared)==len(manifest['files'])and {PREFIX+n for n in NAMES}<=set(declared)
      and set(declared)<={PREFIX+n for n in NAMES|{'deploy_capsule.py'}},'Only the reviewed nine-file source package, optionally this helper')
    need(sum(r['bytes']for r in declared.values())<=4<<20,'Small source-only archive required')
    bodies={}
    with zipfile.ZipFile(a.archive)as archive:
        names=set()
        for item in archive.infolist():
            name=item.filename;relative(name.rstrip('/')if item.is_dir()else name)
            if item.is_dir():continue
            mode=stat.S_IFMT(item.external_attr>>16)
            need(name not in names and name in declared and mode in(0,stat.S_IFREG),'No duplicate, foreign or symlink archive member')
            need(item.file_size==declared[name]['bytes']and item.file_size<=2<<20,'Actual bounded declared source member size')
            raw=archive.read(item);need(hashlib.sha256(raw).hexdigest()==declared[name]['sha256'],'Archive source body SHA differs')
            bodies[name]=raw;names.add(name)
        need(names==set(declared),'Archive must contain every and only declared source body')
    # All validation above is read-only. From here Root's explicit execution
    # creates only this new real capsule; it never edits any inherited layer.
    capsule.mkdir(mode=0o700)
    for name,raw in bodies.items():
        target=capsule.joinpath(*PurePosixPath(name).parts);target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb')as stream:stream.write(raw)
    expansion=capsule/'workflows/expansion';nn=expansion/'exact_nn_cached_v1';nn.mkdir()
    bindings={}
    for name,origin,target in [('typed_rank.py',rank_origin,nn/'typed_rank.py'),('external_sort.py',sort_origin,expansion/'external_sort.py')]:
        with target.open('xb')as stream:stream.write(verify(origin).read_bytes())
        actual=pin(target);need(actual['bytes']==origin['bytes']and actual['sha256']==origin['sha256'],'Original-body copy must be byte-identical')
        bindings[name]=dict(origin_reference=origin,execution_reference=actual)
    nn_paths=unique([nn,Path(rank_origin['path']).parent,*[Path(p)/'exact_nn_cached_v1'for p in exp_paths if(Path(p)/'exact_nn_cached_v1').is_dir()]])
    for path,values in [(capsule/'workflows/__init__.py',unique([capsule/'workflows',*wf_paths])),
      (expansion/'__init__.py',unique([expansion,*exp_paths])),(nn/'__init__.py',nn_paths)]:
        with path.open('x',encoding='utf-8',newline='\n')as stream:stream.write(namespace_source(values))
    fixture=expansion/'alpha_typed_rank_v1/fixture_bundle.py'
    with fixture.open('x',encoding='utf-8',newline='\n')as stream:stream.write(FIXTURE_SOURCE)
    entry=capsule/'layer_entry.py'
    with entry.open('x',encoding='utf-8',newline='\n')as stream:stream.write(ENTRY_SOURCE)
    nsref=save(capsule/'rank_namespace_manifest.json',dict(capsule_exact_nn_cached_v1_path=str(nn),
      exact_nn_cached_v1_search_paths=nn_paths,namespace_source_reference=pin(nn/'__init__.py'),
      inherited_namespace_source_references=[pin(wf_source),pin(exp_source)],metadata_only=True))
    generated=[pin(p)for p in sorted(capsule.rglob('*.py'))]
    inherited=union(prior_refs,[rank_origin,sort_origin])
    refs=union(inherited,generated,[pin(__file__),mref,zref,nsref,pin(wf_source),pin(exp_source)])
    result=dict(schema='ROOT_ALPHA_TYPED_RANK_CAPSULE_SOURCE_DEPLOYMENT_V1',status='SOURCE_ONLY_NO_NATIVE_OR_FULL_RANK_EXECUTION',
      base_code_root=str(base),entry_reference=pin(entry),code_references=refs,source_manifest_reference=mref,
      archive_reference=zref,source_execution_commit=manifest['source_commit'],helper_source_reference=pin(__file__),
      prior_deployment_references=[prior_ref],original_rank_source_bindings=bindings,rank_namespace_manifest_reference=nsref,
      archive_source_references=[dict(archive_member=name,execution_reference=pin(capsule.joinpath(*PurePosixPath(name).parts)))for name in sorted(bodies)],
      helper_generated_source_references=[pin(p)for p in(capsule/'workflows/__init__.py',expansion/'__init__.py',nn/'__init__.py',entry,fixture)],
      optional_fixture_module='workflows.expansion.alpha_typed_rank_v1.fixture_bundle',
      existing_layers_or_201_modified=False,large_DATA_or_cache_read=False,compiler_or_submitter_called=False)
    pending=capsule/'deployment_metadata_for_preflight.json';save(pending,result)
    script='''import sys,json\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[1])
from workflows.expansion.alpha_typed_rank_v1 import authority
from workflows.expansion.exact_nn_cached_v1 import typed_rank
from workflows.expansion import exact_nn_cached_v1 as package
d=authority.read(authority.ref(Path(sys.argv[2])));bound=authority.deployed(d)
assert authority.ref(typed_rank.__file__)==bound['typed_rank.py']
assert authority.ref(Path(typed_rank.create_queues.__code__.co_filename))==bound['external_sort.py']
ns=authority.read(d['rank_namespace_manifest_reference']);assert list(package.__path__)==ns['exact_nn_cached_v1_search_paths']
print(json.dumps(dict(imported_rank=authority.ref(typed_rank.__file__),imported_create_queues=authority.ref(Path(typed_rank.create_queues.__code__.co_filename)),actual_exact_package_search_paths=list(package.__path__),authority_deployed_contract_passed=True,metadata_imports_only=True)))
'''
    command=[str(A/'software/pubchem_completion_20261103_venv/bin/python'),'-I','-B','-c',script,str(capsule),str(pending)]
    try:process=subprocess.run(command,cwd=base,text=True,capture_output=True,check=True)
    except subprocess.CalledProcessError as exc:
        failure=save(capsule/'metadata_preflight_failure.json',dict(returncode=exc.returncode,stdout=exc.stdout,stderr=exc.stderr,
          metadata_imports_only=True,partials_preserved=True))
        raise ValueError('Metadata import preflight failed; preserved witness: '+failure['path'])from exc
    preflight=json.loads(process.stdout.strip());result['metadata_import_preflight']=preflight
    result['preflight_metadata_reference']=pin(pending);result['code_references']=union(refs,[pin(pending)])
    return save(a.output_metadata,result)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in('archive','source-manifest','capsule','output-metadata'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--prior-deployment',type=Path,default=PRIOR)
    print(json.dumps(deploy(p.parse_args()),sort_keys=True))


if __name__=='__main__':main()
