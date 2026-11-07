"""Pure original-parent registration and new generic16 planning authority."""
import pathlib,sys
from workflows.data_v1_final.pprime.formal_packed_day_v1 import contract as F,prepare as P
from workflows.data_v1_final.export.pilot_family_D3_day_v1 import io as Resource
Q=F.Q;ROOT=Q.ROOT;REPO=Q.REPO;PY=Q.PY;need=F.need;meta=F.meta;unique=F.unique
KEY='pprime_ready_mid_partition_v1';MODULE='workflows.data_v1_final.pprime.ready_mid_partition_v1.run'
HERE=REPO/'workflows/data_v1_final/pprime/ready_mid_partition_v1'
FILES=('__init__.py','contract.py','planner.py','run.py','metadata.py','test_v1.py','README.md')
RESOURCES=('resource_authority_reference','cost_decision_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')
REQUIRED=(*RESOURCES,'parallel_user_authority_reference')
NODES=tuple('compute-0-'+str(i) for i in (2,*range(8,20)))
BODY_FIELDS=('molecule_id','effective_role','source_role','S_conformers','Sprime_conformers','global_rank')
def parameters(p):
    return {'purpose':'FROZEN_READY_MID_DISJOINT_ASSIGNMENT_NO_NATIVE_OR_ACTIVE_DB','requested_cpus':16,
      'wall_seconds':86400,'n_shards':p['n_shards'],'maximum_MIDs_per_shard':50000,
      'whole_output_cap_bytes':p['whole_output_cap_bytes'],'source_methods':3,'native_init_invoke_calls':0,
      'no_actual_once_writes':True,'original_eligible_and_CHOSEN_SQL':True,'original_first2_seed':20261025,
      'shared_preparation_pairs_not_created_or_future_pinned':True,'final_Common_or_Model_release':False}
def registration(p):
    r=p['main190_registration'];need(set(r)=={'plan','request','submission','proof'},'EXACT_LIVE_PARENT_FOUR_REGISTRATION_REFS')
    parent=meta(r['plan']);request=meta(r['request']);sub=meta(r['submission']);proof=meta(r['proof'])
    need(request==sub['request']==proof['request'] and sub['request_reference']==proof['request_reference']==r['request']
      and sub['sbatch_returncode']==0 and sub['uid']==proof['uid']==1278 and str(sub['job_id'])==str(proof['job_id'])
      and request['scope_key']==F.KEY and request['cpus']==16 and request['wall_seconds']==86400
      and request['node']==parent['node'] and request['execution_argv']==[PY,'-B','-m',F.MODULE,'--plan',r['plan']['path'],'--startup-proof',r['proof']['path']]
      and r['plan']in request['source_references'],'ACTUAL_FROZEN_LIVE_ORIGINAL_PARENT_SOURCE_ARGV_NOT_ACTIVE_DB')
    for name in F.FILES:need(Q.pin(F.HERE/name)in request['source_references'],'EXACT_ORIGINAL_R2_PARENT_SOURCE:'+name)
    b=F.bootstrap(parent)
    return parent,b,unique([*r.values(),*b['refs'],*parent['source_references']]),b['data']
def sources():
    refs=[Q.pin(HERE/n)for n in FILES]
    for folder in ('cpu_analysis_general_nodes_v1','cpu_analysis_day_v1'):
        refs.extend(Q.pin(REPO/'workflows/data_v1_final/execution'/folder/n)for n in ('__init__.py','contract.py','quota_provider.py'))
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if name.startswith('workflows.')and path and pathlib.Path(path).suffix=='.py':
            path=pathlib.Path(path).absolute();need(REPO in path.parents,'ACTUAL_REPOSITORY_CODE_ONLY');refs.append(Q.pin(path))
    return unique(refs)
def validate(p):
    need(p['schema']=='PPRIME_READY_MID_PARTITION_PLAN_V1'and p['requested_cpus']==16 and p['wall_seconds']==86400
      and p['node']in NODES and type(p['n_shards'])is int and 1<=p['n_shards']<=128
      and type(p['whole_output_cap_bytes'])is int and 2<<30<=p['whole_output_cap_bytes']<=16<<30,
      'EXACT_FINITE_GENERIC16_PLANNER_NOT_NEW_NATIVE_PERMISSION')
    need(p['scope_parameters']==parameters(p)and pathlib.Path(p['output_directory']).parent==ROOT/'artifacts/pprime_ready_mid_partition_v1',
      'EXACT_FRESH_PLANNER_SCOPE_OUTPUT')
    need(type(p['partition_id'])is str and p['partition_id']and len(p['partition_id'])<=128
      and meta(p['parallel_user_authority_reference'])['schema']=='USER_AUTHORIZED_DUAL_CLUSTER_DATA_PARALLELISM_V1',
      'ACTUAL_USER_PARALLEL_RESOURCE_SOURCE_NOT_A_SCIENCE_PERMISSION')
    return p
