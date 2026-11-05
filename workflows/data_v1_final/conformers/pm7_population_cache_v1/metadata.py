"""Stdlib login-only unsigned batch candidates and exact central stage inputs."""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,socket,sys
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO))
from workflows.data_v1_final.conformers.pm7_population_cache_v1 import contract as C
OLD=C.RUN/'artifacts/conformers/pm7_independent_cache32_v1'


def small(path):
    path=pathlib.Path(path);C.need(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)), 'LITERAL_SMALL_SOURCE_OR_METADATA')
    C.need(path.stat().st_size<=2<<20 and path.suffix in {'.py','.json','.md','.txt','.csv','.sbatch'}
        and not any(x in path.parts for x in ('tasks','molecules','results','progress')),'NO_SCIENTIFIC_BODY_ON_LOGIN')
    return path


def pin(path):
    path=small(path)
    with path.open('rb') as f:a=os.fstat(f.fileno());raw=f.read((2<<20)+1);b=os.fstat(f.fileno())
    C.need(len(raw)==a.st_size and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'METADATA_CHANGED')
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def load(path):small(path);return json.loads(pathlib.Path(path).read_text())
def actual(reference):C.need(pin(reference['path'])==C.reference(reference),'ACTUAL_METADATA_PIN');return load(reference['path'])
def unique(rows):
    out={}
    for r in rows:
        r=C.reference(r);C.need(r['path'] not in out or out[r['path']]==r,'PIN_CONFLICT');out[r['path']]=r
    return list(out.values())


def write(path,value):
    raw=C.canonical(value)+b'\n';C.need(len(raw)<=2<<20,'BOUNDED_METADATA_OUTPUT')
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return pin(path)


def resource(path):
    value=load(path);C.need(value['schema']=='SPRIME_MAIN_ACCOUNT_QUOTA_REUSE_ROOT_REVIEW_V3' and value['status']=='APPROVED_RESOURCE_FACT_REUSE_ONLY'
        and value['reviewer']=='root' and value['endpoint']=='202.38.247.57:22' and value['uid']==1278 and value['compute_node']=='compute-0-13','REAL_CURRENT_ROOT_RESOURCE_REVIEW')
    provider=actual(value['provider_review_reference'])
    refs=[pin(path),value['provider_review_reference'],*provider['provider_source_references'],*provider['evidence_references'],provider['marker_reference']]
    for key in ('provider_actual_launch_reference','publisher_identity_reference','prior_resource_review_reference'):
        if value.get(key):refs.append(value[key])
    return value,unique(refs)


