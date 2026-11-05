import importlib.util
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