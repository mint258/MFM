"""CPU partition exception bound only to the actual approved PubChem node21."""
from pathlib import Path
from workflows.expansion.expansion_common_reference_v1 import runtime as R


def approved_partition(plan,actual_node,actual_partition,read_approval=R.read):
    requested=plan.get('partition','cpu')
    R.need(actual_partition==requested,'ACTUAL_COCONUT_PARTITION_DIFFERS_FROM_PLAN')
    if requested=='cpu':return dict(partition='cpu',node=actual_node,exception=False)
    R.need(requested=='all' and actual_node==plan['node']=='compute-0-21','ALL_EXCEPTION_ONLY_APPROVED_CPU21')
    ref=plan.get('resource_authorization_reference')
    R.need(isinstance(ref,dict) and Path(ref['path']).name=='user_cpu21_authorization_20261103.json','EXACT_USER_CPU21_AUTHORIZATION_REFERENCE_REQUIRED')
    approval=read_approval(ref)
    R.need(approval.get('schema')=='PUBCHEM_EXPANSION_USER_CPU21_AUTHORIZATION_V1'
      and approval.get('status')=='USER_APPROVED' and approval.get('node')=='compute-0-21'
      and approval.get('partition')=='all' and approval.get('GPU_used') is False and approval.get('paid_server_used') is False
      and approval.get('scope')=='This PubChem expansion goal only, including statistics, screening and UFF'
      and approval.get('source')=='Direct user reply in this conversation','ACTUAL_USER_APPROVED_PUBCHEM_CPU_ONLY21_AUTHORITY')
    return dict(partition='all',node='compute-0-21',exception=True,authorization_reference=ref)
