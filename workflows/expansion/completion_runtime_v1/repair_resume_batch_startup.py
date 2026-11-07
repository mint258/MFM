"""Repair only pre-science resume shell scripts and rebind unstarted consumers."""
import copy,json,os,pathlib,runpy,shlex,subprocess
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
B=A/'control/pubchem_expansion_runtime_20261103'
D=A/'control/pubchem_completion_environment_20261103'
PREFIX='main_rescue_resume_startup_repair_20261105_v1'

def render(text,node,partition,workers):
    lines=text.splitlines();old_exec=[s for s in lines if s.startswith('exec ')]
    if len(old_exec)!=1 or len([s for s in lines if s.startswith('unset ')])!=1:
        raise ValueError('One original execution/unset line required')
    replacements={'#SBATCH --partition=':partition,'#SBATCH --nodelist=':node,'#SBATCH --cpus-per-task=':str(workers)}
    for prefix,value in replacements.items():
        if sum(s.startswith(prefix)for s in lines)!=1:raise ValueError('One explicit resource header')
        lines=[prefix+value if s.startswith(prefix)else s for s in lines]
    lines=['unset SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU' if s.startswith('unset ')else s for s in lines]
    if [s for s in lines if s.startswith('exec ')]!=old_exec:raise ValueError('Scientific execution command changed')
    return '\n'.join(lines)+'\n'

def rewrite(value,mapping,key=None):
    if isinstance(value,dict):return {k:rewrite(v,mapping,k)for k,v in value.items()}
    if isinstance(value,list):return [rewrite(v,mapping,key)for v in value]
    if isinstance(value,str)and value in mapping:
        if not(key=='job_id' or (key and key.endswith('_job_id'))):raise ValueError('Unexpected literal job-ID field')
        return mapping[value]
    return value

def main():
    if os.getuid()!=1264:raise ValueError('Actual Alpha coordinator only')
    runpy.run_path(str(A/'code/main_rescue_import_transport_20261104_v2/entry.py'),run_name='_startup_shell_repair')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    def native(job):return subprocess.check_output(['scontrol','show','job','-o',job],text=True)
    def pending(job):
        raw=native(job)
        Q.need(all(s in raw for s in('UserId=alpha(1264)','JobState=PENDING','StartTime=Unknown','Restarts=0')),'Own unstarted consumer only')
        return raw
    raw_old=native('1885246');Q.need('JobState=FAILED' in raw_old and 'ExitCode=1:0' in raw_old,'Actual pre-science shell failure only')
    log=B/'node_epochs/main_rescue_resume_20261105_v1_low11_1885246.out'
    Q.need('unset:' in log.read_text() and 'not a valid identifier' in log.read_text(),'Actual unset-line failure')
    raw_high=pending('1885247');Q.need('Reason=JobHeldUser' in raw_high,'Old high branch held before shell startup')
    consumers={j:pending(j)for j in('1885248','1885249','1885250','1885251','1885252','1885255','1885256')}
    rank=pending('1885215');folder=D/PREFIX;folder.mkdir(mode=0o700)
    Q.write(folder/'before.json',dict(failed246=raw_old,held247=raw_high,rank=rank,consumers=consumers,failed_shell_log=Q.reference(log)))
    journal=(D/(PREFIX+'_submissions.jsonl')).open('x');mapping={};scripts=[]
    for old,role,node,partition,workers in [('1885246','low11','compute-0-1','cpu',64),('1885247','high5','sonmi1','cpu',16)]:
        original=B/('main_rescue_resume_20261105_v1_'+role+'.sbatch')
        text=render(original.read_text(),node,partition,workers)
        subprocess.run(['bash','-n'],input=text,text=True,check=True)
        unset=next(s for s in text.splitlines()if s.startswith('unset '))
        subprocess.run(['bash','-c','set -euo pipefail; '+unset],check=True)
        path=B/('main_rescue_resume_20261105_v2_'+role+'.sbatch')
        with path.open('x')as f:f.write(text)
        job=subprocess.check_output(['sbatch','--hold','--parsable','--dependency=afterok:1885245',str(path)],text=True).strip().split(';')[0]
        Q.need(job.isdigit(),'Actual submission ID required');mapping[old]=job
        record=dict(old_job=old,new_job=job,script=Q.reference(path),original_script=Q.reference(original),source=Q.reference(__file__))
        journal.write(json.dumps(record,sort_keys=True)+'\n');journal.flush();os.fsync(journal.fileno());scripts.append(record)
    changes=[];seen=set()
    for job,raw in consumers.items():
        pending(job)
        script=pathlib.Path(next(t[len('Command='):]for t in shlex.split(raw)if t.startswith('Command=')))
        tokens=shlex.split(script.read_text());path=pathlib.Path(tokens[tokens.index('--config')+1])
        if str(path)in seen:continue
        seen.add(str(path));cfg=Q.load(path);fresh=rewrite(cfg,mapping)
        if fresh==cfg:continue
        archive=folder/path.name;old_ref=Q.reference(path)
        with archive.open('x')as f:json.dump(cfg,f,sort_keys=True);f.write('\n')
        nextpath=path.with_name(path.name+'.startup_repair_pending')
        with nextpath.open('x')as f:json.dump(fresh,f,sort_keys=True);f.write('\n')
        os.replace(nextpath,path);changes.append(dict(job_id=job,before=old_ref,archive=Q.reference(archive),after=Q.reference(path)))
    subprocess.run(['scontrol','update','JobId=1885215','Dependency=afterok:'+mapping['1885246']+':'+mapping['1885247']],check=True)
    current=native('1885215')
    Q.need(all('afterok:'+job in current for job in mapping.values()),'Actual rank dependency readback')
    Q.write(folder/'revision.json',dict(schema='ACTUAL_PRE_SCIENCE_SHELL_REPAIR_V1',mapping=mapping,submissions=scripts,pending_config_changes=changes,rank_after=current,scientific_sources_changed=False,failed246_science_started=False,completed245_import_preserved=True))
    subprocess.run(['scancel','1885247'],check=True)
    subprocess.run(['scontrol','release',*mapping.values()],check=True)
    journal.close();print(json.dumps(dict(mapping=mapping,rank_rebound=True,only_unstarted247_cancelled=True,science_unchanged=True)),flush=True)
if __name__=='__main__':main()
