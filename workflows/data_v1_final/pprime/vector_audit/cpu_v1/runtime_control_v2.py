"""Small CPU run controls; scientific inputs and render mathematics remain original."""
from __future__ import annotations
import json,os,pathlib
from workflows.data_v1_final.execution.cpu_analysis_v1 import policy
from workflows.data_v1_final.execution.cpu_analysis_v1 import runtime_v2 as cpu_runtime


def checkpoint_iter(items, check=None):
    """Check before calling next(), including the first source read/parse."""
    if check is None:
        check = cpu_runtime.checkpoint
    iterator = iter(items)
    while True:
        check()
        try:
            item = next(iterator)
        except StopIteration:
            return
        yield item


def source_lineage(source):
    """Never infer a native source-shard ID from the legacy engine grouping."""
    return {'source_shard_id': source.get('shard_id'),
            'source_shard_id_status': 'PRESENT_NATIVE_SHARD_ID' if source.get('shard_id') is not None else 'UNAVAILABLE_IN_PREPARED_SOURCE',
            'legacy_engine_file_group': source['file_group']}


def load_runconfig(path, audit_config, pilot_config, prepared_directory):
    c=policy.load(path)
    policy.require(c['runtime_path']==str(pathlib.Path(cpu_runtime.__file__)), 'EXACT_NODE_LOCAL_RUNTIME_METADATA_REQUIRED')
    policy.require(c['schema']=='VECTOR_PREPARE_CPU_METADATA_V1' and c['scope_key']=='vector_prepare_1000', 'EXACT_READONLY_VECTOR_CPU_SCOPE_REQUIRED')
    policy.require(c['original_molecules']==1000 and c['original_UFF_records']==2000 and c['maximum_audit_molecules']==4 and c['actual_QM_calls']==0, 'BOUNDED_READONLY_INPUT_SCOPE_DIFFERS')
    policy.require(c['scientific_config_mutated'] is False and c['production_membership'] is False, 'NO_SCIENTIFIC_OR_PRODUCTION_PROMOTION')
    for key,p in (('audit_config',audit_config),('pilot_config',pilot_config),('prepared_manifest',pathlib.Path(prepared_directory)/'prepared.json')):
        policy.require(policy.ref(pathlib.Path(p))==c[key], 'EXACT_FROZEN_'+key.upper()+'_REQUIRED')
    return c


def cpu_observed(intent, runconfig, audit_config, audit, cpu):
    proof=cpu_runtime.root_guard(intent,runconfig,audit['max_output_bytes'],wall_limit=3600)
    request=proof['request']
    policy.require(request['scope_key']=='vector_prepare_1000' and request['memory_gib']==32, 'CENTRAL_VECTOR32G_SCOPE_REQUIRED')
    for p in (pathlib.Path(__file__),pathlib.Path(__file__).parent/'prepare_cpu_v2.py',pathlib.Path(audit_config)):
        policy.require(policy.ref(p) in request['source_references'], 'ACTUAL_CPU_VECTOR_IMPORT_OR_CONFIG_NOT_PINNED')
    return ({'job_id':os.environ['SLURM_JOB_ID'], 'node':request['node'],
             'allocated_cpus':int(os.environ['SLURM_CPUS_PER_TASK']), 'workers':16,
             'memory_basis':proof['memory_basis'],
             'execution_variant':'CPU_PARTITION_READONLY_VECTOR_PREPARATION_V1'}, policy.ref(intent))


def prepared_authority(saved, path, expected_sha, cpu, intent):
    policy.require(policy.ref(path)==cpu['prepared_manifest'] and expected_sha==cpu['prepared_manifest']['sha256'], 'PREPARED_MANIFEST_BINDING_DIFFERS')
    policy.require(saved['status']=='PPRIME_PAIRS_READY_NOT_QM_EXECUTED' and saved['QM_started'] is False and saved['runtime']['job_id']=='4520345', 'EXACT_COMPLETED_PREPARATION_AUTHORITY_REQUIRED')
    policy.require(saved['molecules']==1000 and saved['conformers']==2000 and saved['audit_records']==20, 'ORIGINAL1000_2000_PREPARATION_REQUIRED')
    policy.require(saved['config']==cpu['pilot_config'] and saved['outputs']==cpu['prepared_data_references'], 'ORIGINAL_PREPARED_OUTPUT_REFERENCES_CHANGED')
    policy.require(cpu['prepared_manifest'] in policy.load(intent)['request']['source_references'], 'CLOSED_SMALL_INPUT_AUTHORITY_NOT_PINNED')
