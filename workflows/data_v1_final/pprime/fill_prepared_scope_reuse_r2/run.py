"""Reuse a real closed fill scope, original Source3 and original NoInvoke hashes."""
import argparse,concurrent.futures as cf,importlib.util,json,os,pathlib,stat,sys,types
from . import io_adapter as A,workers,publish
from .bare_imports import pprime_bootstrap
from workflows.data_v1_final.execution.cpu_account100_queue_v1.runtime import require_startup
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import prepare as Original,io as OriginalIO,contract as Science
from workflows.data_v1_final.pprime.current_prepared_component_parentstate_v3.run import fixtures
KEY='pprime_fill_prepared_scope_reuse_v1'
MODULE='workflows.data_v1_final.pprime.fill_prepared_scope_reuse_r2.run'
P=pathlib.Path


def scope_closed(plan):
    account=A.meta(plan['scope_parent_accounting_reference']);parent=account['parent']
    A.need(account['schema']=='ACTUAL_PPRIME_FILL_SCOPE_PARENT_ACCOUNTING_V1'and str(account['actual_job_id'])==str(plan['scope_parent_job_id'])
      and parent['JobIDRaw']==str(plan['scope_parent_job_id']) and parent['UID']=='1278'and parent['State']=='COMPLETED'and parent['ExitCode']=='0:0'
      and parent['AllocCPUS']=='16'and parent['NodeList']=='compute-0-18','ACTUAL_CLOSED_SCOPE_PARENT_NOT_OLD_COMMON_C0')
    import csv,io
    rows=[r for r in csv.DictReader(io.StringIO(account['native_raw']),delimiter='|')if r['JobIDRaw']==str(plan['scope_parent_job_id'])]
    A.need(len(rows)==1 and all(rows[0][k]==parent[k]for k in parent),'SAME_NATIVE_SACCT_INLINE_BYTES_AND_PARENT')
    scope=A.meta(plan['closed_scope_reference']);accepted=A.meta(plan['accepted_scope_reference'])
    A.need(accepted['schema']=='ACTUAL_PPRIME_FILL_SCOPE_ACCEPTANCE_V1'and accepted['scope_manifest_reference']==plan['closed_scope_reference']
      and accepted['actual_parent_accounting_reference']==plan['scope_parent_accounting_reference'],'ROOT_ACTUAL_CLOSED_SCOPE_BINDING')
    A.need(scope['schema']=='PPRIME_FILL_FIXED_RANDOM_SCOPE_CLOSED_V1'and str(scope['actual_job_id'])==str(plan['scope_parent_job_id'])
      and scope['original_ready_anti_join_performed']and scope['complete_ordinary_order_before_first2']and scope['seed']==20261025
      and scope['actual_chosen_MIDs']==accepted['actual_chosen_MIDs']and scope['actual_first2_records']==accepted['actual_first2_records']
      and scope['new_UFF_QM_calls']==0 and not scope['old_parent_upgraded'],'ACTUAL_UNCHANGED_CLOSED_SCOPE')
    return scope

def private_resource(plan):
    ref=plan['resource_module_reference'];A.small(ref)
    spec=importlib.util.spec_from_file_location('_prepared_reuse_resource',ref['path']);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    A.need(module.KEY==KEY,'ACTUAL_PREPARED_SCOPE_RESOURCE_MODULE_KEY')
    return module


