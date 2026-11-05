"""Replace the CPU-only UFF chain at a proven pre-native metadata boundary."""
import copy,json,os,pathlib,re,runpy,shlex,shutil,sqlite3,subprocess,sys,time
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026');B=A/'control/pubchem_expansion_runtime_20261103';D=A/'control/pubchem_completion_environment_20261103'
PREFIX='uff_index_cache_swap_20261105_v1';OLD=['1885248','1885249','1885250','1885251','1885252'];PID=23520
PY=A/'software/pubchem_completion_20261103_venv/bin/python';BASE=A/'code/pubchem_completion_20261103_497c584'
def native(job):return subprocess.check_output(['scontrol','show','job','-o',job],text=True)
def own_pending(job):
    raw=native(job)
    if not all(x in raw for x in('UserId=alpha(1264)','JobState=PENDING','Restarts=0','RunTime=00:00:00')):raise ValueError('Own unstarted pending consumer required')
    return raw
def batch_path(raw):return pathlib.Path(next(x[8:]for x in shlex.split(raw)if x.startswith('Command=')))
def argv(path):return shlex.split(next(x[5:]for x in path.read_text().splitlines()if x.startswith('exec ')))
def main():
    if os.getuid()!=1264 or not sys.flags.isolated:raise ValueError('Actual isolated Alpha coordinator')
    source_path=D/'uff_index_cache_20261105_v1_source.json';source=json.loads(source_path.read_bytes());entry=pathlib.Path(source['entry']['path'])
    if not source['only_difference_two_connection_PRAGMAs']or source['deployed_metadata_tests']!={'tests':2,'status':'PASS'}:raise ValueError('Tested exact metadata-only source')
    runpy.run_path(str(entry),run_name='_uff_cache_swap_metadata')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    from workflows.expansion.uff3_alpha_runtime_v1 import prepare_pipeline as pipeline,followup
    for ref in source['code_references']:Q.verify(ref)
    live=native(OLD[0]);pending={j:own_pending(j)for j in OLD[1:]}
    if not all(x in live for x in('UserId=alpha(1264)','JobState=RUNNING','NodeList=compute-0-2','Restarts=0')):raise ValueError('Original own pilot still on known node')
    plan_path=B/'node_epochs/uff_quality_timed_86e1e2e_uff_pilot_job_1885248/plan.json';proof_path=plan_path.parent/'startup.json';plan=Q.load(plan_path);stage=pathlib.Path(plan['output_directory'])
    def probe():
        code="import json,os,pathlib,re; p=pathlib.Path('/proc/23520'); plan=json.loads(pathlib.Path("+repr(str(plan_path))+").read_bytes()); args=p.joinpath('cmdline').read_bytes().rstrip(bytes([0])).decode().split(chr(0)); assert args==plan['execution_argv']; fds=[os.readlink(x)for x in p.joinpath('fd').iterdir()]; parts=[int(re.search(r'source_(\\d+)[.]jsonl$',s).group(1))for s in fds if re.search(r'source_(\\d+)[.]jsonl$',s)]; children=p.joinpath('task/23520/children').read_text().strip(); assert p.stat().st_uid==1264 and len(parts)==1 and 0<=parts[0]<100 and not children; print(json.dumps(dict(pid=23520,uid=p.stat().st_uid,start_ticks=int(p.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),source_part=parts[0],children=children,argv_matches_actual_plan=True,pre_native_source_census=True)))"
        return json.loads(subprocess.check_output(['ssh','-n','compute-0-2',shlex.join([str(PY),'-I','-B','-c',code])],text=True))
    observed=probe();folder=D/PREFIX;folder.mkdir(mode=0o700)
    Q.write(folder/'before.json',dict(pilot_native=live,pending_native=pending,pre_native_probe=observed,source_reference=Q.reference(source_path),coordinator_reference=Q.reference(__file__)))
    batches={j:batch_path(live if j==OLD[0]else pending[j])for j in OLD};original_args={j:argv(p)for j,p in batches.items()}
    old_full_config=pathlib.Path(original_args[OLD[2]][original_args[OLD[2]].index('--config')+1]);full_config=Q.load(old_full_config)
    for j in OLD[1:]:
        config=pathlib.Path(original_args[j][original_args[j].index('--config')+1])
        if any(old in config.read_text()for old in OLD):raise ValueError('Unexpected old job IDs inside runtime configs; inspect explicitly')
    for j in OLD[1:]:subprocess.run(['scontrol','hold',j],check=True)
    template=folder/'pilot_plan_template.json';new_full_config=B/(PREFIX+'_full_runtime_config.json');mapping={};submitted=[]
    tags={j:original_args[j][original_args[j].index('--tag')+1]for j in OLD}
    for number,j in enumerate(OLD):
        text=batches[j].read_text()
        if number==0:
            args=pipeline.launch_argv(template,'pilot',entry,tags[j],B/'node_epochs')
        else:
            args=[mapping.get(x,x)for x in original_args[j]]
            if j==OLD[2]:
                previous_entry=args[3];args=[str(entry)if x==previous_entry else str(new_full_config)if x==str(old_full_config)else x for x in args]
        text='\n'.join('exec '+shlex.join(args)if x.startswith('exec ')else x for x in text.splitlines())+'\n'
        text=text.replace('unset SBATCH_MEM_PER_NODE','unset SBATCH_MEM SBATCH_MEM_PER_NODE')
        subprocess.run(['bash','-n'],input=text,text=True,check=True)
        batch=B/(PREFIX+'_'+str(number)+'.sbatch')
        with batch.open('x')as f:f.write(text)
        command=['sbatch','--hold','--parsable']
        if number:command+=['--dependency=afterok:'+mapping[OLD[number-1]]]
        new=subprocess.check_output(command+[str(batch)],text=True).strip().split(';')[0]
        if not new.isdigit():raise ValueError('Actual held replacement job ID')
        mapping[j]=new;submitted.append(dict(old_job=j,new_job=new,batch=Q.reference(batch),native=own_pending(new)))
        Q.write(folder/'submitted_current.json',dict(mapping=mapping,submitted=submitted),replace=(folder/'submitted_current.json').exists())
    Q.write(folder/'ready_before_cancel.json',dict(mapping=mapping,submitted=submitted,all_successors_held=True,full_resource_workers_unchanged=32,science_recipe_and_source_unchanged=True))
    last_probe=probe();Q.write(folder/'pre_cancel_native_boundary.json',last_probe)
    subprocess.run(['scancel',OLD[0]],check=True)
    while True:
        raw=subprocess.check_output(['sacct','-P','-X','-j',OLD[0],'-o','JobIDRaw,UID,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],text=True)
        rows=raw.splitlines();names=rows[0].split('|');values=[dict(zip(names,x.split('|')))for x in rows[1:]if x]
        parents=[x for x in values if x['JobIDRaw']==OLD[0]]
        if len(parents)==1 and parents[0]['UID']=='1264'and parents[0]['State'].startswith('CANCELLED'):break
        time.sleep(2)
    with(folder/'old_pilot_cancel_native.psv').open('x')as f:f.write(raw)
    gone="import pathlib; p=pathlib.Path('/proc/23520/stat'); assert not p.exists()or int(p.read_text().rsplit(')',1)[1].split()[19])!="+str(last_probe['start_ticks'])
    subprocess.run(['ssh','-n','compute-0-2',shlex.join([str(PY),'-I','-B','-c',gone])],check=True)
    archive=stage/'interrupted'/('metadata_census_job'+OLD[0]);archive.mkdir(parents=True)
    archived=[]
    for suffix in('','-journal','-wal','-shm'):
        path=stage/('index.sqlite'+suffix)
        if path.exists():
            before=path.stat();destination=archive/path.name;shutil.copy2(path,destination);after=path.stat()
            if(before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns)or destination.stat().st_size!=after.st_size:raise ValueError('Closed original metadata copy changed')
            archived.append(dict(path=str(destination),bytes=after.st_size))
    db=sqlite3.connect(stage/'index.sqlite',timeout=120)
    done=db.execute('SELECT count(*) FROM done').fetchone()[0];closed=db.execute("SELECT value FROM meta WHERE key='source_census_complete'").fetchone();source_rows=db.execute('SELECT count(*) FROM source').fetchone()[0];db.close()
    if done!=0 or closed is not None or any((stage/x).exists()for x in('molecules','families')):raise ValueError('Must actually be metadata-only, zero native UFF/D work')
    account_raw=subprocess.check_output(['sacct','-P','-j',OLD[0],'-o','JobIDRaw%40,State%24,ExitCode,UID,ElapsedRaw,AllocCPUS,NodeList%128'],text=True)
    lines=account_raw.splitlines();header=lines[0].split('|');records=[dict(zip(header,line.split('|')))for line in lines[1:]if line];account_parents=[r for r in records if r['JobIDRaw']==OLD[0]]
    with(folder/'native_sacct.txt').open('x')as f:f.write(account_raw)
    account=Q.write(folder/'native_accounting.json',dict(endpoint=Q.ENDPOINT,uid=Q.UID,actual_parents=account_parents,raw_sacct_reference=Q.reference(folder/'native_sacct.txt')))
    from workflows.expansion.uff3_alpha_runtime_v1.terminal import parent
    parent(dict(endpoint=Q.ENDPOINT,uid=Q.UID,job_id=OLD[0]),account,require_C0=False)
    fresh=copy.deepcopy(plan);fresh.pop('execution_argv',None);fresh.update(code_references=source['code_references'],resume_output_directory=str(stage),resume_binding=followup.previous(stage,plan['source_manifest'],[account]),source_deployment_reference=Q.reference(source_path))
    Q.write(template,fresh)
    updated=copy.deepcopy(full_config);updated['deployment_reference']=Q.reference(source_path);updated['previous_accounting_references']=[*updated.get('previous_accounting_references',[]),account];Q.write(new_full_config,updated)
    for j in OLD[1:]:own_pending(j);subprocess.run(['scancel',j],check=True)
    Q.write(folder/'prepared.json',dict(mapping=mapping,source_reference=Q.reference(source_path),pilot_template_reference=Q.reference(template),full_config_reference=Q.reference(new_full_config),old_pilot_accounting_reference=account,pre_cancel_native_boundary=last_probe,closed_old_source_rows=source_rows,old_done_molecules=done,old_source_census_complete=closed,old_metadata_archives=archived,old_scientific_UFF_D_calls=0,all_scientific_source_recipe_candidate_order_and_masks_unchanged=True,all_pending_replacements_held_until_ready=True,workers=32,node='compute-0-2',time_limit='UNLIMITED'))
    for new in mapping.values():subprocess.run(['scontrol','release',new],check=True)
    Q.write(folder/'released.json',dict(mapping=mapping,native={new:native(new)for new in mapping.values()},full_has_no_user_hold=True))
    print(json.dumps(dict(status='CACHE_TUNED_SAME_STAGE_PILOT_AND_FULL_CHAIN_SCHEDULED',mapping=mapping,old_pilot_done=done,old_source_rows=source_rows,all_original_scientific_checks_unchanged=True,full_workers=32)),flush=True)
if __name__=='__main__':main()
