import json
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from phychem_mfm.phase1.v31_record_masks import published_record_masks, apply_published_scalar_mask
from phychem_mfm.phase1.v31_loader import TrainingView


def test_published_masks_join_both_native_record_and_molecule_identity(tmp_path):
    masks = tmp_path/'masks.parquet'
    pq.write_table(pa.Table.from_pylist([dict(record_id='r1', molecule_id='m1',
        field_key='P.ea', leaf_indices=[0])]), masks)
    catalog = tmp_path/'catalog.json'
    catalog.write_text(json.dumps(dict(files=[dict(path=str(masks), records=1)])))
    rows = [dict(record_kind=kind, native_record_id=rid, molecule_id=mid,
                 molecule_index=i, conformer_index=2)
            for kind,rid,mid,i in [('P','r1','m1',1), ('U','r1','m1',2),
                                   ('P','r1','other',3), ('P','r2','m1',4)]]
    pq.write_table(pa.Table.from_pylist(rows), tmp_path/'id_map.parquet')
    payload = dict(source_references={'P_D': dict(closed_training_stage_references={
        'mask_overrides_reference': dict(path=str(catalog))})})
    assert published_record_masks(payload, tmp_path) == {(1,2): {'P.ea': {0}}}
    assert published_record_masks({}, tmp_path) == {}


def test_record_override_precedes_normalization_and_preserves_source():
    fields = [dict(name=key,field_key=key,target_id=key,group='P',family='test',
                   level='molecule',selectors=[[23,i,'mol_labels']])
              for i,key in enumerate(['P.ea','P.other'])]
    schema = dict(columns={'mol_labels': [dict(field_key=key,column_index=i)
                         for i,key in enumerate(['P.ea','P.other'])]})
    norms = {key: dict(center=1.,scale=2.,fit_role='TRAIN') for key in ['P.ea','P.other']}
    view = TrainingView(schema,dict(fields=fields),norms)
    source = np.array([[12.,7.]],dtype=np.float32)
    targets = view.extract({1:np.array([6])},{23:source},mask_overrides={'P.ea':{0}})
    assert np.isnan(targets['P.ea'].raw).all()
    assert np.isnan(targets['P.ea'].values).all() and not targets['P.ea'].valid.any()
    np.testing.assert_allclose(targets['P.other'].values,[[3.]],atol=1e-7,rtol=1e-7)
    np.testing.assert_allclose(source,[[12.,7.]],atol=1e-7,rtol=1e-7)


def test_published_mask_cannot_be_guessed_for_other_leaf_layout():
    for raw,leaves in [(np.zeros((1,2)),{0}),(np.zeros((1,1)),{1})]:
        with pytest.raises(ValueError,match='selected field leaves'):
            apply_published_scalar_mask(raw,leaves)
