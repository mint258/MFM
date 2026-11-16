import importlib.util
import json
from pathlib import Path

import pytest


def observer(monkeypatch):
    path=Path(__file__).absolute().parents[2]/'tools/model_v3/v2_watch_disk.py'
    spec=importlib.util.spec_from_file_location('active_model_disk_observer',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.socket,'gethostname',lambda:'compute-0-21')
    return module


def capacity():
    return dict(total=1000*1024**3,available=800*1024**3,
                total_inodes=1000000,inodes=900000,root=True)


def test_healthy_observer_does_not_signal_jobs(monkeypatch):
    module=observer(monkeypatch)
    monkeypatch.setattr(module,'filesystem_status',lambda path:capacity())
    calls=[]
    result=module.check_and_protect('/shared',[4526020,4526023],node='compute-0-21',
                                    run=lambda *a,**kw:calls.append((a,kw)))
    assert result['status']=='OBSERVING' and calls==[]


@pytest.mark.parametrize('unknown',[False,True])
def test_real_shortfall_or_unknown_capacity_pauses_only_bound_owned_jobs(monkeypatch,unknown):
    module=observer(monkeypatch)
    def inspect(path):
        if unknown:
            raise OSError('capacity unavailable')
        return {**capacity(),'available':1}
    monkeypatch.setattr(module,'filesystem_status',inspect)
    calls=[]
    result=module.check_and_protect('/shared',[4526020,4526023],node='compute-0-21',
                                    run=lambda *a,**kw:calls.append((a,kw)))
    assert result['status']=='DISK_PAUSED'
    command=calls[0][0][0]
    assert command[:3]==['scancel','--signal=STOP','--full']
    assert command[-4:]==['--nodelist','compute-0-21','4526020','4526023']
    assert '--user' in command and calls[0][1]=={'check':True}


def test_observer_refuses_a_different_target_node(monkeypatch):
    module=observer(monkeypatch)
    with pytest.raises(ValueError,match='actual target'):
        module.check_and_protect('/shared',[4526041],node='compute-0-20')


def quota_snapshot(module):
    return dict(schema='LUSTRE_USER_QUOTA_AVAILABLE_V1',uid=module.os.getuid(),
                filesystem='/lfshome',available_bytes=500_000_000_000,
                observed_time=98.75,source_probe_time=100.,clock_safety_bias_seconds=1.25)


def test_real_user_quota_and_combined_growth_control_writes_even_with_free_volume(monkeypatch,tmp_path):
    module=observer(monkeypatch)
    monkeypatch.setattr(module,'filesystem_status',lambda path:capacity())
    monkeypatch.setattr(module.time,'time',lambda:100.)
    reference=tmp_path/'quota.json'
    value=quota_snapshot(module)
    reference.write_text(json.dumps(value))
    calls=[]
    arguments=dict(node='compute-0-21',growth_bytes=100_000_000_000,
        quota_reference=reference,quota_filesystem='/lfshome',quota_concurrent_bytes=170_000_000_000,
        run=lambda *a,**kw:calls.append((a,kw)))
    result=module.check_and_protect('/lfshome/model',[4526242],**arguments)
    required=100_000_000_000+100_000_000_000+170_000_000_000+8*1024**3
    assert result['status']=='OBSERVING' and result['quota']['required']==required and calls==[]
    value['available_bytes']=required-1
    reference.write_text(json.dumps(value))
    result=module.check_and_protect('/lfshome/model',[4526242],**arguments)
    assert result['status']=='DISK_PAUSED' and 'account quota' in result['reason']
    assert len(calls)==1
    assert calls[0][0][0][-3:]==['--nodelist','compute-0-21','4526242']


@pytest.mark.parametrize('observed_time',[94.99,100.01])
def test_unknown_quota_freshness_is_not_replaced_by_free_volume(monkeypatch,tmp_path,observed_time):
    module=observer(monkeypatch)
    monkeypatch.setattr(module.time,'time',lambda:100.)
    value={**quota_snapshot(module),'observed_time':observed_time}
    reference=tmp_path/'quota.json'
    reference.write_text(json.dumps(value))
    with pytest.raises(OSError,match='future or stale'):
        module.quota_headroom(reference,'/lfshome',100_000_000_000,0)


@pytest.mark.parametrize('wrong',['uid','filesystem'])
def test_quota_must_describe_the_actual_account_and_filesystem(monkeypatch,tmp_path,wrong):
    module=observer(monkeypatch)
    monkeypatch.setattr(module.time,'time',lambda:100.)
    value=quota_snapshot(module)
    value[wrong]=module.os.getuid()+1 if wrong=='uid' else '/share'
    reference=tmp_path/'quota.json'
    reference.write_text(json.dumps(value))
    with pytest.raises(OSError,match='identity differs'):
        module.quota_headroom(reference,'/lfshome',100_000_000_000,0)
