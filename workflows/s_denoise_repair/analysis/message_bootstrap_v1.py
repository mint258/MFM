"""Source3 guide-only capability fallback; metadata preparation/start after actual parent closure."""
from concurrent.futures import ThreadPoolExecutor
import argparse,copy,hashlib,json,math,os,socket,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
SOURCE=R/'source_v3'
GUIDE_SHA='240b7b8132603517a7640662a5ea75e67371d5633e8a3c723ab148174c0b8fa3'
PYTHON='/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
GROUPS=['A2','A3','A4']

def ref(path):
    p=Path(path);b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))

def check(row):
    assert ref(row['path'])['sha256']==row['sha256'],'REGISTERED_REFERENCE_CHANGED'

def write_once(path,value):
    text=json.dumps(value,indent=2,allow_nan=False)+'\n'
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():assert path.read_text()==text,'EXISTING_PREPARATION_DIFFERS'
    else:
        with path.open('x') as f:f.write(text)

def assess_fallback(values,selection,threshold,layers,previous=None):
    """No learning or cost tuning: check the guide's exact denoising fallback branch."""
    assert layers in [1,2] and math.isfinite(threshold) and threshold>0
    assert set(values)==set(GROUPS)
    for scores in values.values():
        assert len(scores)==2 and all(isinstance(v,(int,float)) and math.isfinite(v) and v>=0 for v in scores)
    means={name:sum(values[name])/2 for name in GROUPS}
    best=min(GROUPS,key=lambda name:(means[name],GROUPS.index(name)))
    assert selection['selected']==best and selection['scores']==means,'ORIGINAL_LR_SELECTION_DIFFERS'
    capable={name:all(value<threshold for value in values[name]) for name in GROUPS}
    assert not any(capable.values()),'GUIDE_DOES_NOT_AUTHORIZE_CAPABILITY_FALLBACK'
    if layers==2:
        assert previous is not None and previous['status']=='D3_MESSAGE_LAYER_CAPABILITY_FAILED'
        assert previous['message_layers']==1
        measured=previous['local_RMSE_A_by_seed']
        assert len(measured)==2 and all(math.isfinite(v) and v>=0 for v in measured)
        assert previous['lookup_FULL2000_RMSE_A']==threshold
        assert not all(v<threshold for v in measured),'MESSAGE1_CAPABILITY_PASSED_NO_LAYER2_REMEDY'
    return dict(selected_original_LR_group=best,original_multitask_final_RMSE_A_by_seed=values,
        original_multitask_denoising_capable_by_group=capable,original_mean_final_RMSE_A=means,
        lookup_D3_FULL2000_RMSE_A=threshold,message_layers=layers)

def actual_closed(jobs):
    identifiers={job['job_id'] for job in jobs.values()};assert identifiers and all(j.isdecimal() for j in identifiers)
    raw=subprocess.run(['sacct','-j',','.join(sorted(identifiers)),'-n','-X','-P','-o','JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS'],
        stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30,check=True)
    parsed={row[0]:row[1:] for row in (line.strip().split('|') for line in raw.stdout.splitlines() if line.strip())}
    assert set(parsed)==identifiers
    assert all(row[:2]==['COMPLETED','0:0'] and int(row[3])>=16 for row in parsed.values()),'ACTUAL_PARENTS_NOT_CLOSED_C0'
    return dict(status='ACTUAL_SONMI_SACCT_SNAPSHOT',host='sonmi',uid=1278,columns=['State','ExitCode','ElapsedRaw','AllocCPUS'],rows=parsed,raw_stdout=raw.stdout)

