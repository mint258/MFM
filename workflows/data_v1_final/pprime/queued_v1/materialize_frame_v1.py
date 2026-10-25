"""Prepare exact frame-audit queue metadata; never run science or submit Slurm."""
from __future__ import annotations
import argparse,datetime,hashlib,json,os,pathlib,socket
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
PROJECT=ROOT.parent.parent
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
SMALL=2*1024**2
TASKS=('pm7_B','pm7_water','pm7_octanol','pm7_cation','pm7_anion',
 'xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water','xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient')

def need(ok,message):
    if not ok:raise ValueError(message)

def raw_small(path):
    path=pathlib.Path(path)
    need(path.is_absolute() and '..' not in path.parts and path.is_file() and not path.is_symlink(),'LITERAL_SMALL_METADATA_REQUIRED')
    with path.open('rb') as f:
        a=os.fstat(f.fileno());need(a.st_size<=SMALL,'DO_NOT_OPEN_LARGE_BODY_ON_LOGIN')
        raw=f.read(SMALL+1);b=os.fstat(f.fileno())
    need(len(raw)==a.st_size and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'SMALL_SOURCE_CHANGED')
    return raw

def pin(path):
    path=pathlib.Path(path);raw=raw_small(path)
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def load(path):return json.loads(raw_small(path))

