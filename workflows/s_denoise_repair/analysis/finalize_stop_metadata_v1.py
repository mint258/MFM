"""Sonmi metadata-only closure of measured guide STOP and own service retirement."""
import argparse,hashlib,json,os,socket,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
GUIDE='240b7b8132603517a7640662a5ea75e67371d5633e8a3c723ab148174c0b8fa3'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p),bytes=Path(p).stat().st_size)
def load(p):return json.loads(Path(p).read_text())
def save(p,d):
    assert p.is_relative_to(R) and not p.exists()
    with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def query(ids):
    a=['sacct','-X','-j',','.join(sorted(ids)),'-n','-P','--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS']
    p=subprocess.run(a,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60);assert p.returncode==0,p.stderr
    rows={row[0]:row[1:] for row in (line.split('|') for line in p.stdout.splitlines() if line)}
    assert set(rows)==set(ids)
    return rows,p.stdout
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--action',choices=['stop-record','retirement-receipt'],required=True)
    ap.add_argument('--accounting',type=Path);ap.add_argument('--archive-receipt',type=Path)
    ap.add_argument('--quota-retirement',type=Path);ap.add_argument('--archive-retirement',type=Path);ap.add_argument('--output',type=Path);a=ap.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    assert sha(R/'user_repair_guide.md')==GUIDE
    if a.action=='stop-record':
        phases=['d3_local_blocks_v1','d3_message1_v1','d3_message2_v1'];references=[];ids=set();results={}
        for phase in phases:
            directory=R/'control'/phase;st=load(directory/'status.json')
            required='D3_PHASE_COMPLETE_AWAITING_SCIENTIFIC_GATE' if phase==phases[0] else 'D3_MESSAGE_LAYER_CAPABILITY_FAILED'
            assert st['status']==required,(phase,st['status'])
            references.extend([ref(directory/'status.json'),ref(directory/'jobs.json')])
            for key,job in load(directory/'jobs.json').items():
                pointer=load(R/'reports'/(key+'_latest.json'));assert sha(pointer['path'])==pointer['sha256']
                d=load(pointer['path']);assert d['status']=='D3_CONDITION_COMPLETE' and d['optimizer_updates']==4000
                assert d['configuration_sha256']==job['configuration_sha256']==sha(job['configuration'])
                assert d['runtime']['job_id']==job['job_id'];ids.add(job['job_id']);results[key]=pointer
        profile=R/'reports/completed_D3_profiles_message2_v1/profiles.json';d=load(profile)
        assert d['status']=='COMPLETED_CONDITION_COST_AND_GRADIENT_PROFILES_ONLY_NOT_STAGE3_GATE'
        assert {row['condition']+'_seed'+str(row['seed']) for row in d['rows']}=={'A4_msg2_seed0','A4_msg2_seed1'}
        ids.add(d['job_id']);references.extend([ref(profile),ref(profile.with_name('actual_closure_v1.json'))])
        rows,raw=query(ids);assert all(row[:2]==['COMPLETED','0:0'] for row in rows.values())
        gate=R/'reports/Stage3_gate_initial_v1.json';g=load(gate)
        assert g['status']=='STAGE3_GATES_NOT_ALL_PASSED' and not g['formal_training_authorized_by_gate']
        references.extend([ref(gate),ref(R/'configs/D3_source_binding_v4.json'),ref(R/'configs/cost_estimator_v2.json'),ref(R/'configs/lookup_refit_closure_v1.json')])
        record=dict(status='GUIDE_STOP_AFTER_ALL_FIXED_STEP_DIAGNOSTICS_ACTUALLY_CLOSED',reason='D3_MESSAGE_LAYER_CAPABILITY_FAILED',
          phase='d3_message2_v1',guide_sha256=GUIDE,guide_reference=ref(R/'user_repair_guide.md'),timestamp_unix=time.time(),
          guide_stop_quote='先尝试加 1–2 层消息传递；仍不达标就停止，不进入全量训练。',
          explanation='Original A2–A4 and both authorized message-layer remedies did not beat the fixed TRAIN-only lookup in both seeds. Original five-gate table also fails capability and cost.',
          actual_parents=rows,raw_sacct=raw,result_references=results,source_references=references,
          message_A5_performed=False,message_interference_status='UNMEASURED_AFTER_CAPABILITY_FAILURE',
          formal_training_authorized=False,full_training_run=False,epoch_recommendation=None,
          next_action='Finish measured diagnostic delivery; await user decision under the supplied guide.')
        out=R/'GUIDE_STOP.json';save(out,record);print(json.dumps(ref(out)));return
    for p in [a.accounting,a.archive_receipt,a.quota_retirement,a.archive_retirement,a.output]:
        assert p and p.is_absolute() and p.is_relative_to(R)
    accounting=load(a.accounting);assert accounting['status']=='ACTUAL_ALL_REGISTERED_REPAIR_PARENTS_TERMINAL' and not accounting['active_parent_ids']
    actual,raw=query(set(accounting['rows']))
    for jid,row in accounting['rows'].items():assert actual[jid]==[row[k] for k in ['State','ExitCode','ElapsedRaw','AllocCPUS']]
    archive=load(a.archive_receipt);assert archive['records'] and not archive['errors'] and all(r['archival_status']=='ARCHIVED' for r in archive['records'])
    sources={str(p) for p in (R/'diagnostics').glob('*/job_*/wandb/offline-run-*') if p.is_dir() and not p.is_symlink()}
    assert sources=={r['source_run'] for r in archive['records']}
    retirements=[]
    for role,p in [('quota',a.quota_retirement),('archive',a.archive_retirement)]:
        d=load(p);assert d['status']=='EXACT_OWN_METADATA_SERVICE_ACTUALLY_EXITED' and d['role']==role and d['reason']=='task-stop'
        assert not d['after']['exact_process_live'] and d['no_scientific_process_signalled'] and d['metadata_role_whitelist_verified']
        identity_reference=d['identity_reference'];ip=Path(identity_reference['identity_path']);assert sha(ip)==identity_reference['identity_sha256']
        identity=load(ip);assert identity['uid']==1278 and identity['pid']==d['pid'] and identity['scientific_processes_started']==0
        proc=Path('/proc')/str(d['pid']);after={'state':'ABSENT','exact_process_live':False}
        if proc.exists():
            tail=proc.joinpath('stat').read_text().rsplit(')',1)[1].split();same=str(tail[19])==str(identity['start_ticks'])
            assert not same or tail[0]=='Z'
            after={'state':tail[0] if same else 'PID_REUSED_DIFFERENT_START_TICKS','exact_process_live':False}
        inner=dict(role=role,retirement_reference=ref(p),actual_retirement=d,identity=identity,proc_rechecked_after_retirement=after)
        if role=='archive':
            closed=ip.with_name('closed.json');c=load(closed);assert c['identity_sha256']==identity_reference['identity_sha256'] and c['status'] in ['ARCHIVE_SERVICE_STOPPED','ARCHIVE_SERVICE_EXPIRED']
            inner.update(archive_closed_reference=ref(closed),archive_closed=c)
        retirements.append(inner)
    out=dict(status='OWN_SREPAIR_METADATA_SERVICES_RETIRED_AFTER_ALL_JOBS_AND_ARCHIVES_CLOSED',timestamp_unix=time.time(),
      accounting_reference=ref(a.accounting),archive_reference=ref(a.archive_receipt),actual_parent_recheck=actual,raw_sacct=raw,
      retired_own_metadata_services=retirements,no_scientific_or_unrelated_process_signalled=True,source_reference=ref(__file__))
    save(a.output,out);print(json.dumps(ref(a.output)))
if __name__=='__main__':main()
