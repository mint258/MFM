"""Prepare, admit and submit only the now-authorized C3 plus view-inactive H1/D."""
import argparse,copy,csv,datetime,fcntl,json,os,re,shlex,socket,subprocess
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
PY='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
APY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
WRAP=str(R/'tools/model_v3/v2_run_development.sbatch')
J=C/'MODEL_V3_C3_HEADS_LAUNCH_20261113.json'
CP=C/'C3_VIEWS_20261113'
HP=C/'HEADS_V3_20261113'
parser=argparse.ArgumentParser()
parser.add_argument('phase',choices=['prepare','submit','release'])
phase=parser.parse_args().phase
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20'
os.chdir(R)
def run(argv):
    r=subprocess.run(argv,capture_output=True,text=True)
    if r.returncode: raise RuntimeError(str(argv)+' '+r.stderr)
    return r.stdout.strip()
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.next_'+str(os.getpid()))
    tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
def plans(state):
    common=dict(status=state['phase'],selected_C1='C1-0',selected_latent='none',
        selection_source=str(R/'results/model_v3_t1.json'),seed=0,
        source_roles=['train','train_inner_validation'],downstream_TEST_read=False,
        scientific_sample_budget=6000000,effective_batch_size=32,
        single_global_output_forecast=True)
    c3=dict(common,runs=[x for x in state['rows'] if x['stage']=='C3'],
        reused_three_S=dict(run_id='S_C1_0_seed0_v2',original_stage='C1',
            output=str(C/'S_C1_0_seed0_v2'),checkpoint=str(C/'S_C1_0_seed0_v2/samples_6000000.pt'),
            panel=str(B/'DEV_PANEL_V2_20261111/C1-0_S_seed0/R3_summary.json'),
            new_training_samples=0,scientific_budget=6000000),
        estimated_GPU_hours=50,report_above_GPU_hours=75,ask_above_GPU_hours=150,
        decision_manifest=str(CP/'decision_manifest.json'))
    heads=dict(common,runs=[x for x in state['rows'] if x['stage']=='HEADS'],
        execution_reason='Pure P/D do not call structural view builder; start prescribed H1/D while C3 views are pending.',
        view_metadata='three, scientifically inactive in pure D; retain original metadata for reuse',
        remaining_heads_matrix='Complete H1/H2/H3 x P/D/SDP after C3; H1/P original C1-0 P6M and H1/SDP winning C3 are exact reuse candidates.',
        estimated_GPU_hours=115,report_above_GPU_hours=172.5,ask_above_GPU_hours=345)
    save(CP/'plan.json',c3);save(HP/'plan.json',heads)
