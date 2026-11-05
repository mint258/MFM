"""Meaningful CPU tensor/schema/bound tests; no native data or model training."""
import json

import pytest
import torch

import inventory as audit


def payload():
    group=dict(params=[0,1],amsgrad=False,fused=None,capturable=False,differentiable=False,maximize=False)
    return dict(schema='model_v3_training_checkpoint_v1',bindings={},runtime={},
        model={'weight':torch.ones(4,3),'bias':torch.ones(4)},
        optimizer={'param_groups':[group],'state':{0:{'step':torch.tensor(20.),
            'exp_avg':torch.zeros(4,3),'exp_avg_sq':torch.zeros(4,3)}}},
        sampler=dict(schema_version=1,contract_sha256='a'*64,epoch=0,block_position=1,item_offset=0,
            batches_consumed=20,samples_consumed=7680,content_sha256='b'*64),
        clock=dict(schema='model_v3_consumed_sample_clock_v1',sample_budget=10240000,milestones=[],
            samples_consumed=7680,optimizer_updates=20,saved_milestones=[]),
        rng={'cpu':torch.zeros(16,dtype=torch.uint8)},
        extra_state=dict(contract={'plan':audit.PLAN},scheduler={},points={},saved_updates=[20],log_cursor=21,
            input_chain='c'*64,tracker={'id':'unit0001'},model_training=True,dtype_observations={}))


def test_real_weights_only_roundtrip_and_lazy_adam_inventory(tmp_path):
    path=tmp_path/'payload.pt';item=payload()
    item['extra_state']['contract']['plan']={**audit.PLAN,
        'validation_updates':tuple(audit.PLAN['validation_updates']),
        'checkpoint_updates':tuple(audit.PLAN['checkpoint_updates'])}
    torch.save(item,path)
    with path.open('rb') as stream: loaded=torch.load(stream,map_location='cpu',weights_only=True)
    result=audit.inspect(loaded,torch)
    assert result['model_state_numel']==16 and result['initialized_moment_numel']==12
    assert result['uninitialized_parameter_states']==1
    assert result['optimizer_future_state_bound_bytes']>=2*4*16
    assert result['provider_future_state_bound_bytes']>41*16384
    raw=json.dumps(result)
    assert 'tensor(' not in raw and 'data_ptr' not in raw


def test_unknown_optimizer_and_provider_fields_rejected():
    for category in ('state','sampler','variant'):
        item=payload()
        if category=='state':item['optimizer']['state'][0]['mystery']=torch.ones(1)
        elif category=='sampler':item['sampler']['prefetched_records']=['not admitted']
        else:item['optimizer']['param_groups'][0]['amsgrad']=True
        with pytest.raises(ValueError):audit.inspect(item,torch)


def test_no_scalar_tensor_values_or_large_unknown_metadata_exported():
    item=payload();item['model']['weight'].fill_(123456.789)
    result=audit.inspect(item,torch)
    assert '123456' not in json.dumps(result) and result['model']['weight']['shape']==[4,3]
    item['extra_state']['tracker']['unexpected']='x'*20000
    with pytest.raises(ValueError,match='string'):audit.inspect(item,torch)


def test_raw_reference_rejects_tamper_and_byte_budget(tmp_path):
    source=tmp_path/'tiny.json';source.write_text('{"x":1}')
    ref=audit.bound(source);assert audit.read(ref)=={'x':1}
    with pytest.raises(ValueError):audit.bound(source,1)
    source.write_text('{"x":2}')
    with pytest.raises(ValueError):audit.read(ref)