def write_new(path,value):
    raw=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    need(len(raw)<=2*1024**2,'BOUNDED_METADATA_OUTPUT_REQUIRED')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository',type=pathlib.Path,required=True);p.add_argument('--run-root',type=pathlib.Path,required=True)
    p.add_argument('--reviewer',required=True);p.add_argument('--node',default='compute-0-14')
    p.add_argument('--execution-intent',type=pathlib.Path,required=True)
    p.add_argument('--plan-output',type=pathlib.Path,required=True)
    p.add_argument('--output-prefix',type=pathlib.Path,required=True)
    a=p.parse_args();repo=a.repository
    need(os.name=='posix' and os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi','ROOT_LOGIN_METADATA_ONLY')
    need(a.reviewer=='root' and a.run_root==ROOT and repo==ROOT/'repository','ACTUAL_ROOT_REPOSITORY_REQUIRED')
    need(pathlib.Path(__file__).absolute()==repo/'workflows/data_v1_final/pprime/queued_v1/materialize_frame_v1.py','ROOT_MUST_INTEGRATE_REVIEWED_SOURCE_FIRST')
    need(a.node in {'compute-0-'+str(n) for n in range(14,20)},'CPU14_TO19_ONLY')
    need(a.execution_intent.is_absolute() and ROOT/'control' in a.execution_intent.parents and not a.execution_intent.exists(),'NEW_ROOT_EXECUTION_INTENT_PATH_REQUIRED')
    need(a.plan_output.is_absolute() and ROOT/'control' in a.plan_output.parents and not a.plan_output.exists(),'NEW_QUEUE_PLAN_REQUIRED')
    need(a.output_prefix.is_absolute() and a.output_prefix.parent==ROOT/'artifacts/vector_frame_audit' and not a.output_prefix.exists(),'NEW_AUDIT_OUTPUT_PREFIX_REQUIRED')
    sources={};deferred={}
    def add(ref):
        path=pathlib.Path(ref['path'])
        if ref.get('bytes',0)>SMALL or path.suffix.lower() not in {'.py','.json','.sh','.md','.txt','.yaml','.yml','.toml'}:
            deferred[str(path)]=dict(ref);return
        actual=pin(path)
        need(all(actual[k]==ref[k] for k in ('path','sha256') if k in ref) and ('bytes' not in ref or actual['bytes']==ref['bytes']),'SMALL_AUTHORITY_PIN_CHANGED:'+str(path))
        need(str(path) not in sources or sources[str(path)]==actual,'CONFLICTING_SOURCE_REF')
        sources[str(path)]=actual
    def keep(path):
        ref=pin(path);add(ref);return ref
    config_path=repo/'configs/data_v1/pprime/vector_frame_audit_root_v1.json'
    pilot_path=repo/'configs/data_v1/pprime/pilot_v1.json'
    prepared_path=ROOT/'artifacts/vector_frame_audit/prepared_cpu_v4/prepared.json'
    c=load(config_path);pilot=load(pilot_path);prepared=load(prepared_path)
    cp,pp,fp=keep(config_path),keep(pilot_path),keep(prepared_path)
    need(c['schema']=='PPRIME_VECTOR_FRAME_AUDIT_V1' and c['pilot_config']==pp and c['production_membership'] is False,'FROZEN_AUDIT_CONFIG_REQUIRED')
    need(prepared['status']=='VECTOR_AUDIT_INPUTS_PREPARED_QM_NOT_STARTED' and prepared['config']==cp and prepared['pilot_config']==pp
         and prepared['QM_calls_prepared']==72 and prepared['QM_started'] is False and prepared['molecules']==4
         and prepared['production_membership'] is False,'EXACT552_PREPARED72_NOT_QM_REQUIRED')
    need(c['worker_wall_seconds']==5400 and c['max_output_bytes']==2*1024**3 and c['quota_reserve_bytes']==200000000000,'ORIGINAL_FRAME_LIMITS_CHANGED')
    for ref in [*c['parent_source_pins'],*pilot['small_authority_pins'],pilot['source_plan'],pilot['legacy_contract'],
                prepared['audit_membership'],prepared['cases'],prepared['pprime_prepared']]:add(ref)
    contract=load(pilot['legacy_contract']['path'])
    add(contract['protocol']);add(contract['registry']);add(contract['reproduction_package'])
    for ref in contract['sources']:add(ref)
    protocol=load(contract['protocol']['path'])
    need(tuple(t['name'] for t in protocol['tasks'])==TASKS and protocol['seed']==20261010 and protocol['perturb_sigma_A']==0.1,'EXACT_WP5_TWELVE_TASK_PROTOCOL_REQUIRED')
    for ref in protocol['frozen_dependencies'].values():add(ref)
    package=load(contract['reproduction_package']['path'])
    need(package['software_versions']['mopac']['version']=='23.0.3' and package['software_versions']['xtb']['version']=='6.7.1','WP5_PROGRAM_VERSIONS_CHANGED')
    binary_refs=[{'family':name,'path':value['executable'],'sha256':value['sha256'],'software_version_id':value['software_version_id'],
                  'version':value['version'],'verification':'old engine initialization performs actual binary hash on compute node'}
                 for name,value in sorted(package['software_versions'].items())]
    pprime=repo/'workflows/data_v1_final/pprime'
    for folder in (pprime,pprime/'vector_audit',pprime/'queued_v1'):
        for source in sorted(folder.glob('*.py')):keep(source)
    command=[PY,'-B',str(pprime/'queued_v1/run_frame_v1.py'),'--plan',str(a.plan_output),'--root-preflight',str(a.execution_intent)]
    plan={'schema':'PPRIME_VECTOR_FRAME_STRICT_QUEUE_PLAN_V1','status':'READY_FOR_ROOT_QUEUE_NOT_SUBMITTED_NOT_QM_EXECUTED',
      'created_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
      'repository':str(repo),'project_working_directory':str(PROJECT),'kind':'qm','pilot':True,'node':a.node,
      'allowed_nodes':['compute-0-'+str(n) for n in range(14,20)],'cpus':16,'memory_gib':64,'wall_seconds':7200,
      'estimated_peak_output_bytes':c['max_output_bytes']+64*1024**2,'allocated_core_hour_ceiling':32,
      'ceiling_is_runtime_forecast':False,'quota_reserve_bytes':200000000000,
      'formal_memory_rule':'all users positive declared reservations plus full own64GiB <=85%; zero/missing foreign declaration blocks. Pending queue is not an execution admission.',
      'root_instruction':'请你把任务提交上，如果节点需要排队请等待排队，直到所有指令要求的任务都完成之后再结束任务，在没有完成之前请不要停止',
      'original_source':keep(pprime/'vector_audit/run_v1.py'),'original_evaluator':keep(pprime/'vector_audit/evaluate_v1.py'),
      'config':cp,'pilot_config':pp,'prepared':fp,'cases':prepared['cases'],'audit_membership':prepared['audit_membership'],
      'expected_calls':72,'expected_molecules':4,'production_membership':False,
      'source_references':list(sources.values()),'data_references':list(deferred.values()),'runtime_binary_references':binary_refs,
      'command_argv':command,'execution_intent_path':str(a.execution_intent),'output_prefix':str(a.output_prefix),
      'run_output':str(a.output_prefix/'run'),'evaluation_output':str(a.output_prefix/'frame_evaluation.json'),
      'queue_receipt_output':str(a.output_prefix/'queue_execution_receipt.json'),
      'required_frame_status':'INPUT_FRAME_SUPPORTED_ON_TESTED_CONTROLS_WITH_LIMITS',
      'frame_scope':'Only PM7 B and GFN2 clean/noisy/gradient/translation controls; not all twelve-task pilot and not all-corpus certification',
      'all72_output_raw_retained':True,'inputs_retained_as_isolated_audit_reproduction':True,
      'scientific_invocation_or_keywords_changed':False,'old_sources_or_results_modified':False,
      'next_2000_pilot':'Requires actual frame PASS plus new CPU-compatible retention preparation/retention_manifest; no pilot or full release here',
      'full_run_authorized':False,'automatic_submission_or_retry':False}
    write_new(a.plan_output,plan)
    print(json.dumps({'status':plan['status'],'plan':pin(a.plan_output),'command_argv':command,
       'sources':len(sources),'deferred_data_references':len(deferred),'large_bodies_opened_hashed_or_stat_ed':False}))
if __name__=='__main__':main()
