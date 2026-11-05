"""Conservative source-only Native QA dependency admission.

Old broad repository snapshots stay intact. They are not relabelled as the
combined runtime. All local static imports (including imports inside functions)
are followed, plus explicit Native dynamic loader entries and frozen configs.
No project module, data, target, checkpoint or third-party code is executed.
"""
from __future__ import annotations
import ast
import importlib.util
import subprocess
from common import *

PIN_PATH='docs/model_v3/native_s_precision_source_pins_v1.json'
PIN_SHA='4276bcf0b612a41bfc8dcce8aea10f83e3b401c6fb9e92653d511dfc3656a351'
HISTORICAL_ROOT=PROJECT/'MFM_model_v3_native_s_precision'
_GIT_CONTEXT_CACHE={}
NON_NATIVE_CHANGE={
    'current/phychem_mfm/phase1/v3_decision_evidence.py':dict(
        historical='b52ce1ce9c989004898d6c70793a2c087d7fd48198789add1ab6251c57e7bcb6',
        combined='a94241454c16f9efd200588a47b0200a3ba01138e015dc82251b51102c28ba5e',
        use='panel/registered_seed_SD_evidence_selection; added_reject_engineering_configuration; not_Native_training_or_reader')}
DYNAMIC_LOCAL_ENTRIES=(
    'tools/model_v3/run_native_s_precision.py','tools/model_v3/run_precision_experiment.py',
    'tools/model_v3/s_input_stream.py','tools/model_v3/native_runtime_bindings.py',
    'tools/model_v3/profile_s_baseline.py','tools/model_v3/a_execution_runtime.py',
    'tools/model_v3/runtime_monitor.py','tools/model_v3/private_runtime_storage.py','tools/model_v3/run_supervised.py',
    'workflows/sprime_s/scripts/s_native_adapter_v1.py','workflows/sprime_s/scripts/s_native_adapter_v2.py',
    'workflows/sprime_s/scripts/s_loader_recovery_v1.py','workflows/sprime_s/scripts/s_loader_recovery_v2.py',
    'workflows/sprime_s/scripts/s_model_memory_v1.py','workflows/sprime_s/scripts/prepare.py')
DATA_TASK_CONFIGS=('workflows/sprime_s/formal_s/B1_seed0_v2.json','workflows/s_denoise/configs/A4_seed0_v3.json',
    'current/configs/model_v3/performance/b00_fp32.json','current/configs/model_v3/performance/b01_bf16.json',
    'current/configs/model_v3/performance/b_existing_native_s_plan_v1.json')

def source_name(relative):
    value=Path(relative)
    if value.parts[:2]==('current','phychem_mfm'):
        parts=list(value.with_suffix('').parts[1:])
        if parts[-1]=='__init__':parts.pop()
        return '.'.join(parts)
    return value.stem

def legacy_policy(root):
    policy=read(HERE/'legacy_import_guard_policy.json')
    history=read_ref(policy['historical_actual_unit']);key=policy['historical_source_key']
    require(history['sources_unchanged'] is True and history['source_hashes_before'][key]==
        history['source_hashes_after'][key]==policy['owner_sha256'] and
        binding(Path(root)/policy['owner_relative_path'])['sha256']==policy['owner_sha256'],
        'Legacy optional owner differs from actual historical145 capture')
    return policy