if phase=='prepare':
    assert not J.exists(),'Resume the existing journal, never submit duplicate runs'
    t1=json.loads((R/'results/model_v3_t1.json').read_text())
    assert t1['provisional_latent']=='none' and len(t1['rows'])==10
    assert not t1['lambda_k_required'] and not t1['fresh6M_confirmation_required']
    templates=json.loads((R/'configs/model_v3/followon_templates.json').read_text())
    byname={x['name']:x for x in templates['trials']}
    native=run(['/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/cpu_git_tools_v1/bin/git','rev-parse','HEAD'])
    specs=[('C3','two','S','M3_S_two_seed0','compute-0-0','GPU-a967b766-fb5e-8db3-b09c-4ddc6c02b332',32,14800000000),
        ('C3','two','SDP','M3_SDP_two_seed0','compute-0-5','GPU-dac07d74-6269-c7db-8832-340dd3c0b377',16,22000000000),
        ('C3','three','SDP','M3_SDP_three_seed0','compute-0-7','GPU-9db54192-dd3f-3177-e56f-dcd161ff932c',16,22000000000),
        ('HEADS','H1','D','M3_D_H1_seed0','compute-0-6','GPU-bdb3e139-15a8-755e-2e80-f2b8abaf66ef',32,11000000000)]
    state=dict(phase='PREPARING',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_native_commit=native,selected_latent='none',T1_source=str(R/'results/model_v3_t1.json'),
        output_roots=[str(B/'C3_VIEWS_20261113'),str(B/'HEADS_V3_20261113')],
        rows=[],admission={},deleted_files=False,paid_server=False,formal_pretraining=False)
    for stage,arm,cond,template,node,gpu,micro,peak in specs:
        group=CP if stage=='C3' else HP
        name=arm+'_'+cond+'_seed0'
        out=B/group.name/name
        assert not out.exists(),'Existing native output must be retained, not overwritten'
        cfg=copy.deepcopy(byname[template]['configuration'])
        cfg.update(output=str(out),distance_bias='C1-0',condition=cond,latent='none',
            latent_spec=None,stage=stage,arm=arm,views=cfg.get('views') or 'three',
            microbatch_size=micro,code_tag='model-v3:'+native)
        cfg.pop('resume',None)
        cfgpath=group/(name+'.json');save(cfgpath,cfg)
        ev=dict(checkpoint=str(out/'samples_6000000.pt'),output=str(out/'dev_eval_v2'),
            panel='v2',cache_root=str(B/'LATENT_V3_20261111/readout_cache'))
        evpath=group/(name+'_dev.json');save(evpath,ev)
        state['rows'].append(dict(stage=stage,arm=arm,condition=cond,node=node,gpu=gpu,
            mode='native_selected' if cond=='S' else 'selected',python=PY,
            configuration=str(cfgpath),output=str(out),evaluation_configuration=str(evpath),
            evaluation_output=ev['output'],gpu_peak_estimate_bytes=peak,microbatch_size=micro,
            restarts=0,taskbook_stage=5))
    with (C/'model_output_budget.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        budget=json.loads((C/'model_output_budget.json').read_text())
        for root in state['output_roots']:
            if root not in budget['roots']:budget['roots'].append(root)
        save(C/'model_output_budget.json',budget)
        state['global_model_peak_bytes']=budget['total_peak_bytes']
    for row in state['rows']:
        node=row['node']
        control=run(['scontrol','show','node',node,'-o'])
        free=int(re.search(r'\bCPUTot=(\d+)',control)[1])-int(re.search(r'\bCPUAlloc=(\d+)',control)[1])
        assert free>=16,'No free16CPU on '+node
        gpu=run(['ssh','-n',node,'nvidia-smi --query-gpu=uuid,memory.total --format=csv,noheader,nounits'])
        devices={a.strip():int(float(b.strip())*1024**2) for a,b in csv.reader(gpu.splitlines())}
        assert row['gpu'] in devices and devices[row['gpu']]>=row['gpu_peak_estimate_bytes']
        contexts=run(['ssh','-n',node,'nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv,noheader,nounits'])
        assert not contexts,'A GPU context is already present on '+node
        guard=run(['ssh','-n',node,'cd '+str(R)+' && '+PY+' -B tools/model_v3/v2_diagnosis_disk.py --once --output '+row['output']+' --node '+node+' --job 0 --state /dev/null'])
        state['admission'][node]=dict(controller=control,free_CPUs=free,GPU=gpu,contexts=contexts,
            guard=json.loads(guard),mount=run(['ssh','-n',node,'findmnt -T /lfshome/zixiao']),
            bytes=run(['ssh','-n',node,'df -B1 / /lfshome/zixiao /share/home/zixiao/descriptor_analysis']),
            inodes=run(['ssh','-n',node,'df -Pi / /lfshome/zixiao /share/home/zixiao/descriptor_analysis']),
            memory=run(['ssh','-n',node,'head -3 /proc/meminfo']))
    state['phase']='PREPARED_ADMITTED'
    save(J,state);plans(state)
    panels=dict(two=dict(S=state['rows'][0]['evaluation_output']+'/R3_summary.json',
        SDP=state['rows'][1]['evaluation_output']+'/R3_summary.json'),
        three=dict(S=str(B/'DEV_PANEL_V2_20261111/C1-0_S_seed0/R3_summary.json'),
        SDP=state['rows'][2]['evaluation_output']+'/R3_summary.json'))
    save(CP/'decision_manifest.json',dict(kind='candidate_set',group='C3 views',
        comparison='views',simplicity_order=['two','three'],panels=panels,
        selection_source=str(R/'results/model_v3_t1.json'),selected_latent='none'))
else:
    state=json.loads(J.read_text())
    if phase=='submit':
        assert state['phase'] in ('PREPARED_ADMITTED','SUBMITTING_HELD')
        state['phase']='SUBMITTING_HELD';save(J,state)
        def submit(row,mode,cfg,dependency,name,cpu=16,archive=False):
            argv=['sbatch','--hold','--parsable','--partition=all',
                '--nodelist='+('compute-0-20' if archive else row['node']),
                '--cpus-per-task='+str(cpu),'--time=0','--job-name='+name]
            if archive:argv.append('--nice=10000')
            if dependency:argv.append('--dependency=afterok:'+':'.join(map(str,dependency)))
            if mode=='dev' and row['stage']=='C3':
                argv.append('--export=ALL,MODEL_V3_FOLLOWON_PLAN='+str(CP/'plan.json'))
            argv += [WRAP,mode,cfg,'none' if archive else row['gpu'],APY if archive else PY]
            return int(run(argv).split(';')[0])
        for row in state['rows']:
            tag=row['stage']+'-'+row['arm']+'-'+row['condition']
            if 'job' not in row:
                row['job']=submit(row,row['mode'],row['configuration'],None,'v3-'+tag)
                save(J,state)
            if 'evaluation_job' not in row:
                row['evaluation_job']=submit(row,'dev',row['evaluation_configuration'],[row['job']],'v3-dev-'+tag)
                save(J,state)
            if 'archive_job' not in row:
                group=CP if row['stage']=='C3' else HP
                name=row['stage']+'_'+row['arm']+'_'+row['condition']+'_train_evaluation_closed'
                sources=group/(name+'_sources.json')
                save(sources,dict(schema='MODEL_V3_CLOSED_SDK_INPUTS_V1',tracking_root=str(B),
                    runs=[dict(job=job,sdk_directories=[dict(path=str(Path(root)/'offline_wandb'/str(job)),
                        marker='sdk_finished.json')]) for job,root in (
                        (row['job'],row['output']),(row['evaluation_job'],row['evaluation_output']))]))
                acfg=group/(name+'_archive.json')
                aout=B/'WANDB_ARCHIVES_20261111'/name
                save(acfg,dict(sources_manifest=str(sources),jobs=[row['job'],row['evaluation_job']],
                    output=str(aout),name=name+'_offline_SDK_20261113'))
                row['archive_configuration']=str(acfg);row['archive_output']=str(aout)
                row['archive_job']=submit(row,'archive_sdk',str(acfg),
                    [row['job'],row['evaluation_job']],'v3-sdk-'+tag,cpu=1,archive=True)
                save(J,state)
        rp=C/'MODEL_V3_latent_guard_recovery_20261111.json'
        rec=json.loads(rp.read_text());known={r['job'] for r in rec['jobs']}
        for row in state['rows']:
            entries=[dict(row),dict(job=row['evaluation_job'],node=row['node'],gpu=row['gpu'],
                python=PY,mode='dev',configuration=row['evaluation_configuration'],
                output=row['evaluation_output'],restarts=0,training_job=row['job'],
                condition=row['condition'],stage=row['stage'],arm=row['arm']),
                dict(job=row['archive_job'],node='compute-0-20',gpu='none',python=APY,
                mode='archive_sdk',configuration=row['archive_configuration'],
                output=row['archive_output'],restarts=0,source_jobs=[row['job'],row['evaluation_job']],
                selection_use=False,cpus_per_task=1)]
            for entry in entries:
                if entry['job'] not in known:rec['jobs'].append(entry);known.add(entry['job'])
        save(rp,rec);state['recovery_entries']=len(rec['jobs'])
        state['phase']='REGISTERED_CHAINS_HELD';save(J,state);plans(state)
    else:
        assert state['phase'] in ('REGISTERED_CHAINS_HELD','RELEASING')
        state['phase']='RELEASING';save(J,state)
        for row in state['rows']:
            for key in ('job','evaluation_job','archive_job'):
                raw=run(['scontrol','show','job','-o',str(row[key])])
                assert 'UserId=zixiao(1278)' in raw
                if 'JobState=PENDING' in raw and ('JobHeldUser' in raw or 'Priority=0' in raw):
                    run(['scontrol','release',str(row[key])])
        state['phase']='SUBMITTED_CHAINS_RELEASED'
        state['released_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        save(J,state);plans(state)
print(json.dumps(dict(phase=state['phase'],runs=[{k:r.get(k) for k in
    ('stage','arm','condition','node','mode','job','evaluation_job','archive_job')} for r in state['rows']],
    recovery_entries=state.get('recovery_entries'),global_model_peak_bytes=state.get('global_model_peak_bytes'))))