def prepare_all(plan,proof,monitor):
    scope=scope_closed(plan);context=A.meta(plan['source_context_reference']);old=A.meta(plan['original_protocol_reference']);pilot=A.meta(context['pilot_config'])
    Science.authority(plan)
    A.need(old['timeout_seconds']==900 and plan['precision_mode']=='ORIGINAL_WP5'and plan.get('user_precision_decision_reference')is None,'ORIGINAL_WP5_ONLY')
    persistent=P(plan['output_directory']);A.need(not persistent.exists(),'FRESH_LUSTRE_PREPARATION_ROOT');persistent.mkdir(parents=True,mode=0o700)
    local=P(monitor.local_workspace_directory);A.need(local==P(plan['local_workspace_directory']) and local.is_dir(),'RUNTIME_CREATED_REAL_LOCAL_WORKSPACE')
    budget=A.Budget(monitor,plan,proof,local,persistent);budget.forecast_records=max(1,scope['actual_first2_records']);store=A.Store(local,plan['resource_binding']['local_workspace_cap_bytes'],budget)
    store.json(local/'owner.json',dict(uid=1278,job_id=str(proof['job_id']),pid=os.getpid(),node=plan['node'],start_ticks=Original.I.ticks(os.getpid()),
      boot_id=proof['boot_id'],original_scope_reference=plan['closed_scope_reference'],native_invokes=0))
    b=dict(context=context,old=old,pilot=pilot,fill_scope=scope,fill_scope_reference=plan['closed_scope_reference'])
    results=[];component_receipts=[];all_closures=[]
    for component_ref in scope['component_references']:
        header=A.meta(component_ref);number=header['component_index'];component=local/('component_%05d'%number);component.mkdir()
        pool=workers.HashPool(plan,proof,context,component,budget)
        # This is the exact earlier builder body. Its physical source/adapt/audit
        # math is unchanged; only hash-pool, source-held/output IO are rebound.
        science=types.SimpleNamespace(**{k:v for k,v in vars(Science).items()if k!='meta'},meta=A.meta)
        source_namespace=dict(importlib=__import__('importlib'),json=json,pathlib=pathlib,sys=sys,types=types,C=science,pprime_bootstrap=pprime_bootstrap)
        original_proxy=types.SimpleNamespace(**{k:v for k,v in vars(Original).items()if k not in('hash_block','Body')},hash_block=pool.block,Body=Original.Body)
        source_namespace['Original']=original_proxy
        source=A.definitions(plan['source_io_source_reference'],('clone','original_physical_reader','SourceIO'),source_namespace)
        io=types.SimpleNamespace(**{k:v for k,v in vars(OriginalIO).items()if k!='Store'},Store=A.Store)
        build_namespace=dict(C=science,SourceIO=source['SourceIO'],Original=original_proxy,I=io,q=Original.q,hashlib=__import__('hashlib'),json=json,pathlib=pathlib)
        build=A.definitions(plan['prepare_source_reference'],('build',),build_namespace)['build']
        effective=dict(plan,_active_shard_header_reference=component_ref)
        try:prepared=build(effective,proof,component,b,budget,A.Store(component,12<<30,budget))
        finally:pool.close()
        all_closures.extend(pool.closures)
        # The original per-component4GiB prepared-index bound stays a resource
        # bound; it is not a scientific success threshold or truncation rule.
        A.need(prepared['index']['bytes']<4<<30,'ORIGINAL_PREPARED_COMPONENT_INDEX_WITHIN4GIB')
        prepared_ref=publish.publish(prepared,pool.closures,component_ref,plan['closed_scope_reference'],plan,proof,component,persistent,budget)
        results.append(prepared_ref)
        component_receipts.append(A.Store(plan['control_directory'],64<<20).json(P(plan['control_directory'])/('prepared_component_%05d_receipt.json'%number),dict(
          schema='PPRIME_CLOSED_SCOPE_REUSE_COMPONENT_RECEIPT_V1',status='COMPONENT_CLOSED_PARENT_STATE_SEPARATE',actual_job_id=str(proof['job_id']),
          prepared_header_reference=prepared_ref,actual_source3_reference=plan['actual_source3_reference'],scope_reference=plan['closed_scope_reference'],
          plan_reference=A.pin_small(plan['plan_path']),proof_reference=A.pin_small(plan['proof_path']),input_hash_worker_closures=pool.closures,
          parent_C0_claimed=False,new_QM_UFF_calls=0,production_once_written=False)))
    Original.close_inputs();budget.check()
    record=dict(schema='PPRIME_CLOSED_SCOPE_REUSE_PREPARATION_V1',status='CLOSED_LUSTRE_PREPARED_COMPONENTS_NO_QM',actual_job_id=str(proof['job_id']),
      scope_reference=plan['closed_scope_reference'],prepared_header_references=results,component_receipt_references=component_receipts,input_hash_worker_closures=all_closures,
      native_invokes=0,new_UFF_QM_calls=0,production_once_written=False,existing_scope_or_dataset_payload_copied=False,
      local_origin_preserved=str(local),resource_logical=budget.report(),original_versions_keywords_900s_precision_unchanged=True,
      final_Common_or_training_admission=False)
    return A.Store(persistent,16<<20,budget).json(persistent/'preparation_manifest.json',record)


def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--plan',required=True);a.add_argument('--startup-proof',required=True);args=a.parse_args()
    plan_ref=A.pin_small(args.plan);proof_ref=A.pin_small(args.startup_proof);plan=A.meta(plan_ref)
    A.need(plan['schema']=='PPRIME_FILL_CLOSED_SCOPE_REUSE_PREPARATION_PLAN_V1','EXACT_CLOSED_SCOPE_REUSE_PLAN')
    argv=[plan['python_executable'],'-B','-m',MODULE,'--plan',args.plan,'--startup-proof',args.startup_proof]
    proof=require_startup(args.startup_proof,expected_kind='analysis',expected_scope_key=KEY,expected_scope_parameters=plan['scope_parameters'],
      expected_execution_argv=argv,expected_source=P(__file__).absolute(),required_references=[plan_ref,*plan['source_references']])
    A.need(proof['request']['cpus']==16 and proof['request']['node']==plan['node']=='compute-0-18'and proof['request']['data_references']==plan['data_references'],'REAL_GENERIC100_16CPU_NODE18_PREPARATION')
    for k in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='';control=P(plan['control_directory'])
    resource=private_resource(plan);monitor=resource.start(plan,proof,plan_reference=plan_ref,proof_reference=proof_ref)
    try:
        fixture=fixtures(control);monitor.check()
        effective=dict(plan,plan_path=args.plan,proof_path=args.startup_proof,actual_source3_reference=fixture)
        ref=prepare_all(effective,proof,monitor)
    finally:monitor.finish()
    receipt=A.Store(control,64<<20).json(control/'prepared_scope_reuse_receipt.json',dict(actual_job_id=str(proof['job_id']),manifest_reference=ref,
      actual_source3_reference=fixture,resource_report=monitor.report(),new_QM_UFF_calls=0,production_once_written=False,final_Common_or_training_admission=False))
    monitor.cleanup_local_workspace()
    print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()