def guarded_legacy_import(root,relative,node,base,parents,policy):
    if policy is None or relative!=policy['owner_relative_path']:return None
    options=[row for row in policy['imports'] if row['absolute_name']==base]
    if len(options)!=1:return None
    option=options[0];owner=binding(Path(root)/relative)
    if owner['sha256']!=policy['owner_sha256']:return None
    if (node.level!=option['level'] or node.module!=option['relative_module'] or
        [x.name for x in node.names]!=[option['symbol']] or any(x.asname for x in node.names)):return None
    guard=parents.get(node)
    if not isinstance(guard,ast.Try) or guard.body!=[node] or len(guard.handlers)!=1:return None
    handler=guard.handlers[0]
    if not isinstance(handler.type,ast.Name) or handler.type.id!='ImportError' or len(handler.body)!=1:return None
    fallback=handler.body[0]
    if (not isinstance(fallback,ast.ImportFrom) or fallback.level!=0 or fallback.module!=option['fallback_module'] or
        [x.name for x in fallback.names]!=[option['symbol']] or any(x.asname for x in fallback.names)):return None
    function=parents.get(guard)
    while function is not None and not isinstance(function,(ast.FunctionDef,ast.AsyncFunctionDef)):
        function=parents.get(function)
    if function is None or function.name!=policy['function_name']:return None
    return dict(absolute_name=base,owner=owner,function=function.name,import_line=node.lineno,
        try_line=guard.lineno,except_line=handler.lineno,fallback_module=fallback.module,
        guard='exact_except_ImportError',use='legacy_create_dataset_CLI_compatibility_not_Native_reader')

def closure(root,seeds,*,optional_policy=None):
    """Overapproximate all local import branches; an unexpected change rejects."""
    root=Path(root);pending=list(seeds);seen=set();edges=[];external=set();dynamic=[];optional=[]
    if optional_policy is None and root==RUNTIME:optional_policy=legacy_policy(root)
    bases=(root/'current',root/'current/tests',root/'tools/model_v3',root/'workflows/sprime_s/scripts')
    def locate(name):
        target=Path(*name.split('.'))
        for base in bases:
            for path in (base/target.with_suffix('.py'),base/target/'__init__.py'):
                if path.is_file():return path.relative_to(root).as_posix()
        return None
    def add(name,source,line,*,required=False):
        found=locate(name)
        if found is None:
            require(not required,'Unresolved required local module: '+name)
            external.add(name);return
        edges.append(dict(source=source,module=name,target=found,line=line));pending.append(found)
        parts=name.split('.')
        for count in range(1,len(parts)):
            initializer=locate('.'.join(parts[:count]))
            if initializer is not None:pending.append(initializer)
    while pending:
        relative=pending.pop()
        if relative in seen:continue
        path=root/relative;binding(path);seen.add(relative)
        if path.suffix!='.py':continue
        tree=ast.parse(path.read_bytes(),filename=relative);name=source_name(relative)
        parents={child:owner for owner in ast.walk(tree) for child in ast.iter_child_nodes(owner)}
        package=name if path.name=='__init__.py' else name.rpartition('.')[0]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                for alias in node.names:add(alias.name,relative,node.lineno,required=alias.name.startswith('phychem_mfm'))
            elif isinstance(node,ast.ImportFrom):
                if node.level:
                    require(package,'Bare workflow/tools cannot have unresolved relative import')
                    base=importlib.util.resolve_name('.'*node.level+(node.module or ''),package)
                else:base=node.module or ''
                if base:
                    guarded=guarded_legacy_import(root,relative,node,base,parents,optional_policy) if locate(base) is None else None
                    if guarded is not None:
                        optional.append(guarded);external.add(base);continue
                    add(base,relative,node.lineno,required=base.startswith('phychem_mfm'))
                for alias in node.names:
                    if alias.name!='*' and base:
                        child=base+'.'+alias.name
                        if locate(child) is not None:add(child,relative,node.lineno)
            elif isinstance(node,ast.Call):
                function=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
                if function in ('runtime_module','import_module','spec_from_file_location'):
                    literal=node.args[0].value if node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str) else None
                    dynamic.append(dict(source=relative,line=node.lineno,function=function,literal=literal))
                    if literal and function in ('runtime_module','import_module') and locate(literal) is not None:
                        add(literal,relative,node.lineno)
    return dict(files=sorted(seen),edges=edges,dynamic_import_sites=dynamic,optional_legacy_guard_imports=optional,
        third_party_or_unresolved_nonlocal_import_names=sorted(external),
        limitations='source_only_conservative_local_import_graph; external_original_native_transport_is_revalidated_by_unchanged_manifest_snapshot_loader_not_inferred_from_AST')

