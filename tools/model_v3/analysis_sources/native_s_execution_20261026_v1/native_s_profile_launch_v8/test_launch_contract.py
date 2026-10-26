"""CPU metadata/operational mechanism tests; never evidence of native GPU work."""
from copy import deepcopy
import ast
import json
from pathlib import Path
import time
from types import SimpleNamespace
import pytest
import common
import gpu_worker
import operational
import provenance
import resources

def publication():
    return dict(schema='model_v3_Root_exact_tree_publication_receipt_v1',repository='mint258/MFM',branch='model-v3',
        local_code_sha=common.CODE,tree_sha=common.TREE,public_commit_sha=common.PUBLIC,
        actual_readback=dict(model_v3=common.PUBLIC,main='037546cd7f07b32dbb46bc21a69109dfd273f8da'),
        scientific_acceptance=False,formal_pretraining_authorized=False,
        source_files=[dict(path='source.py',sha256='a'*64,bytes=1)],full_root_regression='PENDING')

def qa():
    return dict(returncode=0,sources_unchanged=True,source_hashes_before={'actual_source':'a'*64},
        source_hashes_after={'actual_source':'a'*64},counts=dict(tests=82,failures=0,errors=0,skipped=0))

def test_known_raw_publication_projection_retains_raw_ref_and_pending_scope():
    raw=publication();ref=dict(path='/metadata/raw.json',bytes=1,sha256='b'*64)
    value=provenance.publication_projection(raw,ref)
    assert value['raw_provenance']==ref and value['github_commit_sha']==common.PUBLIC
    assert value['full_Root_regression']=='PENDING' and value['production_20k_allowed'] is False
    assert raw==publication()

@pytest.mark.parametrize('field,value',[('schema','unknown'),('tree_sha','0'*40),('public_commit_sha','1'*40),
    ('scientific_acceptance',True),('formal_pretraining_authorized',True),('source_files',[])])
def test_raw_publication_wrong_scope_or_identity_rejected(field,value):
    raw=publication();raw[field]=value
    with pytest.raises((ValueError,KeyError)):provenance.publication_projection(raw,{'sha256':'a'*64})

def test_exact_real_QA_count_and_source_equivalence_required():
    assert provenance.verify_qa_result(qa(),82)=={'actual_source':'a'*64}

@pytest.mark.parametrize('mutation',['returncode','unstable','source','count','skip','fail'])
def test_failed75_of82_or_skipped_or_changed_QA_is_not_admission(mutation):
    value=qa()
    if mutation=='returncode':value['returncode']=1
    elif mutation=='unstable':value['sources_unchanged']=False
    elif mutation=='source':value['source_hashes_after']['actual_source']='b'*64
    elif mutation=='count':value['counts']['tests']=75
    elif mutation=='skip':value['counts']['skipped']=1
    else:value['counts']['failures']=7
    with pytest.raises(ValueError):provenance.verify_qa_result(value,82)

@pytest.mark.parametrize('allocated',[False,True])
def test_max_requested_and_allocated_memory_and_single_allocation_charge(allocated):
    raw='CPUAlloc=16 CPUTot=64 RealMemory=128000 AllocMem=16000'
    row=resources.memory(raw,'1|other|R|20G|16\n',allocated=allocated)
    assert row['with_this_job_MiB']==str(20480+(0 if allocated else 32768))

@pytest.mark.parametrize('bad',['queue','allocated','unknown'])
def test_capacity85_percent_and_unknown_scheduler_memory_reject(bad):
    node='CPUAlloc=16 CPUTot=64 RealMemory=102000 AllocMem=16000';queue='1|other|R|54G|16\n'
    if bad=='allocated':node=node.replace('AllocMem=16000','AllocMem=55000');queue=''
    if bad=='unknown':queue='unparsed\n'
    with pytest.raises(ValueError):resources.memory(node,queue,allocated=False)

@pytest.mark.parametrize('stderr,allowed',[('Connection refused',True),('Unable to contact slurm controller',True),
    ('Permission denied',False),('Invalid argument',False)])
def test_backend_boundary_only_known_unavailable_can_reuse_Root_frame(stderr,allowed):
    assert resources.unavailable(dict(returncode=1,stderr=stderr)) is allowed

