"""Engineering/source-contract fixtures only; no D5/D6 or scientific acceptance."""
from copy import deepcopy
from dataclasses import asdict, replace
import importlib.util
import json
from pathlib import Path

import pytest

from phychem_mfm.phase1.v3_contract import canonical_hash
from phychem_mfm.phase1.v3_decision_evidence import canonical
from phychem_mfm.phase1.v3_decision_rules import RulePolicy, Stability, LR_GRID
from phychem_mfm.phase1.v3_proxy_plan import Evidence,recipe_plan
from phychem_mfm.phase1.v3_sample_budget_events import binding,read_bound
from phychem_mfm.phase1.v3_recipe_evidence import gradient_p99,classify_stability,confirm_sdp
from phychem_mfm.phase1.v3_recipe_readiness import (rank_learning_rates,joint_lr_batch,compile_trial,
    finalize_request,full_convergence_configuration)
from phychem_mfm.phase1.v3_full_training import validate_full_contract,FULL_MILESTONES
from test_model_v3_decision_rules import setup,noise,measurement


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,allow_nan=False)+'\n')
    return binding(path)


def policy():
    stability={'window':2,'warmup_updates':0,'minimum_updates':3,'ratio':3.,
        'absolute_increase':2.,'baseline_floor':.01,'minimum_spikes':1,
        'numeric_failure_literals':['Nonfinite gradient before optimizer update'],
        'numeric_exception_types':['ValueError','FloatingPointError'],'numeric_failure_phases':['TRAIN_STEP','VALIDATION']}
    return RulePolicy({'stability':stability,'gradient_p99':{'population':'all_effective_TRAIN_updates','quantile':.99,'method':'linear'},
        'SDP_confirmation':{'groups':{'S':['s'],'D':['d'],'P':['p']},'minimum_observed_updates':2,
            'minimum_nonzero_probes':1,'minimum_relative_loss_improvement':.1,'validation_seed':0,'validation_epoch':0}},
        'a'*64,'b'*40,1.)