def historical_relative(before):
    prefix=str(HISTORICAL_ROOT)+'/'
    require(before and all(path.startswith(prefix) for path in before),'Historical QA source origin differs')
    return {path[len(prefix):]:sha for path,sha in before.items()}

def reviewed_difference(relative,old_sha,new_sha,required):
    allowed=NON_NATIVE_CHANGE.get(relative)
    require(relative not in required and allowed is not None and allowed['historical']==old_sha
        and allowed['combined']==new_sha,'Unreviewed or Native-reachable historical mismatch: '+relative)
    return dict(relative_path=relative,**allowed)

def git_context(relative,expected,*,git,candidate):
    """Immutable candidate-version evidence, not a retroactive unit snapshot."""
    key=(str(git),candidate,relative,expected)
    if key in _GIT_CONTEXT_CACHE:return _GIT_CONTEXT_CACHE[key]
    argv=[str(git),'-C',str(RUNTIME),'show',candidate+':'+relative]
    result=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    require(result.returncode==0 and 0<len(result.stdout)<=2<<20 and hashlib.sha256(result.stdout).hexdigest()==expected,
        'Native dependency historical Git version absent/changed; QA must be repeated: '+relative)
    value=dict(argv=argv,returncode=result.returncode,stdout_bytes=len(result.stdout),stdout_sha256=expected,
        stderr=result.stderr.decode('utf-8'),provenance_kind='immutable_candidate_Git_blob_context_not_actual_old_unit_hash_capture')
    _GIT_CONTEXT_CACHE[key]=value
    return value

def missing_legacy_versions(graph,*,git,candidate):
    observations=[]
    for name in sorted({row['absolute_name'] for row in graph['optional_legacy_guard_imports']}):
        relative='current/'+name.replace('.','/')+'.py'
        require(not (RUNTIME/relative).exists(),'Optional legacy target unexpectedly exists')
        for commit in (candidate,CODE):
            argv=[str(git),'-C',str(RUNTIME),'cat-file','-e',commit+':'+relative]
            result=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
            message=result.stderr.decode('utf-8')
            require(result.returncode!=0 and 'does not exist' in message and relative in message,
                'Historical optional absence not proved by actual Git response')
            observations.append(dict(argv=argv,returncode=result.returncode,stdout_bytes=len(result.stdout),
                stderr=message,expected_absence=True,scope='only_exact_ImportError_legacy_target'))
    return observations

