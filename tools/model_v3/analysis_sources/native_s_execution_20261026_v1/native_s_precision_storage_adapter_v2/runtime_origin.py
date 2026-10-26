"""One combined immutable runtime; metadata preflight never opens data inputs."""
from __future__ import annotations
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import sys
import re
import stat
import os

TOOLS=('a_execution_runtime','profile_s_baseline','run_native_s_precision','run_precision_experiment',
    'runtime_monitor','private_runtime_storage','s_input_stream','native_runtime_bindings','s_loader_recovery_v1','s_loader_recovery_v2',
    's_native_adapter_v1','s_native_adapter_v2','s_model_memory_v1','prepare')


def require(value,message):
    if not value: raise ValueError(message)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''): h.update(block)
    return h.hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()


def runtime_identity(value):
    return {key:value[key] for key in ('runtime_root','combined_commit','combined_tree','public_commit',
        'accounting_leaf_provenance','files')}


def read_qa_reference(reference):
    path=Path(reference['path']); require(path.is_absolute() and '..' not in path.parts,'Absolute QA evidence path required')
    info=path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_nlink==1
        and not any(parent.is_symlink() for parent in (path,*path.parents)),'Owned ordinary QA evidence required')
    require(info.st_size==reference['bytes'] and reference['bytes']<=2<<20
        and sha(reference['path'])==reference['sha256'],'Actual QA reference bytes differ')
    return json.loads(Path(reference['path']).read_text())


def verify_candidate_profile(value):
    import evidence_graph
    proof=read_qa_reference(value['candidate_profile_admission'])
    require(proof['schema']=='native_S_candidate_profile_admission_v2' and proof['status']=='CANDIDATE_PROFILE_ONLY_VERIFIED'
        and proof['combined_commit']==value['combined_commit'] and proof['combined_tree']==value['combined_tree']
        and proof['production_20k_allowed'] is False and proof['full_runtime_status']=='PENDING'
        and proof['maximum_optimizer_updates']==20,'Explicit bounded candidate profile admission required')
    class Reader:
        read_bound=staticmethod(read_qa_reference)
    require(set(proof['actual_QA'])=={'combined_checker','native_CPU25','native_real_reader1','storage_v2_QA'},
        'All actual checker/native/reader/v2 QA components required')
    for name,row in proof['actual_QA'].items():
        evidence_graph.terminal(Reader(),row['actual_terminal'])
        raw=read_qa_reference(row['raw_result'])
        require(row['source_before_sha256']==row['source_after_sha256'] and raw['status']=='PASS',
            'Candidate QA actual result/source changed: '+name)
        if name!='storage_v2_QA':
            expected={item['relative_path']:item['sha256'] for item in value['files']}
            require(row['runtime_source_bindings'] and all(expected.get(item['relative_path'])==item['sha256']
                for item in row['runtime_source_bindings']),'Candidate QA source leaves differ from immutable runtime: '+name)
        else:
            pins=read_qa_reference(row['package_source_manifest'])
            for item in pins['files']:
                require(sha(Path(__file__).parent/item['path'])==item['sha256'],'Actual v2 package differs from its QA source snapshot')
    require(proof['actual_QA']['native_CPU25']['passed']==25
        and proof['actual_QA']['native_real_reader1']['passed']==1,'Actual Native25/realreader1 population differs')
    return proof


