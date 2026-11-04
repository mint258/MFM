"""Resume exact NN with measured CPU/RAM budgets; preserve scientific sources."""
import copy,json,os,pathlib,runpy,shlex,subprocess,time
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026');B=A/'control/pubchem_expansion_runtime_20261103';D=A/'control/pubchem_completion_environment_20261103'
PREFIX='alpha_nn_guard_cadence_resume_20261105_v1'
ROLES=[('1885259','low11','compute-0-1','cpu',64),('1885260','high5','compute-0-2','all',32)]
CONSUMERS=('1885248','1885249','1885250','1885251','1885252','1885255','1885256')

def resources(previous,role):
    seed=copy.deepcopy(previous)
    if role=='low11':seed.update(workers=64,worker_rss_cap_bytes=768<<20,parent_rss_cap_bytes=32<<30,software_rss_budget_bytes=80<<30,sql_memory_bytes=24<<30,spill_cap_bytes=48000000000)
    elif role=='high5':seed.update(workers=32,worker_rss_cap_bytes=1<<30,parent_rss_cap_bytes=64<<30,software_rss_budget_bytes=96<<30,sql_memory_bytes=48<<30)
    else:raise ValueError('Explicit existing partition only')
    if seed['worker_rss_cap_bytes']*seed['workers']+seed['parent_rss_cap_bytes']>seed['software_rss_budget_bytes']:raise ValueError('All caches/parent within tree budget')
    return seed

