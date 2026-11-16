"""Actual file allocation and published-input transitions, without data rereads."""
import importlib.util
import json
import os
from pathlib import Path

import pytest

REPO=Path(__file__).resolve().parents[2]

def module(name,file):
    spec=importlib.util.spec_from_file_location(name,REPO/'tools/model_v3'/file)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value

disk=module('followon_disk','v2_diagnosis_disk.py')
binder=module('published_pd_binding','v2_bind_published_pd.py')

def write(path,value):
    path.write_text(json.dumps(value));return path


def test_global_allocations_include_registered_outputs_without_duplicate_or_symlink_credit(tmp_path):
    base=tmp_path/'models';base.mkdir()
    old=base/'M2_DIAG_unit';old.mkdir();(old/'nested').mkdir()
    first=old/'nested'/'first';first.write_bytes(b'a'*16000)
    follow=base/'P_C1_0_seed0';follow.mkdir()
    second=follow/'second';second.write_bytes(b'b'*32000)
    os.link(first,follow/'hardlink')
    outside=tmp_path/'outside';outside.write_bytes(b'x'*65536)
    (follow/'symbolic').symlink_to(outside)
    unregistered=base/'historical_S';unregistered.mkdir();(unregistered/'old').write_bytes(b'x'*65536)
    registry=write(tmp_path/'registry.json',dict(schema='MODEL_OUTPUT_BUDGET_V1',total_peak_bytes=100_000_000_000,roots=[str(follow)]))
    used,remaining=disk.model_growth_forecast(base=base,registry=registry)
    assert used==first.stat().st_blocks*512+second.stat().st_blocks*512
    assert remaining+used==100_000_000_000


def test_registered_output_cannot_credit_files_outside_model_root(tmp_path):
    base=tmp_path/'models';base.mkdir()
    registry=write(tmp_path/'registry.json',dict(schema='MODEL_OUTPUT_BUDGET_V1',total_peak_bytes=100_000_000_000,roots=[str(tmp_path/'outside')]))
    with pytest.raises(OSError):disk.model_growth_forecast(base=base,registry=registry)


def test_nfs_future_is_retired_only_after_final_producer_manifest(tmp_path):
    final=tmp_path/'manifest.json'
    assert disk.remaining_nfs_other(final)==116_769_803_776
    write(final,dict(split_roots={'TRAIN':'closed-path'}))
    assert disk.remaining_nfs_other(final)==116_769_803_776
    write(final,dict(split_roots={'TRAIN':'train','FULL':'full'},molecules={'TRAIN':1194551,'FULL':1}))
    assert disk.remaining_nfs_other(final)==23_179_869_184


def binding_files(tmp_path):
    template=dict(root=None,condition='P',expected_molecules=240000,candidate='C1-a',seed=0,samples=6000000,
                  lr=.0003,clip=1,head_form='H1',views='three',training_view='original-view',
                  normalizations='original-routes',subset_path='original-240k',source='PM7')
    inputs={k:template[k] for k in ('training_view','normalizations','subset_path','source')}
    inputs['root']='published-root'
    binding=dict(schema='ORIGINAL_S240K_SHARED_D6_PD_INPUT_BINDING_V1',status='READY',root='published-root',
        membership_binding=dict(unique_molecules=240000,rows_filtered_or_replaced=0,original_subset_order_preserved=True),
        intersection_applied=False,subset_replaced=False,bindings={'P':inputs})
    return template,binding,write(tmp_path/'template.json',template),write(tmp_path/'binding.json',binding),tmp_path/'execution.json'


def test_ready_binding_changes_only_root_and_preserves_existing_execution(tmp_path):
    template,binding,tp,bp,output=binding_files(tmp_path)
    expected=dict(template,root='published-root')
    assert binder.bind_configuration(tp,bp,output)==expected
    assert binder.bind_configuration(tp,bp,output)==expected
    binding['bindings']['P']['subset_path']='different-ids';write(bp,binding)
    with pytest.raises(ValueError):binder.bind_configuration(tp,bp,output)
    assert json.loads(output.read_text())==expected


@pytest.mark.parametrize('change',('not_ready','root_missing','subset_replaced'))
def test_no_execution_config_is_written_for_unpublished_or_replaced_inputs(tmp_path,change):
    _,binding,tp,bp,output=binding_files(tmp_path)
    if change=='not_ready':binding['status']='NOT_READY'
    elif change=='root_missing':binding['root']=None
    else:binding['membership_binding']['rows_filtered_or_replaced']=1
    write(bp,binding)
    with pytest.raises(ValueError):binder.bind_configuration(tp,bp,output)
    assert not output.exists()
