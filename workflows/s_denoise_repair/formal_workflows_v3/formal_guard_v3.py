"""Explicit guide overrides and Stage-3 provenance, evaluated before CUDA."""
from copy import deepcopy
import json
from pathlib import Path
from prepare import ROOT,OLD,SOURCE,sha

GUIDE_SHA='240b7b8132603517a7640662a5ea75e67371d5633e8a3c723ab148174c0b8fa3'


def validate_configuration(cfg,protocol,*,development):
    assert cfg['configuration_version']==3 and cfg['seed'] in [0,1]
    assert cfg['variant']=='S' and cfg['dynamic_balancer_enabled'] is False
    assert cfg['kind'] in ['B1','B3'] and cfg['epochs']==(1 if cfg['kind']=='B1' else 3)
    assert cfg['train_records']==11104772 and cfg['train_molecules']==1206608
    assert sha(ROOT/'user_repair_guide.md')==cfg['repair_guide_sha256']==GUIDE_SHA
    assert not (ROOT/'GUIDE_STOP.json').exists(),'GUIDE_STOP_MARKER_PRESENT'
    source_ref=cfg['repair_source_binding']
    assert Path(source_ref['path'])==ROOT/'configs/D3_source_binding_v4.json'
    assert sha(source_ref['path'])==source_ref['sha256']
    binding=json.loads(Path(source_ref['path']).read_text())
    assert binding['scientific_gate_passed'] is False  # D3 source binding is historical.
    for item in binding['files']: assert sha(item['path'])==item['sha256']
    selected=cfg['d3_selected_configuration_reference']
    assert Path(selected['path']).is_relative_to(SOURCE/'workflows/s_denoise/configs')
    assert sha(selected['path'])==selected['sha256']
    d3=json.loads(Path(selected['path']).read_text())
    assert d3['model']['head']['geometry_head']=='equivariant_noise' and d3['seed']==cfg['seed']
    assert cfg['model']==d3['model']
    old_model=deepcopy(cfg['model']); old_model['head']=protocol['model']['head']
    assert old_model==protocol['model']
    expected_views={**protocol['views'],'noise_seed_includes_epoch':True}
    assert cfg['views']==expected_views and cfg['sampler']==protocol['sampler']
    expected_loader={**protocol['loader'],'worker_timeout_seconds':600.}
    assert cfg['loader']==expected_loader and cfg['validation_seed']==0
    training=cfg['training']
    assert training['optimizer']==d3['optimizer']
    old_optimizer={**training['optimizer'],'lr':protocol['training']['optimizer']['lr']}
    assert old_optimizer==protocol['training']['optimizer']
    expected_policy=deepcopy(d3['loss_policy'])
    expected_policy['structural_tasks']=['element','denoise_eps_mse','bond_order']
    assert training['loss_policy']==expected_policy
    assert training['loss_policy']['geometry_task']=='denoise_eps_mse'
    assert set(training['loss_policy']['structural_tasks'])=={'element','denoise_eps_mse','bond_order'}
    assert training['loss']=={**protocol['training']['loss'],'denoise_sigma':.10,'geom_angle_std_deg':0.,'geom_bond_scale_std':0.}
    for key in ['gradient_clip_norm','schedule','metric_interval','caps','validation']:
        assert training[key]==protocol['training'][key]
    assert cfg['total_loss_scale']==d3['total_loss_scale']==1.
    assert sha(OLD/'training_inputs_v1/manifest.json')==cfg['input_manifest_sha256']
    assert cfg['directional_convergence_rules']['epoch_extrapolation'] is False
    if development:
        assert cfg['status']=='DRAFT_CANDIDATE_INTERFACE_ONLY'
    else:
        ref=cfg['stage3_gate_reference']
        path=Path(ref['path']); assert path.is_relative_to(ROOT/'reports') and sha(path)==ref['sha256']
        gate=json.loads(path.read_text())
        assert gate['status']=='ALL_STAGE3_GATES_PASS' and gate['formal_training_authorized_by_gate'] is True
        assert set(gate['gates'])=={'denoising','gradient','interference','other_tasks','cost'} and all(gate['gates'].values())
        assert gate['guide_sha256']==GUIDE_SHA and gate['source_binding']==source_ref
        for item in gate['scientific_inputs']: assert sha(item['path'])==item['sha256']
        assert all(value[:2]==['COMPLETED','0:0'] for value in gate['actual_parents'].values())
    return d3