def audit(before,metadata,*,raw_result,git):
    root=Path(metadata['runtime_root']);require(root==RUNTIME,'One immutable combined root required')
    original=historical_relative(before)
    pin_ref=binding(root/PIN_PATH);require(pin_ref['sha256']==PIN_SHA,'Original Native11 manifest differs')
    native_pin=read_ref(pin_ref)
    declared=[row['path'] for row in native_pin['new_files']]+[PIN_PATH]
    require(len(declared)==11 and len(set(declared))==11,'Exact original10+manifest Native11 inventory required')
    required_seed=set(declared)|set(DYNAMIC_LOCAL_ENTRIES)|set(DATA_TASK_CONFIGS)
    graph=closure(root,sorted(required_seed))
    required=graph['files'];required_refs=[];unlisted_git=[]
    context_ref=binding(N/'root_native_s_precision_commit_v1.json');context=read_ref(context_ref)
    candidate=context['candidate_sha']
    require(context['code_sha']==CODE and re.fullmatch('[0-9a-f]{40}',candidate),'Actual historical candidate context required')
    optional_absence=missing_legacy_versions(graph,git=git,candidate=candidate)
    for relative in required:
        reference=binding(root/relative)
        if relative in original:
            require(original[relative]==reference['sha256'],
                'Required Native dependency changed; actual Native/reader QA must be repeated: '+relative)
        else:
            unlisted_git.append(dict(relative_path=relative,current_reference=reference,
                actual_historical_unit_hash_capture=False,
                immutable_version_context=git_context(relative,reference['sha256'],git=git,candidate=candidate)))
        required_refs.append(dict(relative_path=relative,bytes=reference['bytes'],sha256=reference['sha256']))
    expected={row['relative_path']:row for row in metadata['files']}
    same=[];different=[]
    for relative,old_sha in sorted(original.items()):
        if relative not in expected:continue
        now=expected[relative]['sha256']
        if old_sha==now:same.append(relative)
        else:
            different.append(reviewed_difference(relative,old_sha,now,required))
    require(len(different)==1 and different[0]['relative_path'] in NON_NATIVE_CHANGE,
        'This narrow revision requires exactly the reviewed single metadata-only change')
    runtime_refs=[row for row in required_refs if row['relative_path'] in expected]
    require(runtime_refs,'No Native runtime subset bound')
    for row in runtime_refs:require(expected[row['relative_path']]['sha256']==row['sha256'],'Combined contract leaf differs')
    return dict(schema='native_S_historical_QA_scope_audit_v3',status='NATIVE_DEPENDENCY_SUBGRAPH_IDENTICAL',
        historical_result=raw_result,historical_root=str(HISTORICAL_ROOT),combined_root=str(root),
        historical_snapshot_file_count=len(original),historical_complete_source_inventory=original,
        original_Native11_manifest=pin_ref,Native11_paths=declared,required_source_refs=required_refs,
        required_actual_unit_snapshot_paths=sorted(set(required)&set(original)),
        required_not_in_actual_old_unit_snapshot=unlisted_git,historical_candidate_context=context_ref,
        unlisted_scope='strict_same_immutable_candidate_Git_blob_version_only; current_native_unit_helpers_covered_by_independent_combined2592_source_and_test_inventory; not_retroactive_old_unit_measurement',
        runtime_source_bindings=[dict(relative_path=row['relative_path'],sha256=row['sha256']) for row in runtime_refs],
        common_same=same,common_different=different,
        historical_outside_runtime_contract=sorted(set(original)-set(expected)),
        combined_added_not_historically_tested=sorted(set(expected)-set(original)),
        source_import_graph=graph,historical_QA_scope='Native_dependency_subgraph_and_real_reader_only_not_whole_combined',
        optional_legacy_absence_actual_git=optional_absence,optional_guard_policy=binding(HERE/'legacy_import_guard_policy.json'),
        combined_actual_full_regression_reference=binding(OLD/'native_s_precision_identity_v4_retry1_complete.json'),
        combined_all179_acceptance='independent_complete2592_full_source_before_after_bridge_required',
        data_transport_protection='unchanged_full_corpus_loader_s_adapters_native_runtime_bindings_and_original_manifest_snapshot_SHA_guards; changed_decoder_task_geometry_or_reader_source_rejects',
        scientific_acceptance=False,production_20k_allowed=False)


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--metadata-contract',type=Path,required=True)
    p.add_argument('--git',type=Path,default=OLD/'cpu_git_tools_v1/bin/git')
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    root_identity();metadata=read(args.metadata_contract)
    require(metadata['combined_commit']==CODE and metadata['combined_tree']==TREE,'Actual immutable metadata contract required')
    reports={}
    for name,job,stem in (('native_CPU25','4521103','native_s_core_cli'),
        ('native_real_reader1','4521104','native_s_real_reader')):
        path=OLD/f'frozen_units_{job}'/(stem+'.json');value=read(path)
        require(value['returncode']==0 and value['sources_unchanged'] is True and
            value['source_hashes_before']==value['source_hashes_after'],'Original QA changed/failed')
        reports[name]=audit(value['source_hashes_before'],metadata,raw_result=binding(path),git=args.git)
    ref=write(args.output,dict(schema='native_S_historical_dependency_scope_review_v3',
        status='SOURCE_METADATA_REVIEW_ONLY_NOT_NEW_QA',metadata_contract=binding(args.metadata_contract),reports=reports,
        no_project_import_data_model_reservation_or_Slurm=True,scientific_acceptance=False,production_20k_allowed=False))
    print(json.dumps(ref),flush=True)

if __name__=='__main__':main()
