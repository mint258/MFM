"""Swap only the never-started after-coverage allocation; UFF dependencies stay independent."""
import copy,json,os,pathlib,re,runpy,shlex,subprocess,sys,time
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026');B=A/'control/pubchem_expansion_runtime_20261103';D=A/'control/pubchem_completion_environment_20261103'
PREFIX='after_coverage_inverted_swap_20261105_v1';OLD='1885265';CONSUMER='1885256'
def native(job):return subprocess.check_output(['scontrol','show','job','-o',job],text=True)
def pending(job):
    raw=native(job)
    if not all(x in raw for x in('UserId=alpha(1264)','JobState=PENDING','Restarts=0','RunTime=00:00:00')):raise ValueError('Own never-started pending allocation required')
    return raw
def command(raw):return pathlib.Path(next(x[8:]for x in shlex.split(raw)if x.startswith('Command=')))
def arguments(path):return shlex.split(next(line[5:]for line in path.read_text().splitlines()if line.startswith('exec ')))
def main():
    if os.getuid()!=1264 or not sys.flags.isolated:raise ValueError('Actual isolated Alpha coordinator')
    before=pending(OLD);consumer=pending(CONSUMER)
    if 'Reason=JobHeldUser'not in before:raise ValueError('Only previously held unstarted coverage lane')
    old_batch=command(before);args=arguments(old_batch);old_entry=args[3];old_config=pathlib.Path(args[args.index('--config')+1]);tag=args[args.index('--tag')+1]
    source_path=D/'after_coverage_inverted_20261105_v3_source.json';source=json.loads(source_path.read_bytes())
    if source['schema']!='AFTER_COVERAGE_INVERTED_FULLN_SOURCE_V1'or source['deployed_metadata_tests']!=dict(tests=5,failures=0,errors=0,status='PASS')or not source['worker_two_import_inversion_byte_equal']:raise ValueError('Concrete tested immutable provider')
    entry=pathlib.Path(source['entry']['path']);namespace=runpy.run_path(str(entry),run_name='_coverage_pending_swap_metadata')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    from workflows.expansion.expansion_coverage_followup_v1 import prepare_pipeline as prepare
    for pin in source['code_references']:Q.verify(pin)
    Q.verify(source['entry']);old_cfg=Q.load(old_config)
    Q.need(args[args.index('--upstream-job')+1]=='1885222'and old_cfg['backend_adoption_reference']==source['comparison_backend_adoption_reference'],'Original pack222 and old206 producer')
    fresh=copy.deepcopy(old_cfg);fresh.update(deployment_reference=Q.reference(source_path),backend_adoption_reference=source['fast_before_native_equivalence_reference'],comparison_backend_adoption_reference=source['comparison_backend_adoption_reference'])
    old_plan=namespace['old_resource_plan'](old_cfg,'coverage-after',tag);old_plan.update(workers=32,software_rss_budget_bytes=80<<30)
    actual=prepare.resource_plan(fresh,'coverage-after',tag)
    changed={k for k in set(old_plan)|set(actual)if old_plan.get(k)!=actual.get(k)}
    expected={'backend_adoption_reference','comparison_backend_adoption_reference','code_references','source_deployment_reference','worker_rss_cap_bytes','software_rss_budget_bytes'}
    Q.need(changed==expected and actual['workers']==32 and actual['worker_rss_cap_bytes']==5<<29 and actual['software_rss_budget_bytes']==96<<30,'Only provider/pins and the full-reference resource envelope may change')
    mem=subprocess.check_output(['ssh','-n','compute-0-1','cat','/proc/meminfo'],text=True)
    physical=int(next(x.split()[1]for x in mem.splitlines()if x.startswith('MemTotal:')))*1024
    available=int(next(x.split()[1]for x in mem.splitlines()if x.startswith('MemAvailable:')))*1024
    Q.need(physical>=actual['software_rss_budget_bytes']+actual['minimum_node_available_bytes'],'Physical node capacity fits declared software allowance and reserve')
    folder=D/PREFIX;folder.mkdir(mode=0o700)
    Q.write(folder/'before.json',dict(old_pending=before,consumer_pending=consumer,old_batch_reference=Q.reference(old_batch),old_config_reference=Q.reference(old_config),source_reference=Q.reference(source_path),coordinator_reference=Q.reference(__file__)))
    probe=Q.write(folder/'resource_and_source_probe.json',dict(changed_fields={k:dict(before=old_plan.get(k),after=actual.get(k))for k in sorted(changed)},all_other_plan_fields_exactly_equal=True,physical_node_bytes=physical,observed_MemAvailable_bytes=available,software_allowance_not_Slurm_memory_reservation=True,original_coverage_code_object_preserved=source['original_coverage_code_object_preserved'],actual_augmented_native_equivalence_pending=True,UFF_dependency_paths_unchanged=True))
    cfg_ref=Q.write(B/(PREFIX+'_runtime_config.json'),fresh)
    fresh_args=[str(entry)if x==old_entry else(cfg_ref['path']if x==str(old_config)else x)for x in args]
    Q.need(fresh_args[fresh_args.index('--entry')+1]==str(entry),'Both entry routes use fresh provider')
    text='\n'.join('exec '+shlex.join(fresh_args)if line.startswith('exec ')else line for line in old_batch.read_text().splitlines())+'\n'
    text=text.replace('unset SBATCH_MEM_PER_NODE','unset SBATCH_MEM SBATCH_MEM_PER_NODE')
    subprocess.run(['bash','-n'],input=text,text=True,check=True)
    subprocess.run(['bash','-c','set -euo pipefail; '+next(x for x in text.splitlines()if x.startswith('unset '))],check=True)
    batch=B/(PREFIX+'.sbatch')
    with batch.open('x')as f:f.write(text)
    job=subprocess.check_output(['sbatch','--hold','--parsable','--dependency=afterok:1885222',str(batch)],text=True).strip().split(';')[0]
    Q.need(job.isdigit(),'Actual held replacement scheduler ID')
    Q.write(folder/'submitted.json',dict(new_job=job,native=pending(job),source=Q.reference(source_path),config=cfg_ref,batch=Q.reference(batch),old_job=OLD))
    pending(OLD);current=pending(CONSUMER);consumer_args=arguments(command(current));consumer_config=pathlib.Path(consumer_args[consumer_args.index('--config')+1]);old_value=Q.load(consumer_config);matches=[]
    def rewrite(value):
        if isinstance(value,dict):return{k:rewrite(v)for k,v in value.items()}
        if isinstance(value,list):return[rewrite(v)for v in value]
        if value==OLD:matches.append(value);return job
        return value
    updated=rewrite(old_value);Q.need(matches,'Actual graph config binds old coverage job')
    archive=folder/consumer_config.name
    with archive.open('xb')as f:f.write(consumer_config.read_bytes())
    old_ref=Q.reference(consumer_config);Q.write(consumer_config,updated,replace=True);Q.need(Q.load(consumer_config)==updated,'Pending graph config exact readback')
    dependency=next(x.split('=',1)[1]for x in current.split()if x.startswith('Dependency='));dependency=re.sub(r'\([^)]*\)','',dependency)
    Q.need('afterok:'+OLD in dependency,'Native graph dependency awaits old unstarted coverage')
    dependency=dependency.replace('afterok:'+OLD,'afterok:'+job)
    subprocess.run(['scontrol','update','JobId='+CONSUMER,'Dependency='+dependency],check=True)
    after=pending(CONSUMER);Q.need('afterok:'+job in after,'Native graph dependency readback')
    Q.write(folder/'prepared.json',dict(new_job=job,old_job=OLD,source_reference=Q.reference(source_path),config_reference=cfg_ref,batch_reference=Q.reference(batch),resource_probe_reference=probe,old_consumer_config_reference=old_ref,old_consumer_archive_reference=Q.reference(archive),new_consumer_config_reference=Q.reference(consumer_config),consumer_after=after,all_source_population_recipe_order_and_fixed1M_inputs_preserved=True,actual_augmented_equivalence_must_pass_in_producer_before_scientific_rows=True))
    subprocess.run(['scancel',OLD],check=True)
    while True:
        raw=subprocess.check_output(['sacct','-P','-X','-j',OLD,'--format=JobIDRaw,State,ExitCode,UID,ElapsedRaw,AllocCPUS,NodeList'],text=True)
        lines=raw.splitlines();names=lines[0].split('|');rows=[dict(zip(names,r.split('|')))for r in lines[1:]if r]
        own=[r for r in rows if r['JobIDRaw']==OLD]
        if len(own)==1 and own[0]['UID']=='1264'and own[0]['State'].startswith('CANCELLED')and own[0]['ElapsedRaw']=='0':break
        time.sleep(5)
    with(folder/'old_pending_cancel_native.psv').open('x')as f:f.write(raw)
    subprocess.run(['scontrol','release',job],check=True)
    print(json.dumps(dict(status='NEW_EQUIVALENT_PROVIDER_SCHEDULED_AFTER_REAL_PACK',new_job=job,old_never_started_job=OLD,workers=32,node='compute-0-1',dependency='afterok:1885222',graph_consumer=CONSUMER,UFF_lanes_changed=False)),flush=True)
if __name__=='__main__':main()
