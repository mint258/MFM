"""Rebind only the nine unstarted own downstream jobs to actual post-import NN epochs."""
import argparse,copy,hashlib,json,os,pathlib,re,subprocess
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
B=A/'control/pubchem_expansion_runtime_20261103';D=A/'control/pubchem_completion_environment_20261103'
OLD=['1885234','1885235','1885236','1885237','1885238','1885241','1885242','1885243','1885244']
ROLES=dict(zip(OLD,['pilot','qa','full','qa_full','finalize','before','baseline','rn','graph']))
PROTECTED={'1885201','1885215','1885217','1885222','1885223'}
DEPS={'1885234':['1885217'],'1885235':['1885234'],'1885236':['1885235'],'1885237':['1885236'],
 '1885238':['1885237'],'1885241':['1885217'],'1885242':['1885241'],'1885243':['1885217','1885242'],
 '1885244':['1885241','1885223','1885243','1885242']}
def need(ok,message):
    if not ok:raise ValueError(message)
def rewrite(value,mapping):
    if isinstance(value,dict):
        if {'path','bytes','sha256'}<=set(value):
            need(value['path']not in mapping,'Immutable reference cannot be relabeled')
            return copy.deepcopy(value)
        if {'runtime','plan_reference','startup_proof_reference'}<=set(value):
            need(str(value['runtime'].get('job_id'))not in mapping,'Actual producer proof cannot be relabeled')
            return copy.deepcopy(value)
        return{k:rewrite(v,mapping)for k,v in value.items()}
    if isinstance(value,list):return[rewrite(v,mapping)for v in value]
    return mapping.get(value,value)if isinstance(value,str)else value
def replace_job_tokens(body,mapping):
    for old,new in mapping.items():
        if old.isdigit():body=re.sub(r'(?<![0-9])'+re.escape(old)+r'(?![0-9])',new,body)
    return body
def declared_ids(value):
    if isinstance(value,dict):
        return set().union(*(declared_ids(v)for v in value.values()))if value else set()
    if isinstance(value,list):return set().union(*(declared_ids(v)for v in value))if value else set()
    return {value}if isinstance(value,str)and value.isdigit()else set()
def command(argv):return subprocess.check_output(argv,text=True).strip()
def write(path,value):
    with path.open('x')as f:json.dump(value,f,sort_keys=True);f.write('\n')
