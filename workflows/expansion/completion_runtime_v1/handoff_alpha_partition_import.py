"""Handoff only after both rescue producers close; prepare held successors before stop."""
import copy,json,os,pathlib,runpy,shlex,subprocess,time
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
B=A/'control/pubchem_expansion_runtime_20261103'
D=A/'control/pubchem_completion_environment_20261103'
BASE=A/'code/pubchem_completion_20261103_497c584'
PY=A/'software/pubchem_completion_20261103_venv/bin/python'
PREFIX='alpha_partition_import_handoff_20261105_v1'
TARGET=dict(job_id='1885263',tag='main_rescue_resume_20261105_v1_low11')
SOURCES=[dict(job_id='1885267',tag='alpha_rescue6_20261105_v1'),dict(job_id='1885266',tag='alpha_rescue7_20261105_v1')]
CONSUMERS=('1885248','1885249','1885250','1885251','1885252','1885255','1885256')

def script(tag,mode,node,partition,workers,config,entry,helper):
    args=[str(PY),'-I','-B',str(helper),'--mode',mode,'--config',str(config),'--entry',str(entry),'--tag',tag]
    text='\n'.join(['#!/bin/bash','#SBATCH --partition='+partition,'#SBATCH --nodelist='+node,'#SBATCH --nodes=1','#SBATCH --ntasks=1','#SBATCH --cpus-per-task='+str(workers),'#SBATCH --time=0','#SBATCH --job-name=pubchem_cache_'+mode,'#SBATCH --output='+str(B/'node_epochs'/(tag+'_%j.out')),'set -euo pipefail','unset SBATCH_MEM SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU','export CUDA_VISIBLE_DEVICES=','export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1','cd '+shlex.quote(str(BASE)),'exec '+shlex.join(args),''])
    subprocess.run(['bash','-n'],input=text,text=True,check=True)
    subprocess.run(['bash','-c','set -euo pipefail; '+next(s for s in text.splitlines()if s.startswith('unset '))],check=True)
    return text

