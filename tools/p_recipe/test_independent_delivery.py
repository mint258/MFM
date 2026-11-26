"""New independent-delivery boundaries, using synthetic metadata/files only."""
import hashlib
import pytest
from final_report_22B import validate_bundle,ReportNotReady
from test_final_report_22B import ready
from independent_delivery import seal_checkpoint_hashes,assemble_final


def test_skip_only_external_A4_retains_every_P_gate():
    bundle=ready();bundle['A4']=None
    with pytest.raises(ReportNotReady,match='external D'):validate_bundle(bundle)
    assert validate_bundle(bundle,require_external_A4=False) is bundle
    bundle['A5']=None
    with pytest.raises(ReportNotReady,match='A5'):validate_bundle(bundle,require_external_A4=False)


def test_final_weights_are_hashed_once_and_changes_are_rejected(tmp_path):
    checkpoint=tmp_path/'final.pt';checkpoint.write_bytes(b'fake final endpoint, not a model')
    manifest=tmp_path/'hashes.json';calls=[]
    def digest(path):
        calls.append(path);return hashlib.sha256(path.read_bytes()).hexdigest()
    original=seal_checkpoint_hashes(manifest,{'T2':checkpoint},hash_function=digest)
    repeated=seal_checkpoint_hashes(manifest,{'T2':checkpoint},hash_function=digest)
    assert repeated==original and len(calls)==1
    checkpoint.write_bytes(b'changed final endpoint')
    with pytest.raises(ValueError,match='changed after'):seal_checkpoint_hashes(manifest,{'T2':checkpoint},hash_function=digest)
    assert len(calls)==1


def test_assembly_waits_for_actual_A4_even_when_P_is_sealed(tmp_path):
    with pytest.raises(ReportNotReady,match='external D'):
        assemble_final(tmp_path,dict(status='P_SECTIONS_SEALED_WAIT_A4'),'source')
    assert not (tmp_path/'docs/p_recipe/REPORT.md').exists()


def test_hashing_cursor_does_not_start_another_weight_when_stop_requested(tmp_path):
    checkpoint=tmp_path/'final.pt';checkpoint.write_bytes(b'fake')
    def forbidden(path):pytest.fail('A new weight read was started during cleanup')
    assert seal_checkpoint_hashes(tmp_path/'hashes.json',{'T2':checkpoint},should_stop=lambda:True,hash_function=forbidden) is None
    assert not (tmp_path/'hashes.json').exists()