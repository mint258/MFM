"""Resume original two Alpha NN roots only after a real completed score import."""
import argparse,copy,os,runpy,subprocess,sys
from pathlib import Path
A=Path('/gfshome/alpha/codex_data_v1_20261026');B=A/'control/pubchem_expansion_runtime_20261103'
D=A/'control/pubchem_completion_environment_20261103';BASE=A/'code/pubchem_completion_20261103_497c584'
PY=A/'software/pubchem_completion_20261103_venv/bin/python'
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True,type=Path)
    p.add_argument('--entry',required=True,type=Path);p.add_argument('--tag',required=True);a=p.parse_args()
    if os.getuid()!=1264 or not sys.flags.isolated or not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('Actual isolated Alpha NN continuation allocation only')
    runpy.run_path(str(a.entry),run_name='_NN_resume_source_bootstrap')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    from workflows.expansion.uff3_alpha_runtime_v1.prepare_pipeline import upstream,terminal_account,literal
    from workflows.expansion.uff3_alpha_runtime_v1.terminal import parent
    from workflows.expansion.alpha_sharded_novelty_v1.prepare_pipeline import prepare
    cfg=Q.load(a.config);source=Q.load(Q.verify(cfg['deployment_reference']))
    Q.need(Q.reference(__file__)==cfg['prepare_script_reference']and Q.reference(a.entry)==source['entry'],'Actual NN preparation/source entry')
    literal(os.environ['SLURM_JOB_ID'],a.tag)
    inputs=B/'node_epochs'/(a.tag+'_inputs_job_'+os.environ['SLURM_JOB_ID']);inputs.mkdir(mode=0o700,parents=True)
    command=['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=5','218.192.171.238','sacct']
    imported=upstream(str(cfg['import_job_id']),cfg['import_tag'],B/'node_epochs')
    folder=inputs/'import_completed';folder.mkdir()
    imported['accounting_reference']=terminal_account(str(cfg['import_job_id']),folder,command)
    receipt=Q.reference(Path(imported['output_directory'])/'manifest.json');value=Q.load(Q.verify(receipt))
    Q.need(value['schema']=='ALPHA_MAIN_EXACT_RESCUE_IMPORT_V1'and value['status']=='COMPLETE'
        and value['actual']['uid']==1264 and str(value['actual']['job_id'])==str(cfg['import_job_id'])
        and value['resource_plan']==imported['plan_reference']and value['startup_proof_reference']==imported['startup_proof_reference']
        and value['original_binding_journals_data_rewritten']is False and value['next_epoch_must_reference_this_import_manifest']is True,
        'Actual closed import/native plan/old-cache conservation')
    old=upstream(str(cfg['previous_job_id']),cfg['previous_tag'],B/'node_epochs')
    folder=inputs/'previous_writer';folder.mkdir()
    raw=subprocess.run([*command,'-j',str(cfg['previous_job_id']),'--parsable2',
        '--format=JobIDRaw%40,State%24,ExitCode,UID,ElapsedRaw,AllocCPUS,NodeList%128'],capture_output=True,text=True)
    Q.need(raw.returncode==0,'Native previous NN accounting unavailable')
    lines=raw.stdout.splitlines();Q.need(lines,'Actual native header');names=lines[0].split('|')
    rows=[dict(zip(names,line.split('|')))for line in lines[1:]if line]
    rawpath=folder/'native_sacct.txt'
    with rawpath.open('x')as f:f.write(raw.stdout)
    account=Q.write(folder/'native_accounting.json',dict(endpoint=Q.ENDPOINT,uid=Q.UID,
        actual_parents=[r for r in rows if r.get('JobIDRaw')==str(cfg['previous_job_id'])],raw_sacct_reference=Q.reference(rawpath)))
    parent(old['runtime'],account,require_C0=False)
    previous=Q.load(Q.verify(old['plan_reference']));seed=copy.deepcopy(Q.load(Q.verify(cfg['seed_template_reference'])))
    Q.need(previous['output_directory']==seed['resume_output_directory']==cfg['expected_output_root']
        and value['source_filter_reference']==previous['filtered_pool_reference']
        and value['reference_manifest_reference']==previous['reference_manifest'],
        'Exact old root/full source/reference after external cache import')
    previous_binding={k:old[k]for k in('runtime','plan_reference','startup_proof_reference')}
    previous_binding['accounting_reference']=account
    writers=list(previous.get('resume_previous_allocations',[]))
    if not any(v['runtime']==previous_binding['runtime']for v in writers):writers.append(previous_binding)
    refs=list(source['code_references'])
    for ref in(Q.reference(__file__),Q.reference(a.config)):
        if ref not in refs:refs.append(ref)
    seed.update(resume_output_directory=cfg['expected_output_root'],resume_previous_allocations=writers,
        external_score_import_references=[receipt],external_score_import_completed={k:imported[k]for k in
            ('runtime','plan_reference','startup_proof_reference','accounting_reference')},
        code_references=refs,source_deployment_reference=cfg['deployment_reference'])
    for key in('execution_argv','runtime_existing_output_stage_reused'):
        seed.pop(key,None)
    seed=prepare(seed,'nn',inputs,Q.verify(previous['filtered_pool_reference']),[])
    path=inputs/'input_plan.json';Q.write(path,seed)
    argv=[str(PY),'-I','-B',str(D/'node_launcher_rpc_v3_resume.py'),'--template',str(path),'--base-root',str(BASE),
        '--entry',str(a.entry),'--module','workflows.expansion.alpha_sharded_novelty_v1.run','--tag',a.tag,
        '--control-root',str(B/'node_epochs'),'--gluster-rpc-program',str(D/'gluster_readonly_rpc.py')]
    os.chdir(BASE);os.execv(str(PY),argv)
if __name__=='__main__':main()
