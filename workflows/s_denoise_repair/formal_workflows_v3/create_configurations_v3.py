"""Create new v3 configurations; full variants require a passing Stage3 gate."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from prepare import ROOT,OLD,SOURCE,sha
from formal_guard_v3 import GUIDE_SHA,validate_configuration


def build(kind,seed,selected,gate=None):
    old_path=OLD/'formal_s'/('B3_seed0_v2.json')
    cfg=json.loads(old_path.read_text())
    d3_path=SOURCE/'workflows/s_denoise/configs'/(selected+'_seed'+str(seed)+'_v3.json')
    d3=json.loads(d3_path.read_text())
    cfg.update(configuration_version=3,kind=kind,seed=seed,epochs=1 if kind=='B1' else 3,
        status='FORMAL_PROTOCOL_RESOLVED_AND_FROZEN' if gate else 'DRAFT_CANDIDATE_INTERFACE_ONLY',
        model=deepcopy(d3['model']),views={**cfg['views'],'noise_seed_includes_epoch':True},
        repair_guide_sha256=GUIDE_SHA,total_loss_scale=d3['total_loss_scale'],
        repair_source_binding=dict(path=str(ROOT/'configs/D3_source_binding_v4.json'),sha256=sha(ROOT/'configs/D3_source_binding_v4.json')),
        historical_base_configuration=dict(path=str(old_path),sha256=sha(old_path)),
        d3_selected_configuration_reference=dict(path=str(d3_path),sha256=sha(d3_path)))
    cfg['training']['optimizer']=deepcopy(d3['optimizer'])
    cfg['training']['loss_policy']=deepcopy(d3['loss_policy'])
    cfg['training']['loss_policy']['structural_tasks']=['element','denoise_eps_mse','bond_order']
    cfg['training']['loss'].update(denoise_sigma=.10,geom_angle_std_deg=0.,geom_bond_scale_std=0.)
    cfg['frozen_reference_resolution']=dict(status='REPAIR_GUIDE_EXPLICIT_OVERRIDES_OF_STAGE59',resolved=True,
        original_protocol=cfg['frozen_protocol_reference'],repair_guide_sha256=GUIDE_SHA,
        overrides=['equivariant noise head from selected D3 condition','normalized denoise_eps_mse',
            'fixed S-only task weights selected and gated in D3','epoch-hashed noise',
            'D3-selected LR with remaining optimizer unchanged','B1 two seeds x1 epoch; B3 two seeds x3 epochs',
            'directional metric-appropriate convergence; no epoch extrapolation'])
    cfg['directional_convergence_rules']=json.loads((SOURCE/'workflows/s_denoise/configs/decision_rules_v3.json').read_text())['formal_convergence']
    cfg['probe_protocol_reference']=dict(path=str(OLD/'configs/s_probe_protocol_v2.json'),sha256=sha(OLD/'configs/s_probe_protocol_v2.json'))
    cfg['expected_downstream']=dict(endpoints=12,linear_fit_cells=492,reported_task_rows=420,primary_tasks_per_endpoint=32,
        ETKDG_UFF_and_scaffold_membership_unchanged=True,remove_pretraining_overlap=False)
    if gate: cfg['stage3_gate_reference']=dict(path=str(gate),sha256=sha(gate))
    protocol=json.loads(Path(cfg['frozen_protocol_reference']['path']).read_text())
    validate_configuration(cfg,protocol,development=gate is None)
    return cfg


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--draft-group')
    parser.add_argument('--stage3-gate',type=Path)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    assert bool(args.draft_group) != bool(args.stage3_gate)
    assert args.output_dir.is_absolute() and args.output_dir.is_relative_to(ROOT)
    gate=args.stage3_gate
    if gate:
        report=json.loads(gate.read_text())
        assert report['status']=='ALL_STAGE3_GATES_PASS' and all(report['gates'].values())
        group=report['selected']
    else: group=args.draft_group
    args.output_dir.mkdir(parents=True,exist_ok=False)
    for kind in ['B1','B3']:
        for seed in [0,1]:
            cfg=build(kind,seed,group,gate)
            path=args.output_dir/(kind+'_seed'+str(seed)+'_v3.json')
            with path.open('x') as stream: json.dump(cfg,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(status='FOUR_V3_CONFIGURATIONS_CREATED',development_only=gate is None,output=str(args.output_dir))))


if __name__=='__main__':main()
