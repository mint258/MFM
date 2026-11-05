"""Prepare one real allocated UFF continuation, then exec the existing launcher."""
import argparse
import copy
import os
from pathlib import Path
import subprocess
import sys
from ..alpha_runtime_v1 import common as Q
from .terminal import parent
from . import prepare,followup,completion

A=Path('/gfshome/alpha/codex_data_v1_20261026')
B=A/'control/pubchem_expansion_runtime_20261103'
D=A/'control/pubchem_completion_environment_20261103'
BASE=A/'code/pubchem_completion_20261103_497c584'
PY=A/'software/pubchem_completion_20261103_venv/bin/python'


def literal(job,tag):
    Q.need(isinstance(job,str)and job.isdigit()and isinstance(tag,str)and bool(tag)
        and all(c.isalnum()or c in '_-'for c in tag),'Literal actual numeric job and stage tag')
    return tag+'_job_'+job


def upstream(job,tag,control):
    root=Path(control)/literal(job,tag);path=root/'plan.json';startup=root/'startup.json'
    plan=Q.load(path);proof=Q.load(startup);ref=Q.reference(path)
    Q.need(proof['request']['producer_plan_reference']==ref and str(proof['job_id'])==job
        and proof['endpoint']==plan['endpoint']==Q.ENDPOINT and proof['uid']==plan['uid']==Q.UID,
        'Actual same upstream allocation native startup/plan/endpoint/UID')
    out=Path(plan['output_directory'])
    Q.need(out.is_absolute()and out.is_relative_to('/gfshome/alpha')
        and not any(p.is_symlink()for p in (out,*out.parents)), 'Literal actual Alpha upstream output path')
    return dict(runtime=dict(endpoint=Q.ENDPOINT,uid=Q.UID,job_id=job),plan_reference=ref,
        startup_proof_reference=Q.reference(startup),output_directory=str(out))


def terminal_account(job,folder,command):
    Q.need(isinstance(command,list)and bool(command)and all(isinstance(s,str)and s for s in command),
           'Explicit native sacct command prefix, no shell command string')
    result=subprocess.run([*command,'-j',job,'--parsable2',
        '--format=JobIDRaw%40,State%24,ExitCode,UID,ElapsedRaw,AllocCPUS,NodeList%128'],capture_output=True,text=True)
    Q.need(result.returncode==0,'Native upstream Slurm accounting unavailable: '+result.stderr)
    lines=result.stdout.splitlines();Q.need(bool(lines),'Actual accounting output is empty')
    header=lines[0].split('|');rows=[dict(zip(header,line.split('|')))for line in lines[1:]if line]
    parents=[r for r in rows if r.get('JobIDRaw')==job]
    raw=Path(folder)/'native_sacct.txt'
    with raw.open('x')as out:out.write(result.stdout)
    ref=Q.write(Path(folder)/'native_accounting.json',dict(endpoint=Q.ENDPOINT,uid=Q.UID,
        actual_parents=parents,raw_sacct_reference=Q.reference(raw)))
    parent(dict(endpoint=Q.ENDPOINT,uid=Q.UID,job_id=job),ref)
    return ref


def result_reference(meta,kind):
    root=Path(meta['output_directory']);job=meta['runtime']['job_id']
    if kind=='generation':
        matches=list(root.glob('receipt_job'+job+'_*.json'))
        Q.need(len(matches)==1,'Exactly one real upstream generation receipt for actual job, no prefix/guess')
        path=matches[0]
    else:path=root/('source_manifest.json'if kind=='source'else'result.json')
    ref=Q.reference(path);value=Q.load(path)
    if kind=='source':
        Q.need(str(value['actual_parent']['job_id'])==job and value['resource_plan']==meta['plan_reference'],
               'Actual source result belongs to upstream job and native plan')
    else:
        Q.need(str(value['runtime']['job_id'])==job
            and value['execution_metadata']['original_launcher_plan_reference']==meta['plan_reference']
            and value['execution_metadata']['original_startup_proof_reference']==meta['startup_proof_reference'],
            'Actual generation/QA result matches upstream launcher plan/startup')
    return ref