@pytest.mark.parametrize('precision',['fp32','bf16'])
def test_real_supervisor_parser_receives_no_unknown_observations_flag(precision):
    phase=common.N/'metadata_profile_fixture';submission=dict(path='/metadata/submission.json',sha256='a'*64)
    argv=gpu_worker.supervisor_command(phase,precision,submission,'/metadata/contract.json','123')
    boundary=argv.index('--')
    assert '--observations' not in argv[:boundary] and argv.count('--observations')==1
    assert argv[argv.index('--observations')+1]==str(phase/'job_123/management/supervisor.json.jsonl')
    assert argv[argv.index('--wall-seconds')+1]=='1100'
    assert argv[argv.index('--output-budget-bytes')+1]==str(2<<30)
    assert argv[argv.index('--private-storage-budget-bytes')+1]==str(2<<30)
    assert argv[argv.index('--rss-limit-bytes')+1]==str(28<<30)
    assert '--updates' in argv[boundary:] and argv[argv.index('--updates')+1]=='20'
    assert common.GPU in argv and '3d9b1cc0c580dacc9398a5570b0c2fff3e257618' in argv

def test_original_QA_source_leaves_match_combined_paths_without_basename_aliasing():
    files=[dict(relative_path='current/phychem_mfm/same.py',sha256='a'*64)]
    before={'/historical_tree/current/phychem_mfm/same.py':'a'*64}
    assert provenance.source_leaves(before,files)==[dict(relative_path='current/phychem_mfm/same.py',sha256='a'*64)]
    with pytest.raises(ValueError):provenance.source_leaves({'/foreign/current/other/same.py':'a'*64},files)
    with pytest.raises(ValueError):provenance.source_leaves({'/foreign/current/phychem_mfm/same.py':'b'*64},files)

@pytest.mark.parametrize('state,code',[('FAILED','1:0'),('COMPLETED','0:9'),('COMPLETED','1:0')])
def test_actual_raw_accounting_failure_cannot_become_C0(state,code):
    row=dict(returncode=0,argv=['sacct','-j','123','--format=JobIDRaw,State,ExitCode'],stdout=f'123|{state}|{code}\n')
    with pytest.raises(ValueError):common.require_C0(row,'123')

def test_full_raw_json_nonfinite_and_sha_tamper_rejected(tmp_path):
    path=tmp_path/'raw.json';ref=common.write(path,dict(actual='metadata'))
    path.write_text('{"not_original":1}\n')
    with pytest.raises(ValueError):common.read_ref(ref)
    path.write_text('{"value":NaN}\n')
    with pytest.raises(ValueError):common.read(path)

def test_whole_census_uses_exact_child_layout_and_unique_stdio(tmp_path):
    import runtime_monitor
    phase=tmp_path/'phase';job='123';control=phase/'control';management=phase/'job_123/management';child=phase/'job_123/child'
    for root in (control,management,child):root.mkdir(parents=True)
    common.write(control/'config.json',{'metadata_only':True})
    common.write(management/'guard.json',{'metadata_only':True})
    (child/'payload-fixture.txt').write_text('fixture')
    log=phase/'slurm.log';log.write_text('one actual file\n')
    result=operational.whole_census(phase,job,dict(stdout=str(log),stderr=str(log)),runtime_monitor)
    assert result['unique_stdio_bytes']==log.stat().st_size
    assert result['whole_bytes']==sum(result['directory_bytes'].values())+log.stat().st_size
    assert result['cap_bytes']==2<<30

def test_lineage3GiB_does_not_change_per_job2GiB_child_or_private():
    limits=operational.policy()
    assert limits['durable_bytes']==3<<30 and limits['segment_bytes']==2<<30
    assert common.OUTER==common.PRIVATE==2<<30 and common.CHILD==(2<<30)-(96<<20)
    assert limits['counts']['launch_attempts']==2 and limits['counts']['failed_attempts']==1

def test_generated_runner_is_parseable_and_preserves_native_API_and_300_second_pause():
    text=(Path(__file__).parent/'short_profile.py').read_text();ast.parse(text)
    assert 'wall_seconds=CHILD_WALL' in text and 'MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES=' not in text
    assert 'NativeSPrecisionExperiment' in text and 'ExistingNativeSInputs(seed=0)' in text
    assert 'pause_requested=lambda:profile_lifecycle.should_pause' in text
    assert "set(outcome['validation'])=={'0'}" in text
    assert 'future_state_bounds=' in text and 'Root_must_prove_from_actual_safe_CP_and_frozen_shapes' in text

def test_all_operational_Python_sources_parse_and_no_import_side_effects_dispatch():
    for path in Path(__file__).parent.glob('*.py'):ast.parse(path.read_text())
    assert '__main__' in (Path(__file__).parent/'operations.py').read_text()

