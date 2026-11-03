"""Explicit IO context for unchanged postprocess_day_v1.common.build."""
import importlib,json,sys,types
from pathlib import Path
from .runtime import need,pin,read,verify,save


def bind_original_namespace(config_reference):
    """Load unchanged legacy objects at their real canonical source namespace.

    The historical contract derives ledger paths from __file__. A worktree is
    not a copied data run. Preserve that invariant by importing the canonical
    source, rather than changing its constants or relaxing its config guard.
    """
    verify(config_reference)
    repo=Path(config_reference['path']).parents[3]
    expected=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository')
    need(repo==expected and (repo/'workflows/data_v1_final').is_dir(),'ACTUAL_FROZEN_CANONICAL_REPOSITORY')
    # Cache the new shared-runtime package at this checkout before changing
    # legacy import priority. Its API stays the current Root source epoch.
    importlib.import_module('workflows.expansion.completion_runtime_v1')
    legacy=('workflows.data_v1_final.','workflows.expansion.common_molecular_fp_main_v1.',
      'workflows.expansion.common_molecular_fp_candidate_v1.')
    for name,module in list(sys.modules.items()):
        if name.startswith(legacy):
            file=getattr(module,'__file__',None)
            need(file is None or repo in Path(file).absolute().parents,'LEGACY_SOURCE_ALREADY_IMPORTED_FROM_WRONG_NAMESPACE:'+name)
    for name,relative in (('workflows','workflows'),('workflows.expansion','workflows/expansion')):
        package=importlib.import_module(name);path=str(repo/relative)
        package.__path__=[path,*[p for p in package.__path__ if p!=path]]
    return repo


def ensure_spawn_entrypoint():
    """Original finalize imports prepend canonical REPO to sys.path.

    Spawn must first find this new entry module, then its __mp_main__ hook
    restores canonical legacy imports before unpickling original callables.
    """
    checkout=str(Path(__file__).absolute().parents[3])
    sys.path[:]=[checkout,*[p for p in sys.path if p!=checkout]]
    importlib.invalidate_caches()
    return checkout