def build(config,phase,job,tag,inputs,control,*,generation_job=None,generation_tag=None):
    config=copy.deepcopy(config);config.setdefault('closed_allocations',[]);cache={};inputs=Path(inputs)
    def load(j,t):
        key=(j,t)
        if key not in cache:
            meta=upstream(j,t,control);folder=inputs/literal(j,t);folder.mkdir()
            meta['accounting_reference']=terminal_account(j,folder,config.get('accounting_command_prefix',['sacct']))
            cache[key]=meta
        return cache[key]
    meta=load(job,tag);output=inputs/'prepared'
    bindings=config.get('quality_bindings_reference')or Q.reference(prepare.BINDINGS)
    if phase=='pilot':
        allocations=list(config.get('closed_allocations',[]))
        for source in config.get('closed_allocation_sources',[]):
            current=load(str(source['job_id']),source['tag'])
            b={k:current[k]for k in ('runtime','plan_reference','startup_proof_reference','accounting_reference')}
            b['scope']=source['scope']
            if not any(a['plan_reference']==b['plan_reference']for a in allocations):allocations.append(b)
        config['closed_allocations']=allocations
        source=result_reference(meta,'source')
        completed={k:meta[k]for k in ('runtime','startup_proof_reference','accounting_reference')}
        return prepare.prepare(config,source,completed,output,bindings)
    if phase=='qa':
        return followup.qa(config,result_reference(meta,'generation'),meta['accounting_reference'],output,bindings)
    if phase=='qa-full':
        return completion.prepare_completion(config,result_reference(meta,'generation'),meta['accounting_reference'],output,bindings_ref=bindings)
    Q.need(generation_job is not None and generation_tag is not None,
           'Full/finalize need explicit actual generation job/tag in addition to upstream QA')
    gen=load(generation_job,generation_tag);genref=result_reference(gen,'generation');qaref=result_reference(meta,'quality')
    if phase=='full':
        return followup.full(config,genref,gen['accounting_reference'],qaref,meta['accounting_reference'],output,bindings)
    Q.need(phase=='finalize','Only the five explicit pipeline phases')
    return completion.prepare_completion(config,genref,gen['accounting_reference'],output,
        qa_ref=qaref,qa_account_ref=meta['accounting_reference'],bindings_ref=bindings)


def launch_argv(template,phase,entry,tag,control,*,python=PY,base=BASE,launcher=D/'node_launcher_rpc_v3_resume.py',rpc=D/'gluster_readonly_rpc.py'):
    literal('0',tag)
    module='workflows.expansion.uff3_candidate_finalize_v1.entry'if phase=='finalize'else'workflows.expansion.uff3_alpha_runtime_v1.entry'
    return [str(python),'-I','-B',str(launcher),'--template',str(template),'--base-root',str(base),
        '--entry',str(entry),'--module',module,'--tag',tag,'--control-root',str(control),'--gluster-rpc-program',str(rpc)]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase',required=True,choices=('pilot','qa','full','qa-full','finalize'))
    p.add_argument('--config',required=True,type=Path);p.add_argument('--upstream-job',required=True);p.add_argument('--upstream-tag',required=True)
    p.add_argument('--generation-job');p.add_argument('--generation-tag');p.add_argument('--entry',required=True,type=Path);p.add_argument('--tag',required=True)
    p.add_argument('--control-root',type=Path,default=B/'node_epochs');p.add_argument('--python',type=Path,default=PY)
    p.add_argument('--base-root',type=Path,default=BASE);p.add_argument('--launcher',type=Path,default=D/'node_launcher_rpc_v3_resume.py')
    p.add_argument('--gluster-rpc-program',type=Path,default=D/'gluster_readonly_rpc.py');a=p.parse_args()
    job=os.environ.get('SLURM_JOB_ID','')
    Q.need(os.getuid()==Q.UID and sys.flags.isolated and job.isdigit(), 'Only actual isolated native Alpha Slurm allocation')
    config=Q.load(a.config)
    Q.need(int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=config.get('workers',32)>=16,'Actual allocated CPU workers, no GPU use')
    deployment=Q.load(Q.verify(config['deployment_reference']))
    Q.need(Q.reference(__file__)in deployment['code_references'],'Actual pipeline source pinned by current immutable deployment')
    inputs=a.control_root/(a.tag+'_inputs_job_'+job);literal(job,a.tag);inputs.mkdir(mode=0o700)
    template=build(config,a.phase,a.upstream_job,a.upstream_tag,inputs,a.control_root,
        generation_job=a.generation_job,generation_tag=a.generation_tag)
    argv=launch_argv(template['path'],a.phase,a.entry,a.tag,a.control_root,
        python=a.python,base=a.base_root,launcher=a.launcher,rpc=a.gluster_rpc_program)
    os.chdir(a.base_root);os.execv(str(a.python),argv)


if __name__=='__main__':main()