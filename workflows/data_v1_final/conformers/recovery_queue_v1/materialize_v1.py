"""Root metadata-only materialization of an independent strict queued recovery.

No scheduler commands, scientific imports, task/package/LMDB bodies, or execution.
Only the actual integrated Root source may run this preparer on sonmi.
"""
from __future__ import annotations
import argparse,ast,copy,datetime,hashlib,json,os,re,socket,stat
from pathlib import Path

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REPO=ROOT/'repository'
PYTHON='/share/home/zixiao/.conda/envs/chemprop/bin/python'
SMALL_CAP=2*1024**2
USER_REPLY='请你把任务提交上，如果节点需要排队请等待排队，直到所有指令要求的任务都完成之后再结束任务，在没有完成之前请不要停止'
FROZEN_INPUTS={
    "workflows/data_v1_final/conformers/recovery_v1/recovery_common.py":  {
                                                                              "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/conformers/recovery_v1/recovery_common.py",
                                                                              "bytes":  12267,
                                                                              "sha256":  "704ada3f67a6ee45389a27a12bab2f6be5e31e1c2a80fe0cc4c41a2176ea9cd3"
                                                                          },
    "workflows/data_v1_final/conformers/recovery_v1/run_recovery.py":  {
                                                                           "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/conformers/recovery_v1/run_recovery.py",
                                                                           "bytes":  10654,
                                                                           "sha256":  "1f3b989c3766c6a3b6b2c3a82d292aeec5c1fd303732e2285f2d4c57d6f278ea"
                                                                       },
    "workflows/data_v1_final/conformers/recovery_v1/close_recovered.py":  {
                                                                              "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/conformers/recovery_v1/close_recovered.py",
                                                                              "bytes":  13098,
                                                                              "sha256":  "ce36efb617fdc8642b1875a262649b7ca1fb8453a87843bd6a1473af7657d95b"
                                                                          },
    "workflows/data_v1_final/conformers/recovery_v1/test_recovery.py":  {
                                                                            "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/conformers/recovery_v1/test_recovery.py",
                                                                            "bytes":  4096,
                                                                            "sha256":  "a09aff9cde6af0deb0750fe14af499e8642355fa91e8092795b2fbcc2fd9403d"
                                                                        },
    "workflows/data_v1_final/conformers/recovery_v1/README.md":  {
                                                                     "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/conformers/recovery_v1/README.md",
                                                                     "bytes":  9309,
                                                                     "sha256":  "37284dc646ed8f4244a8896c73d0ccaed37ce184103ff5b52de699e83700dd71"
                                                                 },
    "configs/data_v1/conformers/recovery_v1.template.json":  {
                                                                 "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/conformers/recovery_v1.template.json",
                                                                 "bytes":  5985,
                                                                 "sha256":  "91c748b49194003ac8e299931a4f61a3e172a0f3622f6070782566753710d413"
                                                             },
    "configs/data_v1/conformers/recovery_approval_v1.template.json":  {
                                                                          "path":  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/conformers/recovery_approval_v1.template.json",
                                                                          "bytes":  390,
                                                                          "sha256":  "b2d8a6c0a7d9534d350a14f2f9ec74442e2ff77c71b4800590f4874a7864665c"
                                                                      }
}


def require(ok,message):
    if not ok:raise ValueError(message)


def read_small(path):
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path,*path.parents)), 'LITERAL_SMALL_SOURCE_REQUIRED')
    with path.open('rb') as f:
        before=os.fstat(f.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size<=SMALL_CAP,
                'SMALL_REGULAR_OWNED_SOURCE_ONLY')
        raw=f.read(SMALL_CAP+1);after=os.fstat(f.fileno())
    frame=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_uid)
    require(len(raw)==before.st_size<=SMALL_CAP and frame(before)==frame(after),'SMALL_SOURCE_CHANGED')
    return raw


def reference(path):
    path=Path(path);raw=read_small(path)
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def verify(pin):
    expected={k:pin[k] for k in ('path','bytes','sha256')}
    require(reference(pin['path'])==expected,'SMALL_PIN_CHANGED:'+pin['path'])
    return Path(pin['path'])


def load_pin(pin):
    return json.loads(read_small(verify(pin)))