def logs(tmp_path,*,n=5,split=None,skip=(),failed=False,groups=None):
    """Synthetic producer/controller JSON, with no payload.pt created or read."""
    from phychem_mfm.phase1.v3_sample_budget_events import canonical as event_digest
    config=write(tmp_path/'configuration.json',{'seed':0,'engineering_only':False,
        'experiment_scope':'SYNTHETIC_METADATA_FIXTURE_NOT_REAL_AUTHORITY',
        'proxy_contract':{'groups':groups or ['S','D','P'],'optimizer':{'lr':.0003},'sample_budget':max(100,2*n),
            'validation':{'seed':0,'epoch':0,'population_bindings':{r:'1'*64 for r in ('VAL','TRAIN_UNSEEN_CONFORMATION')}}}})
    rows=[];updates=samples=0
    def add(row):
        row.update(log_cursor=len(rows),samples_consumed=samples,optimizer_updates=updates)
        rows.append({'step':len(rows),'commit':True,'row':row})
    def val(loss):
        for role in ('VAL','TRAIN_UNSEEN_CONFORMATION'):
            add({'event':'VALIDATION','role':role,'validation_seed':0,'validation_epoch':0,
                'population_binding_sha256':'1'*64,'input_population_sha256':'2'*64,
                'fields':{f:{'valid_labels':8,'loss':loss} for f in ('s','d','p')}})
    val(1.)
    for i in range(n):
        samples+=2;active=i not in skip;updates+=int(active)
        row={'event':'TRAIN_STEP','optimizer_updated':active,'loss/total':1.-i*.0001,
            'gradient_norm_before_clip':float(i+1) if active else None,
            **{'valid_count/'+f:int(active) for f in ('s','d','p')}}
        if active and updates % 500 == 0:row.update({'shared_gradient_norm/'+g:float(j+1) for j,g in enumerate(('S','D','P'))})
        add(row)
    val(.5)
    cuts=[0,split,len(rows)] if split is not None else [0,len(rows)]
    m={'schema':'model_v3_recipe_log_inputs_v1','training_run_id':'SYNTHETIC_METADATA_ONLY',
        'scientific_identity_sha256':'3'*64,'seed':0,'segments':[]}
    previous={'optimizer_updates':0,'samples_consumed':0,'log_cursor':0};parent=None
    for index,(a,b) in enumerate(zip(cuts,cuts[1:])):
        root=tmp_path/str(index);root.mkdir();job=str(4520000+index)
        history=root/'history.jsonl';history.write_text(''.join(json.dumps(x,allow_nan=False)+'\n' for x in rows[a:b]))
        last=rows[b-1]['row'];end={k:last[k] for k in ('optimizer_updates','samples_consumed')};end['log_cursor']=b
        request=write(root/'request.json',{'configuration':config})
        launch=write(root/'RUN_BINDING.json',{'schema':'model_v3_proxy_segment_launch_v1','job_id':job,'request':request,
            'initial_cursors':{'optimizer_updates':0,'samples_consumed':0,'log_cursor':0},'resume_complete':parent})
        term=write(root/'raw_sacct.json',{'argv':['sacct','-X','--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],
            'returncode':0,'stdout':f'{job}|zixiao|'+('FAILED|1:0' if failed else 'COMPLETED|0:0')+'|10|16|compute-0-15\n','stderr':''})
        initial={'kind':'origin','run_binding':launch} if parent is None else {'kind':'checkpoint','reference':parent,'run_binding':launch}
        if failed:
            primary={'schema':'model_v3_recipe_primary_failure_v1','job_id':job,'phase':'TRAIN_STEP',
                'type':'ValueError','message':'Nonfinite gradient before optimizer update'}
            child=write(root/'CHILD_RECEIPT.json',{'schema':'model_v3_proxy_child_receipt_v1','status':'CHILD_FAILED',
                'job_id':job,'first_failure':{k:primary[k] for k in ('type','message')},'primary_failure':primary,
                'committed_cursors':{**end,'pending_log':False}})
            final={'kind':'failed_child','reference':child,'run_binding':launch}
            m.setdefault('failure_observations',[]).append({'child_receipt':child,'run_binding':launch})
        else:
            cp=root/'checkpoint';trainer=cp/'trainer'
            payload={'path':str(trainer/'payload.pt'),'sha256':'5'*64,'bytes':17}
            bindings={'configuration_sha256':config['sha256']}
            marker=write(trainer/'COMPLETE.json',{'schema':'model_v3_training_checkpoint_v1','bindings':bindings,
                'payload_sha256':payload['sha256'],'payload_bytes':17,'samples_consumed':end['samples_consumed'],'optimizer_updates':end['optimizer_updates']})
            state={**end,'pending_log':False,'contract':{'model_configuration':config,'trainer_bindings':bindings}}
            intent=write(cp/'INTENT.json',{'schema':'model_v3_sample_checkpoint_intent_v1','state':deepcopy(state)})
            event={'checkpoint':payload,'training_completion':marker};event['event_id']=event_digest(event)
            state['event']=event
            state_ref=write(cp/'STATE.json',state)
            parent=write(cp/'EXPERIMENT_COMPLETE.json',{'schema':'model_v3_sample_experiment_checkpoint_v1',
                'state':state_ref,'trainer_marker':marker,'trainer_payload':payload,'intent':intent})
            final={'kind':'checkpoint','reference':parent}
            assert not Path(payload['path']).exists()  # the reader must remain metadata-only
        segment={'schema':'model_v3_recipe_closed_log_segment_v1','training_run_id':m['training_run_id'],
            'scientific_identity_sha256':m['scientific_identity_sha256'],'seed':0,'training_start_epoch':2.,
            'configuration':config,'initial':previous,'final':end,'history':binding(history),'terminal':term,'job_id':job,
            'initial_anchor':initial,'final_anchor':final}
        m['segments'].append(write(root/'closure.json',segment));previous=end
    return m


def set_failure(m,*,kind='ValueError',phase='TRAIN_STEP',message='Nonfinite gradient before optimizer update'):
    s=read_bound(m['segments'][0]);child=read_bound(s['final_anchor']['reference'])
    child['primary_failure'].update(type=kind,phase=phase,message=message)
    child['first_failure']={'type':kind,'message':message}
    ref=write(Path(s['final_anchor']['reference']['path']),child);s['final_anchor']['reference']=ref
    m['segments'][0]=write(Path(m['segments'][0]['path']),s)
    m['failure_observations']=[{'child_receipt':ref,'run_binding':s['initial_anchor']['run_binding']}]

def alter_row(manifest,index,change):
    s=read_bound(manifest['segments'][0]);path=Path(s['history']['path'])
    rows=[json.loads(x) for x in path.read_text().splitlines()]
    change(rows[index]);path.write_text(''.join(json.dumps(x)+'\n' for x in rows))
    s['history']=binding(path);manifest['segments'][0]=write(Path(manifest['segments'][0]['path']),s)


def test_p99_uses_effective_preclip_updates_and_resume_once(tmp_path):
    m=logs(tmp_path,n=100,split=52,skip=(0,))
    result=gradient_p99(m,policy())
    assert result['sample_count']==99 and result['p99']==pytest.approx(99.02)
    assert result['proof']['final']['optimizer_updates']==99 and not result['frozen']


@pytest.mark.parametrize('change',['duplicate','gap','nonfinite','wrongnorm','postclip','floatstep','uncommitted'])
def test_p99_rejects_corrupt_or_uncommitted_population(tmp_path,change):
    m=logs(tmp_path)
    def mutate(x):
        if change=='duplicate':x['row']['optimizer_updates']=0
        elif change=='gap':x['row']['optimizer_updates']=3
        elif change=='nonfinite':x['row']['gradient_norm_before_clip']=float('inf')
        elif change=='wrongnorm':x['row']['gradient_norm_before_clip']=None
        elif change=='postclip':x['row']['gradient_norm_after_clip']=x['row'].pop('gradient_norm_before_clip')
        elif change=='floatstep':x['step']=float(x['step'])
        else:x['commit']=False
    alter_row(m,2,mutate)
    with pytest.raises(ValueError):gradient_p99(m,policy())


def test_p99_rejects_partial_start_empty_nonzero_exit_and_missing_policy(tmp_path):
    m=logs(tmp_path/'start');s=read_bound(m['segments'][0]);s['initial']['optimizer_updates']=1
    m['segments'][0]=write(Path(m['segments'][0]['path']),s)
    with pytest.raises(ValueError,match='complete run'):gradient_p99(m,policy())
    with pytest.raises(ValueError,match='No effective'):gradient_p99(logs(tmp_path/'empty',n=0),policy())
    with pytest.raises(ValueError,match='successful'):gradient_p99(logs(tmp_path/'failed',failed=True),policy())
    p=policy();p.rules.pop('gradient_p99')
    with pytest.raises(ValueError,match='policy|preregistered'):gradient_p99(logs(tmp_path/'policy'),p)


def test_resume_overlap_or_gap_is_rejected_instead_of_dedup(tmp_path):
    m=logs(tmp_path,split=4);s=read_bound(m['segments'][1]);s['initial']['optimizer_updates']+=1
    m['segments'][1]=write(Path(m['segments'][1]['path']),s)
    with pytest.raises(ValueError,match='overlapping'):gradient_p99(m,policy())


def test_stability_recomputes_spikes_and_requires_actual_numeric_failure(tmp_path):
    m=logs(tmp_path/'spike')
    alter_row(m,6,lambda x:x['row'].update({'loss/total':9.}))
    assert classify_stability(m,policy())['stability']['loss_spike']
    m=logs(tmp_path/'infra',failed=True)
    set_failure(m,phase='RESOURCE_PREFLIGHT',message='Quota feed stale or future')
    with pytest.raises(ValueError,match='Non-numeric'):classify_stability(m,policy())
    set_failure(m)
    assert classify_stability(m,policy())['stability']['diverged']
    late=replace(policy(),commit_epoch=3.)
    with pytest.raises(ValueError,match='precede'):classify_stability(m,late)


@pytest.mark.parametrize('change',['none','cohort','group','gradient','coverage','noimprovement'])
def test_sdp_confirmation_requires_all_groups_learning_and_fixed_cohort(tmp_path,change):
    m=logs(tmp_path,n=500)
    if change=='cohort':alter_row(m,502,lambda x:x['row'].update(population_binding_sha256='4'*64))
    if change=='group':
        s=read_bound(m['segments'][0]);cfg=read_bound(s['configuration']);cfg['proxy_contract']['groups']=['S']
        s['configuration']=write(Path(s['configuration']['path']),cfg);m['segments'][0]=write(Path(m['segments'][0]['path']),s)
    if change=='gradient':alter_row(m,501,lambda x:x['row'].update({'shared_gradient_norm/P':0.}))
    if change=='coverage':
        s=read_bound(m['segments'][0]);path=Path(s['history']['path']);items=[json.loads(x) for x in path.read_text().splitlines()]
        for x in items:
            if x['row']['event']=='TRAIN_STEP':x['row']['valid_count/p']=0
        path.write_text(''.join(json.dumps(x)+'\n' for x in items));s['history']=binding(path);m['segments'][0]=write(Path(m['segments'][0]['path']),s)
    if change=='noimprovement':alter_row(m,502,lambda x:x['row']['fields']['p'].update(loss=1.1))
    if change in ('cohort','group'):
        with pytest.raises(ValueError):confirm_sdp(m,policy())
    else:
        result=confirm_sdp(m,policy())
        assert result['status']==('PROPOSED_CONFIRMATION' if change=='none' else 'REPORT_REQUIRED')
        assert result['scientific_acceptance'] is False


def rates_fixture():
    scores={(c,r):(.9 if r=='3e-4' else .8 if r=='1e-4' else .2) for c in ('S','P') for r in LR_GRID}
    rows,p=setup('learning_rate',('S','P'),LR_GRID,scores,loss_spike_policy={'fixture':'registered'})
    p.rules['recipe']={'top_two_ranking':'equal_mean_S_P','top_two_tie':'smaller_learning_rate'}
    stability={c:{r:Stability(False,False,canonical([c,r]),canonical(p.rules['learning_rate']['loss_spike_policy']),
        tuple(x.training_run_id for x in rows[c][r])) for r in LR_GRID} for c in rows}
    return rows,p,stability


@pytest.mark.parametrize('score,expected_batch',[(.75,'B0'),(.95,'2B0')])
def test_top2_and_joint_batch_reuse_existing_rules_with_doubled_run_bindings(score,expected_batch):
    rows,p,stability=rates_fixture();first=rank_learning_rates(rows,noise(),p,stability)
    assert first['top_two']==['3e-4','1e-4'] and first['common_learning_rate']=='1e-4'
    doubled={c:{r:[measurement(c,'double-'+r,score)] for r in first['top_two']} for c in ('S','P')}
    p.rules['batch_by_lr']={r:{'seed_aggregation':'equal_seed_mean','pretraining_seed_roles':{'initial':0,'repeat':1},
        'scientific_identities':{c:{'B0':rows[c][r][0].scientific_identity_sha256,
        '2B0':doubled[c][r][0].scientific_identity_sha256} for c in ('S','P')}} for r in first['top_two']}
    ds={c:{r:Stability(False,False,canonical(['double',c,r]),stability[c][r].policy_sha256,
        tuple(x.training_run_id for x in doubled[c][r])) for r in first['top_two']} for c in ('S','P')}
    result=joint_lr_batch(rows,doubled,noise(),p,stability,doubled_stability=ds)
    assert result['selected_batch']==expected_batch and result['selected_learning_rate']=='1e-4'
    with pytest.raises(ValueError):joint_lr_batch(rows,{'S':{}},noise(),p,stability,doubled_stability=ds)


@pytest.fixture
def template(tmp_path):
    from phychem_mfm.phase1.v3_proxy_run import engineering_request
    ref=engineering_request(tmp_path/'metadata',code_sha='a'*40,layers=6,budget=100,seed=0)
    request=read_bound(ref);cfg=read_bound(request['configuration']);cfg['engineering_only']=False
    p=policy();p.rules['recipe']={'top_two_ranking':'equal_mean_S_P','top_two_tie':'smaller_learning_rate',
        'model_sha256':canonical(cfg['model']),'B0':2,'sample_budget':100,'warmup_fraction':.02,
        'wsd_decay_fraction':.15,'minimum_lr_ratio':0.,'clip_source_condition':'S'}
    ev=write(tmp_path/'evidence.json',{'scope':'SYNTHETIC_UNIT_NO_PLATFORM_OR_DATA_AUTHORITY'})
    p.rules['recipe']['evidence_sha256']={key:ev['sha256'] for key in ('selected_backbone','budget_evidence','rules_evidence')}
    e=Evidence(ev['path'],ev['sha256']);trials=recipe_plan(sample_budget=100,batch_base_samples=2,
        selected_backbone=e,budget_evidence=e,rules_evidence=e)
    return request,cfg,p,trials


def test_compiler_connects_all19_trials_to_concrete_scheduler_and_batch(template):
    from phychem_mfm.phase1.v3_trainer import SampleLRScheduler
    import torch
    _,cfg,p,trials=template
    resolutions={'top_two':['3e-4','1e-4'],'learning_rate':.0001,'batch_base_samples':4,'schedule':'wsd','clip_norm':2.5}
    for trial in trials:
        result=compile_trial(trial,cfg,resolutions,p);c=result['proxy_contract']
        assert '$' not in json.dumps(result) and result['engineering_only'] is False
        assert c['clip_norm']==(2.5 if trial.condition == 'SDP' else cfg['proxy_contract']['clip_norm'])
        optimizer=torch.optim.AdamW([torch.nn.Parameter(torch.ones(1))],**c['optimizer'])
        schedule=SampleLRScheduler(optimizer,sample_budget=100,**c['schedule'])
        assert schedule.contract['sample_budget']==100
        if c['schedule']['mode']=='wsd':assert c['schedule']['decay_start_samples']==85
    with pytest.raises(ValueError,match='Missing closed'):compile_trial(trials[10],cfg,{},p)
    bad=deepcopy(cfg);bad['model']['backbone']['layers']=4
    with pytest.raises(ValueError):compile_trial(trials[0],bad,{},p)


def full_configuration(tmp_path,template):
    _,cfg,p,_=template;cfg=deepcopy(cfg)
    release=write(tmp_path/'D6.metadata.json',{'scope':'SYNTHETIC_CONSUMER_FIXTURE_NOT_D6_RELEASE'})
    profile=write(tmp_path/'profile.json',{'scope':'SYNTHETIC_METADATA_NOT_ACTUAL_CAPACITY'})
    full={'schema':'model_v3_full_TRAIN_consumption_v1','role':'TRAIN','population_scope':'entire_frozen_v1_TRAIN',
        'molecule_count':7,'membership_sha256':'6'*64,'release_evidence':release,'geometry_source':'PM7','conformations':'all_authorized'}
    resource={'schema':'model_v3_full_TRAIN_resource_declaration_v1','profile_evidence':profile,
        'checkpoint_upper_bytes':300 << 20,'retained_checkpoint_limit':80,'atomic_inflight_checkpoints':1,
        'noncheckpoint_upper_bytes':2 << 30,'durable_upper_bytes':32 << 30}
    cfg['long_run_policy']={'deliberately_unadmitted_unit_fixture':True}
    p.rules['full_convergence']={'maximum_samples':64_000_000,'recipe_configuration_sha256':canonical(cfg),
        'schedule':{'mode':'wsd','warmup_samples':1_280_000,'decay_start_samples':54_400_000,'minimum_ratio':0.},
        'max_total_checkpoints':80,'recovery_interval_samples':1_000_000}
    confirmation={'status':'PROPOSED_CONFIRMATION','frozen':False}
    result=full_convergence_configuration(cfg,confirmation,full,resource,condition='P',policy=p)
    return result,full


@pytest.mark.parametrize('change',['none','FULL','prefix','subset','milestone','capacity','resource','long','group'])
def test_full_train_contract_is_separate_from_proxy_and_requires_finite_storage(tmp_path,template,change):
    cfg,_=full_configuration(tmp_path,template)
    if change=='FULL':cfg['full_train_contract']['role']='FULL'
    elif change=='prefix':cfg['full_train_contract']['population_scope']='prefix'
    elif change=='subset':cfg['proxy_contract']['sampler']['selection']={'mode':'first','k':2}
    elif change=='milestone':cfg['proxy_contract']['sample_plan']['panel_samples'].remove(8_000_000)
    elif change=='capacity':cfg['full_resource_contract']['durable_upper_bytes']=2 << 30
    elif change=='resource':cfg.pop('full_resource_contract')
    elif change=='long':cfg.pop('long_run_policy')
    elif change=='group':cfg['proxy_contract']['groups']=['S','P']
    if change=='none':
        assert validate_full_contract(cfg)['role']=='TRAIN'
        assert cfg['proxy_contract']['sample_budget']==64_000_000
        assert set(FULL_MILESTONES)<=set(cfg['proxy_contract']['sample_plan']['panel_samples'])
    else:
        with pytest.raises(ValueError):validate_full_contract(cfg)


def test_final_binding_routes_through_existing_validator_and_closes_provider(tmp_path,monkeypatch):
    from phychem_mfm.phase1 import v3_proxy_run as proxy
    candidate=write(tmp_path/'request.json',{'mode':'authoritative_full_train','Root_admission':None})
    calls=[]
    def validate(request,**kw):
        calls.append(('validate',kw['input_kind']));assert request['long_run']=={'new':'Root refs'}
        return {},None,{}
    class Provider:
        def close(self):calls.append(('close',True))
    class Inputs:provider=Provider()
    monkeypatch.setattr(proxy,'validate_request',validate)
    monkeypatch.setattr(proxy,'bind_inputs',lambda r,c:Inputs())
    result=finalize_request(candidate,{}, {'path':'actualRoot'},tmp_path/'final.json',operational={'long_run':{'new':'Root refs'}})
    assert read_bound(result)['mode']=='authoritative_full_train' and calls==[('validate','authoritative_full_train'),('close',True)]
    with pytest.raises(ValueError):finalize_request(candidate,{}, {},tmp_path/'never.json',operational={'sources':{}})


def test_compiled_recipe_runs_one_real_synthetic_producer_update(template,tmp_path):
    """Real six-layer API wiring, explicitly converted to dual-gated engineering.

    No D authority, model comparison or optimizer checkpoint is claimed/saved.
    """
    import torch
    from phychem_mfm.phase1 import v3_proxy_run as proxy
    from test_model_v3_trainer import UnitTracker
    request,cfg,p,trials=template
    compiled=compile_trial(trials[0],cfg,{},p)
    compiled['engineering_only']=True;compiled['experiment_scope']=proxy.ENGINEERING
    # Tiny finite CPU fixture budget keeps the same compiler/producer interfaces.
    compiled['proxy_contract']['execution'].update(device='cpu',gpu_uuid=None,gpu_name=None,threads=1)
    request['configuration']=write(tmp_path/'compiled_engineering.json',compiled)
    request.update(mode='synthetic_engineering',scope='engineering')
    threads,precision=torch.get_num_threads(),torch.get_float32_matmul_precision()
    mm,cc=torch.backends.cuda.matmul.allow_tf32,torch.backends.cudnn.allow_tf32
    inputs=experiment=None
    try:
        torch.set_num_threads(1);torch.set_float32_matmul_precision('highest')
        torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        actual,plan,_=proxy.validate_request(request,input_kind='synthetic',engineering_only=True)
        inputs=proxy.bind_inputs(request,actual)
        experiment=proxy.build_experiment(request,actual,plan,inputs,UnitTracker('recipe-engineering'),
            output_root=tmp_path/'one-update'/'training',lineage_root=tmp_path/'one-ledger',
            lineage='explicit-engineering-recipe',device='cpu',allow_unit_tracker=True)
        row=experiment.trainer.next_step(2)
        assert row['optimizer_updated'] and row['optimizer_updates']==1 and row['samples_consumed']==2
        assert row['gradient_norm_before_clip']>0 and row['lr_used'][0]==pytest.approx(0.)
        assert experiment.trainer.groups==('S',)
    finally:
        if inputs is not None:inputs.provider.close()
        torch.set_num_threads(threads);torch.set_float32_matmul_precision(precision)
        torch.backends.cuda.matmul.allow_tf32=mm;torch.backends.cudnn.allow_tf32=cc


def test_actual_full_adapter_dispatch_verifies_whole_train_not_proxy_prefix(tmp_path,template):
    from phychem_mfm.phase1 import v3_proxy_run as proxy
    from dataclasses import asdict
    cfg,full=full_configuration(tmp_path,template)
    adapter=tmp_path/'consumer_adapter.py'
    adapter.write_text('''from dataclasses import replace\nfrom phychem_mfm.phase1.v3_proxy_run import ProxyInputs\nfrom phychem_mfm.phase1.v3_proxy_engineering import synthetic_proxy_inputs\nfrom phychem_mfm.phase1.v3_contract import canonical_hash\nclass EntireTRAIN:\n    role='TRAIN'\n    authority='data_line'\n    content_sha256='6'*64\n    def __init__(self,version):self.version=version\n    def __len__(self):return 7\ndef verify_and_bind_model_v3_full_TRAIN_inputs(request):\n    from phychem_mfm.phase1.v3_sample_budget_events import read_bound\n    config=read_bound(request['configuration']); source=synthetic_proxy_inputs()\n    return replace(source,index=EntireTRAIN(source.index.version),registry=replace(source.registry,authority='data_line'),\n        authority_kind='data_line_final',release_accepted=True,verified_request_sha256=canonical_hash(request),\n        authority_receipt={'full_TRAIN_consumption_contract_sha256':canonical_hash(config['full_train_contract'])},\n        full_train_contract=config['full_train_contract'])\n''')
    # Protocol fixture only: the fake hook is deliberately not an admitted release.
    source=proxy.bind_inputs(template[0],read_bound(template[0]['configuration']))
    projection={'index_sha256':'6'*64,'registry_sha256':replace(source.registry,authority='data_line').content_sha256,
        'normalization_sha256':canonical_hash({k:asdict(v) for k,v in source.normalizations.items()}),
        'adapter_sha256':source.provider.source_sha256,'data_version':source.index.version}
    source.provider.close()
    request={'mode':'authoritative_full_train','adapter':binding(adapter),
        'configuration':write(tmp_path/'full_config.json',cfg),'input_projection':projection}
    inputs=proxy.bind_inputs(request,cfg)
    assert len(inputs.index)==7 and inputs.index.role=='TRAIN';inputs.provider.close()
    # Same hook cannot be silently consumed by the unchanged proxy/D5 path.
    request['mode']='authoritative_proxy'
    with pytest.raises(ValueError,match='hook'):proxy.bind_inputs(request,cfg)


def test_failed_numeric_lr_is_excluded_without_fabricating_a_development_score(tmp_path):
    from phychem_mfm.phase1.v3_decision_rules import choose_learning_rate
    from phychem_mfm.phase1.v3_proxy_run import identity
    m=logs(tmp_path,failed=True,groups=['S'])
    rows,p,stability=rates_fixture()
    p.rules['stability']=policy().rules['stability']
    p.rules['learning_rate']['loss_spike_policy']=p.rules['stability']
    cfg=read_bound(read_bound(m['segments'][0])['configuration'])

    p.rules['recipe']['sample_budget']=100
    p.rules['failed_training_configurations']={'S':{'3e-4':identity(cfg)}}
    rows['S']['3e-4']=[]
    for c in stability:
        for lr,v in list(stability[c].items()):stability[c][lr]=replace(v,policy_sha256=canonical(p.rules['stability']))
    failure={'S':{'3e-4':write(tmp_path/'failed_logs.json',m)}}
    # The fixture's initial seed/start must agree with the registered roles.
    verdict=choose_learning_rate(rows,noise(),p,stability,failure_exclusions=failure)
    assert '3e-4' in verdict['excluded'] and verdict['selected']=='1e-4'
    rows['P']['3e-4']=[]
    with pytest.raises(ValueError,match='Missing panel'):choose_learning_rate(rows,noise(),p,stability,failure_exclusions=failure)


def test_full_runner_requires_D6_registration_and_own_profile_admission(tmp_path,template,monkeypatch):
    """Only the opaque external auth/source gates are fixtures; full dispatch is real."""
    from phychem_mfm.phase1 import v3_proxy_run as proxy,v3_long_run_storage as storage
    cfg,full=full_configuration(tmp_path,template);request=deepcopy(template[0])
    request['input_projection']['index_sha256']=full['membership_sha256']
    cfg['input_projection_sha256']=canonical_hash(request['input_projection'])
    request.update(mode='authoritative_full_train',scope='full_convergence',
        configuration=write(tmp_path/'full.json',cfg),registrations={x:{} for x in ('budget','validation','recipe','full_train')},
        long_run={'profile':cfg['full_resource_contract']['profile_evidence']})
    request['sources'].update(tree_sha='c'*40,state='clean_committed')
    monkeypatch.setattr(proxy,'validate_sources',lambda r:cfg['runtime_source_inventory_sha256'])
    called=[]
    monkeypatch.setattr(proxy,'_registration',lambda ref,*,purpose,configuration:called.append(purpose) or {'fixture':True})
    monkeypatch.setattr(storage,'policy',lambda config,plan=None:{'durable_bytes':cfg['full_resource_contract']['durable_upper_bytes'],
        'checkpoint_bytes':cfg['full_resource_contract']['checkpoint_upper_bytes']})
    monkeypatch.setattr(storage,'validate_admission',lambda req,config:called.append('fresh_quota_and_lease'))
    evidence=write(tmp_path/'other_D_evidence.json',{'scope':'SYNTHETIC_NO_ACTUAL_D_AUTHORITY'})
    admission={'schema':'model_v3_proxy_Root_admission_v1','status':'ROOT_ADMITTED_FINAL_INPUTS',
        'configuration_identity_sha256':proxy.identity(cfg),'scope':request['scope'],
        'code_sha':request['sources']['code_sha'],'tree_sha':request['sources']['tree_sha'],
        'request_identity_sha256':canonical_hash(request),
        'evidence':{**{k:evidence for k in ('D1','D2','D3','D4','three_GPU_SDP_smoke')},'D6':full['release_evidence']}}
    request['Root_admission']=write(tmp_path/'Root_admission.json',admission)
    _,plan,_=proxy.validate_request(request,input_kind='authoritative_full_train')
    assert plan.sample_budget==64_000_000 and {'budget','validation','recipe','full_train','fresh_quota_and_lease'}<=set(called)
    bad=deepcopy(request);admission['evidence'].pop('D6');admission['evidence']['D5']=evidence
    bad['Root_admission']=write(tmp_path/'wrong_D.json',admission)
    with pytest.raises(ValueError,match='authority'):proxy.validate_request(bad,input_kind='authoritative_full_train')
    with pytest.raises(ValueError,match='scope'):proxy.validate_request(request,input_kind='authoritative_proxy')


def test_missing_numeric_policy_and_changed_raw_source_never_default_pass(tmp_path):
    m=logs(tmp_path)
    p=policy();p.rules.pop('stability')
    with pytest.raises(ValueError,match='policy'):classify_stability(m,p)
    p=policy();p.rules.pop('SDP_confirmation')
    with pytest.raises(ValueError,match='policy'):confirm_sdp(m,p)
    closure=read_bound(m['segments'][0]);Path(closure['history']['path']).write_text('{}\n')
    with pytest.raises(ValueError):gradient_p99(m,policy())


def test_selected_recipe_initial_validation_hook_preserves_resume_ack(monkeypatch):
    from types import SimpleNamespace
    from phychem_mfm.phase1.v3_proxy_run import ProxyStepTrainer
    from phychem_mfm.phase1.v3_architecture_training import ArchitectureStepTrainer
    calls=[]
    trainer=SimpleNamespace(recipe_initial_validation=True,clock=SimpleNamespace(samples_consumed=0),
        validation_state={r:{'completed_runs':0} for r in ('VAL','TRAIN_UNSEEN_CONFORMATION')})
    def validate(role):
        calls.append(role);trainer.validation_state[role]['completed_runs']+=1
    trainer.validate=validate
    # Use a genuine instance shell so super() resolution exercises the real hook.
    obj=object.__new__(ProxyStepTrainer);obj.__dict__.update(trainer.__dict__)
    obj.validate=validate
    monkeypatch.setattr(ArchitectureStepTrainer,'next_step',lambda self,count:calls.append(('step',count)))
    ProxyStepTrainer.next_step(obj,2);ProxyStepTrainer.next_step(obj,2)
    assert calls==['VAL','TRAIN_UNSEEN_CONFORMATION',('step',2),('step',2)]


def test_thin_cli_rejects_wrong_raw_input_before_creating_output(tmp_path):
    file=Path(__file__).absolute().parents[2]/'tools/model_v3/prepare_recipe_experiment.py'
    spec=importlib.util.spec_from_file_location('recipe_readiness_cli',file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    ref=write(tmp_path/'inputs.json',{'schema':'SYNTHETIC_BAD_MANIFEST_NO_RUN'})
    out=tmp_path/'never'/'result.json'
    with pytest.raises(ValueError,match='raw SHA'):
        module.main(['resolve','--inputs',ref['path'],'--inputs-sha256','0'*64,'--output',str(out)])
    assert not out.parent.exists()


def test_resealed_truncated_population_cannot_self_certify_committed_cursors(tmp_path):
    m=logs(tmp_path,n=5);s=read_bound(m['segments'][0]);path=Path(s['history']['path'])
    rows=[json.loads(x) for x in path.read_text().splitlines()]
    del rows[3]
    for i,x in enumerate(rows):
        x['step']=i;x['row']['log_cursor']=i
        if i>=3:x['row']['optimizer_updates']-=1
    path.write_text(''.join(json.dumps(x)+'\n' for x in rows));s['history']=binding(path)
    s['final']['optimizer_updates']-=1;s['final']['log_cursor']-=1
    m['segments'][0]=write(Path(m['segments'][0]['path']),s)
    with pytest.raises(ValueError,match='actual committed'):gradient_p99(m,policy())


def test_missing_actual_checkpoint_anchor_is_not_a_complete_population(tmp_path):
    m=logs(tmp_path);s=read_bound(m['segments'][0]);s['final_anchor']=None
    m['segments'][0]=write(Path(m['segments'][0]['path']),s)
    with pytest.raises(ValueError,match='anchor'):gradient_p99(m,policy())


def test_bool_origin_counter_cannot_alias_integer_zero(tmp_path):
    m=logs(tmp_path);s=read_bound(m['segments'][0]);a=s['initial_anchor']
    launch=read_bound(a['run_binding']);launch['initial_cursors']['optimizer_updates']=False
    a['run_binding']=write(Path(a['run_binding']['path']),launch)
    m['segments'][0]=write(Path(m['segments'][0]['path']),s)
    with pytest.raises(ValueError,match='integer'):gradient_p99(m,policy())


@pytest.mark.parametrize('kind,phase,message',[
    ('OSError','TRAIN_STEP','Nonfinite gradient before optimizer update'),
    ('OutOfMemoryError','TRAIN_STEP','Nonfinite gradient before optimizer update'),
    ('ValueError','SETUP','Nonfinite gradient before optimizer update'),
    ('ValueError','TRAIN_STEP','IO failed; old text: Nonfinite gradient before optimizer update'),
    ('ValueError','TRAIN_STEP','expected-error: Nonfinite gradient before optimizer update'),
    ('ValueError','RESOURCE_PREFLIGHT','Nonfinite gradient before optimizer update')])
def test_engineering_primary_cause_with_numeric_text_never_excludes_lr(tmp_path,kind,phase,message):
    m=logs(tmp_path,failed=True);set_failure(m,kind=kind,phase=phase,message=message)
    with pytest.raises(ValueError,match='Non-numeric'):classify_stability(m,policy())


def test_legacy_free_text_failure_is_unknown_not_divergence(tmp_path):
    m=logs(tmp_path,failed=True)
    m['failure_observations']=[write(tmp_path/'free_text.json',{'job_id':'4520000','message':'Nonfinite gradient before optimizer update'})]
    with pytest.raises(ValueError,match='UNKNOWN'):classify_stability(m,policy())


def test_typed_primary_exception_wrong_actual_job_is_rejected(tmp_path):
    m=logs(tmp_path,failed=True);s=read_bound(m['segments'][0]);child=read_bound(s['final_anchor']['reference'])
    child['primary_failure']['job_id']='9999999'
    ref=write(Path(s['final_anchor']['reference']['path']),child);s['final_anchor']['reference']=ref
    m['segments'][0]=write(Path(m['segments'][0]['path']),s)
    m['failure_observations'][0]['child_receipt']=ref
    with pytest.raises(ValueError,match='primary'):classify_stability(m,policy())


def test_schedule_clip_cannot_change_until_sdp_p99_stage(template):
    _,cfg,p,trials=template
    schedule=next(t for t in trials if t.name.startswith('Schedule_'))
    bad=replace(schedule,parameters=tuple(sorted((*schedule.parameters,('clip_norm',9.)))))
    resolution={'top_two':['3e-4','1e-4'],'learning_rate':.0001,'batch_base_samples':2,'schedule':'wsd','clip_norm':2.5}
    with pytest.raises(ValueError,match='base clip'):compile_trial(bad,cfg,resolution,p)