def test_actual_uuid_normalization_and_foreign_process_rejection():
    gpu=common.GPU+', NVIDIA GeForce RTX 5090, 590.44.01, 32768, 32760\n'
    assert resources.selected_gpu(gpu,'')[0]==common.GPU
    assert common.normalized_uuid(common.GPU[4:])==common.GPU
    with pytest.raises(ValueError):resources.selected_gpu(gpu,common.GPU+', 123, foreign, 1\n')

@pytest.mark.parametrize('age',[-10,121])
def test_sealed_Root_frame_future_or_stale_is_not_live_admission(age):
    row=dict(started_unix=1000,completed_unix=1001)
    with pytest.raises(ValueError):common.fresh(row,now=1001+age)

def test_inline_pass_is_explicitly_pending_outer_and_not_independent_CPU_C0():
    from inline_qa import verdict
    counts=dict(tests=42,failures=0,errors=0,skipped=0)
    assert verdict(0,counts,{'source':'a'*64},{'source':'a'*64},42)=='CHILD_QA_PASS_PENDING_OUTER_TERMINAL'

@pytest.mark.parametrize('mutation',['returncode','failed','skipped','source'])
def test_inline_preflight_failure_forbids_model_without_creating_C0(mutation):
    from inline_qa import verdict
    counts=dict(tests=42,failures=0,errors=0,skipped=0);before={'source':'a'*64};after=dict(before);code=0
    if mutation=='returncode':code=1
    elif mutation=='failed':counts['failures']=1
    elif mutation=='skipped':counts['skipped']=1
    else:after['source']='b'*64
    with pytest.raises(ValueError):verdict(code,counts,before,after,42)

def operational_fixture(tmp_path,monkeypatch):
    import operations
    source=tmp_path/'source';source.mkdir()
    file=source/'tiny_source.py';file.write_text('# metadata fixture only\n')
    ref=common.binding(file)
    pins=dict(files=[dict(path=file.name,bytes=ref['bytes'],sha256=ref['sha256'])])
    manifest=common.write(source/'source_pins.json',pins)
    monkeypatch.setattr(operations,'HERE',source)
    result=operations.snapshot_operations(tmp_path/'snapshot',manifest,pins)
    return operations,result,manifest

def test_unpublished_operations_have_real_snapshot_and_no_fake_publication(tmp_path,monkeypatch):
    operations,reference,manifest=operational_fixture(tmp_path,monkeypatch)
    value=operations.verify_source_snapshot(reference,manifest)
    assert value['status']=='UNPUBLISHED_CANDIDATE' and value['published_operational_commit'] is None
    assert value['scientific_model_prereg_sha']==common.PUBLIC
    assert value['usable_scientific_result'] is False and value['production_20k_allowed'] is False
    assert len(value['files'])==2

def test_unpublished_snapshot_source_tamper_rejected(tmp_path,monkeypatch):
    operations,reference,manifest=operational_fixture(tmp_path,monkeypatch)
    (Path(reference['path']).parent/'tiny_source.py').write_text('# changed\n')
    with pytest.raises(ValueError):operations.verify_source_snapshot(reference,manifest)

@pytest.mark.parametrize('field,value',[('published_operational_commit','a'*40),
    ('scientific_model_prereg_sha','b'*40),('usable_scientific_result',True)])
def test_snapshot_cannot_be_renamed_published_or_replace_scientific_prereg(tmp_path,monkeypatch,field,value):
    operations,reference,manifest=operational_fixture(tmp_path,monkeypatch)
    changed=common.read_ref(reference);changed[field]=value
    Path(reference['path']).write_bytes(common.encoded(changed))
    with pytest.raises(ValueError):operations.verify_source_snapshot(common.binding(reference['path']),manifest)

def test_Native_import_closure_includes_nested_decoder_geometry_and_package_initializers(tmp_path):
    from native_qa_scope import closure
    package=tmp_path/'current/phychem_mfm';(package/'phase1').mkdir(parents=True);(package/'data').mkdir()
    for relative in ('__init__.py','phase1/__init__.py','data/__init__.py'):(package/relative).write_text('')
    (package/'phase1/reader.py').write_text('def open_reader():\n    from .decoder import decode\n')
    (package/'phase1/decoder.py').write_text('from ..data.geometry import preserve_order\n')
    (package/'data/geometry.py').write_text('def preserve_order(): return None\n')
    graph=closure(tmp_path,['current/phychem_mfm/phase1/reader.py'])
    assert set(graph['files'])=={'current/phychem_mfm/'+p for p in
        ('__init__.py','phase1/__init__.py','data/__init__.py','phase1/reader.py','phase1/decoder.py','data/geometry.py')}

