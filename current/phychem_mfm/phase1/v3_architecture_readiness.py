"""Concrete stage5 proposals on the original C backbone, never scientific admission.

Reuses the existing inspected-run, one-SD/timing/auxiliary rules and actual proxy
request/CP/H0 route. Metadata compilation neither certifies data nor grants an
FP32 pass. No compensated numeric or checkpoint helper is imported.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import math

from .v3_contract import LabelRegistry
from .v3_decision_evidence import bound_json,canonical,digest,require,verify_global_seed_sd
from .v3_decision_rules import RulePolicy,Timing,AuxiliaryMetric,choose_c1,choose_c3,registered_policy
from .v3_proxy_plan import PlannedTrial,Evidence,architecture_plan
from .v3_recipe_readiness import inspect_measurements,_concrete,_fraction_samples
from .v3_sample_budget_events import write_once
from ..model.v3_architecture import ArchitectureOptions,source_s_architecture_configuration

BIAS='distance_bias_projection_bias'


def _policy(policy):
    require(isinstance(policy,RulePolicy),'Source-bound preregistered rule policy required')
    p=policy.rules.get('architecture')
    require(type(p) is dict and {'template_configuration_sha256','B0','sample_budget',
        'common_head','evidence_sha256'} <= set(p),'Complete fixed stage5 compilation policy required')
    digest(p['template_configuration_sha256'])
    require(type(p['B0']) is int and p['B0']>0 and type(p['sample_budget']) is int
        and p['sample_budget']>0,'Positive fixed B0 and actual selected sample budget required')
    return p


def _source_configuration(run):
    request=bound_json(run.sources['request'])
    return bound_json(request['model_configuration'])


def _check_runs(rows,*,distance,views,head):
    for condition,candidates in rows.items():
        for label,runs in candidates.items():
            for run in runs:
                cfg=_source_configuration(run);c=cfg['proxy_contract'];b=cfg['model']['backbone']
                actual=b.get('v3_architecture',{}).get('distance_bias','C1-0')
                expected=label if distance is None else distance
                expected_views=label if views is None else views
                require(b.get(BIAS) is False and actual==expected
                    and c['views']==expected_views and c['validation']['views']==expected_views
                    and c['groups']==({'S':['S'],'P':['P'],'SDP':['S','D','P']}[condition])
                    and c['heads']['forms']==head and not c['heads'].get('pooling_overrides'),
                    'Closed selection run differs in C bias/distance/views/head/condition')


def resolve_inputs(reference,policy):
    """Recompute C1/C3 choices from original closed panel/CP/execution evidence.

    Timing row files are the existing rule's three value/GPU/run-ID inputs;
    auxiliary row files contain value/population/run-IDs/scope. Their raw hashes
    become Timing/AuxiliaryMetric.source_sha256. These transport rows are not a
    new execution certificate: inspect_run and the final Root admission remain
    mandatory, and no missing observation is synthesized.
    """
    p=_policy(policy);m=bound_json(reference)
    require(m.get('schema')=='model_v3_architecture_resolution_inputs_v1'
        and m['policy_sha256']==policy.sha256,'Bound stage5 selection inputs/policy required')
    noise=verify_global_seed_sd(m['global_seed_sd'])
    def inspected(entries):
        return inspect_measurements(entries,panel_reference=m['panel'],
            preregistration_commit=m['panel_preregistration_commit'])
    result={'inputs':deepcopy(reference),'policy_sha256':policy.sha256}
    if 'C1' in m:
        source=m['C1'];rows=inspected(source['measurements'])
        _check_runs(rows,distance=None,views='three',head=p['common_head'])
        timing={}
        for condition,candidates in source['timings'].items():
            timing[condition]={}
            for candidate,ref in candidates.items():
                value=bound_json(ref)
                require(set(value)=={'seconds_per_million_samples','gpu_uuid','run_ids'}
                    and type(value['run_ids']) is list and value['run_ids']
                    and all(type(x) is str and x for x in value['run_ids']),
                    'Original source-bound timing observation required')
                timing[condition][candidate]=Timing(value['seconds_per_million_samples'],
                    value['gpu_uuid'],ref['sha256'],tuple(value['run_ids']))
        decision=choose_c1(rows,noise,policy,timing)
        require(decision['status']=='RULE_PROPOSAL','C1 selection is not closed under existing rules')
        result['C1']=decision
    if 'C3' in m:
        require('C1' in result,'C3 cannot precede the actual selected C1')
        source=m['C3'];rows=inspected(source['measurements'])
        _check_runs(rows,distance=result['C1']['selected'],views=None,head=p['common_head'])
        auxiliary={}
        for condition,candidates in source['auxiliary'].items():
            auxiliary[condition]={}
            for candidate,metrics in candidates.items():
                auxiliary[condition][candidate]={}
                for metric,ref in metrics.items():
                    value=bound_json(ref)
                    require(set(value)=={'value','population_sha256','run_ids','scope'}
                        and type(value['run_ids']) is list and value['run_ids'],
                        'Original source-bound auxiliary metric required')
                    auxiliary[condition][candidate][metric]=AuxiliaryMetric(value['value'],ref['sha256'],
                        value['population_sha256'],tuple(value['run_ids']),value['scope'])
        decision=choose_c3(rows,noise,policy,auxiliary)
        require(decision['status']=='RULE_PROPOSAL','C3 selection is not closed under existing rules')
        result['C3']=decision
    return result


def compile_trial(trial,template,resolutions,policy,*,registry):
    """Pure complete configuration proposal; data/admission gates are unchanged."""
    require(isinstance(trial,PlannedTrial) and trial.stage==5,'Original stage5 PlannedTrial required')
    require(isinstance(registry,LabelRegistry),'The actual unmodified bound label registry is required')
    p=_policy(policy);params=dict(trial.parameters)
    require(canonical(template)==p['template_configuration_sha256'],
        'Template differs from the registered common configuration')
    budget=Evidence(**params['budget_evidence']);rules=Evidence(**params['rules_evidence'])
    expected=architecture_plan(sample_budget=p['sample_budget'],batch_base_samples=p['B0'],
        budget_evidence=budget,rules_evidence=rules)
    require(trial in expected,'Only the exact original20 initial trials may compile; no arbitrary override/repeat')
    for name in ('budget_evidence','rules_evidence'):
        require(params[name]['sha256']==p['evidence_sha256'][name],
            'Trial evidence differs from the registered budget/rules')
        bound_json(params[name])
    require(params[BIAS] is False and params['proxy_molecules']==240000
        and params['geometry']=='PM7' and params['conformers']=='all_authorized_D5',
        'C keeps bias=False and the original actual240k/PM7/all-conformer proxy')
    cfg=deepcopy(template);c=cfg['proxy_contract'];model=cfg['model']
    require(cfg['engineering_only'] is False and model['backbone']['dim']==512
        and model['backbone']['layers']==6 and model['backbone'].get('heads',8)==8,
        'Scientific stage5 retains original6x512x8')
    require('training_execution' not in cfg and 'performance_execution_v1' not in model,
        'Bias-free C currently uses the original plain runtime; unsupported optimized execution is not a fallback')
    require(c['sampler']=={'selection':{'mode':'all','k':None},'geometry_source':'PM7'}
        and c['sample_budget']==trial.sample_budget==p['sample_budget'],
        'Actual selected budget and original PM7/all sampler required')
    require(model['head']['profile']=='phase1' and model['head']['geometry_head']=='equivariant_noise'
        and not model['backbone'].get('use_radius_mask',False),
        'The original A4 head/global attention architecture must remain fixed')
    def selected(name,allowed):
        value=resolutions.get(name)
        require(type(value) is dict and value.get('status')=='RULE_PROPOSAL'
            and value.get('policy_sha256')==policy.sha256 and value.get('selected') in allowed
            and type(resolutions.get('inputs')) is dict,
            'Missing closed source-bound selection dependency: '+name)
        return value['selected']
    distance=params['distance_bias']
    if distance=='$selected_C1':distance=selected('C1',('C1-0','C1-a','C1-b'))
    require(distance in ('C1-0','C1-a','C1-b'),'Concrete original C1 distance architecture required')
    views=params['views']
    if views=='$selected_C3':views=selected('C3',('two','three'))
    if type(views) is int:views={2:'two',3:'three'}.get(views)
    require(views in ('two','three'),'Concrete original two/three physical view policy required')
    head=p['common_head'] if params['head']=='preregistered_common_head' else params['head']
    pd_fields={f.name for f in registry.fields if f.group!='S'}
    require((type(head) is str and head in ('H1','H2','H3')) or
        (type(head) is dict and set(head)==pd_fields and set(head.values())<={'H1','H2','H3'}),
        'One actual common/field-consistent head form required')
    model['backbone'].pop('v3_architecture',None)
    model['backbone'][BIAS]=False
    cfg['model']=source_s_architecture_configuration(model,ArchitectureOptions(distance_bias=distance))
    c['views']=views;c['validation']['views']=views
    c['groups']={'S':['S'],'P':['P'],'D':['D'],'SDP':['S','D','P']}[trial.condition]
    c['heads']['forms']=deepcopy(head);c['heads'].pop('pooling_overrides',None)
    pooling=params['pooling']
    require(pooling in ('registry_fixed','learned_mixer'),'Concrete supported pooling policy required')
    if pooling=='learned_mixer':
        require(trial.name=='H_H1_P_learned_pooling' and head=='H1' and trial.condition=='P',
            'Only the registered H1/P pooling trial may enable learned mixing')
        overrides={f.name:'learned' for f in registry.fields
            if f.group=='P' and f.level=='graph' and f.representation=='scalar'}
        require(overrides,'The unchanged registry has no P graph-scalar pooling fields')
        c['heads']['pooling_overrides']=overrides
    c['optimizer'].update(lr=params['learning_rate'],betas=deepcopy(params['adamw_betas']))
    c['clip_norm']=params['clip_norm'];c['batch_limits']['max_molecules']=p['B0']
    require(params['schedule']=='cosine','Original stage5 cosine schedule required')
    c['schedule']={'mode':'cosine','warmup_samples':_fraction_samples(trial.sample_budget,.02),
        'decay_start_samples':None,'minimum_ratio':c['schedule']['minimum_ratio']}
    cfg['seed']=trial.pretraining_seed
    cfg['experiment_scope']='ARCHITECTURE_COMPARISON_PROPOSAL'
    _concrete(cfg)
    return cfg


def prepare_trial(trial,base_request,resolutions,policy,output,*,base_request_ref):
    """Use the real admitted base; produce only a fresh UNADMITTED successor."""
    from .v3_proxy_run import validate_request,bind_inputs,identity
    require(bound_json(base_request_ref)==base_request and base_request.get('mode')=='authoritative_proxy',
        'Actual bound authoritative D5 proxy base request required')
    require(policy.reference is not None
        and registered_policy(policy.reference,expected_sha256=policy.sha256)==policy,
        'Actual registered policy bytes/Git identity required')
    template,_,_=validate_request(base_request,input_kind='authoritative_proxy')
    actual=bind_inputs(base_request,template)
    try:
        require(actual.index.role=='TRAIN' and len(actual.index)==240000,
            'Original complete authoritative D5 240k TRAIN population required')
        registry=actual.registry
    finally:actual.provider.close()
    required={'C1_selection_closed':'C1','C3_selection_closed':'C3'}
    if any(name in trial.requires for name in required):
        require(type(resolutions.get('inputs')) is dict,'Actual closed selection input reference required')
        require(resolve_inputs(resolutions['inputs'],policy)==resolutions,
            'Selection differs from its inspected actual sources/existing decision rules')
    cfg=compile_trial(trial,template,resolutions,policy,registry=registry)
    root=Path(output);require(not root.exists(),'Fresh architecture preparation directory required')
    root.mkdir(parents=True)
    cfgref=write_once(root/'configuration.json',cfg)
    request=deepcopy(base_request)
    request.update(configuration=cfgref,scope='comparison',registrations={},Root_admission=None)
    request.pop('long_run',None)
    request['architecture_preparation']={'trial_name':trial.name,
        'planned_scientific_identity_sha256':trial.scientific_identity,
        'resolved_configuration_identity_sha256':identity(cfg),
        'base_request':deepcopy(base_request_ref),'resolution_inputs':resolutions.get('inputs'),
        'resolutions_sha256':canonical(resolutions),'policy_sha256':policy.sha256,
        'policy_reference':deepcopy(policy.reference),'frozen':False}
    _concrete(request)
    reqref=write_once(root/'request.UNADMITTED.json',request)
    return write_once(root/'PREPARED.json',dict(schema='model_v3_architecture_prepared_v1',
        status='CONFIG_CONCRETE_UNADMITTED',configuration=cfgref,request=reqref,
        required_gates=['current exact source and common parameter/config/CP/H0 tests',
            'actual final D1/D2/D3/D4/D5,240k TRAIN,PM7/all and registered budget/panel/rules',
            'new FP32 physical acceptance; FP64 mathematics is not an FP32 pass',
            'fresh Root resource/quota/source admission and actual execution'],
        no_scientific_acceptance_or_freeze=True))