def read_contract(path,*,metadata_only=False,allow_candidate_profile=False):
    value=json.loads(Path(path).read_text(encoding='utf-8'))
    require(value['schema']=='native_S_single_combined_runtime_v2','Exact combined runtime contract required')
    candidate=value['status']=='CANDIDATE_PROFILE_ONLY'
    require(value['status']=='PUBLISHED_IMMUTABLE_RUNTIME' or (candidate and allow_candidate_profile) or
        (metadata_only and value['status'] in ('PREPUBLICATION_METADATA_ONLY','CANDIDATE_PROFILE_ONLY')),
        'Combined commit/tree/publication pin missing; no production admission')
    root=Path(value['runtime_root'])
    require(root.is_absolute() and '..' not in root.parts,'Absolute immutable runtime root required')
    for row in value['files']:
        target=root/row['relative_path']
        require(target.is_file() and not target.is_symlink() and target.stat().st_size==row['bytes']
            and sha(target)==row['sha256'],'Combined runtime source differs: '+str(target))
    if not metadata_only:
        ref=value['publication_receipt']; require(sha(ref['path'])==ref['sha256'],'Public raw receipt differs')
        publication=json.loads(Path(ref['path']).read_text(encoding='utf-8'))
        require(publication['schema']=='model_v3_exact_tree_publication_receipt_v1'
            and publication['local_code_sha']==value['combined_commit'] and publication['tree_sha']==value['combined_tree']
            and publication['github_commit_sha']==value['public_commit']
            and publication['exact_tree_verified'] is True and publication['published_head_readback_verified'] is True,
            'Actual combined/public exact-tree publication proof differs')
        if candidate:
            require(value['production_20k_allowed'] is False,'Candidate contract cannot authorize20k')
            verify_candidate_profile(value)
            return value
        require(value['production_20k_allowed'] is True,'Full production contract must explicitly allow20k')
        closure=value.get('full_runtime_verification')
        require(isinstance(closure,dict) and sha(closure['path'])==closure['sha256'],
            'Actual full combined-runtime verification required; candidate publication is not full PASS')
        verified=json.loads(Path(closure['path']).read_text())
        require(verified['schema']=='native_S_full_runtime_verification_v2' and verified['status']=='FULL_RUNTIME_VERIFIED'
            and verified['combined_commit']==value['combined_commit'] and verified['combined_tree']==value['combined_tree'],
            'Full runtime verification identity/status differs')
        import evidence_graph
        class Reader:
            def read_bound(self,reference):
                require(sha(reference['path'])==reference['sha256'] and Path(reference['path']).stat().st_size==reference['bytes'],
                    'Raw full-runtime evidence bytes differ')
                return json.loads(Path(reference['path']).read_text())
        reader=Reader()
        require(verified['full_suite_parts'] and verified['checker'],'Actual full-suite parts/checker closure required')
        for part in [*verified['full_suite_parts'],verified['checker']]:
            evidence_graph.terminal(reader,part['actual_terminal'])
            require(part['source_before_sha256']==part['source_after_sha256'], 'Runtime source bytes changed during validation')
            require(sha(part['raw_result']['path'])==part['raw_result']['sha256'],'Actual checker/pytest result bytes differ')
        require(verified['failed']==0 and verified['passed']>0 and verified['collected']==verified['passed']+verified['skipped'],
            'Full runtime pytest population incomplete/failed')
    return value


def expected_path(name,root):
    if name=='phychem_mfm' or name.startswith('phychem_mfm.'):
        stem=root/'current'/Path(*name.split('.'))
        return stem/'__init__.py' if (stem/'__init__.py').is_file() else stem.with_suffix('.py')
    if name in TOOLS:
        base=root/'workflows/sprime_s/scripts' if name in ('s_loader_recovery_v1','s_loader_recovery_v2','s_native_adapter_v1','s_native_adapter_v2','s_model_memory_v1','prepare') else root/'tools/model_v3'
        return base/(name+'.py')
    return None


