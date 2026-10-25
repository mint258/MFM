"""Root small-metadata registration of queued retention preparation, never QM."""
from __future__ import annotations
import argparse,datetime,os,pathlib,socket
from workflows.data_v1_final.pprime.queued_v1.materialize_frame_v1 import ROOT,PROJECT,PY,SMALL,pin,load,write_new,need

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository',type=pathlib.Path,required=True);p.add_argument('--run-root',type=pathlib.Path,required=True)
    p.add_argument('--reviewer',required=True);p.add_argument('--node',default='compute-0-14')
    p.add_argument('--execution-intent',type=pathlib.Path,required=True);p.add_argument('--source-proof',type=pathlib.Path,required=True)
    p.add_argument('--plan-output',type=pathlib.Path,required=True);p.add_argument('--output-prefix',type=pathlib.Path,required=True)
    a=p.parse_args();repo=a.repository;parent=repo/'workflows/data_v1_final/pprime'
    need(os.name=='posix' and os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi','ROOT_LOGIN_METADATA_ONLY')
    need(a.reviewer=='root' and a.run_root==ROOT and repo==ROOT/'repository'
        and pathlib.Path(__file__).absolute()==parent/'queued_retention_v1/materialize_v1.py','ACTUAL_ROOT_REVIEWED_SOURCE_REQUIRED')
    need(a.node in {'compute-0-'+str(n) for n in range(14,20)},'LEGACY_RUNTIME_CPU14_TO19_ONLY')
    need(a.execution_intent.is_absolute() and ROOT/'control' in a.execution_intent.parents and not a.execution_intent.exists(),'NEW_EXECUTION_INTENT_REQUIRED')
    need(a.plan_output.is_absolute() and ROOT/'control' in a.plan_output.parents and not a.plan_output.exists(),'NEW_QUEUE_PLAN_REQUIRED')
    need(a.output_prefix.parent==ROOT/'artifacts/pprime_retention_v1' and not a.output_prefix.exists(),'NEW_RETENTION_OUTPUT_PREFIX_REQUIRED')
    source_refs={};data_refs={}
    def add(ref):
        path=pathlib.Path(ref['path'])
        if ref.get('bytes',0)>SMALL or path.suffix.lower() not in {'.py','.json','.sh','.md','.txt','.yaml','.yml','.toml'}:
            data_refs[str(path)]=dict(ref);return
        actual=pin(path)
        need(all(actual[k]==ref[k] for k in ('path','sha256') if k in ref)
            and ('bytes' not in ref or actual['bytes']==ref['bytes']),'SMALL_PIN_CHANGED:'+str(path))
        source_refs[str(path)]=actual
    def keep(path):
        result=pin(path);add(result);return result
    cp=repo/'configs/data_v1/pprime/stable_raw_retention_v1.json';config=load(cp);config_ref=keep(cp)
    pilot=load(config['pilot_config']['path']);add(config['pilot_config'])
    original_path=ROOT/'artifacts/pprime/prepared_v1/prepared.json';original=load(original_path);original_ref=keep(original_path)
    need(config['schema']=='PPRIME_STABLE_RAW_RETENTION_POLICY_V1' and config['basis_points']==100 and config['modulus']==10000
        and config['seed']==20261010 and config['max_output_bytes']==8*1024**3,'ORIGINAL_RETENTION_POLICY_REQUIRED')
    need(original['status']=='PPRIME_PAIRS_READY_NOT_QM_EXECUTED' and original['QM_started'] is False
        and original['molecules']==1000 and original['conformers']==2000 and original['audit_records']==20
        and original['config']==config['pilot_config'],'ORIGINAL345_EXACT2000_NOT_QM_REQUIRED')
    outputs={pathlib.Path(ref['path']).name:ref for ref in original['outputs']}
    need(set(outputs)=={'pairs.jsonl','audit_selected.parquet','audit_membership.json'},'ORIGINAL_PREPARED_OUTPUT_SET_REQUIRED')
    for ref in [*config['parent_source_pins'],config['selector'],*pilot['small_authority_pins'],pilot['source_plan'],*original['outputs']]:add(ref)
    proof=load(a.source_proof);proof_ref=keep(a.source_proof)
    core=parent/'retention_v1/prepare_cpu_queued_v2.py';old=parent/'retention_v1/prepare_v1.py'
    need(proof['schema']=='QUEUED_RETENTION_CPU_BINDING_SOURCE_PROOF_V1' and proof['status']=='PASS_SOURCE_ONLY_NOT_RETENTION_EXECUTED'
        and proof['variant_source']==pin(core) and proof['original_source']==pin(old)
        and proof['inverse_full_file_bytes_equal'] and proof['normalized_AST_identical'],'ACTUAL_CORE_CPU_EQUIVALENCE_PROOF_REQUIRED')
    for folder in (parent,parent/'retention_v1',parent/'raw_policy_proposal_v1',parent/'queued_retention_v1'):
        for source in sorted(folder.glob('*.py')):keep(source)
    keep(parent/'queued_v1/materialize_frame_v1.py')
    command=[PY,'-B',str(parent/'queued_retention_v1/run_prepare_v1.py'),'--plan',str(a.plan_output),'--root-preflight',str(a.execution_intent)]
    plan={'schema':'PPRIME_QUEUED_RETENTION_PREPARATION_PLAN_V1','status':'READY_FOR_ROOT_STRICT_QUEUE_NOT_SUBMITTED',
        'created_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'kind':'analysis','pilot':True,'node':a.node,'allowed_nodes':['compute-0-'+str(n) for n in range(14,20)],
        'cpus':16,'memory_gib':64,'wall_seconds':3600,'estimated_peak_output_bytes':8*1024**3+64*1024**2,
        'allocated_core_hour_ceiling':16,'ceiling_is_runtime_forecast':False,'quota_reserve_bytes':200000000000,
        'expected_molecules':1000,'expected_pairs':2000,'expected_original_audit_records':20,'new_UFF_QM_calls':0,
        'config':config_ref,'pilot_config':config['pilot_config'],'original_prepared':original_ref,
        'original_pairs':outputs['pairs.jsonl'],'original_audit_selected20':outputs['audit_selected.parquet'],
        'original_audit_membership':outputs['audit_membership.json'],'source_proof':proof_ref,
        'original_source':keep(old),'core_variant':keep(core),'source_references':list(source_refs.values()),'data_references':list(data_refs.values()),
        'command_argv':command,'project_working_directory':str(PROJECT),'execution_intent_path':str(a.execution_intent),
        'output_prefix':str(a.output_prefix),'retention_output':str(a.output_prefix/'prepared'),
        'queue_receipt_output':str(a.output_prefix/'queue_execution_receipt.json'),
        'frame_actual_pass_required_for_this_non_QM_preparation':False,
        'future_2000_QM_requires':['actual frame PASS with limits','actual retention closure and SHA','new strict64G science request and untouched science-once ledger'],
        'user_instruction':'请你把任务提交上，如果节点需要排队请等待排队，直到所有指令要求的任务都完成之后再结束任务，在没有完成之前请不要停止',
        'foreign_zero_memory_blocks_execution':True,'original_random_order_or_science_or_selector_changed':False,
        'original_outputs_modified':False,'full_run_authorized':False,'automatic_submission_or_retry':False}
    write_new(a.plan_output,plan)
    print(__import__('json').dumps({'status':plan['status'],'plan':pin(a.plan_output),'command_argv':command,
        'sources':len(source_refs),'deferred_data_references':len(data_refs),'new_UFF_QM_calls':0,'large_data_bodies_opened_hashed_or_stat_ed':False}))
if __name__=='__main__':main()
