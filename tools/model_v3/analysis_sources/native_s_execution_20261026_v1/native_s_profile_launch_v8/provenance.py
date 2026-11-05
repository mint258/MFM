"""Derive candidate-only contracts from real Root observations, never boolean QA."""
from __future__ import annotations
from pathlib import Path
import json
import sys
from common import *

def publication_projection(raw,raw_ref):
    require(raw['schema']=='model_v3_Root_exact_tree_publication_receipt_v1'
        and raw['repository']=='mint258/MFM' and raw['branch']=='model-v3'
        and raw['local_code_sha']==CODE and raw['tree_sha']==TREE and raw['public_commit_sha']==PUBLIC,
        'Known raw combined/publication identity required')
    require(raw['actual_readback']==dict(model_v3=PUBLIC,main='037546cd7f07b32dbb46bc21a69109dfd273f8da')
        and raw['scientific_acceptance'] is False and raw['formal_pretraining_authorized'] is False,
        'Actual candidate readback/scope differs')
    require(raw['source_files'] and all(len(row['sha256'])==64 and row['bytes']>0 for row in raw['source_files']),
        'Raw publication lacks actual source graph')
    return dict(schema='model_v3_exact_tree_publication_receipt_v1',
        local_code_sha=CODE,github_commit_sha=PUBLIC,tree_sha=TREE,
        exact_tree_verified=True,published_head_readback_verified=True,
        projection_kind='model_owned_projection_of_known_Root_raw_receipt',raw_provenance=raw_ref,
        full_Root_regression=raw['full_root_regression'],production_20k_allowed=False)

def verify_qa_result(value,expected):
    require(value['returncode']==0 and value['sources_unchanged'] is True,'QA child failed/source unstable')
    before=value['source_hashes_before']; after=value['source_hashes_after']
    require(before and before==after,'QA source set changed')
    counts=value['counts']
    require(counts==dict(tests=expected,failures=0,errors=0,skipped=0),'Exact no-skip QA count required')
    return before

def source_leaves(before,files):
    expected={r['relative_path']:r for r in files}; leaves={}
    for source,sha in before.items():
        for prefix in ('/current/','/tools/','/workflows/'):
            if prefix not in source: continue
            relative=prefix.strip('/')+'/'+source.split(prefix,1)[1]
            if relative in expected:
                require(expected[relative]['sha256']==sha,'QA leaf differs from combined immutable source: '+relative)
                leaves[relative]=sha
            break
    require(leaves,'No source overlap with combined runtime')
    return [dict(relative_path=p,sha256=sha) for p,sha in sorted(leaves.items())]

def accounting_projection(raw,job,root):
    require_C0(raw,job)
    ref=write(root/f'raw_sacct_{job}.json',raw)
    return write(root/f'terminal_{job}.json',dict(schema='native_S_actual_terminal_projection_v2',
        job_id=str(job),status='COMPLETED',exit_code=0,raw_sacct=ref))

def prepare_metadata(output,git):
    output=Path(output); require(not output.exists(),'Fresh metadata contract required')
    verify_package(V2,V2_PIN)
    machine=read(N/'native_s_combined_immutable_runtime_v1.json')
    require((machine['code_sha'],machine['tree_sha'],machine['runtime_root'])==(CODE,TREE,str(RUNTIME)),
        'Immutable runtime machine frame differs')
    row=actual([PYTHON,'-B',V2/'prepare_runtime_contract.py','--combined-record',
        N/'native_s_combined_immutable_runtime_v1.json','--git',git,'--metadata-only','--output',output],
        timeout=120,env=runtime_environment(cpu=True))
    return read(output),row