class Context:
    def __init__(self,plan,proof,out,budget):
        repo=bind_original_namespace(plan['original_config_reference'])
        from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as F,runtime_io as R
        self.F=F;self.plan,self.proof,self.out,self.budget=plan,proof,Path(out),budget;self.cpus=plan['cpus'];self.job_id=str(proof['job_id'])
        self.value=F.config(plan['original_config_reference']);self.common_out=self.out/'common';self.common_out.mkdir()
        need(F.REPO==repo and F.RUN==repo.parent and F.LEDGER==Path(self.value['attempt_ledger_root'])
          and F.BASE==Path(self.value['external_output_root']),'UNCHANGED_ORIGINAL_CONFIG_AND_TRUE_LEDGER_NAMESPACE')
        save(self.out/'canonical_original_namespace.json',dict(original_config_reference=plan['original_config_reference'],
          canonical_repository=str(repo),contract=pin(F.__file__),runtime_io=pin(R.__file__),
          attempt_ledger_root=str(F.LEDGER),old_external_output_root=str(F.BASE),legacy_constants_modified=False,
          standalone_module_source_unchanged=str(Path(__file__).absolute())))
        self.args=types.SimpleNamespace(config=Path(plan['original_config_reference']['path']),completion_index=None)
        self.allowed={};self.evidence={};self.geometry_sha=R.common().geometry_sha
        self.trust([plan['original_config_reference'],*[self.value[k] for k in ('per_molecule','roles_authority','formal_source_receipt','sprime_manifest')]])
        formal=read(self.value['formal_source_receipt']);refs=[r['reference'] for r in formal['outputs'] if r['name']=='formal_population']
        need(formal['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED' and len(refs)==1,'EXACT_ORIGINAL_FORMAL_SOURCE_PIN')
        self.formal_reference=refs[0];self.trust(refs)
        baseline=read(self.value['sprime_manifest']);self.trust([r for r in baseline['references'] if r['kind']=='conformers'])
    def trust(self,refs):
        for ref in refs:
            triple={k:ref[k] for k in ('path','bytes','sha256')};previous=self.allowed.get(ref['path'])
            need(previous is None or previous==triple,'CONFLICTING_ORIGINAL_INPUT_REFERENCES');self.allowed[ref['path']]=triple
    def authorized(self,refs):
        for ref in refs:
            triple={k:ref[k] for k in ('path','bytes','sha256')}
            need(self.allowed.get(ref['path'])==triple or self.out in Path(ref['path']).parents,'SOURCE_NOT_FROM_EXACT_CONFIG_OR_CENSUS')
    def check(self,*args,**kwargs):return self.budget.check(*args,**kwargs)
    def require(self,ref):self.authorized([ref]);return verify({k:ref[k] for k in ('path','bytes','sha256')},self.check)
    require_pin=require
    def read(self,ref,limit=2<<20):need(ref['bytes']<=limit,'SMALL_METADATA_LIMIT');return json.loads(self.require(ref).read_text())
    def reference(self,path):return pin(path,self.check)
    def write_json_new(self,path,value):
        need(self.out in Path(path).parents,'FRESH_OWN_OUTPUT_ONLY');self.check();ref=save(path,value);self.trust([ref]);return ref
    def write_parquet_new(self,path,table):
        import pyarrow.parquet as pq
        need(self.out in Path(path).parents and not Path(path).exists(),'FRESH_OWN_PARQUET_ONLY');self.check()
        pq.write_table(table,path,compression='zstd',row_group_size=4096);ref=pin(path,self.check);self.trust([ref]);return ref
    def roles(self,value):
        authority=read(value['roles_authority']);r=authority['source_role_manifest'];self.trust([r]);m=read(r)
        need(authority['validation_source']=='ROUTINE' and m['status']=='ROUTINE_MOLECULE_VAL_ROLES_FROZEN','ORIGINAL_ROUTINE_ROLES')
        refs=[{k:v[k] for k in ('path','bytes','sha256')} for v in m['outputs'] if '/molecule_roles/' in v['path']]
        need(len(refs)==16,'ALL16_WHOLE_SOURCE_ROLE_PARTS');self.trust(refs)
        for ref in refs:self.require(ref)
        return r,refs
    def attempt_binding(self,packet,value,imports):
        mid=packet['molecule_id'];e=self.evidence[mid];meta=e['original_meta'];ref=e['package_reference']
        need(all(packet['source'][k]==ref[k] for k in ('path','bytes','sha256')),'EXACT_DURABLE_CENSUS_PACKAGE_SOURCE')
        lr=e['ledger_reference'];claim=read(lr)
        need(claim['molecule_id']==mid and claim['task_key']==meta['task_key'] and claim['seed']==packet['summary']['seed']
            and packet['summary']['status']==e['scientific_status'],'ORIGINAL_ONCE_LEDGER_MID_SEED_STATUS')
        start=packet['formal_start']
        if start is not None:
            need(start['task_key']==claim['task_key'] and start['molecule_id']==mid and start['seed']==claim['seed']
                and start['job_id']==claim['job_id'] and start['dispatch_reference']==lr,'TRUE_ORIGINAL_WORKER_NOT_NEW_PARENT')
            if e.get('start_reference'):
                self.trust([e['start_reference']]);need(read(e['start_reference'])==start,'ACTUAL_CLOSED_WORKER_START_SOURCE')
            if 'task_sha256' in e:need(start['task_sha256']==claim['task_sha256']==e['task_sha256'],'TRUE_ORIGINAL_TASK_PAYLOAD')
        else:
            need(e['origin']=='HISTORICAL_IMPORTED_ATTEMPT' and mid in imports and
                 all(imports[mid]['package_reference'][k]==ref[k] for k in ('path','bytes','sha256')),
                 'ONLY_ACTUAL_HISTORICAL_IMPORT_CAN_HAVE_NO_FORMAL_START')
        self.check();return dict(task_key=meta['task_key'],once_ledger_path=lr['path'],once_ledger_sha256=lr['sha256'],once_ledger_bytes=lr['bytes'])