def main():
    if os.getuid()!=1264 or not sys_isolated():raise ValueError('Actual isolated Alpha coordinator')
    runpy.run_path(str(A/'code/shard_guard_cadence_20261105_v2/entry.py'),run_name='_partition_handoff_metadata')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    from workflows.expansion.uff3_alpha_runtime_v1.terminal import parent,TERMINAL,raw_rows
    helper=D/'prepare_alpha_partition_import_20261105_v1.py'
    functions=runpy.run_path(str(helper),run_name='_partition_prepare_functions')
    rewrite=runpy.run_path(str(D/'repair_resume_batch_startup_20261105_v1.py'),run_name='_pending_config_functions')['rewrite']
    def native(job):return subprocess.check_output(['scontrol','show','job','-o',job],text=True)
    def pending(job):
        raw=native(job)
        Q.need(all(s in raw for s in('UserId=alpha(1264)','JobState=PENDING','Restarts=0','RunTime=00:00:00')),'Own unstarted dependent only')
        return raw
    target_plan_path=B/'node_epochs'/(TARGET['tag']+'_job_'+TARGET['job_id'])/'plan.json'
    previous=Q.load(target_plan_path);root=pathlib.Path(previous['output_directory'])
    if(root/'manifest.json').exists():
        print(json.dumps(dict(status='SKIPPED_ORIGINAL_LOW_ALREADY_COMPLETE',target_manifest_reference=Q.reference(root/'manifest.json'))),flush=True);return
    # No filesystem or scheduler mutation until the actual rescue parent AND steps are C0.
    before={}
    for item in SOURCES:
        job=item['job_id'];raw=subprocess.check_output(['sacct','-P','-j',job,'--format=JobIDRaw,State,ExitCode,UID'],text=True)
        rows=raw_rows(raw,job)
        Q.need(rows and any(r[0]==job+'.batch'for r in rows)and all(r[1:] ==('COMPLETED','0:0')for r in rows),'Both complete rescue parent/batch/all steps required before handoff')
        before[job]=raw
    writer=native(TARGET['job_id']);Q.need(all(s in writer for s in('UserId=alpha(1264)','JobState=RUNNING','NumCPUs=64','NodeList=compute-0-1')),'Actual original running low11 writer')
    rank=pending('1885215');consumers={job:pending(job)for job in CONSUMERS}
    Q.need('afterok:1885263'in rank,'Rank still awaits original writer')
    source_path=D/'alpha_partition_cache_import_20261105_v1_source.json';source=Q.load(source_path)
    Q.need(source['schema']=='ALPHA_OWN_PARTITION_CACHE_IMPORT_SOURCE_V1'and source['original_scientific_runtime_changed']is False,'Immutable separate importer deployment')
    Q.verify(source['entry']);Q.verify(Q.reference(helper))
    folder=D/PREFIX;folder.mkdir(mode=0o700)
    Q.write(folder/'before.json',dict(writer=writer,rank=rank,consumers=consumers,rescue_native=before,target_plan_reference=Q.reference(target_plan_path),coordinator_source=Q.reference(__file__)))
    for index,item in enumerate(SOURCES):
        meta,plan=functions['upstream'](Q,parent,item,folder/('source_'+str(index)),True)
        receipt=Q.load(pathlib.Path(meta['root'])/'manifest.json')
        Q.need(receipt['status']=='SHARD_COMPLETE'and receipt['resource_plan']==meta['plan_reference']and receipt['assigned_hash_buckets']==[str(6+index)]and plan['source_deployment_reference']==previous['source_deployment_reference'],'Actual original-runtime closed rescue manifest')
    refs=list(source['code_references'])+[Q.reference(helper),Q.reference(__file__)]
    for ref in refs:Q.verify(ref)
    import_tag='alpha_partition_import_20261105_v1';resume_tag=TARGET['tag']
    import_seed=copy.deepcopy(previous)
    for key in('execution_argv','runtime_existing_output_stage_reused','resume_output_directory','resume_previous_allocations','external_score_import_references','external_score_import_completed','alpha_partition_score_import_references','alpha_partition_score_import_completed','launcher_startup_proof_reference','upstream_completed'):import_seed.pop(key,None)
    import_seed.update(workers=32,worker_rss_cap_bytes=768<<20,parent_rss_cap_bytes=64<<30,software_rss_budget_bytes=96<<30,sql_memory_bytes=48<<30,spill_cap_bytes=30000000000,output_directory='/gfshome/alpha/pubchem_expansion_20261103/exact/producer_LAUNCHER_ASSIGN_REAL_JOB_ID',scope_key='import_closed_Alpha_rescue6_7_into_original_low11_20261105_v1',code_references=refs,source_deployment_reference=Q.reference(source_path))
    Q.need(import_seed['output_scope_root']=='/gfshome/alpha/pubchem_expansion_20261103/exact'and import_seed['output_cap_bytes']==300000000000 and import_seed['minimum_free_bytes']>=200000000000,'Same aggregate exact cap and future floor')
    import_seed_ref=Q.write(B/(PREFIX+'_import_seed.json'),import_seed)
    config=dict(target=TARGET,sources=SOURCES,expected_target_root=str(root),deployment_reference=Q.reference(source_path),prepare_script_reference=Q.reference(helper),seed_reference=import_seed_ref)
    import_config=B/(PREFIX+'_import_config.json');Q.write(import_config,config)
    import_script=B/(PREFIX+'_import.sbatch')
    with import_script.open('x')as f:f.write(script(import_tag,'import','compute-0-2','all',32,import_config,Q.verify(source['entry']),helper))
    submissions=(folder/'submissions.jsonl').open('x')
    def submit(path,dependency):
        job=subprocess.check_output(['sbatch','--hold','--parsable','--dependency='+dependency,str(path)],text=True).strip().split(';')[0]
        Q.need(job.isdigit(),'Actual held scheduler ID')
        record=dict(job_id=job,script_reference=Q.reference(path),dependency=dependency,native_state=native(job))
        submissions.write(json.dumps(record,sort_keys=True)+'\n');submissions.flush();os.fsync(submissions.fileno())
        Q.need('JobState=PENDING'in record['native_state']and 'UserId=alpha(1264)'in record['native_state'],'Own held successor allocation')
        return job
    import_job=submit(import_script,'afterany:'+TARGET['job_id'])
    seed=copy.deepcopy(previous);seed['resume_output_directory']=str(root)
    seed_ref=Q.write(B/(PREFIX+'_resume_seed.json'),seed)
    resume_cfg=dict(target=TARGET,importer=dict(job_id=import_job,tag=import_tag),expected_target_root=str(root),deployment_reference=previous['source_deployment_reference'],prepare_script_reference=Q.reference(helper),seed_reference=seed_ref)
    resume_deployment=D/'shard_projection_cadence_20261105_v1_source.json'
    original_source=Q.load(resume_deployment)
    Q.need(original_source['schema']=='ALPHA_SHARD_PROJECTION_CADENCE_SOURCE_V1'and original_source['previous_source_reference']==previous['source_deployment_reference']and original_source['resource_changes_only']is True and original_source['byte_identical_to_previous_runtime_after_one_resource_inversion']is True and original_source['Core5_math_queries_F64_and_cache_bindings_changed']is False,'Only the paired-tested projection resource cadence may differ for the next continuation')
    for item in original_source['code_references']:Q.verify(item)
    resume_cfg['deployment_reference']=Q.reference(resume_deployment)
    resume_config=B/(PREFIX+'_resume_config.json');Q.write(resume_config,resume_cfg)
    resume_script=B/(PREFIX+'_resume.sbatch')
    with resume_script.open('x')as f:f.write(script(resume_tag,'resume','compute-0-1','cpu',64,resume_config,Q.verify(original_source['entry']),helper))
    resume_job=submit(resume_script,'afterok:'+import_job)
    changes=[];seen=set();mapping={TARGET['job_id']:resume_job}
    for job,raw in consumers.items():
        pending(job);path=pathlib.Path(next(t[8:]for t in shlex.split(raw)if t.startswith('Command=')))
        args=shlex.split(path.read_text());config_path=pathlib.Path(args[args.index('--config')+1])
        if str(config_path)in seen:continue
        seen.add(str(config_path));old=Q.load(config_path);fresh=rewrite(old,mapping)
        if old==fresh:continue
        archive=folder/config_path.name
        with archive.open('xb')as f:f.write(config_path.read_bytes())
        before_ref=Q.reference(config_path);temporary=config_path.with_name(config_path.name+'.alpha_import_pending')
        with temporary.open('x')as f:json.dump(fresh,f,sort_keys=True);f.write('\n')
        os.replace(temporary,config_path);Q.need(Q.load(config_path)==fresh,'Pending consumer readback')
        changes.append(dict(job_id=job,before=before_ref,archive=Q.reference(archive),after=Q.reference(config_path)))
    pending('1885215');subprocess.run(['scontrol','update','JobId=1885215','Dependency=afterok:'+resume_job+':1885264'],check=True)
    rank_after=native('1885215');Q.need('afterok:'+resume_job in rank_after,'Real rank dependency retargeted before old writer stop')
    Q.write(folder/'prepared.json',dict(import_job=import_job,resume_job=resume_job,mapping=mapping,config_changes=changes,rank_after=rank_after,original_scientific_runtime_unchanged=True,source_deployment_reference=Q.reference(source_path),resume_source_deployment_reference=Q.reference(resume_deployment),coordinator_reference=Q.reference(__file__)))
    if(root/'manifest.json').exists():
        # A naturally completed original wins; undo only this coordinator's pending changes.
        for item in changes:
            path=pathlib.Path(item['after']['path']);Q.need(Q.reference(path)==item['after'],'Unconsumed own pending config');path.write_bytes(Q.verify(item['archive']).read_bytes())
        subprocess.run(['scontrol','update','JobId=1885215','Dependency=afterok:1885263:1885264'],check=True)
        subprocess.run(['scancel',import_job,resume_job],check=True)
        Q.write(folder/'original_completed_before_stop.json',dict(manifest_reference=Q.reference(root/'manifest.json'),new_held_jobs_cancelled=[import_job,resume_job],pending_configs_restored=True))
        return
    Q.need('JobState=RUNNING'in native(TARGET['job_id']),'Original writer still running immediately before own stop')
    subprocess.run(['scancel',TARGET['job_id']],check=True)
    while True:
        raw=subprocess.check_output(['sacct','-P','-j',TARGET['job_id'],'--format=JobIDRaw,State,ExitCode,UID,ElapsedRaw,AllocCPUS,NodeList'],text=True)
        rows=raw_rows(raw,TARGET['job_id'])
        if rows and any(r[0]==TARGET['job_id']+'.batch'for r in rows)and all(r[1]in TERMINAL for r in rows):break
        time.sleep(5)
    with(folder/'previous_writer_native_terminal.psv').open('x')as f:f.write(raw)
    subprocess.run(['scontrol','release',import_job,resume_job],check=True);submissions.close()
    print(json.dumps(dict(status='HELD_SUCCESSORS_PREPARED_BEFORE_STOP_AND_RELEASED',import_job=import_job,resume_job=resume_job,rank_retargeted=True,old_writer_all_recorded_steps_terminal=True)),flush=True)

def sys_isolated():
    import sys
    return bool(sys.flags.isolated)
if __name__=='__main__':main()
