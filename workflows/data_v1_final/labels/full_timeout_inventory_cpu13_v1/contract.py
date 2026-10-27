"""Only current resource identity changes; old TIMEOUT evidence stays frozen."""
from pathlib import Path
from workflows.data_v1_final.labels.full_timeout_inventory_v1 import contract as ORIGINAL
from workflows.data_v1_final.labels.full_timeout_inventory_v1.contract import (
 RUN,REPO,PY,OLD,BOOK,STATUS,need,triple,option,parent_chain)
HERE=REPO/'workflows/data_v1_final/labels/full_timeout_inventory_cpu13_v1'
ORIGINAL_HERE=ORIGINAL.HERE
FILES=('__init__.py','contract.py','run.py','metadata.py','test_resource.py','README.md')
KEY='labels_full_timeout_inventory_cpu13_v1'
MODULE='workflows.data_v1_final.labels.full_timeout_inventory_cpu13_v1.run'
STAGE='LABELS_FULL_TIMEOUT_COMMITTED_WINDOW_READONLY_INVENTORY_CPU13'
SCHEMA='LABELS_FULL_TIMEOUT_INVENTORY_CPU13_PLAN_V1'
ADAPTER='LABELS_FULL_TIMEOUT_CPU13_RESOURCE_ADAPTER_V1'
PARAMETERS=dict(ORIGINAL.PARAMETERS,current_inventory_node='compute-0-13',historical_original_node='compute-0-17',
 adapter_boundary_methods=3,historical_original_job_id='4521904')


def validate_current_request(request):
    need(request['kind']=='analysis' and request['pilot'] is False and type(request['cpus']) is int and request['cpus']==16
      and request['node']=='compute-0-13' and type(request['wall_seconds']) is int and request['wall_seconds']==1800
      and type(request['estimated_peak_output_bytes']) is int and request['estimated_peak_output_bytes']==2<<30
      and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and 'memory_gib' not in request,
      'REAL_CPU13_16_NOMEM_1800_2GIB_NOT_HISTORICAL17')
    return True


def execution_argv(plan,proof,output):
    return [PY,'-B','-m',MODULE,'--plan',str(Path(plan).absolute()),'--startup-proof',str(Path(proof).absolute()),'--output',str(Path(output).absolute())]


def validate_execution(actual,plan,proof,output):
    need(actual==execution_argv(plan,proof,output),'EXACT_NEW_PRIMARY_AND_ALL_OPTIONS_NO_LEGACY_ALIAS')
    return True