def test_historical_source_root_cannot_be_implicitly_relabelled_combined():
    from native_qa_scope import historical_relative,HISTORICAL_ROOT
    assert historical_relative({str(HISTORICAL_ROOT)+'/reader.py':'a'*64})=={'reader.py':'a'*64}
    with pytest.raises(ValueError):historical_relative({'/another/tree/reader.py':'a'*64})

@pytest.mark.parametrize('mutation',['reachable','unknown','wrong_version'])
def test_nonNative_metadata_exception_cannot_hide_reader_or_unreviewed_change(mutation):
    from native_qa_scope import reviewed_difference,NON_NATIVE_CHANGE
    path=next(iter(NON_NATIVE_CHANGE));row=NON_NATIVE_CHANGE[path];old=row['historical'];new=row['combined'];required=[]
    if mutation=='reachable':required=[path]
    elif mutation=='unknown':path='current/phychem_mfm/phase1/decoder.py'
    else:new='0'*64
    with pytest.raises(ValueError):reviewed_difference(path,old,new,required)

def test_Native_import_closure_respects_UTF8_BOM_without_rewriting_raw_source(tmp_path):
    from native_qa_scope import closure
    package=tmp_path/'current/phychem_mfm';package.mkdir(parents=True)
    (package/'__init__.py').write_bytes(b'\xef\xbb\xbf')
    reader=package/'reader.py';reader.write_bytes(b'\xef\xbb\xbffrom .decoder import decode\n')
    (package/'decoder.py').write_text('def decode(): return None\n')
    before=common.binding(reader)
    graph=closure(tmp_path,['current/phychem_mfm/reader.py'])
    assert 'current/phychem_mfm/decoder.py' in graph['files']
    assert common.binding(reader)==before and reader.read_bytes().startswith(b'\xef\xbb\xbf')

def legacy_guard_fixture(tmp_path,*,modern=False):
    from native_qa_scope import closure
    package=tmp_path/'current/phychem_mfm';(package/'training').mkdir(parents=True)
    (package/'__init__.py').write_text('');(package/'training/__init__.py').write_text('')
    relative='current/phychem_mfm/training/degrade_molecules.py';owner=tmp_path/relative
    namespace='data' if modern else 'dataset'
    owner.write_text('def create_dataset(path):\n    try:\n        from ..'+namespace+
        '.dataset_lmdb import LmdbMoleculeDataset\n    except ImportError:\n        from '+namespace+
        '.dataset_lmdb import LmdbMoleculeDataset\n')
    policy=deepcopy(common.read(common.HERE/'legacy_import_guard_policy.json'))
    policy['owner_sha256']=common.binding(owner)['sha256']
    return closure,tmp_path,[relative],policy

def test_exact_old_ImportError_guard_is_recorded_as_optional_not_scientific_required(tmp_path):
    closure,root,seeds,policy=legacy_guard_fixture(tmp_path)
    result=closure(root,seeds,optional_policy=policy)
    assert len(result['optional_legacy_guard_imports'])==1
    record=result['optional_legacy_guard_imports'][0]
    assert record['absolute_name']=='phychem_mfm.dataset.dataset_lmdb'
    assert record['guard']=='exact_except_ImportError' and record['function']=='create_dataset'

def test_modern_decoder_is_still_required_even_when_same_owner_has_ImportError_handler(tmp_path):
    closure,root,seeds,policy=legacy_guard_fixture(tmp_path,modern=True)
    with pytest.raises(ValueError,match='Unresolved required local module'):
        closure(root,seeds,optional_policy=policy)

def test_actual1329_task_scratch_receipt_shape_enters_both_ops_and_coverage_without_claiming_live_inode():
    import root_coverage,native_s_storage
    proof=common.read(common.HERE/'coverage_ops_extension_provenance.json')
    actual=common.read_ref(proof['actual1329_private_receipt'])
    assert actual['schema']=='model_v3_private_storage_v1' and str(actual['job_id'])=='4521329'
    assert operational.private_domains(actual,job_id='4521329')==[
        dict(path='/tmp/mv3n_4521329',domain='node_local_ephemeral')]
    assert root_coverage.task_scratch_metadata(actual['roots'][0],job_id='4521329')=='/tmp/mv3n_4521329'
    assert native_s_storage.root_coverage is root_coverage
    source=root_coverage.ops_extension_source()
    assert Path(source['actual_file'])==common.HERE/'root_coverage.py' and source['prior82_covers_extension'] is False
    # The old /tmp root is already retired. This checks its real saved schema,
    # not a recreated UID/inode/mount or a fabricated live receipt.