def write_new(path,value):
    raw=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    require(len(raw)<=SMALL_CAP,'BOUNDED_METADATA_OUTPUT_REQUIRED')
    with Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository',type=Path,required=True)
    parser.add_argument('--run-root',type=Path,required=True)
    parser.add_argument('--reviewer',required=True)
    parser.add_argument('--name',required=True)
    parser.add_argument('--node',required=True)
    parser.add_argument('--root-preflight',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    require(os.name=='posix' and os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and
            a.repository==REPO and a.run_root==ROOT and a.reviewer=='root' and
            Path(__file__).absolute()==REPO/'workflows/data_v1_final/conformers/recovery_queue_v1/materialize_v1.py',
            'ROOT_INTEGRATION_AND_PERSONAL_METADATA_INVOCATION_REQUIRED')
    require(re.fullmatch(r'dv1_[A-Za-z0-9_]+',a.name) and
            a.node in {f'compute-0-{n}' for n in range(14,20)},'STRICT_CPU_NODE_AND_NEW_NAME_REQUIRED')
    require(a.root_preflight.is_absolute() and ROOT/'control' in a.root_preflight.parents and
            '..' not in a.root_preflight.parts,'NEW_ROOT_STARTUP_PROOF_PATH_REQUIRED')
    outroot=ROOT/'artifacts/conformers/recovery_v1'
    require(a.output.is_absolute() and a.output!=outroot and outroot in a.output.parents and
            '..' not in a.output.parts and not a.output.exists() and
            not any(p.is_symlink() for p in (a.output,*a.output.parents)),
            'NEW_RECOVERY_CHILD_OUTPUT_REQUIRED')
    prefix=ROOT/'control/requests'/a.name
    plan_path=prefix.with_name(prefix.name+'.plan.json')
    approval_path=prefix.with_name(prefix.name+'.approval.json')
    dispatch_path=prefix.with_name(prefix.name+'.dispatch.json')
    require(all(not p.exists() and not p.is_symlink() for p in (plan_path,approval_path,dispatch_path)),
            'EXCLUSIVE_NEW_RECOVERY_METADATA_REQUIRED')
    source={}
    def add_source(pin):
        pin={k:pin[k] for k in ('path','bytes','sha256')};verify(pin)
        require(pin['path'] not in source or source[pin['path']]==pin,'CONFLICTING_SMALL_SOURCE_PIN')
        source[pin['path']]=pin
    for pin in FROZEN_INPUTS.values():add_source(pin)
    plan=load_pin(FROZEN_INPUTS['configs/data_v1/conformers/recovery_v1.template.json'])
    approval=load_pin(FROZEN_INPUTS['configs/data_v1/conformers/recovery_approval_v1.template.json'])
    require(plan['schema']=='SPRIME_MISSING_RECOVERY_PLAN_V1' and
            plan['status']=='PENDING_ROOT_BUDGET_AND_RESOURCE_REVIEW' and
            plan['original_job_id']=='4520364' and plan['expected_original_molecules']==336 and
            plan['expected_missing_molecules']=={'principal_01112964':7,'principal_00509656':10} and
            plan['workers']==plan['cpus']==16 and plan['memory_gib']==64 and
            plan['new_logical_retry_count']==0 and plan['scientific_recipe_changed'] is False,
            'UNCHANGED_RECOVERY_TEMPLATE_REQUIRED')
    audit=load_pin(plan['partial_audit_report']);add_source(plan['partial_audit_report'])
    add_source(plan['partial_audit_monitor_closure'])
    require(audit['schema']=='PARTIAL_SPRIME_PILOT_READONLY_AUDIT_V1' and
            audit['status']=='PARTIAL_PILOT_NOT_ACCEPTED_FOR_FORMAL' and
            audit['original_job_id']=='4520364' and audit['original_parent_state']=='TIMEOUT' and
            audit['complete_reusable_molecules']==334 and audit['missing_molecules']==2 and
            audit['invalid_molecules']==audit['unexpected_entries']==0,
            'REAL_334_PLUS_TWO_AUDIT_REQUIRED')
    for pin in audit['outputs']:add_source(pin)
    complete_pin=next(pin for pin in audit['outputs'] if Path(pin['path']).name=='complete_packages.json')
    closed=load_pin(complete_pin)
    require(len(closed)==334 and len({r['molecule_id'] for r in closed})==334,'UNIQUE334_OLD_PACKAGES_REQUIRED')
    controls=sorted(r['molecule_id'] for r in closed if r['summary']['status']=='SUCCESS' and
                    r['detail']['new_real_accepted_count']>0)[:14]
    require(len(controls)==14 and controls==plan['replay_control_ids'] and plan['replay_control_count']==14,
            'ORIGINAL_FIXED_FOURTEEN_CONTROL_IDS_CHANGED')
    prepared=load_pin(audit['prepared_reference']);add_source(audit['prepared_reference'])
    require(prepared['molecules']==336 and plan['recipe_config']==audit['original_pilot_config_reference']==prepared['config'] and
            plan['tasks_reference']==audit['tasks_reference'],'ORIGINAL_TASK_CONFIG_BINDING_CHANGED')
    recipe=load_pin(plan['recipe_config']);add_source(plan['recipe_config'])
    recovery_dir=REPO/'workflows/data_v1_final/conformers/recovery_v1'
    old_module=ast.parse(read_small(recovery_dir/'recovery_common.py'))
    assignments=[n for n in old_module.body if isinstance(n,ast.Assign) and
                 any(isinstance(t,ast.Name) and t.id=='OLD_SHA' for t in n.targets)]
    require(len(assignments)==1,'UNIQUE_FROZEN_OLD_SOURCE_DICT_REQUIRED')
    old_sha=ast.literal_eval(assignments[0].value)
    for rel,sha in old_sha.items():
        pin=reference(REPO/'workflows/data_v1_final/conformers'/rel)
        require(pin['sha256']==sha,'OLD_SCIENCE_SOURCE_CHANGED:'+rel);add_source(pin)
    for rel in plan['required_additional_source_relative_paths']:add_source(reference(REPO/rel))
    for path in recovery_dir.glob('*.py'):add_source(reference(path))
    for pin in recipe['science_source_pins']:add_source(pin)
    # Small code/JSON authority refs are read; all data bodies stay unopened.
    data={}
    def add_data(pin):
        pin=copy.deepcopy(pin)
        require(isinstance(pin.get('path'),str) and Path(pin['path']).is_absolute() and
                type(pin.get('bytes')) is int and pin['bytes']>=0 and
                re.fullmatch(r'[0-9a-f]{64}',pin.get('sha256','')),'DATA_LOCATOR_WITH_PRIOR_SHA_REQUIRED')
        prior=data.get(pin['path'])
        require(prior is None or all(prior[k]==pin[k] for k in ('path','bytes','sha256')),'DATA_LOCATOR_CONFLICT')
        data[pin['path']]=pin
    for pin in [*recipe.get('authority_pins',[]),*prepared.get('source_pins',[])]:
        if Path(pin['path']).suffix in {'.py','.json','.md'} and pin['bytes']<=SMALL_CAP:add_source(pin)
        else:add_data(pin)
    add_data(plan['tasks_reference'])
    for pin in prepared.get('outputs',[]):
        if Path(pin['path']).suffix=='.json' and pin['bytes']<=SMALL_CAP:add_source(pin)
        else:add_data(pin)
    for pin in prepared.get('source_sprime_files',[]):add_data(pin)
    for row in closed:add_data(row['reference'])
    require(plan['original_pilot_actual_core_seconds']==230800 and
            plan['original_pilot_estimated_core_seconds']==230400 and
            plan['original1p5_estimate_gate_core_seconds']==345600,
            'ORIGINAL_COST_FACTS_AND_GATE_MUST_NOT_CHANGE')
    plan['status']='ROOT_APPROVED_RECOVERY_EXECUTION'
    plan['wall_seconds']=6900
    plan['additional_allocated_core_seconds_cap']=110400
    plan['root_budget_resource_review']=(
        'Root independently selects16CPU64GiB/6900seconds under the2026-10-26 continuous-submit instruction. '
        'Prior230800+new110400<=original345600core-second guide gate; this ceiling is not a runtime forecast. '
        'Queue admission is pending until the original all-user-declared85pct and live64G checks pass. '
        'No old336 approval, small-test measured-memory policy, new seed or logical retry is reused.')
    require(plan['runtime_forecast']=='RIGHT_CENSORED_NO_DEFENSIBLE_POINT_ESTIMATE' and
            plan['formal_generation_authorized'] is False,'RECOVERY_IS_NOT_FORECAST_OR_FULL_AUTHORITY')
    write_new(plan_path,plan)
    approval.update(status='APPROVED_FOR_THIS_RECOVERY_ONLY',plan_reference=reference(plan_path),
        cost_ceiling_not_forecast=110400,user_budget_and_resource_reply=USER_REPLY,
        original_336_approval_reused=False,
        action='Queue this bounded recovery; execute only after actual strict startup admission. No automatic retry or full-run release.',
        user_instruction_source='Active thread continuous-submit objective dated2026-10-26',
        root_budget_choice_within_existing_guide_gate=True,
        strict_resources={'cpus':16,'memory_gib':64,'wall_seconds':6900,'nodes':'14-19','all_user_declared_memory_fraction':0.85,
            'zero_other_memory_is_unbounded':True,'small_test_memory_exception_used':False},
        cost_calculation={'original_actual_core_seconds':230800,'new_allocation_ceiling_core_seconds':110400,
            'combined_ceiling_core_seconds':341200,'original1p5_gate_core_seconds':345600,'headroom_core_seconds':4400},
        reviewed_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat())
    write_new(approval_path,approval)
    add_source(reference(plan_path));add_source(reference(approval_path));add_source(reference(Path(__file__).absolute()))
    argv=[PYTHON,'-B',str(recovery_dir/'run_recovery.py'),'--plan',str(plan_path),'--approval',str(approval_path),
          '--root-preflight',str(a.root_preflight),'--output',str(a.output)]
    tests=[PYTHON,'-B','-m','unittest','discover','-s',str(recovery_dir),'-p','test_recovery.py','-v']
    dispatch={'schema':'STRICT_QUEUED_SPRIME_RECOVERY_DISPATCH_V1','status':'READY_METADATA_ONLY_NOT_QUEUED_NOT_RUN',
        'job_name':a.name,'plan':reference(plan_path),'approval':reference(approval_path),'root_preflight_path':str(a.root_preflight),
        'execution_argv':argv,'new_fixture_argv':tests,'new_fixture_count':6,
        'request_fields':{'kind':'conformer','pilot':True,'partition':'cpu','node':a.node,'cpus':16,'memory_gib':64,
            'wall_seconds':6900,'estimated_peak_output_bytes':plan['max_output_bytes']+plan['closure_max_output_bytes']+64*1024**2,
            'root_review':{'status':'APPROVED','reviewer':'root','approval_reference':reference(approval_path),
                'scope':'Only two original missing-task physical reexecutions and14same-seed controls;334oldpackages retained. Strict queued startup admission required.'}},
        'source_references':list(source.values()),'data_references':list(data.values()),
        'output':str(a.output),'closure_output_requires_independent_analysis_request':True,
        'required_startup_proof_fields':['observed_at','uid','request','existing_jobs_all_users','node_metadata',
            'committed_memory_mib','account_free_bytes'],
        'startup_proof_notes':{'observed_at':'fresh target-node-compatible ISO timestamp;0<=age<=3600seconds',
            'uid':1278,'request':'Must match exact node/16CPU/64GiB/6900seconds,kind=conformer,pilot=true,root_reviewAPPROVED,no resource_policy or memory_basis',
            'source_references':'Include this dispatch source list plus actual queue launcher/controller/script dependencies',
            'existing_jobs_all_users':'Other jobs only, each metadata contains exactly one positive MinMemoryNode or MinMemoryCPU; zero/missing blocks',
            'committed_memory_mib':'Conservative other-job declared reservation excluding this actual64GiB allocation; own64GiB is added once',
            'node_metadata':'Must include RealMemory; other declarations+64GiB<=85pctRealMemory',
            'account_free_bytes':'Must leave>=200GB after8GiB science output; request peak also includes1GiBclosure+64MiBmetadata'},
        'original_336_timeout_preserved':True,'original_334_package_bodies_read_or_stat_ed':False,
        'tasks_or_LMDB_or_parquet_bodies_read_or_stat_ed':False,'scientific_imports_or_computation_run':False,
        'scheduler_commands_run':False,'automatic_submission_or_retry':False,'formal_generation_authorized':False,
        'limits':'Metadata preparation is not actual resource admission, fixture execution, recovery success, closure acceptance or a full-population release.'}
    write_new(dispatch_path,dispatch)
    print(json.dumps({'status':dispatch['status'],'plan':reference(plan_path),'approval':reference(approval_path),
        'dispatch':reference(dispatch_path),'execution_argv':argv,'new_fixture_argv':tests,
        'source_references':len(source),'data_references':len(data),'combined_generation_ceiling_core_seconds':341200,
        'scheduler_commands_run':False,'science_run':False}))


if __name__=='__main__':main()
