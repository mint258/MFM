"""Root exact new auto-memory plan/review/spec; metadata only, never submission."""
from __future__ import annotations
import argparse,datetime,json,os,pathlib,socket
from workflows.data_v1_final.pprime.queued_v1.materialize_frame_v1 import ROOT,PROJECT,PY,SMALL,pin,load,raw_small,write_new,need


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=('frame','retention'),required=True);p.add_argument('--reviewer',required=True)
    p.add_argument('--old-plan',type=pathlib.Path,required=True);p.add_argument('--authority',type=pathlib.Path,required=True)
    p.add_argument('--source-proof',type=pathlib.Path,required=True);p.add_argument('--plan-output',type=pathlib.Path,required=True)
    p.add_argument('--review-output',type=pathlib.Path,required=True);p.add_argument('--spec-output',type=pathlib.Path,required=True)
    p.add_argument('--output-prefix',type=pathlib.Path,required=True)
    a=p.parse_args();repo=ROOT/'repository';here=repo/'workflows/data_v1_final/pprime/cpu_auto_memory_v1'
    need(os.name=='posix' and os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and a.reviewer=='root'
        and pathlib.Path(__file__).absolute()==here/'materialize_v1.py','ROOT_REVIEWED_METADATA_INVOCATION_REQUIRED')
    for path in (a.plan_output,a.review_output,a.spec_output):need(path.is_absolute() and ROOT/'control' in path.parents and not path.exists(),'NEW_STAGE_METADATA_DESTINATION_REQUIRED')
    parent=ROOT/'artifacts/vector_frame_audit' if a.stage=='frame' else ROOT/'artifacts/pprime_retention_v1'
    need(a.output_prefix.parent==parent and not a.output_prefix.exists(),'NEW_OUTPUT_PREFIX_REQUIRED_NO_REUSE')
    old=load(a.old_plan);authority_ref=pin(a.authority);authority=load(a.authority);proof=load(a.source_proof)
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority,validate_scope_spec
    validate_authority(authority_ref,read_small=raw_small)
    expected_old='PPRIME_VECTOR_FRAME_STRICT_QUEUE_PLAN_V1' if a.stage=='frame' else 'PPRIME_QUEUED_RETENTION_PREPARATION_PLAN_V1'
    need(old['schema']==expected_old and proof['schema']=='PPRIME_CPU_AUTO_MEMORY_SOURCE_EQUIVALENCE_V1'
        and proof['status']=='PASS_DECLARED_RESOURCE_DISPATCH_EDITS_ONLY_NOT_SCIENTIFIC_ACCEPTANCE','EXACT_OLD_SCIENCE_AND_NEW_SOURCE_PROOF_REQUIRED')
    need(proof['science_or_tests_executed'] is False,'SOURCE_PROOF_IS_NOT_EXECUTION_ACCEPTANCE')
    source={};data={};deferred={}
    def add(ref):
        path=pathlib.Path(ref['path']);suffix=path.suffix.lower()
        if 'bytes' not in ref:
            if suffix=='.sbatch':
                current=pin(path);need(current['sha256']==ref['sha256'],'OLD_SBATCH_PROVENANCE_SHA_CHANGED');source[str(path)]=current
            else:deferred[str(path)]=dict(ref)
            return
        clean={k:ref[k] for k in ('path','bytes','sha256')}
        if ref['bytes']>SMALL or suffix not in {'.py','.json','.sh','.sbatch','.md','.txt','.yaml','.yml','.toml'}:
            need(str(path) not in source,'DATA_SOURCE_COLLISION');data[str(path)]=clean;return
        need(pin(path)==clean and str(path) not in data,'SMALL_SOURCE_CHANGED_OR_COLLISION');source[str(path)]=clean
    def keep(path):
        result=pin(path);add(result);return result
    for value in old['source_references']:add(value)
    for value in old.get('data_references',[]):add(value)
    for value in old.get('deferred_authority_references',[]):add(value)
    old_ref=keep(a.old_plan);proof_ref=keep(a.source_proof);keep(a.authority)
    for path in here.glob('*.py'):keep(path)
    keep(here/'source_edits_v1.json')
    keep(repo/'workflows/data_v1_final/pprime/queued_v1/materialize_frame_v1.py')
    keep(repo/'workflows/data_v1_final/pprime/queued_retention_v1/binding_v1.py')
    config=old['config'];add(config);prepared=old['prepared'] if a.stage=='frame' else old['original_prepared'];add(prepared)
    saved=load(prepared['path']);c=load(config['path'])
    if a.stage=='frame':
        need(saved['status']=='VECTOR_AUDIT_INPUTS_PREPARED_QM_NOT_STARTED' and saved['QM_calls_prepared']==72 and saved['molecules']==4
            and saved['QM_started'] is False and saved['config']==config and c['max_output_bytes']==2*1024**3,'EXACT_ORIGINAL72_INPUT_CONTROLS_REQUIRED')
        pilot=old['pilot_config'];add(pilot)
        scope_key='pprime_frame72_cpu_auto_memory_v1';kind='qm';wall=7200;pilot_flag=True;mode='BOUNDED_PERFORMANCE_BATCH'
        parameters={'molecules':4,'qm_calls':72,'prepared_sha256':prepared['sha256'],'production_membership':False,'scientific_recipe_changed':False}
        script=here/'run_frame_v1.py';run_output=a.output_prefix/'run'
        argv=[PY,'-B',str(script),'--execute','--scope-plan',str(a.plan_output),'--config',config['path'],'--pilot-config',pilot['path'],
            '--prepared',str(pathlib.Path(prepared['path']).parent),'--prepared-sha256',prepared['sha256'],
            '--root-preflight','__ROOT_STARTUP_PROOF__','--output',str(run_output)]
        algorithm_cap=32*1024**3;dispatch_deadline=5400
    else:
        need(saved['status']=='PPRIME_PAIRS_READY_NOT_QM_EXECUTED' and saved['molecules']==1000 and saved['conformers']==2000
            and saved['QM_started'] is False and c['max_output_bytes']==8*1024**3,'EXACT_ORIGINAL1000_BY_TWO_REQUIRED')
        scope_key='pprime_retention2000_cpu_auto_memory_v1';kind='analysis';wall=3600;pilot_flag=False;mode='BOUNDED_METADATA_PREPARATION'
        parameters={'molecules':1000,'uff_geometries':2000,'original_pairs_sha256':old['original_pairs']['sha256'],'new_UFF_QM_calls':0,
            'scientific_selection_changed':False}
        script=here/'prepare_retention_v1.py';run_output=a.output_prefix/'prepared'
        argv=[PY,'-B',str(script),'--scope-plan',str(a.plan_output),'--config',config['path'],
            '--original-prepared',str(pathlib.Path(prepared['path']).parent),'--original-prepared-sha256',prepared['sha256'],
            '--root-preflight','__ROOT_STARTUP_PROOF__','--output',str(run_output)]
        algorithm_cap=8*1024**3;dispatch_deadline=3480
    soft_limits={'algorithm_rss_soft_cap_bytes':algorithm_cap,'minimum_mem_available_bytes':4*1024**3,
        'algorithm_limits_are_slurm_requests':False,'sample_seconds':1,'maximum_sample_age_seconds':3,
        'max_samples':wall+60,'max_evidence_uncompressed_bytes':32*1024**2}
    parameters.update(algorithm_rss_soft_cap_bytes=algorithm_cap,minimum_mem_available_bytes=4*1024**3)
    plan={'schema':'PPRIME_CPU_AUTO_MEMORY_STAGE_PLAN_V1','status':'ROOT_REVIEWED_NEW_RESOURCE_ADAPTER_NOT_EXECUTED',
        'stage':a.stage,'kind':kind,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','slurm_memory_requested':False,
        'scope_key':scope_key,'scope_parameters':parameters,'resource_authority':authority_ref,
        'old_scientific_plan':old_ref,'source_equivalence_proof':proof_ref,'config':config,'prepared':prepared,
        'output_prefix':str(a.output_prefix),'run_output':str(run_output),'stage_output_cap_bytes':c['max_output_bytes'],
        'estimated_peak_output_bytes':c['max_output_bytes']+64*1024**2,'wall_seconds':wall,'soft_limits':soft_limits,
        'dispatch_deadline_seconds':dispatch_deadline,'new_UFF_calls':0,'new_QM_calls_authorized':72 if a.stage=='frame' else 0,
        'scientific_gates_unchanged':True,'reuse_old_pending_job_output':False,'new_scope_review_required':True,
        'original_input_order_restored_after_bounded_thread_map':True,'signals_sent':False,'automatic_retry':False}
    if a.stage=='frame':plan.update(pilot_config=pilot,original_evaluator=old['original_evaluator'])
    else:plan['original_pairs']=old['original_pairs']
    write_new(a.plan_output,plan);plan_ref=keep(a.plan_output)
    parents=[old_ref,prepared,proof_ref]
    source_status='SOURCE_INPUT_PREPARATION_CLOSED_JOB_'+str(saved['runtime']['job_id'])
    common={'kind':kind,'scope_key':scope_key,'scope_parameters':parameters,'pilot':pilot_flag,'wall_seconds':wall,
        'estimated_peak_output_bytes':plan['estimated_peak_output_bytes'],'execution_argv':argv,'source_status_stage':source_status,
        'stage_output_cap_bytes':c['max_output_bytes']}
    review=dict(common,schema='EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1',status='APPROVED_FOR_EXACT_STAGE',reviewer='root',
        resource_authority_reference=authority_ref,scope_mode=mode,parent_evidence_references=parents,
        bounded_batch_limits_reviewed=a.stage=='frame',
        algorithm_soft_limits=soft_limits,slurm_memory_limits_requested=False,
        note='Independent new scope under actual latest user authority; old64GiB/declaration guards not reused; original science, raw retention and success/cost gates remain.')
    write_new(a.review_output,review);review_ref=pin(a.review_output)
    spec=dict(common,schema='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',
        scope={'mode':mode,'review':review_ref,'parent_profile':None},source_references=list(source.values()),
        data_references=list(data.values()),deferred_authority_references=list(deferred.values()),
        producer_stage_plan_reference=plan_ref,producer_memory_soft_limits=soft_limits,
        source_adapter_equivalence_reference=proof_ref,scientific_source_input_status=source_status)
    validate_scope_spec(spec,authority_ref,read_small=raw_small);write_new(a.spec_output,spec)
    print(json.dumps({'status':'NEW_PPRIME_AUTO_MEMORY_PLAN_REVIEW_SPEC_PREPARED_NOT_SUBMITTED','stage':a.stage,
        'plan':plan_ref,'review':review_ref,'spec':pin(a.spec_output),'source_count':len(source),'data_count':len(data),
        'deferred_authority_count':len(deferred),'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','slurm_memory_requested':False}))
if __name__=='__main__':main()
