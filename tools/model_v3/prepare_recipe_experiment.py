#!/usr/bin/env python3
"""Source-bound recipe preparation/decisions. Never submits, reserves or freezes."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).absolute().parents[2]
sys.path.insert(0,str(ROOT/'current'))


def main(argv=None):
    from phychem_mfm.phase1.v3_decision_evidence import bound_json,verify_global_seed_sd,inspect_run
    from phychem_mfm.phase1.v3_decision_rules import registered_policy,doubling_plateau,propose_b_star
    from phychem_mfm.phase1.v3_proxy_plan import PlannedTrial,stage_gpu_budget
    from phychem_mfm.phase1.v3_sample_budget_events import binding,write_once,require
    from phychem_mfm.phase1.v3_recipe_readiness import resolve_inputs,prepare_trial,prepare_full,finalize_request,verify_sdp_selected
    from phychem_mfm.phase1.v3_recipe_evidence import gradient_p99,classify_stability,confirm_sdp
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('resolve','prepare','full','grid','admit','p99','stability','sdp','budget'))
    parser.add_argument('--inputs',type=Path,required=True); parser.add_argument('--inputs-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    ref=binding(args.inputs); require(ref['sha256'] == args.inputs_sha256,'Exact input manifest raw SHA required')
    m=bound_json(ref)
    require(not args.output.exists() and not args.output.resolve().is_relative_to(ROOT.resolve()),'Fresh outside-Git output required')
    policy=registered_policy(m['policy'],expected_sha256=m['policy_sha256'])
    if args.command == 'resolve':
        result=resolve_inputs(m['resolution_inputs'],policy)
    elif args.command in ('p99','stability','sdp'):
        run=inspect_run(m['run'],panel_reference=m['panel'],preregistration_commit=m['panel_preregistration_commit'])
        if args.command == 'sdp': verify_sdp_selected(run,m['training_request'],policy)
        fn={'p99':gradient_p99,'stability':classify_stability,'sdp':confirm_sdp}[args.command]
        result=fn(bound_json(m['logs']),policy,run=run)
    elif args.command == 'prepare':
        raw=m['trial']; trial=PlannedTrial(**{**raw,'parameters':tuple(tuple(x) for x in raw['parameters']),'requires':tuple(raw['requires'])})
        resolutions=resolve_inputs(m['resolution_inputs'],policy) if 'resolution_inputs' in m else {}
        return prepare_trial(trial,bound_json(m['base_request']),resolutions,policy,args.output,base_request_ref=m['base_request'])
    elif args.command == 'full':
        base=bound_json(m['base_request']); template=bound_json(base['configuration'])
        return prepare_full(template,m['SDP_confirmation'],m['full_train_contract'],m['full_resource_contract'],
            policy,base,condition=m['condition'],adapter=m['adapter'],input_projection=m['input_projection'],output=args.output)
    elif args.command == 'grid':
        from phychem_mfm.phase1.v3_grid_training import prepare_grid
        return prepare_grid(bound_json(m['base_request']), m['grid_train_contract'], adapter=m['adapter'],
            input_projection=m['input_projection'], training_plan=m['training_plan'], output=args.output,
            base_request_ref=m['base_request'])
    elif args.command == 'admit':
        from phychem_mfm.phase1.v3_proxy_run import finalize_training_request
        return finalize_training_request(m['candidate'],m['registrations'],m['Root_admission'],args.output,operational=m.get('operational'))
    else:
        noise=verify_global_seed_sd(m['global_seed_sd'])
        curves={}
        for condition in ('S','P'):
            points=[(x['samples'],inspect_run(x['run'],panel_reference=m['panel'],
                preregistration_commit=m['panel_preregistration_commit'])) for x in m['curves'][condition]]
            curves[condition]=doubling_plateau(points,noise,policy=policy,condition=condition)
        result={'schema':'model_v3_recipe_budget_proposals_v1','curves':curves,
            'B_star':propose_b_star(curves['S'],curves['P']),'frozen':False}
        if 'stage_accounting' in m:
            # Root's bound complete stage attribution includes every failed attempt.
            cost=bound_json(m['stage_accounting'])
            result['stage_cost']=stage_gpu_budget(stage=6,allocated_gpu_job_seconds=cost['allocated_gpu_job_seconds'],
                all_costs_registered=cost['all_costs_registered'])
            result['stage_accounting']=m['stage_accounting']
    result['input_manifest']=ref
    return write_once(args.output,result)


if __name__ == '__main__':
    main()
