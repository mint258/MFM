"""The current exclusion-only producer preserves source and normalization data."""
import importlib.util,json
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


def test_exclusion_is_whole_molecule_without_refitting_normalization(tmp_path,monkeypatch):
    path=Path(__file__).resolve().parents[2]/'tools/p_recipe/prepare_corpus.py'
    spec=importlib.util.spec_from_file_location('p_recipe_prepare_corpus',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source=tmp_path/'runs/data_v1_20261025/artifacts/export/D6_full_v31_20261105_v1/compact';source.mkdir(parents=True)
    control=tmp_path/'control';control.mkdir();output=tmp_path/'cohort'
    (control/'D6_identity.json').write_text(json.dumps(dict(overlapping_molecules=['excluded'])))
    (source/'manifest.json').write_text(json.dumps(dict(split_roots=dict(TRAIN=str(source)),molecules=dict(TRAIN=3))))
    ids=source/'id_map.parquet';pq.write_table(pa.table(dict(molecule_id=['kept1','excluded','kept2'],molecule_index=[0,1,2],record_kind=['M']*3)),ids)
    original=ids.read_bytes();normalization=tmp_path/'original_routes.json';normalization.write_text('{"unchanged":true}\n')
    monkeypatch.setattr(module,'ROOT',tmp_path);monkeypatch.setattr(module,'CONTROL',control);monkeypatch.setattr(module,'OUTPUT',output)
    result=module.main()
    np.testing.assert_array_equal(np.load(result['train_indices']),[0,2])
    assert result['excluded_molecule_ids']==['excluded'] and result['excluded_indices']==[1]
    assert ids.read_bytes()==original and normalization.read_text()=='{"unchanged":true}\n'
    assert result['original_files_modified'] is False and result['identity_audit_repeated'] is False
