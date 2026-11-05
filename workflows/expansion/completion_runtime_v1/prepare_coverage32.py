"""Replace only unstarted after-coverage allocation; preserve all scientific inputs."""
import copy,hashlib,json,os,pathlib,re,runpy,shlex,subprocess,sys,time
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026');B=A/'control/pubchem_expansion_runtime_20261103';D=A/'control/pubchem_completion_environment_20261103'
PREFIX='after_coverage32_20261105_v1';OLD_JOB='1885223';CONSUMER='1885256'
def native(job):return subprocess.check_output(['scontrol','show','job','-o',job],text=True)
def pending(job):
    value=native(job)
    if not all(s in value for s in ('UserId=alpha(1264)','JobState=PENDING','Restarts=0','RunTime=00:00:00')):raise ValueError('Own never-started pending job required')
    return value

def command(raw):return pathlib.Path(next(x[8:]for x in shlex.split(raw)if x.startswith('Command=')))
def arguments(script):return shlex.split(next(line[5:]for line in script.read_text().splitlines()if line.startswith('exec ')))
def main():
    if os.getuid()!=1264 or not sys.flags.isolated:raise ValueError('Isolated actual Alpha metadata coordinator only')
    before=pending(OLD_JOB);consumer=pending(CONSUMER);folder=D/PREFIX;folder.mkdir(mode=0o700)
    old_script=command(before);args=arguments(old_script);old_entry=args[3];old_config=pathlib.Path(args[args.index('--config')+1]);tag=args[args.index('--tag')+1]
    runpy.run_path(old_entry,run_name='_original_resource_metadata')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    from workflows.expansion.expansion_coverage_followup_v1 import prepare_pipeline as prepare
    cfg=Q.load(old_config);old_source=Q.load(Q.verify(cfg['deployment_reference']))
    original_factory=prepare.resource_plan;original_code=original_factory.__code__
    if old_entry!=old_source['entry']['path'] or args[args.index('--upstream-job')+1]!='1885222':raise ValueError('Actual original after222 dependency and source entry')
    mem=subprocess.check_output(['ssh','-n','compute-0-1','cat','/proc/meminfo'],text=True)
    physical=int(next(x.split()[1]for x in mem.splitlines()if x.startswith('MemTotal:')))*1024
    if physical<(32*2+8+24)*(1<<30):raise ValueError('Node physical capacity cannot fit future32 caches, parent and reserve')
    target=A/'code'/PREFIX;target.mkdir(mode=0o700);entry=target/'entry.py';body=(D/'coverage32_entry_20261105_v1.py').read_text();compile(body,str(entry),'exec')
    with entry.open('x')as f:f.write(body)
    refs=list(old_source['code_references'])
    for path in (entry,D/'coverage32_entry_20261105_v1.py',pathlib.Path(__file__)):
        ref=Q.reference(path)
        if ref not in refs:refs.append(ref)
    for ref in refs:Q.verify(ref)
    source=Q.write(D/(PREFIX+'_source.json'),dict(schema='ALPHA_RESOURCE_ONLY_COVERAGE32_SOURCE_V1',entry=Q.reference(entry),code_references=refs,original_source_reference=cfg['deployment_reference'],resource_overlay_only=True,original_scientific_modules_replaced=False))
    fresh=copy.deepcopy(cfg);fresh['deployment_reference']=source
    original=original_factory(fresh,'coverage-after',tag)
    pack_original=original_factory(fresh,'pack-after',tag)
    runpy.run_path(str(entry),run_name='_coverage32_preparation_probe')
    actual=prepare.resource_plan(fresh,'coverage-after',tag);pack_actual=prepare.resource_plan(fresh,'pack-after',tag)
    changed={k for k in set(original)|set(actual)if original.get(k)!=actual.get(k)}
    if changed!={'workers','software_rss_budget_bytes'} or actual['workers']!=32 or actual['software_rss_budget_bytes']!=80<<30 or pack_actual!=pack_original:raise ValueError('Exactly two coverage resource fields and unchanged pack phase')
    from workflows.expansion.exact_nn_cached_v1 import coverage as science
    probe=dict(schema='PUBCHEM_COVERAGE32_ACTUAL_RESOURCE_PLAN_PROBE_V1',original_config=Q.reference(old_config),source_reference=source,changed_fields={k:dict(before=original[k],after=actual[k])for k in sorted(changed)},all_other_plan_fields_exactly_equal=True,pack_phase_exactly_unchanged=True,original_resource_factory_code_object_retained=prepare.resource_plan.__globals__['original_resource_plan'].__code__ is original_code,original_scientific_coverage_source_reference=Q.reference(science.__file__),physical_node_bytes=physical,future_private_cache_and_parent_allowance_bytes=72<<30,node_available_reserve_bytes=24<<30,current_free_memory_not_claimed_reserved=True)
    Q.write(folder/'resource_plan_probe.json',probe)
    config=Q.write(B/(PREFIX+'_runtime_config.json'),fresh)
    render=runpy.run_path(str(D/'repair_resume_batch_startup_20261105_v1.py'),run_name='_metadata_render')['render']
    text=render(old_script.read_text(),'compute-0-1','cpu',32)
    fresh_args=[str(entry)if x==old_entry else(config['path']if x==str(old_config)else x)for x in args]
    if fresh_args[fresh_args.index('--entry')+1]!=str(entry):raise ValueError('Both entry routes use actual fresh resource overlay')
    text='\n'.join('exec '+shlex.join(fresh_args)if line.startswith('exec ')else line for line in text.splitlines())+'\n'
    subprocess.run(['bash','-n'],input=text,text=True,check=True)
    subprocess.run(['bash','-c','set -euo pipefail; '+next(x for x in text.splitlines()if x.startswith('unset '))],check=True)
    script=B/(PREFIX+'.sbatch')
    with script.open('x')as f:f.write(text)
    job=subprocess.check_output(['sbatch','--hold','--parsable','--dependency=afterok:1885222',str(script)],text=True).strip().split(';')[0]
    if not job.isdigit():raise ValueError('Literal actual scheduler job ID')
    Q.write(folder/'submitted.json',dict(job_id=job,source=source,config=config,script=Q.reference(script),old_job=OLD_JOB,before=before,consumer_before=consumer))
    pending(OLD_JOB);current=pending(CONSUMER);consumer_script=command(current);consumer_args=arguments(consumer_script);consumer_config=pathlib.Path(consumer_args[consumer_args.index('--config')+1]);old_value=Q.load(consumer_config);matches=[]
    def replace(value):
        if isinstance(value,dict):return{k:replace(v)for k,v in value.items()}
        if isinstance(value,list):return[replace(v)for v in value]
        if value==OLD_JOB:matches.append(value);return job
        return value
    updated=replace(old_value)
    if not matches:raise ValueError('Actual pending graph config must bind old coverage job')
    old_consumer_ref=Q.reference(consumer_config);archive=folder/consumer_config.name
    with archive.open('xb')as f:f.write(consumer_config.read_bytes())
    Q.write(consumer_config,updated,replace=True)
    dependency=next(x.split('=',1)[1]for x in current.split()if x.startswith('Dependency='));dependency=re.sub(r'\([^)]*\)','',dependency)
    if 'afterok:'+OLD_JOB not in dependency:raise ValueError('Actual graph scheduler dependency must include old coverage')
    dependency=dependency.replace('afterok:'+OLD_JOB,'afterok:'+job)
    subprocess.run(['scontrol','update','JobId='+CONSUMER,'Dependency='+dependency],check=True)
    after=native(CONSUMER)
    if 'afterok:'+job not in after:raise ValueError('Actual graph dependency readback')
    Q.write(folder/'prepared.json',dict(job_id=job,old_job_id=OLD_JOB,source_reference=source,config_reference=config,script_reference=Q.reference(script),resource_probe_reference=Q.reference(folder/'resource_plan_probe.json'),old_consumer_config_reference=old_consumer_ref,old_consumer_archive_reference=Q.reference(archive),new_consumer_config_reference=Q.reference(consumer_config),consumer_after=after,scientific_recipe_inputs_and_order_unchanged=True,coordinator_source=Q.reference(__file__)))
    subprocess.run(['scancel',OLD_JOB],check=True)
    terminal={'COMPLETED','CANCELLED','FAILED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}
    while True:
        raw=subprocess.check_output(['sacct','-P','-j',OLD_JOB,'--format=JobIDRaw,State,ExitCode,UID,ElapsedRaw,AllocCPUS,NodeList'],text=True);lines=raw.splitlines();names=lines[0].split('|');rows=[dict(zip(names,x.split('|')))for x in lines[1:]if x]
        if any(x['JobIDRaw']==OLD_JOB for x in rows)and all(x['UID']=='1264'and x['State'].split()[0].rstrip('+')in terminal for x in rows):break
        time.sleep(5)
    with(folder/'previous_native_terminal.psv').open('x')as f:f.write(raw)
    subprocess.run(['scontrol','release',job],check=True)
    print(json.dumps(dict(new_job=job,old_job=OLD_JOB,workers=32,node='compute-0-1',dependency='afterok:1885222',graph_consumer=CONSUMER,old_never_started_all_steps_terminal=True)),flush=True)
if __name__=='__main__':main()