def build_candidate(root,*,git,v2_job,v2_result,v2_supervisor):
    """Login-only actual sacct; worker subsequently reuses these hash-bound rows."""
    root_identity(); root=Path(root); require(not root.exists(),'Fresh candidate evidence root required')
    root.mkdir(mode=0o700,parents=True)
    metadata,_=prepare_metadata(root/'metadata_contract.json',git)
    pub_raw_ref=binding(N/'native_integration_public_receipt_v1.json')
    pub_raw=read_ref(pub_raw_ref)
    publication=publication_projection(pub_raw,pub_raw_ref)
    published={x['path']:x for x in pub_raw['source_files']}
    for row in metadata['files']:
        if row['relative_path'] in published:
            require(row['sha256']==published[row['relative_path']]['sha256'],
                'Raw publication leaf differs from clean immutable tree')
    pub=write(root/'publication_projection.json',publication)
    qa={}
    specs=[('native_CPU25','4521103',OLD/'frozen_units_4521103/native_s_core_cli.json',
        OLD/'frozen_units_supervisor_4521103.json',25),
        ('native_real_reader1','4521104',OLD/'frozen_units_4521104/native_s_real_reader.json',
        OLD/'frozen_units_supervisor_4521104.json',1),
        ('storage_v2_QA',str(v2_job),Path(v2_result),Path(v2_supervisor),82)]
    for name,job,result_path,supervisor_path,count in specs:
        raw=actual(['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,State,ExitCode'])
        terminal=accounting_projection(raw,job,root)
        supervisor=read(supervisor_path)
        require(str(supervisor['job_id'])==job and supervisor['status']=='COMPLETED'
            and supervisor['exit_code']==0 and supervisor['first_failure'] is None,
            'QA actual parent/supervisor not completed')
        value=read(result_path); before=verify_qa_result(value,count)
        receipt=write(root/(name+'_result_projection.json'),dict(status='PASS',
            derivation='actual_source_bound_frozen_units_counts_and_real_C0',actual_result=binding(result_path),
            actual_supervisor=binding(supervisor_path),source_before_sha256=digest(before),
            source_after_sha256=digest(value['source_hashes_after']),passed=count))
        item=dict(actual_terminal=terminal,raw_result=receipt,source_before_sha256=digest(before),
            source_after_sha256=digest(before),passed=count)
        if name=='storage_v2_QA':
            pins_ref,pins=verify_package(V2,V2_PIN)
            for row in pins['files']:
                require(before.get(str(V2/row['path']))==row['sha256'],'Actual v2 QA did not bind all frozen source leaves')
            require(before.get(str(V2/'source_pins.json'))==pins_ref['sha256'],'Actual v2 manifest not bound')
            item['package_source_manifest']=pins_ref
            repair=N/'native_s_storage_v2_test_revision_v1'
            repair_ref,repair_pins=verify_package(repair)
            require(before.get(str(repair/'source_pins.json'))==repair_ref['sha256'] and
                all(before.get(str(repair/row['path']))==row['sha256'] for row in repair_pins['files']),
                'Actual revised82 QA did not bind the fixture repair package')
            require(all(str(repair/name) in value['argv'] for name in ('test_native_s_storage.py','test_root_coverage.py')),
                'Actual revised82 QA did not execute the two repaired tests')
            item['fixture_revision_source_manifest']=repair_ref
        else:
            import native_qa_scope
            scoped=native_qa_scope.audit(before,metadata,raw_result=binding(result_path),git=git)
            scope_ref=write(root/(name+'_historical_source_scope.json'),scoped)
            item['runtime_source_bindings']=scoped['runtime_source_bindings']
            item['historical_source_scope_audit']=scope_ref
            item['scope']='historical_Native_subgraph_QA_not_whole_combined_acceptance'
        qa[name]=item
    integrated=read(N/'root_native_s_precision_commit_v1.json')
    checker=read(OLD/'source_check_4521127.log')
    require(integrated['code_sha']==CODE and integrated['tree_sha']==TREE and
        integrated['all12_merged_raw_files_match_candidate'] is True and checker['status']=='PASS' and checker['errors']==[],
        'Actual integrated checker source closure differs')
    raw=actual(['sacct','-X','-n','-P','-j','4521127','--format=JobIDRaw,State,ExitCode'])
    terminal=accounting_projection(raw,'4521127',root)
    closure=write(root/'checker_result_projection.json',dict(status='PASS',
        actual_checker=binding(OLD/'source_check_4521127.log'),integrated_source_closure=binding(N/'root_native_s_precision_commit_v1.json'),
        derivation='Root_machine_merge_raw_leaf_equality_and_original_PASS_checker'))
    checker_leaf=qa['native_CPU25']['runtime_source_bindings']
    observed={row['relative_path']:row['sha256'] for row in metadata['files']}
    after_leaf=[dict(relative_path=row['relative_path'],sha256=observed[row['relative_path']]) for row in checker_leaf]
    qa['combined_checker']=dict(actual_terminal=terminal,raw_result=closure,
        source_before_sha256=digest(checker_leaf),source_after_sha256=digest(after_leaf),runtime_source_bindings=checker_leaf,
        before_after_semantics='strict_Native_dependency_subset_with_explicit_immutable_Git_context_vs_current_clean_combined; not_whole_historical_QA_or_checker_pre_post_timestamps')
    from full_runtime_bridge import build
    full=build(root,metadata,qa['combined_checker'])
    write(root/'profile_QA_preconditions.json',dict(schema='native_S_profile_QA_preconditions_v1',
        status='ALL_ACTUAL_QA_C0',combined_commit=CODE,combined_tree=TREE,
        production_20k_allowed=False,full_runtime_status='ACTUAL_PASS',actual_full_runtime_verification=full,
        maximum_optimizer_updates=20,actual_QA=qa))
    command=[PYTHON,'-B',V2/'prepare_runtime_contract.py','--combined-record',
        N/'native_s_combined_immutable_runtime_v1.json','--git',git,
        '--full-runtime-verification',full['path'],'--full-runtime-verification-sha256',full['sha256'],
        '--publication-receipt',pub['path'],'--publication-sha256',pub['sha256'],'--output',root/'candidate_contract.json']
    observation=actual(command,env=runtime_environment(cpu=True),timeout=120)
    return write(root/'CANDIDATE_READY.json',dict(schema='native_S_launch_candidate_ready_v1',
        status='PROFILE_ONLY_RUNTIME_READY',contract=binding(root/'candidate_contract.json'),actual_preparation=observation,
        production_20k_allowed=False,full_Root_regression='ACTUAL_PASS',actual_full_runtime_verification=full,
        runtime_contract_flag_semantics='runtime_gate_passed; complete_science20k_still_HOLD_until_all_profile_certificates'))