def load_result(group,seed,jobs,inputs):
    key=group+'_seed'+str(seed);pointer=R/'reports'/(key+'_latest.json')
    row=json.loads(pointer.read_text());check(row);result=json.loads(Path(row['path']).read_text())
    job=jobs[key]
    assert result['status']=='D3_CONDITION_COMPLETE' and result['optimizer_updates']==4000
    assert result['condition']==group and result['seed']==seed and result['runtime']['job_id']==job['job_id']
    assert result['configuration_sha256']==job['configuration_sha256']==ref(job['configuration'])['sha256']
    inputs.extend([ref(pointer),row,ref(job['configuration'])]);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--message-layers',type=int,choices=[1,2],required=True);ap.add_argument('--start',action='store_true');args=ap.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    assert ref(R/'user_repair_guide.md')['sha256']==GUIDE_SHA and not (R/'GUIDE_STOP.json').exists()
    binding_path=R/'configs/D3_source_binding_v4.json';binding=json.loads(binding_path.read_text())
    assert binding['source_root']==str(SOURCE)
    with ThreadPoolExecutor(16) as pool:list(pool.map(check,binding['files']))
    initial=R/'control/d3_local_blocks_v1';initial_status=json.loads((initial/'status.json').read_text())
    assert initial_status['status']=='D3_PHASE_COMPLETE_AWAITING_SCIENTIFIC_GATE','INITIAL_D3_INCOMPLETE'
    jobs=json.loads((initial/'jobs.json').read_text());assert len(jobs)==12
    snapshot=actual_closed(jobs)
    selection=json.loads((initial/'LR_selection.json').read_text());inputs=[]
    values={name:[load_result(name,seed,jobs,inputs)['final']['local_rmse_A'] for seed in [0,1]] for name in GROUPS}
    lookup_closure=R/'configs/lookup_refit_closure_v1.json';lookup_binding=json.loads(lookup_closure.read_text())
    assert lookup_binding['status']=='ACTUAL_FULL_TRAIN_LOOKUP_REFIT_CLOSED' and lookup_binding['guide_sha256']==GUIDE_SHA
    assert lookup_binding['actual_parent'][:2]==['COMPLETED','0:0']
    check(lookup_binding['result_reference']);lookup=json.loads(Path(lookup_binding['result_reference']['path']).read_text())
    assert lookup['status']=='NEW_TRAIN_LOOKUP_REFIT_AND_FULL_EVALUATION_COMPLETE' and lookup['TRAIN_records']==11104772 and lookup['validation_values_used_for_fit'] is False
    threshold=lookup['metrics']['D3_FULL2000']['lookup_rmse_A'];previous=None;previous_snapshot=None
    if args.message_layers==2:
        prior=R/'control/d3_message1_v1';previous=json.loads((prior/'status.json').read_text())
        previous_jobs=json.loads((prior/'jobs.json').read_text());assert len(previous_jobs)==2
        previous_snapshot=actual_closed(previous_jobs)
        for seed in [0,1]:
            result=load_result(selection['selected']+'_msg1',seed,previous_jobs,inputs)
            assert result['final']['local_rmse_A']==previous['local_RMSE_A_by_seed'][seed]
        inputs.extend([ref(prior/'status.json'),ref(prior/'jobs.json')])
    assessment=assess_fallback(values,selection,threshold,args.message_layers,previous)
    phase='d3_message'+str(args.message_layers)+'_v1';group=selection['selected']+'_msg'+str(args.message_layers)
    control=R/'control'/phase;control.mkdir(parents=True,exist_ok=True)
    assert not (control/'identity.json').exists() and not (control/'bootstrap_start.json').exists(),'MESSAGE_ROOT_ALREADY_STARTED'
    snapshot_path=R/'control/accounting_snapshots'/('message'+str(args.message_layers)+'_bootstrap_initial_v1.json')
    write_once(snapshot_path,snapshot)
    if previous_snapshot is not None:write_once(R/'control/accounting_snapshots'/'message2_bootstrap_previous_v1.json',previous_snapshot)
    source_binding=ref(binding_path)
    authorization=dict(status='GUIDE_AUTHORIZED_MESSAGE_CAPABILITY_FALLBACK',guide_sha256=GUIDE_SHA,source_binding=source_binding,
        initial_phase='d3_local_blocks_v1',initial_actual_parent_snapshot=ref(snapshot_path),
        initial_selection_reference=ref(initial/'LR_selection.json'),lookup_closure_reference=ref(lookup_closure),
        scientific_input_references=inputs,**assessment)
    authorization_path=R/'configs'/('message'+str(args.message_layers)+'_capability_authorization_v1.json')
    write_once(authorization_path,authorization)
    configurations=[]
    for seed in [0,1]:
        parent=SOURCE/'workflows/s_denoise/configs'/(selection['selected']+'_seed'+str(seed)+'_v3.json')
        cfg=json.loads(parent.read_text());cfg['condition']=group
        cfg['model']['head']['geometry_message_layers']=args.message_layers
        assert not cfg['model']['head'].get('geometry_cache_atom_projections',False)
        cfg['message_fallback']={'guide_capability_authorization':ref(authorization_path),'parent_configuration':ref(parent),
            'message_scalar_aggregation_normalization':'sqrt_degree','output_vector_normalization':'none'}
        dest=SOURCE/'workflows/s_denoise/configs'/(group+'_seed'+str(seed)+'_v3.json')
        write_once(dest,cfg);configurations.append(ref(dest))
    plan=dict(status='GUIDE_CAPABILITY_MESSAGE_FALLBACK_SAME_ORIGINAL_SELECTED_LR_V3',phase=phase,conditions=[group],scan_groups=[group],
        A5_name='A5_msg'+str(args.message_layers),message_layers=args.message_layers,new_lookup_reference=lookup_binding['result_reference'],
        source_binding=source_binding,guide_capability_fallback_authorization=ref(authorization_path),configurations=configurations)
    plan_path=R/'configs'/('D3_message'+str(args.message_layers)+'_plan_v1.json');write_once(plan_path,plan)
    if args.start:
        # The Root is metadata-only. Model computation is submitted exclusively by Slurm.
        controller=R/'analysis/d3_message_root_v2.py';tested=json.loads((R/'configs/source_aware_metadata_tests_closure_v1.json').read_text())
        for row in tested['source_references']:check(row)
        assert any(row['path']==str(controller) for row in tested['source_references']) and tested['tests']==31
        env=dict(os.environ);env['PYTHONPATH']=str(SOURCE/'workflows/s_denoise')+':'+str(R/'analysis');env['PYTHONDONTWRITEBYTECODE']='1'
        argv=[PYTHON,'-B',str(controller),'--plan',str(plan_path)]
        with (control/'root.stdout.log').open('x') as log:
            process=subprocess.Popen(argv,cwd=R.parent.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        write_once(control/'bootstrap_start.json',dict(pid=process.pid,argv=argv,controller_reference=ref(controller),plan_reference=ref(plan_path),
            timestamp=time.time(),uid=1278,role='Metadata-only Slurm message capability fallback coordinator'))
    print(json.dumps(dict(status='MESSAGE_BOOTSTRAP_STARTED' if args.start else 'MESSAGE_BOOTSTRAP_PREPARED',phase=phase,group=group,plan_reference=ref(plan_path))))

if __name__=='__main__':main()
