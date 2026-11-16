"""Only the declared validation summary layout is allowed as a result CSV."""
import importlib.util
from pathlib import Path


def test_validation_summary_csv_is_metadata_and_excludes_other_payloads():
    path = Path(__file__).resolve().parents[2] / 'tools/check_repository.py'
    spec = importlib.util.spec_from_file_location('repository_validation_csv', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    header = 'run_id,consumed_samples,panel,records,molecules,s_element_loss,s_noise_loss,s_bond_loss,noise_component_RMSE_A,selection_use\n'
    row = 'S_C1_0_seed0,6000000,FULL,66991,7016,0.75,0.17,0.002,0.04,False\n'
    name = 'results/model_v3_v2_validation.csv'
    raw = (header + row).encode()
    assert module.model_summary_csv(name, raw)
    assert not module.model_summary_csv('results/raw_data.csv', raw)
    assert not module.model_summary_csv(name, raw.replace(b'False', b'True'))
    assert not module.model_summary_csv(name, raw.replace(b'0.75', b'nan'))
    assert not module.model_summary_csv(name, raw + row.encode())
    assert not module.model_summary_csv(name, b'molecule_id,label\n1,0.75\n')