def main():
    if os.getuid()!=1264:raise ValueError('Actual Alpha coordinator only')
    runpy.run_path(str(A/'code/inverted_cache_resume_20261104_v1/entry.py'),run_name='_resource_resume_metadata')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    prepare=runpy.run_path(str(D/'prepare_main_import_novelty_resume_20261104_v1.py'),run_name='_metadata_functions')
    helpers=runpy.run_path(str(D/'repair_resume_batch_startup_20261105_v1.py'),run_name='_pending_only_helpers')
    def native(job):return subprocess.check_output(['scontrol','show','job','-o',job],text=True)
    def pending(job):
        raw=native(job)
        Q.need(all(s in raw for s in('UserId=alpha(1264)','JobState=PENDING','Restarts=0','RunTime=00:00:00')),'Own unstarted consumer')
        return raw
    before={};old=[]
    for job,role,node,partition,workers in ROLES:
        raw=native(job);Q.need('UserId=alpha(1264)'in raw and 'JobState=RUNNING'in raw and 'NodeList='+node in raw,'Actual own previous writer')
        tag='main_rescue_resume_20261105_v1_'+role;meta=prepare['upstream'](Q,job,tag,B/'node_epochs');plan=Q.load(Q.verify(meta['plan_reference']))
        Q.need(plan['partition_id']==role and plan['reference_manifest']['sha256']=='1ef86c58d193264af960b361a4d04691828b9402f95c77b6ddde7302840fa45e','Original logical partition/full reference')
        old.append(dict(job=job,role=role,node=node,partition=partition,workers=workers,tag=tag,meta=meta,plan=plan));before[job]=raw
    rank=pending('1885215');consumers={j:pending(j)for j in CONSUMERS}
    folder=D/PREFIX;folder.mkdir(mode=0o700)
    Q.write(folder/'before.json',dict(writers=before,rank=rank,consumers=consumers,native_resources=subprocess.check_output(['sinfo','-N','-h','-o','%N %P %t %C'],text=True)))
    journal=(D/(PREFIX+'_submissions.jsonl')).open('x');mapping={};submitted=[]
    for item in old:
        role=item['role'];raw=before[item['job']]
        script=pathlib.Path(next(x[8:]for x in shlex.split(raw)if x.startswith('Command=')))
        text=helpers['render'](script.read_text(),item['node'],item['partition'],item['workers'])
        tokens=shlex.split(next(line for line in text.splitlines()if line.startswith('exec '))[5:]);index=tokens.index('--config')+1
        entry_index=tokens.index('--entry')+1
        Q.need(tokens[entry_index]==str(A/'code/inverted_cache_resume_20261104_v1/entry.py'),'Actual old immutable entry routing')
        deployment=D/'shard_guard_cadence_20261105_v2_source.json';fresh_source=Q.load(deployment)
        Q.need(fresh_source['resource_changes_only']is True and fresh_source['byte_identical_after_exact_two_resource_inversions']is True,'Only actual proved resource edits')
        tokens[entry_index]=str(Q.verify(fresh_source['entry']))
        old_config=pathlib.Path(tokens[index]);cfg=copy.deepcopy(Q.load(old_config));seed=resources(item['plan'],role)
        cfg['deployment_reference']=Q.reference(deployment)
        seedref=Q.write(B/(PREFIX+'_'+role+'_seed.json'),seed)
        cfg.update(previous_job_id=item['job'],previous_tag=item['tag'],seed_template_reference=seedref)
        config=B/(PREFIX+'_'+role+'_config.json');Q.write(config,cfg)
        original_args=list(tokens);tokens[index]=str(config)
        Q.need(tokens[:index]+tokens[index+1:]==original_args[:index]+original_args[index+1:],'Only configuration routing differs')
        text='\n'.join('exec '+shlex.join(tokens)if line.startswith('exec ')else line for line in text.splitlines())+'\n'
        subprocess.run(['bash','-n'],input=text,text=True,check=True)
        subprocess.run(['bash','-c','set -euo pipefail; '+next(s for s in text.splitlines()if s.startswith('unset '))],check=True)
        target=B/(PREFIX+'_'+role+'.sbatch')
        with target.open('x')as f:f.write(text)
        job=subprocess.check_output(['sbatch','--hold','--parsable','--dependency=afterany:'+item['job'],str(target)],text=True).strip().split(';')[0]
        Q.need(job.isdigit(),'Actual scheduler ID');mapping[item['job']]=job
        record=dict(previous_job=item['job'],new_job=job,tag=item['tag'],script=Q.reference(target),config=Q.reference(config),seed=seedref,previous_allocation=item['meta'],coordinator_source=Q.reference(__file__))
        journal.write(json.dumps(record,sort_keys=True)+'\n');journal.flush();os.fsync(journal.fileno());submitted.append(record)
    changes=[];seen=set()
    for job,raw in consumers.items():
        pending(job);script=pathlib.Path(next(x[8:]for x in shlex.split(raw)if x.startswith('Command=')))
        args=shlex.split(script.read_text());path=pathlib.Path(args[args.index('--config')+1])
        if str(path)in seen:continue
        seen.add(str(path));value=Q.load(path);fresh=helpers['rewrite'](value,mapping)
        if fresh==value:continue
        archive=folder/path.name;original=Q.reference(path)
        with archive.open('xb')as f:f.write(path.read_bytes())
        temporary=path.with_name(path.name+'.resource_resume_pending')
        with temporary.open('x')as f:json.dump(fresh,f,sort_keys=True);f.write('\n')
        os.replace(temporary,path);changes.append(dict(job_id=job,before=original,archive=Q.reference(archive),after=Q.reference(path)))
    subprocess.run(['scontrol','update','JobId=1885215','Dependency=afterok:'+':'.join(mapping.values())],check=True)
    updated=native('1885215');Q.need(all('afterok:'+job in updated for job in mapping.values()),'Actual downstream dependency readback before stop')
    Q.write(folder/'prepared.json',dict(submissions=submitted,mapping=mapping,config_changes=changes,rank_after=updated,scientific_sources_changed=False))
    subprocess.run(['scancel',*mapping],check=True)
    terminal={'COMPLETED','CANCELLED','FAILED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}
    while True:
        raw=subprocess.check_output(['sacct','-P','-j',','.join(mapping),'--format=JobIDRaw,State,ExitCode,UID,ElapsedRaw,AllocCPUS,NodeList'],text=True)
        lines=raw.splitlines();header=lines[0].split('|');rows=[dict(zip(header,line.split('|')))for line in lines[1:]if line]
        parents={r['JobIDRaw']for r in rows if r['JobIDRaw']in mapping}
        if parents==set(mapping)and all(r['State'].split()[0].rstrip('+')in terminal for r in rows):break
        time.sleep(5)
    with(folder/'previous_writers_native_terminal.psv').open('x')as f:f.write(raw)
    subprocess.run(['scontrol','release',*mapping.values()],check=True);journal.close()
    print(json.dumps(dict(mapping=mapping,workers=96,previous_writers_all_terminal=True,original_two_roots_and_science_preserved=True)),flush=True)
if __name__=='__main__':main()
