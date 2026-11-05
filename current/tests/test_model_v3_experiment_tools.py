"""Request/Slurm/summary tools preserve source bindings without submission."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).absolute().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools/model_v3' / (name+'.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def arguments(tmp_path):
    repo = tmp_path / 'repo'; repo.mkdir()
    (repo / 'source.py').write_text('value = 1\n')
    config = tmp_path / 'model.json'; config.write_text(json.dumps({'seed': 7, 'model': {'backbone': {'dim': 512, 'layers': 6}}}))
    panel = tmp_path / 'panel.json'; panel.write_text('{}')
    store = tmp_path / 'store.json'; store.write_text('{}')
    weights = tmp_path / 'checkpoint.pt'; weights.write_bytes(b'synthetic binding fixture; not a model')
    return dict(panel=panel, training_store=store, model_configuration=config, checkpoint=weights,
        code_sha='a'*40, preregistration_sha='b'*40, data_version='synthetic-v1', pretraining_seed=7,
        output_root=tmp_path / 'outputs', cache_root=tmp_path / 'cache', run_id='unit_run',
        source_files=['source.py'], repository_root=repo)


def test_request_binds_seed_sources_and_does_not_submit(tmp_path):
    prepare = module('prepare_dev_evaluation'); args = arguments(tmp_path)
    request = prepare.make_request(**args)
    assert request['source_files'][0]['sha256'] == hashlib.sha256(b'value = 1\n').hexdigest()
    assert request['pretraining_seed'] == 7 and request['device'] == 'cuda:0'
    assert request['h0_packing']['max_padded_pairs'] == 1_000_000
    assert request['packing_binding_status'] == 'METADATA_PLANNING_REQUIRED'
    assert not Path(request['output_root']).exists()
    with pytest.raises(ValueError, match='seed differs'):
        prepare.make_request(**{**args, 'pretraining_seed': 8})
    with pytest.raises(ValueError, match='outside the source tree'):
        prepare.make_request(**{**args, 'cache_root': args['repository_root'] / 'cache'})
    with pytest.raises(ValueError, match='source inventory'):
        prepare.make_request(**{**args, 'source_files': []})


def test_sbatch_is_single_gpu_lf_and_uses_the_logical_interpreter(tmp_path):
    prepare = module('prepare_dev_evaluation')
    script = prepare.sbatch_text(tmp_path / 'request.json', 'a'*64, node='compute-0-20',
        python_entry='/verified/venv/bin/python', gpu_uuid='GPU-'+'a'*36,
        log_path=tmp_path / 'dev_%j.log')
    assert '\r' not in script and '#SBATCH --cpus-per-task=16' in script
    assert 'CUDA_VISIBLE_DEVICES=GPU-' in script and '/verified/venv/bin/python -B' in script
    assert 'sbatch ' not in script and '--nodelist=compute-0-20' in script
    with pytest.raises(ValueError):
        prepare.sbatch_text(tmp_path / 'request.json', 'a'*64, node='other-server',
            python_entry='/verified/venv/bin/python', gpu_uuid='GPU-'+'a'*36, log_path=tmp_path / 'log')


def test_summary_serialization_is_typed_and_no_raw_field_can_be_added():
    summarize = module('summarize_experiments')
    row = dict(run_id='offline_run', stage='4', config_sha256='a'*64, code_sha='b'*40,
        data_version='synthetic-v1', seed=0, gpu_model='CPU', elapsed_seconds=1.5,
        status='COMPLETED', preregistration_sha='c'*40, dev_score=-.2, peak_memory_bytes=0)
    assert summarize.summary_bytes([row]).startswith(b'run_id,stage,config_sha256,')
    with pytest.raises(ValueError):
        summarize.summary_bytes([{**row, 'smiles': 'CCO'}])
    with pytest.raises(ValueError):
        summarize.summary_bytes([row, row])


def test_readout_journal_uses_a_global_cursor_across_independent_probes(tmp_path):
    import time
    runner = module('evaluate_dev_panel')
    class Run:
        def __init__(self):
            self.rows = []
        def log(self, row, *, step, commit):
            assert commit is True and step == len(self.rows)
            self.rows.append(row)
    run = Run(); journal = runner.RunJournal(run, tmp_path, time.monotonic(), 30)
    first = journal.scoped('task_one'); second = journal.scoped('task_two')
    first.log({'loss': 1.}, step=0, commit=True)
    first.log({'loss': .5}, step=1, commit=True)
    second.log({'loss': 2.}, step=0, commit=True)
    journal.close()
    assert journal.step == 3 and len((tmp_path / 'history.jsonl').read_text().splitlines()) == 3
    assert 'task_two/loss' in run.rows[2]


def test_frozen_panel_has_native_fields_and_approved_classification_coverage():
    panel = json.loads((ROOT / 'configs/dev_panel_v1.json').read_text())
    tasks = panel['tasks']
    assert len(tasks) == 9 and len({r['task_id'] for r in tasks}) == 9
    assert {r['field'] for r in tasks if r['dataset_id'] == 'cyp_isoform'} == {'3A4', '2D6'}
    assert {r['field'] for r in tasks if r['dataset_id'] == 'qm9'} == {'U0', 'homo', 'lumo', 'alpha'}
    assert all(r['kind'] == 'regression' for r in tasks if r['dataset_id'] == 'expansionrx')
    assert panel['authority']['classification_coverage_user_decision']['date'] == '2026-10-25'
    assert panel['source_roles']['selection']['labels_consulted'] is False


def test_metadata_plan_validation_never_calls_target_get(tmp_path, monkeypatch):
    prepare = module('prepare_dev_evaluation'); runner = module('evaluate_dev_panel')
    args = arguments(tmp_path)
    panel = json.loads((ROOT / 'configs/dev_panel_v1.json').read_text())
    args['panel'].write_text(json.dumps(panel))
    requests = prepare.make_request(**args)
    request_path = tmp_path / 'request.json'; raw = json.dumps(requests).encode(); request_path.write_bytes(raw)
    import phychem_mfm.phase1.v3_dev_store as store_module

    class MetadataStore:
        data_version = 'synthetic-v1'
        integrity_scope = 'synthetic metadata fixture only'
        def __init__(self, path, digest):
            self.group_map = {(dataset, i): {'member_uid': f'{dataset}:{i}',
                'full_inchikey': chr(65+i)*14+'-ABCDEFGHIJ-A'}
                for dataset in ('qm9', 'expansionrx', 'cyp_isoform') for i in range(20)}
        def contract(self, dataset, fold):
            members = {'train': list(range(15)),
                       'train_inner_validation': [] if dataset == 'expansionrx' else list(range(15, 20))}
            fields = [row['field'] for row in panel['tasks'] if row['dataset_id'] == dataset]
            return {'tasks': fields, 'output_level': 'atom' if dataset == 'cyp_isoform' else 'graph',
                    'member_indices': members, 'ordered_members': {
                        role: [f'{dataset}:{i}' for i in ids] for role, ids in members.items()}}
        def view(self, dataset, fold, *, role):
            return self.contract(dataset, fold)['member_indices'][role]
        def get(self, *args):
            raise AssertionError('Metadata preparation must not decode labels')
        def native_geometry_metadata(self, dataset, member_index):
            return {'dataset_id': dataset, 'member_index': member_index,
                    'member_uid': f'{dataset}:{member_index}', 'native_n_atoms': 2+member_index%3,
                    'geometry_ready': True}

    monkeypatch.setattr(store_module, 'TrainOnlyPackedStore', MetadataStore)
    monkeypatch.setattr(runner, 'ROOT', args['repository_root'])
    request, _, _, views, tasks, _ = runner.load_plan(request_path, hashlib.sha256(raw).hexdigest(), allow_unbound_packing=True)
    assert len(views) == 3 and len(tasks) == 9 and request['pretraining_seed'] == 7
    with pytest.raises(ValueError, match='metadata-planned'):
        runner.load_plan(request_path, hashlib.sha256(raw).hexdigest())
    from phychem_mfm.phase1.v3_h0_packing import packing_plans_for_views, packing_budget, canonical
    plans = packing_plans_for_views(MetadataStore('', ''), views, request['h0_packing'])
    requests['h0_packing_plan_sha256'] = {key: value['plan_sha256'] for key, value in plans.items()}
    requests['packing_binding_status'] = 'BOUND'
    bound_path = tmp_path / 'bound_request.json'; bound_raw = json.dumps(requests).encode(); bound_path.write_bytes(bound_raw)
    runner.load_plan(bound_path, hashlib.sha256(bound_raw).hexdigest())
    requests['h0_packing'] = packing_budget(max_padded_pairs=1_000_001)
    requests['h0_packing_budget_sha256'] = canonical(requests['h0_packing'])
    changed_path = tmp_path / 'drifted_request.json'; changed_raw = json.dumps(requests).encode(); changed_path.write_bytes(changed_raw)
    with pytest.raises(ValueError, match='pinned H0 packing plan differs'):
        runner.load_plan(changed_path, hashlib.sha256(changed_raw).hexdigest())
