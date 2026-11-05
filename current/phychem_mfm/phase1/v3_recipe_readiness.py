"""Stage6 compiles existing rules into concrete experiments; never freezes a recipe."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction
import math
from pathlib import Path

from .v3_decision_evidence import (RunEvidence, bound_json, canonical, digest, require,
    verify_global_seed_sd, inspect_run)
from .v3_decision_rules import (RulePolicy, Stability, LR_GRID, choose_learning_rate,
    choose_batch, choose_schedule)
from .v3_proxy_plan import PlannedTrial, Evidence
from .v3_sample_budget_events import write_once, read_bound


def _policy(policy):
    require(isinstance(policy,RulePolicy), 'Fixed preregistered recipe policy required')
    p=policy.rules.get('recipe')
    require(type(p) is dict and p.get('top_two_ranking') in ('equal_mean_S_P','worst_condition')
        and p.get('top_two_tie') == 'smaller_learning_rate', 'Explicit top2/cross-S-P/tie policy required')
    return p


def _subpolicy(policy, name, value):
    rules=deepcopy(policy.rules); rules[name]=value
    return replace(policy,rules=rules)


def rank_learning_rates(measurements,noise,policy,stability,*,failure_exclusions=None):
    p=_policy(policy)
    verdict=choose_learning_rate(measurements,noise,policy,stability,failure_exclusions=failure_exclusions)
    if verdict['status'] != 'RULE_PROPOSAL': return verdict
    allowed=[r for r in LR_GRID if r not in verdict['excluded']]
    require(len(allowed) >= 2,'Fewer than two stable LR candidates; report instead of inventing a second')
    means={c:{r:sum(x.score for x in measurements[c][r])/len(measurements[c][r]) for r in allowed} for c in ('S','P')}
    ranking={r:(sum(means[c][r] for c in means)/2 if p['top_two_ranking'] == 'equal_mean_S_P'
                 else min(means[c][r] for c in means)) for r in allowed}
    top=sorted(allowed,key=lambda r:(-ranking[r],float(r)))[:2]
    return {'schema':'model_v3_recipe_LR_scan_proposal_v1','status':'PROPOSED_NOT_FROZEN',
        'top_two':top,'ranking':ranking,'common_learning_rate':verdict['selected'],
        'decision':verdict,'policy_sha256':policy.sha256,'frozen':False}


def joint_lr_batch(initial,doubled,noise,policy,stability,*,doubled_stability,failure_exclusions=None):
    first=rank_learning_rates(initial,noise,policy,stability,failure_exclusions=failure_exclusions)
    require(first['status'] == 'PROPOSED_NOT_FROZEN','Closed initial LR scan required')
    top=first['top_two']
    require(set(doubled) == {'S','P'} and all(set(doubled[c]) == set(top) for c in doubled),
            'Exactly top2 x S/P doubled-batch measurements required')
    batches={}; merged=deepcopy(initial); merged_stability=deepcopy(stability)
    for lr in top:
        rule=policy.rules.get('batch_by_lr',{}).get(lr)
        require(type(rule) is dict,'Registered per-LR B0/2B0 identities required')
        rows={c:{'B0':initial[c][lr],'2B0':doubled[c][lr]} for c in ('S','P')}
        verdict=choose_batch(rows,noise,_subpolicy(policy,'batch',rule))
        require(verdict['status'] == 'RULE_PROPOSAL','Complete batch comparison required')
        batches[lr]=verdict
        if verdict['selected'] == '2B0':
            for c in ('S','P'):
                merged[c][lr]=doubled[c][lr]; merged_stability[c][lr]=doubled_stability[c][lr]
    rule=deepcopy(policy.rules['learning_rate'])
    for lr in top:
        for c in ('S','P'):
            rule['scientific_identities'][c][lr]=policy.rules['batch_by_lr'][lr]['scientific_identities'][c][batches[lr]['selected']]
    # Same LR rule, full five-rate grid; only measured retained B changes.
    verdict=choose_learning_rate(merged,noise,_subpolicy(policy,'learning_rate',rule),merged_stability,failure_exclusions=failure_exclusions)
    # A changed retained run needs its own bound numeric stability observation.
    return {'schema':'model_v3_recipe_joint_LR_batch_proposal_v1','status':verdict['status'],
        'selected_learning_rate':verdict.get('selected'),
        'selected_batch':batches.get(verdict.get('selected'),{}).get('selected','B0'),
        'initial_scan':first,'batch_decisions':batches,'decision':verdict,'frozen':False}


def select_schedule(measurements,noise,policy):
    return choose_schedule(measurements,noise,policy)


def inspect_measurements(entries,*,panel_reference,preregistration_commit):
    require(type(entries) is dict and entries,'Explicit source-bound measurement matrix required')
    return {c:{name:[inspect_run(e,panel_reference=panel_reference,
            preregistration_commit=preregistration_commit) for e in rows]
            for name,rows in names.items()} for c,names in entries.items()}


def _concrete(value):
    if isinstance(value,dict):
        for v in value.values(): _concrete(v)
    elif isinstance(value,(list,tuple)):
        for v in value: _concrete(v)
    elif isinstance(value,str):
        require(not value.startswith('$'),'Unresolved experiment placeholder')


def _fraction_samples(total,fraction):
    require(type(fraction) in (int,float) and math.isfinite(fraction) and 0 <= fraction < 1,
            'Explicit finite scheduler fraction required')
    f=Fraction(str(fraction))
    return total*f.numerator//f.denominator


def compile_trial(trial,template,resolutions,policy):
    """Pure configuration compilation; final data/Root admission happens separately.

    Operational receipt paths/reservations belong to the request, not recipe
    identity. The inherited source/config/data identities are never fabricated.
    """
    require(isinstance(trial,PlannedTrial) and trial.stage == 6,'Registered stage6 PlannedTrial required')
    p=_policy(policy); config=deepcopy(template)
    require({'model_sha256','B0','sample_budget','warmup_fraction','wsd_decay_fraction','minimum_lr_ratio','evidence_sha256'} <= set(p), 'Complete registered recipe compilation policy required')
    require(trial.condition in ('S','P','SDP'),'Stage6 scan has S/P or SDP confirmation only')
    require(config.get('engineering_only') is False and config['model']['backbone']['dim'] == 512
        and config['model']['backbone']['layers'] == 6,'Scientific recipe keeps the selected 6x512 architecture')
    require(canonical(config['model']) == p['model_sha256'],'Template differs from preregistered selected model')
    require(type(p['B0']) is int and p['B0'] > 0 and trial.sample_budget == p['sample_budget']
        == config['proxy_contract']['sample_budget'],'Registered scan budget and B0 required; 6M is not automatic')
    params=dict(trial.parameters)
    replacements={
        '$top_two_LR_rank1':float(resolutions['top_two'][0]) if 'top_two' in resolutions else None,
        '$top_two_LR_rank2':float(resolutions['top_two'][1]) if 'top_two' in resolutions else None,
        '$common_selected_LR':resolutions.get('learning_rate'),
        '$selected_batch':resolutions.get('batch_base_samples'),
        '$selected_schedule':resolutions.get('schedule'),
        '$TRAIN_preclip_p99':resolutions.get('clip_norm')}
    for key,value in list(params.items()):
        if isinstance(value,str) and value.startswith('$'):
            require(value in replacements and replacements[value] is not None,'Missing closed selection dependency: '+value)
            params[key]=replacements[value]
    lr=params.get('learning_rate'); batch=params.get('batch_base_samples')
    require(type(lr) in (int,float) and math.isfinite(lr) and float(lr) in tuple(map(float,LR_GRID))
        and type(batch) is int and batch in (p['B0'],2*p['B0']),'Concrete scanned LR/batch required')
    # Evidence references must be real bounded source documents, not just labels.
    for key in ('selected_backbone','budget_evidence','rules_evidence'):
        ref=params.get(key); require(type(ref) is dict,'Bound selected model/budget/rules required')
        require(ref['sha256'] == p['evidence_sha256'].get(key),'Plan evidence differs from preregistered model/budget/rules')
        bound_json(ref)
    c=config['proxy_contract']; require(c['sampler'] == {'selection':{'mode':'all','k':None},'geometry_source':'PM7'},
        'Recipe scan preserves PM7/all authorized conformations')
    c['groups']={'S':['S'],'P':['P'],'SDP':['S','D','P']}[trial.condition]
    c['optimizer']['lr']=float(lr); c['batch_limits']['max_molecules']=batch
    # All throughput atom/padded capacities remain from the accepted template.
    if trial.condition == 'SDP':
        require('clip_norm' in params,'SDP requires the actual selected TRAIN p99')
        c['clip_norm']=params['clip_norm']
    else:
        require(params.get('clip_norm',c['clip_norm']) == c['clip_norm'], 'LR/B/schedule scans retain the common base clip; p99 applies only to SDP')
    require(type(c['clip_norm']) in (int,float) and math.isfinite(c['clip_norm']) and c['clip_norm'] > 0,'Positive source-bound clip threshold required')
    require(type(params['schedule']) is str,'Concrete scheduler name required')
    mode=params['schedule'].lower(); require(mode in ('cosine','wsd'),'Concrete supported scheduler required')
    require(type(p['minimum_lr_ratio']) in (int,float) and math.isfinite(p['minimum_lr_ratio']) and 0 <= p['minimum_lr_ratio'] <= 1,'Explicit finite LR floor required')
    warmup=_fraction_samples(trial.sample_budget,p['warmup_fraction'])
    start=None
    if mode == 'wsd':
        fraction=p['wsd_decay_fraction']; require(type(fraction) in (int,float) and .1 <= fraction <= .2,'Preregistered WSD final10-20percent required')
        decay=_fraction_samples(trial.sample_budget,fraction); require(decay > 0,'Nonempty WSD decay required')
        start=trial.sample_budget-decay; require(start >= warmup,'WSD stable window invalid')
    c['schedule']={'mode':mode,'warmup_samples':warmup,'decay_start_samples':start,
                   'minimum_ratio':p['minimum_lr_ratio']}
    config['seed']=trial.pretraining_seed; config['experiment_scope']='RECIPE_SCAN_PROPOSAL'
    _concrete(config)
    return config


def prepare_trial(trial,base_request,resolutions,policy,output,*,base_request_ref):
    """Write a fresh complete config + explicit UNADMITTED successor; no jobs."""
    from .v3_proxy_run import validate_request,bind_inputs
    require(bound_json(base_request_ref) == base_request,'Preparation base request raw binding differs')
    require(base_request.get('mode') == 'authoritative_proxy','Recipe compilation retains the original D5 proxy route')
    template,_,_=validate_request(base_request,input_kind='authoritative_proxy')
    inputs=bind_inputs(base_request,template)
    inputs.provider.close()
    if any(key in trial.requires for key in ('LR_first_scan_closed','LR_and_batch_consensus_closed','schedule_selection_closed')):
        require(type(resolutions.get('inputs')) is dict,'Actual bound selection inputs required')
        actual=resolve_inputs(resolutions['inputs'],policy)
        require(actual == resolutions,'Selection resolution differs from its actual closed sources')
    config=compile_trial(trial,template,resolutions,policy)
    root=Path(output); require(not root.exists(),'Fresh preparation directory required')
    root.mkdir(parents=True)
    cfg=write_once(root/'configuration.json',config)
    request=deepcopy(base_request); request.update(configuration=cfg,scope='recipe',registrations={},Root_admission=None)
    request['recipe_preparation']={'trial':asdict(trial),'base_request':base_request_ref,
        'resolution_inputs':resolutions.get('inputs'),'resolutions_sha256':canonical(resolutions),
        'policy_sha256':policy.sha256,'policy_reference':policy.reference,'frozen':False}
    _concrete(request)
    request.pop('long_run',None)  # Fresh seed-specific reservation/admission comes only at final binding.
    req=write_once(root/'request.UNADMITTED.json',request)
    return write_once(root/'PREPARED.json',{'schema':'model_v3_recipe_prepared_v1',
        'status':'CONFIG_CONCRETE_AWAITING_REGISTRATION_AND_ROOT_ADMISSION','configuration':cfg,'request':req,
        'configuration_identity_sha256':__import__('phychem_mfm.phase1.v3_proxy_run',fromlist=['identity']).identity(config),
        'required_actual_gates':['final D1-D5 and exact adapter','registered rules/budget/validation/recipe',
        'Root source/resource/quota admission','actual Slurm/supervisor/SDK closure'],'frozen':False})


def finalize_request(candidate,registrations,admission,output,*,operational=None):
    """The same real runner validators + adapter are the final admission gate."""
    from .v3_proxy_run import validate_request,bind_inputs
    request=deepcopy(bound_json(candidate)); request.update(registrations=registrations,Root_admission=admission)
    if operational is not None:
        require(type(operational) is dict and set(operational) == {'long_run'},'Only seed-specific durable operational refs may be added')
        request.update(deepcopy(operational))
    _concrete(request)
    kind=request['mode']; config,_,_=validate_request(request,input_kind=kind)
    inputs=bind_inputs(request,config)
    try: return write_once(output,request)
    finally: inputs.provider.close()


def full_convergence_configuration(template,recipe,full_train_contract,resource_contract,*,condition,policy):
    """D6 full TRAIN uses a new population contract, not a larger proxy budget."""
    from .v3_full_training import FULL_MILESTONES, validate_full_contract
    require(condition in ('S','P') and recipe.get('status') == 'PROPOSED_CONFIRMATION'
        and recipe.get('frozen') is False,'Closed selected recipe/SDP proposal required before full curves')
    require(canonical(template['model']) == _policy(policy)['model_sha256'],'Full recipe model differs from selected architecture')
    config=deepcopy(template); c=config['proxy_contract']
    c['groups']=[condition]; c['sample_budget']=FULL_MILESTONES[-1]; c['milestones']=list(FULL_MILESTONES)
    c['sample_plan'].update(sample_budget=FULL_MILESTONES[-1],panel_samples=list(FULL_MILESTONES),validation_samples=list(FULL_MILESTONES))
    config.update(full_train_contract=deepcopy(full_train_contract),full_resource_contract=deepcopy(resource_contract),
        experiment_scope='FULL_TRAIN_CONVERGENCE_PROPOSAL',engineering_only=False)
    # Explicit policy supplies the new full-data sample clock, never old proxy boundaries.
    p=policy.rules.get('full_convergence')
    require(type(p) is dict and p['maximum_samples'] == FULL_MILESTONES[-1]
        and p['recipe_configuration_sha256'] == canonical(template),'Registered full-data recipe/cap required')
    c['schedule']=deepcopy(p['schedule']); c['sample_plan']['max_total_checkpoints']=p['max_total_checkpoints']
    c['sample_plan']['recovery_interval_samples']=p['recovery_interval_samples']
    validate_full_contract(config); _concrete(config)
    return config


def resolve_inputs(reference,policy):
    """Recompute choices from closed panel + scalar logs, never trust result booleans."""
    from .v3_recipe_evidence import classify_stability,gradient_p99
    m=bound_json(reference)
    require(m.get('schema') == 'model_v3_recipe_resolution_inputs_v1'
        and m['policy_sha256'] == policy.sha256,'Bound resolution manifest/policy required')
    noise=verify_global_seed_sd(m['global_seed_sd'])
    def inspect(entries):
        return inspect_measurements(entries,panel_reference=m['panel'],preregistration_commit=m['panel_preregistration_commit'])
    def verdicts(rows):
        result={}
        for condition,names in rows.items():
            result[condition]={}
            for name,runs in names.items():
                if not runs: continue  # only a separately verified failed attempt may lack a panel
                items=[classify_stability(bound_json(m['logs'][r.training_run_id]),policy,run=r) for r in runs]
                require(canonical(policy.rules['stability']) == canonical(policy.rules['learning_rate']['loss_spike_policy']),
                    'LR and numeric classifier use one exact preregistered policy')
                result[condition][name]=Stability(any(i['stability']['diverged'] for i in items),
                    any(i['stability']['loss_spike'] for i in items),canonical(items),canonical(policy.rules['stability']),
                    tuple(sorted(r.training_run_id for r in runs)))
        return result
    first=inspect(m['initial']); common=verify_scan_contracts(first,policy,phase='initial'); stable=verdicts(first)
    initial=rank_learning_rates(first,noise,policy,stable,failure_exclusions=m.get('failed_attempts'))
    require(initial['status'] == 'PROPOSED_NOT_FROZEN','Initial scan not eligible for successor requests')
    out={'schema':'model_v3_recipe_resolutions_v1','inputs':reference,'policy_sha256':policy.sha256,
         'top_two':initial['top_two'],'learning_rate':float(initial['common_learning_rate']),
         'batch_base_samples':_policy(policy)['B0'],'initial':initial,'frozen':False}
    retained=first
    if 'doubled' in m:
        doubled=inspect(m['doubled'])
        verify_scan_contracts(doubled,policy,phase='doubled',baseline=common)
        joint=joint_lr_batch(first,doubled,noise,policy,stable,doubled_stability=verdicts(doubled),failure_exclusions=m.get('failed_attempts'))
        require(joint['status'] == 'RULE_PROPOSAL','LR/batch consensus requires report; no successor admitted')
        lr=joint['selected_learning_rate']; batch=joint['selected_batch']
        out.update(learning_rate=float(lr),batch_base_samples=_policy(policy)['B0']*(2 if batch == '2B0' else 1),joint=joint)
        retained={c:{**first[c],**{r:doubled[c][r] for r,v in joint['batch_decisions'].items() if v['selected']=='2B0'}} for c in ('S','P')}
        condition=_policy(policy)['clip_source_condition']
        require(condition in ('S','P'),'Explicit selected-LR clip source condition required')
        runs=retained[condition][lr]
        require(len(runs) == 1,'Clip source seed/run must be explicit, not silently pooled')
        run=runs[0]
        p99=gradient_p99(bound_json(m['logs'][run.training_run_id]),policy,run=run)
        out.update(clip_norm=p99['p99'],clip_evidence=p99)
    if 'schedules' in m:
        require('joint' in out,'Schedule results require the complete LR x B comparison')
        schedules=inspect(m['schedules'])
        verify_scan_contracts(schedules,policy,phase='schedule',expected_lrs=out['learning_rate'],expected_batch=out['batch_base_samples'],baseline=common)
        decision=select_schedule(schedules,noise,policy)
        require(decision['status'] == 'RULE_PROPOSAL','Schedule conflict requires report')
        out.update(schedule=decision['selected'],schedule_evidence=decision)
    return out


def prepare_full(template,recipe_confirmation,full_contract,resource_contract,policy,base_request,
                 *,condition,adapter,input_projection,output):
    """Build the explicit new D6 successor, pending its own registration/admission."""
    confirmation=verify_sdp_artifact(recipe_confirmation,policy)
    require(confirmation.get('schema') == 'model_v3_SDP_recipe_confirmation_proposal_v1'
        and confirmation['status'] == 'PROPOSED_CONFIRMATION','Bound actual SDP confirmation required')
    origin=bound_json(confirmation['input_manifest'])
    measured=bound_json(origin['run']['request'])['model_configuration']
    require(base_request['configuration'] == measured and canonical(template) == canonical(bound_json(measured)), 'Full-data template differs from the actually confirmed SDP recipe')
    config=full_convergence_configuration(template,confirmation,full_contract,resource_contract,
        condition=condition,policy=policy)
    config['input_projection_sha256']=canonical(input_projection)
    bound_json(full_contract['release_evidence'])
    from .v3_decision_evidence import bound_bytes
    bound_bytes(adapter)
    root=Path(output); require(not root.exists(),'Fresh full-data preparation required'); root.mkdir(parents=True)
    cfg=write_once(root/'configuration.json',config)
    req=deepcopy(base_request); req.update(mode='authoritative_full_train',scope='full_convergence',
        configuration=cfg,adapter=adapter,input_projection=input_projection,registrations={},Root_admission=None)
    req.pop('long_run',None)
    req['recipe_preparation']={'SDP_confirmation':recipe_confirmation,'policy_sha256':policy.sha256,
        'policy_reference':policy.reference,'data_authority_asserted':False}
    _concrete(req)
    return write_once(root/'request.UNADMITTED.json',req)


def verify_sdp_artifact(reference,policy):
    from .v3_recipe_evidence import confirm_sdp
    artifact=bound_json(reference); manifest_ref=artifact['input_manifest']; m=bound_json(manifest_ref)
    require(m['policy_sha256'] == policy.sha256,'SDP artifact numeric policy differs')
    run=inspect_run(m['run'],panel_reference=m['panel'],preregistration_commit=m['panel_preregistration_commit'])
    verify_sdp_selected(run,m['training_request'],policy)
    actual=confirm_sdp(bound_json(m['logs']),policy,run=run); actual['input_manifest']=manifest_ref
    require(actual == artifact,'Saved SDP confirmation differs from its closed source observations')
    return actual


def verify_scan_contracts(rows,policy,*,phase,expected_lrs=None,expected_batch=None,baseline=None):
    """Compare actual producer configs, not candidate names alone."""
    p=_policy(policy); common=baseline
    for condition,names in rows.items():
        require(condition in ('S','P'),'Recipe scan condition differs')
        for name,runs in names.items():
            for run in runs:
                req=bound_json(run.sources['request']); config=bound_json(req['model_configuration'])
                c=config['proxy_contract']
                require(c['groups'] == [condition] and c['sample_budget'] == p['sample_budget']
                    and run.checkpoint_samples == p['sample_budget'] and canonical(config['model']) == p['model_sha256'],
                    'Scan must complete the same registered model/budget/condition')
                lr=float(name) if phase != 'schedule' else expected_lrs
                batch=p['B0']*(2 if phase == 'doubled' else 1) if phase != 'schedule' else expected_batch
                require(c['optimizer']['lr'] == lr and c['batch_limits']['max_molecules'] == batch,
                    'Actual scanned LR or B differs from candidate label')
                mode=name if phase == 'schedule' else 'cosine'
                require(c['schedule']['mode'] == mode and c['schedule']['warmup_samples'] == _fraction_samples(p['sample_budget'],p['warmup_fraction']),
                    'Actual schedule/warmup differs from preregistered scan')
                expected_start=(p['sample_budget']-_fraction_samples(p['sample_budget'],p['wsd_decay_fraction'])) if mode == 'wsd' else None
                require(c['schedule']['decay_start_samples'] == expected_start
                    and c['schedule']['minimum_ratio'] == p['minimum_lr_ratio'],'Actual decay boundary/floor differs')
                projected=deepcopy(config);projected.pop('seed')
                pc=projected['proxy_contract'];pc.pop('groups');pc.pop('schedule')
                pc['optimizer'].pop('lr');pc['batch_limits'].pop('max_molecules')
                value=canonical(projected)
                if common is None: common=value
                require(value == common,'Scan changed an unscanned model/data/recipe/source/validation parameter')
    return common


def verify_sdp_selected(run,training_request,policy):
    """The confirmed SDP run must implement the actual preceding scan choices."""
    request=bound_json(training_request)
    require(request['mode'] == 'authoritative_proxy' and request['scope'] == 'recipe'
        and request['configuration'] == bound_json(run.sources['request'])['model_configuration'],
        'SDP confirmation must bind its real recipe training request/configuration')
    prep=request['recipe_preparation']; raw=prep['trial']
    trial=PlannedTrial(**{**raw,'parameters':tuple(tuple(x) for x in raw['parameters']),'requires':tuple(raw['requires'])})
    require(trial.condition == 'SDP' and trial.stage == 6,'SDP confirmation cannot use a different stage/condition')
    resolutions=resolve_inputs(prep['resolution_inputs'],policy)
    require('schedule' in resolutions and 'clip_norm' in resolutions
        and prep['resolutions_sha256'] == canonical(resolutions),'Full scan/schedule/clip choices missing from SDP provenance')
    base=bound_json(prep['base_request']); template=bound_json(base['configuration'])
    expected=compile_trial(trial,template,resolutions,policy)
    require(canonical(expected) == canonical(bound_json(request['configuration'])),
        'Actual SDP model/recipe differs from source-bound selected configuration')
    return expected
