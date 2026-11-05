import importlib.util
from pathlib import Path

import pytest


def launcher():
    path = Path(__file__).absolute().parents[2]/'tools/model_v3/v2_prepare_grid_cell.py'
    spec = importlib.util.spec_from_file_location('taskbook_grid_launcher', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen():
    model = dict(status='FROZEN', code_tag='fixture-only', architecture=dict(layers=6,dim=512,
        backbone_activation_checkpointing=False,head_activation_checkpointing=False,
        distance_bias='C1-a',views='two',head_form='H2',pooling='registry'))
    recipe = dict(status='FROZEN',optimizer='AdamW',betas=[.9,.95],warmup_fraction=.02,
        sample_budget=8_000_000,batch_size=32,lr=3e-4,schedule='wsd',clip=2.)
    return model, recipe


def test_required_grid_has_nine_s_p_seven_d_and_two_sprime_cells():
    module = launcher()
    cells = module.required_cells()
    assert {condition: sum(c == condition for c,m,k in cells) for condition in ('S','P','D','Sprime')} == {
        'S':9, 'P':9, 'D':7, 'Sprime':2}
    assert ('D',1_126_937,5) not in cells


def test_sprime_and_actual_kstar_pprime_use_uff_and_explicit_d4():
    module = launcher()
    model, recipe = frozen()
    common = dict(molecules=120_000,order='fixed_random',seed=0,root='/data',subset='/subset',
                  training_view='/view',normalizations='/independent-pprime',output='/run')
    s = module.make_configuration(model, recipe, condition='Sprime', k=None, **common)
    assert s['source'] == 'UFF' and s['condition'] == 'S' and s['k'] is None
    p = module.make_configuration(model, recipe, condition='Pprime', k=None, shared_k_star='all', **common)
    assert p['source'] == 'UFF' and p['condition'] == 'P'
    assert p['normalizations'] == '/independent-pprime'
    with pytest.raises(ValueError, match='shared-k'):
        module.make_configuration(model, recipe, condition='Pprime', k=2, **common)


def test_prepared_job_uses_slurm_and_one_uuid_lock_without_memory_or_time_gates(tmp_path):
    module = launcher()
    script = module.slurm_script(tmp_path/'input.json', tmp_path/'run', node='compute-0-5',
        gpu_uuid='GPU-1234-abcd', python='/env/bin/python', repo=tmp_path/'repo')
    assert '#SBATCH --partition=all' in script and '#SBATCH --cpus-per-task=16' in script
    assert 'flock ' in script and 'CUDA_VISIBLE_DEVICES=GPU-1234-abcd' in script
    assert '--mem' not in script and '--time' not in script and 'v2_train_v31.py' in script


def test_user_approved_final_d5_pool_replaces_nominal_maximum():
    module = launcher()
    model, recipe = frozen()
    common = dict(order='fixed_random',seed=0,root='/data',subset='/final-d5',
                  training_view='/view',normalizations='/D4',output='/run')
    cells = module.required_cells()
    assert not any(m == 1_200_000 for condition,m,k in cells)
    for condition in ('S', 'P', 'D'):
        allowed = (1,) if condition == 'D' else (1, 2, 5)
        assert {k for c,m,k in cells if c == condition and m == 1_126_937} == set(allowed)
        for k in allowed:
            config = module.make_configuration(model, recipe, condition=condition,
                molecules=1_126_937, k=k, **common)
            assert config['expected_molecules'] == 1_126_937
        with pytest.raises(ValueError, match='outside the preregistered'):
            module.make_configuration(model, recipe, condition=condition,
                molecules=1_200_000, k=1, **common)