def candidate(args,out):
    prep_ref=pin(OLD/'prepared_v1/prepared.json');prep=actual(prep_ref);base_ref=prep['plan_reference'];base=actual(base_ref)
    geometry_ref=pin(OLD/'run_v1/receipt.json');geometry=actual(geometry_ref)
    hof_ref=pin(OLD/'hof_augmentation_v1/receipt.json');hof=actual(hof_ref);hof_plan=actual(hof['plan_reference'])
    shards=actual(prep['future_shards']);selected=C.selection(dict(file_group=args.file_group,shard_index=args.shard_index,offset=args.offset,limit=args.limit))
    matches=[s for s in shards['descriptors'] if (s['file_group'],s['shard_index'])==(selected['file_group'],selected['shard_index'])]
    C.need(len(matches)==1 and selected['offset']+selected['limit']<=matches[0]['molecules'],'EXACT_EXISTING247_DESCRIPTOR_RANGE')
    accounts={k:pin(C.RUN/'control/accounting'/n) for k,n in (
        ('population_prepare_accounting_reference','pm7_cache32_prepare_4521593_v1.json'),
        ('geometry32_accounting_reference','pm7_cache32_run_4521602_v1.json'),('hof32_accounting_reference','pm7_hof_aug32_4521643_v1.json'))}
    source=[pin(C.HERE/n) for n in C.FILES];data=[]
    # Historical proofs supply dependency inventory only, never admission.
    for receipt in (geometry,hof):
        proof=actual(receipt['startup_proof_reference']);source.extend(proof['request']['source_references']);data.extend(proof['request']['data_references'])
    sources_extra=[prep_ref,base_ref,geometry_ref,hof_ref,hof['plan_reference'],prep['source_authority_reference'],prep['future_shards'],hof_plan['hof_authority_review']]
    source.extend(sources_extra)
    data.extend(r['packet_reference'] for r in geometry['packets'])
    data.extend(r['packet_reference'] for r in hof['packets'])
    for r in accounts.values():source.extend([r,actual(r)['raw_sacct_reference']])
    previous=[];previous_outputs=[]
    for p in args.previous_parent_accounting:
        r=pin(p);value=actual(r);C.need(value['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and value['endpoint']=='202.38.247.57:22'
            and value['uid']==1278 and value['query_returncode']==0,'ACTUAL_PREVIOUS_PARENT_ACCOUNTING');previous.append(r);source.extend([r,value['raw_sacct_reference']])
    for p in args.previous_submission:
        r=pin(p);submission=actual(r);request=actual(submission['request_reference'])
        C.need(submission['schema']=='CPU_AUTO_MEMORY_SUBMISSION_V1' and submission['uid']==1278 and submission['sbatch_returncode']==0
            and request['scope_key']==C.SCOPE and request['execution_argv'][2]==str(C.HERE/'run.py'),'REAL_PRIOR_THIS_NAMESPACE_SUBMISSION')
        previous_outputs.append(r);source.extend([r,submission['request_reference']])
    quota,resources=resource(args.quota_reuse_review);source.extend(resources)
    # All scientific payload refs stay declarative; no stat/hash/parse here.
    data.extend([base['formal_source'],base['per_molecule'],prep['whole_molecule_roster']])
    source=unique(source);source_paths={r['path'] for r in source};data=unique(r for r in data if r['path'] not in source_paths)
    for r in source:C.need(pin(r['path'])==r,'CURRENT_SMALL_SOURCE_OR_METADATA_PIN')
    value={'schema':C.SCHEMA,'status':'ROOT_REVIEW_REQUIRED','reviewer':'UNSIGNED','proposed_runtime_status':C.STATUS,
        'endpoint':'202.38.247.57:22','uid':1278,'selection':selected,'ledger_root':str(C.LEDGER),'formal_source':base['formal_source'],
        'per_molecule':base['per_molecule'],'whole_molecule_roster':prep['whole_molecule_roster'],'future_shards_reference':prep['future_shards'],
        'population_prepared_reference':prep_ref,'base_plan_reference':base_ref,'geometry32_receipt_reference':geometry_ref,'hof32_receipt_reference':hof_ref,
        'hof_authority_review':hof_plan['hof_authority_review'],'metadata_source_references':source,'data_references':data,
        'previous_parent_accounting_references':previous,'previous_submission_references':previous_outputs,
        'whole_population_is_union_of_existing247_whole_molecule_shards':True,'source_population_molecules':1220466,'source_population_records':11231854,
        'Sprime_SUCCESS_or_Common_used_as_filter':False,'common':False,'full_cache_release':False,**accounts}
    old=quota['whole_wave_output_reserve_bytes'];quota=dict(quota,status='ROOT_REVIEW_REQUIRED',reviewer='UNSIGNED',
        proposed_runtime_status='APPROVED_RESOURCE_FACT_REUSE_ONLY',prior_resource_review_reference=pin(args.quota_reuse_review),
        preserved_previous_reserve_bytes=old,additional_PM7_batch_output_cap_bytes=C.CAP,whole_wave_output_reserve_bytes=old+C.CAP,
        publisher_started_or_renewed=False)
    print(json.dumps({'plan_candidate':write(out/'plan_candidate.json',value),'quota_candidate':write(out/'quota_candidate.json',quota),'approved':False,'submitted':False}))


def stage(args,out):
    value=load(args.plan);plan_ref=pin(args.plan)
    C.need(value['schema']==C.SCHEMA and value['status']==C.STATUS and value['reviewer']=='root','INDEPENDENT_APPROVED_ROOT_BATCH_PLAN')
    _,resources=resource(args.quota_reuse_review);quota_ref=pin(args.quota_reuse_review)
    source=unique([*value['metadata_source_references'],*resources,plan_ref]);data=unique(value['data_references'])
    C.need(not({r['path'] for r in source}&{r['path'] for r in data}),'SOURCE_DATA_DISJOINT')
    C.need(C.BASE in args.stage_output.parents and not args.stage_output.exists() and 1200<=args.wall_seconds<=172800,'NEW_OUTPUT_FINITE_WALL')
    from pathlib import Path
    py='/share/home/zixiao/.conda/envs/chemprop/bin/python'
    argv=[py,'-B',str(C.HERE/'run.py'),'--plan',str(args.plan),'--root-preflight','__ROOT_STARTUP_PROOF__',
        '--quota-reuse-review',str(args.quota_reuse_review),'--output',str(args.stage_output)]
    authority=pin(C.REPO/'configs/data_v1/user_cpu_auto_memory_20261026_v1.json')
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':'UNSIGNED',
        'proposed_runtime_status':'APPROVED_FOR_EXACT_STAGE','resource_authority_reference':authority,'kind':'analysis','scope_key':C.SCOPE,
        'scope_parameters':C.scope(value['selection']),'pilot':False,'wall_seconds':args.wall_seconds,'estimated_peak_output_bytes':C.CAP,
        'stage_output_cap_bytes':C.CAP,'execution_argv':argv,'source_status_stage':None,'scope_mode':'BOUNDED_METADATA_PREPARATION',
        'parent_evidence_references':[plan_ref,quota_ref,value['population_prepare_accounting_reference'],value['geometry32_accounting_reference'],value['hof32_accounting_reference']],
        'root_review_reason':None}
    candidate_ref=write(out/'scope_candidate.json',review)
    spec={k:review[k] for k in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv','source_status_stage')}
    spec.update(schema='UNSIGNED_PM7_POPULATION_BATCH_STAGE_INPUTS_V1',cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',
        source_references=source,data_references=data,scope={'mode':'BOUNDED_METADATA_PREPARATION','review':None,'parent_profile':None},unsigned_scope_candidate_reference=candidate_ref)
    if args.scope_review:
        approved=load(args.scope_review);C.need(approved['status']=='APPROVED_FOR_EXACT_STAGE' and approved['reviewer']=='root','NO_ROOT_PROXY_SIGNING')
        for k in ('schema','resource_authority_reference','kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv','source_status_stage','scope_mode','parent_evidence_references'):
            C.need(approved[k]==review[k],'EXACT_ACTUAL_SCOPE:'+k)
        r=pin(args.scope_review);spec.update(schema='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1');spec['scope']['review']=r
        spec['source_references']=unique([*source,r]);spec.pop('unsigned_scope_candidate_reference')
    print(json.dumps({'stage_inputs':write(out/('stage_spec.json' if args.scope_review else 'stage_inputs_candidate.json'),spec),'submitted':False}))


def main():
    C.need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi','MAIN_LOGIN_METADATA_ONLY')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('catalog','candidate','stage'))
    for name in ('plan','quota-reuse-review','scope-review','stage-output','output'):p.add_argument('--'+name,type=pathlib.Path,required=name=='output')
    for name,default in (('file-group',1),('shard-index',0),('offset',0),('limit',256),('wall-seconds',7200)):p.add_argument('--'+name,type=int,default=default)
    p.add_argument('--previous-parent-accounting',type=pathlib.Path,action='append',default=[])
    p.add_argument('--previous-submission',type=pathlib.Path,action='append',default=[]);args=p.parse_args()
    C.need(C.RUN/'control' in args.output.parents and not args.output.exists(),'NEW_CONTROL_ONLY_NO_OVERWRITE');args.output.mkdir(parents=True,exist_ok=False,mode=0o700)
    if args.mode=='catalog':
        prep=load(OLD/'prepared_v1/prepared.json');shards=actual(prep['future_shards']);C.need(len(shards['descriptors'])==247,'EXISTING247_NOT_NEW_POPULATION')
        print(json.dumps({'whole_population_batch_inventory':write(args.output/'existing247_shards.json',dict(shards,execution_authorized=False,new_jobs=0))}));return
    C.need(args.quota_reuse_review is not None,'ACTUAL_CURRENT_ROOT_RESOURCE_REVIEW')
    if args.mode=='candidate':candidate(args,args.output)
    else:C.need(args.plan and args.stage_output,'APPROVED_PLAN_AND_NEW_OUTPUT');stage(args,args.output)


if __name__=='__main__':main()
