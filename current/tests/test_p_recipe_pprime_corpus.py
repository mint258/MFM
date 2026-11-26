"""Source-eligible Pprime cohorts retain published membership and roles."""
import importlib.util,json
from pathlib import Path
import lmdb
import numpy as np
import pytest
from test_v31_loader import encode
from phychem_mfm.phase1.v31_loader import record_key

def tool():
    path=Path(__file__).resolve().parents[2]/'tools/p_recipe/prepare_pprime_corpus.py'
    spec=importlib.util.spec_from_file_location('pprime_cohort',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def database(path,records):
    with lmdb.open(str(path),map_size=1048576) as env:
        with env.begin(write=True) as txn:
            for index,arrays in records.items():txn.put(record_key('M',index),encode(arrays))

def test_pprime_train_filters_only_published_members_without_reordering(tmp_path):
    directory=tmp_path/'TRAIN'
    database(directory,{
        1:{14:np.array([0,0],dtype='u1'),18:np.array([0,1],dtype='u1')},
        2:{14:np.array([],dtype='u1'),18:np.array([],dtype='u1')},
        4:{14:np.array([1,0],dtype='u1'),18:np.array([1,1],dtype='u1')},
        9:{14:np.array([0],dtype='u1'),18:np.array([1],dtype='u1')}})
    # Record9 is eligible but outside the supplied clean TRAIN; never add it.
    assert tool().select_eligible(directory,np.array([4,2,1]),train=True).tolist()==[4,1]

def test_full_validation_does_not_apply_train_only_m18(tmp_path):
    directory=tmp_path/'FULL'
    database(directory,{
        0:{14:np.array([1],dtype='u1'),18:np.array([1],dtype='u1')},
        3:{14:np.array([0],dtype='u1'),18:np.array([0],dtype='u1')}})
    assert tool().select_eligible(directory,np.array([3,0]),train=False).tolist()==[3]

def test_source_available_validation_is_fixed_and_uses_only_eligible_rows(tmp_path):
    pytest.importorskip('pyarrow')
    from phychem_mfm.phase1.p_recipe_data import validation_indices
    array=tmp_path/'available.npy';np.save(array,np.arange(20,40,dtype=np.int64))
    corpus=tmp_path/'corpus.json';corpus.write_text(json.dumps({'source_available_common_validation_indices':str(array)}))
    c={'corpus':str(corpus)}
    a=validation_indices(c,count=8);b=validation_indices(c,count=8)
    assert np.array_equal(a,b) and len(np.unique(a))==8 and set(a)<=set(range(20,40))


def test_prepare_preserves_original_and_reuses_source_cohort(tmp_path,monkeypatch):
    from phychem_mfm.phase1 import p_recipe_data
    root=tmp_path/'compact';root.mkdir()
    train=root/'TRAIN';train.mkdir();full=root/'FULL';full.mkdir()
    (root/'manifest.json').write_text(json.dumps({'split_roots':{'TRAIN':str(train),'FULL':str(full)},'molecules':{'TRAIN':128000,'FULL':2000}}))
    original_indices=np.arange(128000,dtype=np.int64)
    original_array=tmp_path/'original.npy';np.save(original_array,original_indices)
    corpus=tmp_path/'corpus.json'
    original={'source_root':str(root),'train_indices':str(original_array),'train_molecules':128000,'base_normalizations':'unchanged'}
    corpus.write_text(json.dumps(original))
    configuration=tmp_path/'fit.json';configuration.write_text(json.dumps({'root':str(root),'corpus':str(corpus)}))
    val=np.arange(2000,dtype=np.int64);calls=[]
    monkeypatch.setattr(p_recipe_data,'validation_indices',lambda c,count:val)
    module=tool()
    def select(directory,indices,*,train):
        assert isinstance(directory,Path)
        calls.append(train)
        return np.asarray(indices)
    monkeypatch.setattr(module,'select_eligible',select)
    result=module.prepare(configuration)
    assert result['train_molecules']==128000 and result['source_available_common_validation_molecules']==2000
    assert json.loads(corpus.read_text())==original
    assert np.array_equal(np.load(original_array),original_indices)
    assert json.loads(configuration.read_text())['corpus']!=str(corpus)
    module.prepare(configuration)
    assert calls==[True,False]