def audit_loaded(contract,*,classes=False):
    root=Path(contract['runtime_root']).absolute(); result=[]
    declared={str((root/row['relative_path']).absolute()) for row in contract['files']}
    for name,module in tuple(sys.modules.items()):
        require(not name.startswith('_native_s_root_storage_'),'Legacy split accounting namespace preloaded')
        expected=expected_path(name,root)
        if expected is None: continue
        actual=module.__dict__.get('__file__')
        require(isinstance(actual,str) and Path(actual).is_absolute() and Path(actual).absolute()==expected.absolute()
            and str(expected.absolute()) in declared,'Protected runtime module from another tree: '+name)
        origin=getattr(module.__dict__.get('__spec__'),'origin',None)
        require(origin is None or Path(origin).absolute()==expected.absolute(),'Protected module spec origin differs: '+name)
        package_path=module.__dict__.get('__path__')
        if package_path is not None:
            require(list(map(lambda p:str(Path(p).absolute()),package_path))==[str(expected.parent.absolute())],
                'Protected package path contains another tree: '+name)
        for key in ('REPO','REPOSITORY'):
            if key in module.__dict__: require(Path(module.__dict__[key]).absolute()==root,'Protected '+key+' points to another tree: '+name)
        result.append(dict(module=name,file=str(expected),package_path=None if package_path is None else list(package_path)))
    relationships=[]
    if classes:
        get=lambda name:sys.modules[name]
        native=get('phychem_mfm.phase1.v3_native_s_precision')
        data=get('phychem_mfm.phase1.v3_native_s_precision_data')
        trainer=get('phychem_mfm.phase1.v3_trainer')
        model=get('phychem_mfm.model.v3_multiview')
        performance=get('phychem_mfm.model.v3_performance')
        checks=(('native.ExistingNativeSInputs',native.ExistingNativeSInputs,data.ExistingNativeSInputs),
            ('data.PreparedV3Batch',data.PreparedV3Batch,trainer.PreparedV3Batch),
            ('native.V3StepTrainer',native.V3StepTrainer,trainer.V3StepTrainer),
            ('native.V3MultiViewModel',native.V3MultiViewModel,model.V3MultiViewModel),
            ('trainer.V3MultiViewModel',trainer.V3MultiViewModel,model.V3MultiViewModel),
            ('native.PerformanceOptions',native.PerformanceOptions,performance.PerformanceOptions))
        for name,actual,expected in checks:
            require(actual is expected,'Canonical runtime class identity differs: '+name)
            relationships.append(name)
        for module,names in ((native,('NativeSPrecisionPlan','NativeSPrecisionExperiment')),
                (data,('ExistingNativeSInputs',)),(trainer,('PreparedV3Batch','V3StepTrainer')),
                (model,('V3MultiViewModel',)),(performance,('PerformanceOptions',))):
            for name in names:
                cls=getattr(module,name)
                require(cls.__module__==module.__name__ and Path(inspect.getsourcefile(cls)).absolute()==Path(module.__file__).absolute(),
                    'Canonical class definition origin differs: '+name)
        for module_name,function_name in (('run_native_s_precision','collect_native_sources'),('run_precision_experiment','collect_sources')):
            fn=getattr(get(module_name),function_name)
            require(fn.__module__==module_name and Path(inspect.getsourcefile(fn)).absolute()==expected_path(module_name,root),
                'Source collector function origin differs: '+module_name)
            require(fn.__globals__ is get(module_name).__dict__ and Path(fn.__globals__['REPO']).absolute()==root,
                'Source collector globals belong to another runtime')
    return dict(status='ORIGIN_METADATA_VERIFIED',combined_commit=contract['combined_commit'],combined_tree=contract['combined_tree'],
        modules=sorted(result,key=lambda row:row['module']),class_relationships=relationships,
        data_inputs_constructed=False,CUDA_or_training_acceptance=False)


def configure_paths(contract):
    audit_loaded(contract)
    root=Path(contract['runtime_root'])
    # sys.path may be configured before import; protected __path__ and loaded
    # modules are never changed, cleared, or silently replaced.
    sys.path[:0]=[str(root/'current'),str(root/'tools/model_v3'),str(root/'workflows/sprime_s/scripts')]


def import_runtime(contract):
    configure_paths(contract)
    for name in ('phychem_mfm.phase1.v3_long_run_storage','phychem_mfm.phase1.v3_native_s_precision',
        'phychem_mfm.phase1.v3_native_s_precision_data','run_native_s_precision','run_precision_experiment',
        'a_execution_runtime','profile_s_baseline','runtime_monitor','private_runtime_storage'):
        importlib.import_module(name)
    result=audit_loaded(contract,classes=True)
    return sys.modules['phychem_mfm.phase1.v3_long_run_storage'],result
