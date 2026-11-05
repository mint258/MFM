"""Metadata protobuf comparisons only; no init/API, GPU, model, corpus, or SDK read."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).parent))
import profile_sdk_tap as tap


@pytest.fixture(scope='module')
def reader():
    sources=json.loads((Path(__file__).parent/'dependencies.json').read_text())
    ref=sources['sources']['history_reader']; path=Path(ref['path'])
    import hashlib
    assert hashlib.sha256(path.read_bytes()).hexdigest()==ref['sha256'] and path.stat().st_size==ref['bytes']
    spec=importlib.util.spec_from_file_location('native_profile_unit_v7',path)
    module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module)
    return module


def saved():
    ref=lambda name:dict(path='/synthetic/metadata/'+name,bytes=1,sha256='a'*64)
    refs={name:ref(name) for name in ('sdk','mirror','configuration','summary')}
    profile=dict(schema='existing_native_S_storage_profile_result_v2',status='PROFILE_CHILD_COMPLETED_PENDING_OUTER_AND_NATIVE_SDK',
        purpose=tap.PURPOSE,observed_profile_updates=20,production_20k_allowed=False,scientific_acceptance=False,D5_authority=False,
        failure=None,cleanup_errors=[],native_SDK_verification='REQUIRED_INDEPENDENTLY',SDK_expectations=refs,
        precision='fp32',scope=tap.SCOPE,tracker_id='unitprof0',native_sources={'source.py':'b'*64},native_code_sha='c'*40,prereg_sha='d'*40)
    config=dict(purpose=tap.PURPOSE,callback=dict(seed=0,precision='fp32',scope=tap.SCOPE,sources=profile['native_sources'],
        code_sha=profile['native_code_sha'],prereg_sha=profile['prereg_sha']),
        Root_storage_binding={'scope':'fixture','array':[1,2.,False],'empty':{},'none':None},
        profile_runner_source={'path':'/synthetic/runner.py','sha256':'e'*64})
    rows=[{'step':0,'commit':True,'row':dict(log_cursor=0,event='VALIDATION',role='PRETRAIN_VAL',records=1024,
        optimizer_updates=0,samples_consumed=0,metrics={'loss':.25,'flag':False,'none':None})}]
    rows += [{'step':i,'commit':True,'row':dict(log_cursor=i,event='TRAIN',optimizer_updates=i,samples_consumed=i*32,
        loss=1./i,valid_counts={'field':32})} for i in range(1,21)]
    summary=tap.merged_summary(rows); summary['profile_v2']=dict(purpose=tap.PURPOSE,
        completed_requested_short_target=True,optimizer_updates=20,native_code_sha=profile['native_code_sha'],D5_authority=False)
    return profile,config,summary,rows,refs


def context():
    p,c,s,r,e=saved(); return tap.prepare(p,c,s,r,job_id='1234567',expectations=e)


def native(context,*,config=None,summary=None,exit_code=0,ancillary=0):
    from wandb.proto import wandb_internal_pb2 as pb
    first=pb.Record(); first.run.run_id=context['run_id']; first.run.display_name=context['run_name']; first.run.project=context['project']
    for key,value in (context['expected_config'] if config is None else config).items():
        first.run.config.update.add(key=key,value_json=json.dumps(value))
    records=[first]
    for _ in range(ancillary):
        record=pb.Record(); record.metric.name='ancillary-metric'; records.append(record)
    for row in context['mirror_rows']:
        record=pb.Record()
        for key,value in {'_step':row['step'],**row['row']}.items(): record.history.item.add(key=key,value_json=json.dumps(value))
        records.append(record)
    record=pb.Record()
    values=context['expected_summary'] if summary is None else summary
    for key,value in {'_step':len(context['mirror_rows'])-1,**values}.items(): record.summary.update.add(key=key,value_json=json.dumps(value))
    records.append(record)
    if exit_code is not None:
        record=pb.Record(); record.exit.exit_code=exit_code; records.append(record)
    return records


def compare(reader,context,records=None,**limits):
    from wandb.proto import wandb_internal_pb2 as pb
    records=iter(native(context) if records is None else records)
    class MetadataStream:
        def scan_data(self):
            item=next(records,None); return None if item is None else item.SerializeToString()
    return tap.compare(reader,MetadataStream(),pb.Record,context,**limits)


def test_exact_full_config_history_summary_and_ancillary_packets_are_distinct(reader):
    c=context(); result=compare(reader,c,native(c,ancillary=7))
    history=result['raw_history_verification']; summary=result['raw_config_summary_verification']
    assert history['schema']=='model_v3_native_mirror_verification_v7' and history['history_rows']==21
    assert history['native_packets']==31 and history['sdk_exit_codes']==[0] and history['clean_eof']
    assert summary['schema']=='native_S_config_summary_verification_v2' and summary['missing']==summary['different']==[]
    assert summary['configuration_exact_before_every_history_and_afterwards'] and summary['summary_exact']
    assert result['is_full_execution_or_storage_projection_certificate'] is False
    assert 'Root_storage_binding' not in json.dumps(result) and 'source.py' not in json.dumps(result)


@pytest.mark.parametrize('kind',('missing','extra','bool_type','value'))
def test_native_full_config_rejects_missing_extra_type_or_value(reader,kind):
    c=context(); actual=deepcopy(c['expected_config'])
    if kind=='missing': actual.pop('Root_storage_binding')
    elif kind=='extra': actual['undeclared']='extra'
    elif kind=='bool_type': actual['callback']['seed']=False
    else: actual['callback']['precision']='bf16'
    with pytest.raises(ValueError): compare(reader,c,native(c,config=actual))


@pytest.mark.parametrize('kind',('missing','extra','value'))
def test_native_full_summary_rejects_missing_extra_or_different(reader,kind):
    c=context(); actual=deepcopy(c['expected_summary'])
    if kind=='missing': actual.pop('metrics')
    elif kind=='extra': actual['undeclared']='extra'
    else: actual['profile_v2']['D5_authority']=True
    with pytest.raises(ValueError): compare(reader,c,native(c,summary=actual))


def test_config_drift_after_history_cannot_be_hidden_by_final_restore(reader):
    from wandb.proto import wandb_internal_pb2 as pb
    c=context(); records=native(c); changed=pb.Record(); changed.config.update.add(key='purpose',value_json='"wrong"')
    restored=pb.Record(); restored.config.update.add(key='purpose',value_json=json.dumps(tap.PURPOSE))
    records[2:2]=[changed,restored]
    with pytest.raises(ValueError): compare(reader,c,records)


@pytest.mark.parametrize('key',('run_id','display_name','project'))
def test_actual_native_run_identity_name_project_are_exact(reader,key):
    c=context(); records=native(c); setattr(records[0].run,key,'foreign')
    with pytest.raises(ValueError): compare(reader,c,records)


@pytest.mark.parametrize('damage',('metric','step_float','no_exit','exit1','summary_step'))
def test_full_history_step_exit_and_final_summary_step_cannot_be_bool_claims(reader,damage):
    c=context(); records=native(c)
    if damage=='metric': records[2].history.item.add(key='undeclared',value_json='1')
    elif damage=='step_float': records[1].history.item[0].value_json='0.0'
    elif damage=='no_exit': records.pop()
    elif damage=='exit1': records[-1].exit.exit_code=1
    else: records[-2].summary.update[0].value_json='19'
    with pytest.raises(ValueError): compare(reader,c,records)


def test_saved_expected_summary_is_reconstructed_from_actual_mirror_merge():
    p,c,s,r,e=saved(); s['loss']=999.
    with pytest.raises(ValueError,match='mirror merge'): tap.prepare(p,c,s,r,job_id='1234567',expectations=e)


def test_uncommitted_mirror_is_rejected_before_any_native_decode():
    p,c,s,r,e=saved(); r[4]['commit']=False
    with pytest.raises(ValueError,match='mirror envelope'): tap.prepare(p,c,s,r,job_id='1234567',expectations=e)


def test_row_population_comes_from_mirror_not_a_hardcoded_twentyone():
    p,c,s,r,e=saved(); skipped=deepcopy(r[1]); skipped['row']['optimizer_updates']=0
    skipped['row']['valid_counts']={'field':0}
    r.insert(1,skipped)
    for index,row in enumerate(r): row['step']=row['row']['log_cursor']=index; row['row']['samples_consumed']=index*32
    s=tap.merged_summary(r); s['profile_v2']=dict(purpose=tap.PURPOSE,completed_requested_short_target=True,
        optimizer_updates=20,native_code_sha=p['native_code_sha'],D5_authority=False)
    result=tap.prepare(p,c,s,r,job_id='1234567',expectations=e)
    assert len(result['mirror_rows'])==22 and result['mirror_rows'][-1]['row']['optimizer_updates']==20


def test_native_packet_budget_remains_distinct_and_cannot_be_increased(reader):
    import time
    c=context()
    with pytest.raises(ValueError): compare(reader,c,native(c,ancillary=20),max_native_records=10)
    with pytest.raises(ValueError,match='tighten'): compare(reader,c,max_native_records=500001)
    with pytest.raises(ValueError,match='Deadline'): compare(reader,c,deadline=time.monotonic()+181)


# These names reproduce the real metadata shape, with synthetic values only.
def slash_saved_context():
    p,c,s,r,e=saved()
    p['native_sources']={'/synthetic/source.py':'b'*64,'/synthetic/source.py/child':'c'*64}
    c['callback']['sources']=deepcopy(p['native_sources'])
    for row in r[1:]:
        row['row'].update({'loss/s_element':.1,'loss/s_noise':.2,'loss/s_bond':.3})
    s=tap.merged_summary(r)
    s['profile_v2']=dict(purpose=tap.PURPOSE,completed_requested_short_target=True,
        optimizer_updates=20,native_code_sha=p['native_code_sha'],D5_authority=False)
    return tap.prepare(p,c,s,r,job_id='1234567',expectations=e)


def test_actual_shape_loss_scalar_and_literal_slash_siblings_preserve_all_fields(reader):
    c=slash_saved_context(); result=compare(reader,c)
    values=reader.flatten(c['mirror_rows'][1]['row'])
    assert all(key in values for key in ('loss','loss~1s_element','loss~1s_noise','loss~1s_bond'))
    assert result['raw_history_verification']['history_rows']==21
    assert result['raw_history_verification']['scientific_key_encoding']=='rfc6901_literal_segments_v1'
    assert result['raw_config_summary_verification']['summary_exact']


def test_literal_slash_and_nested_segments_do_not_alias(reader):
    c=slash_saved_context()
    c['expected_config']['Root_storage_binding'].update({'a/b':1,'a':{'b':2}})
    result=compare(reader,c)
    assert result['raw_config_summary_verification']['configuration_exact_before_every_history_and_afterwards']
    assert reader.flatten({'a/b':1,'a':{'b':2}})=={'a~1b':1,'a/b':2}


def test_duplicate_literal_metric_still_rejected(reader):
    c=slash_saved_context(); records=native(c)
    records[2].history.item.add(key='loss/s_noise',value_json='0.2')
    with pytest.raises(ValueError,match='Duplicate or overlapping'):
        compare(reader,c,records)


def test_scalar_ancestor_and_true_nested_child_still_rejected(reader):
    from wandb.proto import wandb_internal_pb2 as pb
    record=pb.Record(); record.history.item.add(key='a',value_json='1')
    record.history.item.add(nested_key=['a','b'],value_json='2')
    with pytest.raises(ValueError,match='Duplicate or overlapping'):
        reader.native_items(record.history.item)


def test_same_nested_path_from_object_and_nested_key_still_rejected(reader):
    from wandb.proto import wandb_internal_pb2 as pb
    record=pb.Record(); record.history.item.add(key='a',value_json='{"b":1}')
    record.history.item.add(nested_key=['a','b'],value_json='2')
    with pytest.raises(ValueError,match='Duplicate or overlapping'):
        reader.native_items(record.history.item)


def test_literal_to_nested_wire_key_drift_cannot_match(reader):
    c=slash_saved_context(); records=native(c)
    item=next(item for item in records[2].history.item if item.key=='loss/s_noise')
    item.key=''; item.nested_key.extend(['loss','s_noise'])
    with pytest.raises(ValueError):
        compare(reader,c,records)


def test_tilde_escape_is_injective_for_literal_and_nested_keys(reader):
    c=slash_saved_context()
    c['expected_config']['Root_storage_binding'].update({'a~1b':1,'a/b':2,'a':{'b':3}})
    compare(reader,c)
    assert reader.flatten({'a~1b':1,'a/b':2,'a':{'b':3}})=={'a~01b':1,'a~1b':2,'a/b':3}


def test_literal_metric_value_type_missing_and_extra_are_all_checked(reader):
    for damage in ('value','type','missing','extra'):
        c=slash_saved_context(); records=native(c)
        index=next(i for i,item in enumerate(records[2].history.item) if item.key=='loss/s_noise')
        if damage=='value':records[2].history.item[index].value_json='999'
        elif damage=='type':records[2].history.item[index].value_json='true'
        elif damage=='missing':del records[2].history.item[index]
        else:records[2].history.item.add(key='undeclared/a',value_json='1')
        with pytest.raises(ValueError):compare(reader,c,records)
