"""Retry only the pre-DATA importer packaging failure; retain all prior jobs/caches."""
import copy,json,os,pathlib,runpy,subprocess
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
B=A/'control/pubchem_expansion_runtime_20261103'
D=A/'control/pubchem_completion_environment_20261103'
PREFIX='alpha_partition_import_retry_20261105_v1'
def main():
    import sys
    if os.getuid()!=1264 or not sys.flags.isolated:raise ValueError('Actual isolated Alpha coordinator')
    runpy.run_path(str(A/'code/shard_guard_cadence_20261105_v2/entry.py'),run_name='_retry_import_metadata')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    from workflows.expansion.uff3_alpha_runtime_v1.terminal import raw_rows
    def native(job):return subprocess.check_output(['scontrol','show','job','-o',job],text=True)
    def pending(job):
        raw=native(job)
        Q.need(all(s in raw for s in('UserId=alpha(1264)','JobState=PENDING','Restarts=0','RunTime=00:00:00')),'Own unstarted continuation only')
        return raw
    source_path=D/'alpha_partition_cache_import_20261105_v2_source.json';source=Q.load(source_path)
    Q.need(source['schema']=='ALPHA_OWN_PARTITION_CACHE_IMPORT_SOURCE_V1'and source['original_scientific_runtime_changed']is False and source['actual_metadata_probe']['actual_execute_prefix_imports']==12,'Actual complete dependency deployment, unchanged scientific runtime')
    for item in source['code_references']:Q.verify(item)
    Q.need(Q.reference(source_path)['sha256']=='df1d8967463448021fd99b54051e4b2c938234ef8d9e1f680b2ee89e5ecb54b7','Actual deployed source capsule')
    raw=subprocess.check_output(['sacct','-P','-j','1885268','--format=JobIDRaw,State,ExitCode,UID'],text=True)
    rows=raw_rows(raw,'1885268')
    Q.need(any(r==('1885268','FAILED','1:0')for r in rows)and any(r==('1885268.batch','FAILED','1:0')for r in rows)and all(r[1]in('FAILED','COMPLETED')for r in rows),'Previous importer all recorded steps terminal')
    previous_plan=B/'node_epochs/alpha_partition_import_20261105_v1_job_1885268/plan.json'
    plan=Q.load(previous_plan)
    Q.need(not pathlib.Path(plan['output_directory']).exists(),'Failed import exited before creating its DATA root')
    config_path=B/'alpha_partition_import_handoff_20261105_v1_resume_config.json'
    resume=Q.load(config_path);Q.need(resume['importer']==dict(job_id='1885268',tag='alpha_partition_import_20261105_v1'),'Still the original unstarted continuation configuration')
    before=pending('1885269');Q.need('afterok:1885268'in before,'Continuation still awaits previous failed import')
    folder=D/PREFIX;folder.mkdir(mode=0o700)
    Q.write(folder/'before.json',dict(previous_import_native=raw,previous_plan_reference=Q.reference(previous_plan),pending_resume=before,resume_configuration_reference=Q.reference(config_path),coordinator_reference=Q.reference(__file__)))
    subprocess.run(['scontrol','hold','1885269'],check=True);pending('1885269')
    original=Q.load(B/'alpha_partition_import_handoff_20261105_v1_import_config.json')
    old_seed=Q.load(Q.verify(original['seed_reference']));seed=copy.deepcopy(old_seed)
    seed.update(code_references=list(source['code_references'])+[Q.reference(__file__),original['prepare_script_reference']],source_deployment_reference=Q.reference(source_path))
    seed_ref=Q.write(B/(PREFIX+'_seed.json'),seed)
    cfg=copy.deepcopy(original);cfg.update(deployment_reference=Q.reference(source_path),seed_reference=seed_ref)
    fresh_config=B/(PREFIX+'_config.json');Q.write(fresh_config,cfg)
    helper=Q.verify(cfg['prepare_script_reference'])
    script=runpy.run_path(str(D/'handoff_alpha_partition_import_20261105_v3.py'),run_name='_retry_script_builder')['script']
    tag='alpha_partition_import_20261105_v2';batch=B/(PREFIX+'.sbatch')
    with batch.open('x')as f:f.write(script(tag,'import','compute-0-2','all',32,fresh_config,Q.verify(source['entry']),helper))
    job=subprocess.check_output(['sbatch','--hold','--parsable','--dependency=afterany:1885268',str(batch)],text=True).strip().split(';')[0]
    Q.need(job.isdigit(),'Actual held retry allocation ID')
    Q.write(folder/'submission.json',dict(job_id=job,native=pending(job),batch_reference=Q.reference(batch),config_reference=Q.reference(fresh_config),seed_reference=seed_ref))
    archive=folder/config_path.name
    with archive.open('xb')as f:f.write(config_path.read_bytes())
    pending('1885269');Q.need(Q.load(config_path)==resume,'Unconsumed resume config unchanged')
    fresh=copy.deepcopy(resume);fresh['importer']=dict(job_id=job,tag=tag)
    temporary=config_path.with_name(config_path.name+'.retry_pending')
    Q.write(temporary,fresh);os.replace(temporary,config_path)
    Q.need(Q.load(config_path)==fresh,'Pending resume config readback')
    subprocess.run(['scontrol','update','JobId=1885269','Dependency=afterok:'+job],check=True)
    after=pending('1885269');Q.need('afterok:'+job in after,'Native dependency retargeted')
    Q.write(folder/'prepared.json',dict(import_job=job,resume_job='1885269',previous_failed_job='1885268',source_deployment_reference=Q.reference(source_path),pending_resume_after=after,pending_config_archive_reference=Q.reference(archive),pending_config_reference=Q.reference(config_path),scientific_score_math_or_cache_rewritten=False))
    subprocess.run(['scontrol','release',job,'1885269'],check=True)
    print(json.dumps(dict(status='PACKAGING_RETRY_RELEASED',import_job=job,resume_job='1885269',old_failed_job_retained='1885268')),flush=True)
if __name__=='__main__':main()
