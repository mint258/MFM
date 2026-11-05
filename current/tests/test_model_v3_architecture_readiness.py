"""Stage5 metadata compiler only; all synthetic evidence is explicitly unadmitted."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import json
import pytest
from phychem_mfm.phase1.v3_contract import FieldSpec,LabelRegistry
from phychem_mfm.phase1.v3_decision_evidence import canonical
from phychem_mfm.phase1.v3_decision_rules import RulePolicy
from phychem_mfm.phase1.v3_proxy_plan import Evidence,architecture_plan
from phychem_mfm.phase1.v3_sample_budget_events import read_bound,write_once
from phychem_mfm.phase1 import v3_architecture_readiness as readiness


def registry():
    return LabelRegistry((FieldSpec('p_extensive','P','unit','graph',pooling='sum'),
        FieldSpec('p_intensive','P','unit','graph',pooling='mean'),
        FieldSpec('d_intensive','D','unit','graph',pooling='mean'),
        FieldSpec('p_dipole','P','unit','graph',representation='vector')),
        'stage5_synthetic_metadata_only','1'*64)


@pytest.fixture
def setup(tmp_path):
    from phychem_mfm.phase1.v3_proxy_run import engineering_request
    ref=engineering_request(tmp_path/'engineering_metadata',code_sha='a'*40,layers=6,budget=100,seed=0)
    request=read_bound(ref);cfg=read_bound(request['configuration'])
    cfg['engineering_only']=False  # Pure compiler fixture, not actual authoritative input.
    evidence=write_once(tmp_path/'unit_evidence.json',{'scope':'SYNTHETIC_NO_DATA_BUDGET_OR_SELECTION_AUTHORITY'})
    e=Evidence(evidence['path'],evidence['sha256'])
    trials=architecture_plan(sample_budget=100,batch_base_samples=2,budget_evidence=e,rules_evidence=e)
    rules={'architecture':dict(template_configuration_sha256=canonical(cfg),B0=2,sample_budget=100,
        common_head='H1',evidence_sha256=dict(budget_evidence=e.sha256,rules_evidence=e.sha256))}
    policy=RulePolicy(rules,'b'*64,'a'*40,0,None)
    resolutions={'inputs':evidence,'policy_sha256':policy.sha256,
        'C1':dict(status='RULE_PROPOSAL',selected='C1-b',policy_sha256=policy.sha256),
        'C3':dict(status='RULE_PROPOSAL',selected='two',policy_sha256=policy.sha256)}
    return request,cfg,policy,trials,resolutions,ref


def test_all20_trials_have_real_concrete_distance_views_heads_and_C_flag(setup):
    _,cfg,policy,trials,resolutions,_=setup
    before=deepcopy(cfg);reg=registry();reg_sha=reg.content_sha256
    assert len(trials)==20 and all(dict(t.parameters)['distance_bias_projection_bias'] is False for t in trials)
    for trial in trials:
        out=readiness.compile_trial(trial,cfg,resolutions,policy,registry=reg);c=out['proxy_contract']
        assert '$' not in json.dumps(out) and out['model']['backbone']['distance_bias_projection_bias'] is False
        assert out['model']['backbone']['layers']==6 and out['model']['backbone']['dim']==512
        assert out['model']['head']==cfg['model']['head']
        assert c['views']==c['validation']['views'] and c['sampler']==cfg['proxy_contract']['sampler']
        assert c['sample_budget']==100 and c['schedule']['warmup_samples']==2
        assert c['optimizer']['lr']==3e-4 and c['optimizer']['betas']==[.9,.95] and c['clip_norm']==1.
        assert out['engineering_only'] is False and out['seed']==0
        if trial.name=='H_H1_P_learned_pooling':
            assert c['heads']['forms']=='H1'
            assert c['heads']['pooling_overrides']=={'p_extensive':'learned','p_intensive':'learned'}
        else:assert 'pooling_overrides' not in c['heads']
        if trial.name.startswith('C1_'):
            assert c['views']=='three' and c['heads']['forms']=='H1'
        else:
            assert out['model']['backbone']['v3_architecture']['distance_bias']=='C1-b'
    assert cfg==before and reg.content_sha256==reg_sha and reg.by_name()['p_extensive'].pooling=='sum'


def test_missing_or_forged_selection_never_becomes_a_concrete_successor(setup):
    _,cfg,p,trials,resolutions,_=setup
    for value in ({},{'inputs':resolutions['inputs'],'C1':{'status':'PASS','selected':'C1-a','policy_sha256':p.sha256}},
                  {**resolutions,'C1':{**resolutions['C1'],'policy_sha256':'c'*64}}):
        with pytest.raises(ValueError,match='selection'):readiness.compile_trial(trials[6],cfg,value,p,registry=registry())
    with pytest.raises(ValueError):
        readiness.compile_trial(replace(trials[0],name='not_a_registered_trial'),cfg,resolutions,p,registry=registry())
    with pytest.raises(ValueError):
        readiness.compile_trial(replace(trials[0],pretraining_seed=1),cfg,resolutions,p,registry=registry())


@pytest.mark.parametrize('fault',('bias_true','budget','extra_parameter','engineering','optimized'))
def test_template_and_trial_cannot_escape_fixed_C_only_scope(setup,fault):
    _,cfg,p,trials,resolutions,_=setup;trial=trials[0];template=deepcopy(cfg)
    if fault=='bias_true':
        params=dict(trial.parameters);params['distance_bias_projection_bias']=True
        trial=replace(trial,parameters=tuple(sorted(params.items())))
    elif fault=='budget':trial=replace(trial,sample_budget=101)
    elif fault=='extra_parameter':
        trial=replace(trial,parameters=tuple(sorted((*trial.parameters,('arbitrary_scale',.1)))))
    elif fault=='engineering':
        template['engineering_only']=True
        p=replace(p,rules={'architecture':{**p.rules['architecture'],'template_configuration_sha256':canonical(template)}})
    else:
        template['training_execution']={'options':{}}
        p=replace(p,rules={'architecture':{**p.rules['architecture'],'template_configuration_sha256':canonical(template)}})
    with pytest.raises(ValueError):readiness.compile_trial(trial,template,resolutions,p,registry=registry())


def test_prepare_refuses_synthetic_and_full_scope_without_output(setup,tmp_path):
    request,_,p,trials,resolutions,ref=setup
    with pytest.raises(ValueError,match='authoritative'):
        readiness.prepare_trial(trials[0],request,resolutions,p,tmp_path/'not_written',base_request_ref=ref)
    assert not (tmp_path/'not_written').exists()


def test_prepare_keeps_real_data_gate_and_recomputes_selection_before_writing(setup,tmp_path,monkeypatch):
    from phychem_mfm.phase1 import v3_proxy_run as proxy
    request,cfg,p,trials,resolutions,_=setup
    request=deepcopy(request);request['mode']='authoritative_proxy'
    ref=write_once(tmp_path/'authoritative_transport_UNIT_NOT_AUTHORITY.json',request)
    p=replace(p,reference={'fixture':'not_real_Git'})
    monkeypatch.setattr(readiness,'registered_policy',lambda reference,expected_sha256:p)
    def refuse(*args,**kwargs):raise ValueError('Real D1 D3 D5 and Root gate refused')
    monkeypatch.setattr(proxy,'validate_request',refuse)
    with pytest.raises(ValueError,match='Real D1'):
        readiness.prepare_trial(trials[0],request,{},p,tmp_path/'data_gate',base_request_ref=ref)
    assert not (tmp_path/'data_gate').exists()
    monkeypatch.setattr(proxy,'validate_request',lambda *a,**k:(cfg,None,None))
    closed=[]
    class Index:
        role='TRAIN'
        def __len__(self):return 240000
    monkeypatch.setattr(proxy,'bind_inputs',lambda *a:SimpleNamespace(index=Index(),registry=registry(),
        provider=SimpleNamespace(close=lambda:closed.append(True))))
    monkeypatch.setattr(readiness,'resolve_inputs',lambda *a:{'different':'actual evidence'})
    with pytest.raises(ValueError,match='Selection differs'):
        readiness.prepare_trial(trials[6],request,resolutions,p,tmp_path/'selection_gate',base_request_ref=ref)
    assert closed==[True] and not (tmp_path/'selection_gate').exists()


def test_preparation_is_only_UNADMITTED_not_a_new_F32_or_data_certificate(setup,tmp_path,monkeypatch):
    from phychem_mfm.phase1 import v3_proxy_run as proxy
    request,cfg,p,trials,_,_=setup;request=deepcopy(request);request['mode']='authoritative_proxy'
    ref=write_once(tmp_path/'transport_UNIT.json',request);p=replace(p,reference={'fixture':'not_real_Git'})
    monkeypatch.setattr(readiness,'registered_policy',lambda reference,expected_sha256:p)
    monkeypatch.setattr(proxy,'validate_request',lambda *a,**k:(cfg,None,None))
    class Index:
        role='TRAIN'
        def __len__(self):return 240000
    monkeypatch.setattr(proxy,'bind_inputs',lambda *a:SimpleNamespace(index=Index(),registry=registry(),
        provider=SimpleNamespace(close=lambda:None)))
    prepared=read_bound(readiness.prepare_trial(trials[0],request,{},p,tmp_path/'proposal',base_request_ref=ref))
    result=read_bound(prepared['request']);config=read_bound(prepared['configuration'])
    assert prepared['status']=='CONFIG_CONCRETE_UNADMITTED' and prepared['no_scientific_acceptance_or_freeze'] is True
    assert result['registrations']=={} and result['Root_admission'] is None and result['scope']=='comparison'
    assert '$' not in json.dumps(result) and config['model']['backbone']['distance_bias_projection_bias'] is False


def test_resolution_transport_rejects_unknown_schema_or_stale_policy(setup,tmp_path):
    _,_,p,_,_,_=setup
    for body in ({'schema':'UNKNOWN','policy_sha256':p.sha256},
                 {'schema':'model_v3_architecture_resolution_inputs_v1','policy_sha256':'c'*64}):
        path=tmp_path/('bad_'+str(len(list(tmp_path.glob('bad*'))))+'.json')
        with pytest.raises(ValueError):readiness.resolve_inputs(write_once(path,body),p)