def snapshot(job):
    raw=command(['scontrol','show','job','-o',job])
    need('UserId=alpha(1264)'in raw,'Only actual own Alpha job')
    return raw
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--blueprint',required=True,type=pathlib.Path)
    p.add_argument('--low-job',required=True);p.add_argument('--high-job',required=True)
    p.add_argument('--low-tag',required=True);p.add_argument('--high-tag',required=True);p.add_argument('--prefix',required=True)
    a=p.parse_args();need(os.getuid()==1264,'Actual Alpha coordinator UID')
    need(a.low_job.isdigit()and a.high_job.isdigit()and a.low_job!=a.high_job
        and not {a.low_job,a.high_job}&set(OLD+['1885232','1885233',*PROTECTED]),'Actual distinct new NN allocation IDs')
    need(all(re.fullmatch('[A-Za-z0-9_-]+',s)for s in(a.prefix,a.low_tag,a.high_tag)),'Literal operation prefix/tags')
    blueprint=json.loads(a.blueprint.read_text());need(blueprint['uid']==1264
        and [x['job_id']for x in blueprint['jobs']]==OLD,'Exactly the nine original pending jobs')
    newNN={}
    for job,tag,previous,root in [(a.low_job,a.low_tag,'1885232','partitioned_novelty_ded6679_low11_job_1885213'),
        (a.high_job,a.high_tag,'1885233','partitioned_novelty_ded6679_high5_job_1885214')]:
        raw=snapshot(job);path=pathlib.Path(re.search(r'(?:^| )Command=(\S+)',raw).group(1))
        need(path.is_relative_to(B),'Own task control command')
        body=path.read_text();need('prepare_main_import_novelty_resume_20261104_v1.py'in body
            and re.search(r'--tag\s+'+re.escape(tag)+r'(?:\s|$)',body),'Actual post-import continuation command/tag')
        config_paths=re.findall(r'--config\s+(\S+)',body);need(len(config_paths)==1,'One actual NN continuation config')
        cfg=json.loads(pathlib.Path(config_paths[0]).read_text())
        need(str(cfg['previous_job_id'])==previous and cfg['expected_output_root']=='/gfshome/alpha/pubchem_expansion_20261103/exact/'+root,
            'New epoch preserves actual original root and previous own writer')
        newNN[job]=raw
    before={}
    for item in blueprint['jobs']:
        job=item['job_id'];raw=snapshot(job)
        need('JobState=PENDING'in raw and 'RunTime=00:00:00'in raw and 'StartTime=Unknown'in raw and 'Restarts=0'in raw
            and 'Command='+item['script']in raw,'Only unchanged unstarted own job may be replaced')
        script=pathlib.Path(item['script']);need(script.is_relative_to(B)and script.read_text()==item['script_body'],'Original immutable script body')
        config=pathlib.Path(item['config']);blob=config.read_bytes();expected=blueprint['configs'][str(config)]
        need(config.is_relative_to(B)and len(blob)==expected['bytes']and hashlib.sha256(blob).hexdigest()==expected['sha256'],
            'Original immutable config body')
        before[job]=raw
    rank=snapshot('1885215');need('JobState=PENDING'in rank,'Rank must remain unstarted')
    deps=set(re.findall(r'afterok:(\d+)',rank))
    need(deps in ({'1885232','1885233'},{a.low_job,a.high_job}),'Expected original or already rebound rank dependency')
    record=D/(a.prefix+'_pending_before_rebind.json');write(record,dict(jobs=before,new_NN=newNN,rank=rank))
    subprocess.run(['scontrol','update','JobId=1885215','Dependency=afterok:'+a.low_job+':'+a.high_job],check=True)
    actual=snapshot('1885215');need(set(re.findall(r'afterok:(\d+)',actual))=={a.low_job,a.high_job},'Actual rank dependency readback')
    # All nine jobs were individually verified PENDING. No running producer is changed here.
    journal_path=D/(a.prefix+'_submissions.jsonl')
    with journal_path.open('x'):pass
    subprocess.run(['scancel',*OLD],check=True)
    mapping={'1885232':a.low_job,'1885233':a.high_job,
        'inverted_resume_20261104_v1_low11':a.low_tag,'inverted_resume_20261104_v1_high5':a.high_tag}
    submissions=[]
    for item in blueprint['jobs']:
        old=item['job_id'];base=pathlib.Path(item['config'])
        cfg=rewrite(blueprint['configs'][str(base)]['value'],mapping)
        need(not declared_ids(cfg)&set(OLD+['1885232','1885233']),'No stale canceled producer IDs in a new pending config')
        destination=B/(a.prefix+'_'+ROLES[old]+'_'+base.name);write(destination,cfg)
        body=item['script_body'].replace(str(base),str(destination));body=replace_job_tokens(body,mapping)
        need(not any(re.search(r'(?<![0-9])'+j+r'(?![0-9])',body)for j in OLD),'Every scripted old stage reference mapped before submission')
        script=B/(a.prefix+'_'+ROLES[old]+'_'+pathlib.Path(item['script']).name)
        with script.open('x')as f:f.write(body)
        dependency='afterok:'+':'.join(mapping.get(j,j)for j in DEPS[old])
        new=command(['sbatch','--parsable','--dependency='+dependency,str(script)]).split(';')[0]
        need(new.isdigit()and new not in PROTECTED|set(OLD),'Actual returned new own allocation ID')
        mapping[old]=new;submissions.append(dict(old_job=old,new_job=new,dependency=dependency,script=str(script),config=str(destination)))
        # Save actual progress immediately; a coordinator interruption must not repeat submission.
        with journal_path.open('a')as f:
            f.write(json.dumps(submissions[-1],sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
    result=dict(schema='ACTUAL_POST_IMPORT_PENDING_DAG_REBIND_V1',mapping=mapping,submissions=submissions,
        new_NN_jobs=[a.low_job,a.high_job],preserved_jobs=sorted(PROTECTED),running_201_touched=False,
        running_232_233_changed_here=False,original_scripts_configs_rewritten=False,scientific_completion_claimed=False)
    out=D/(a.prefix+'_downstream_dag.json');write(out,result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
