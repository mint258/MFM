"""Reuse actual Kraken JSONL reader and original Drugs Budget/Writer objects."""
import os,stat,sys
from pathlib import Path
from workflows.expansion.marcel_kraken_decontamination_main_v1.runtime import rows,Budget,Writer
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from . import contract as C
Q=C.Q

def file_guard(ref):
    C.data_reference({k:ref[k] for k in ('path','bytes','sha256')});p=Path(ref['path']);s=p.lstat()
    Q.need(not any(x.is_symlink() for x in (p,*p.parents)) and stat.S_ISREG(s.st_mode) and s.st_uid==1278
        and s.st_nlink==1 and s.st_size==ref['bytes'],'REGULAR_OWNED_SINGLE_LINK_EXACT_DATA_NO_SYMLINK')
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_mode,s.st_nlink)

def admit(args,plan,parents):
    Q.need(plan['schema']=='MARCEL_DRUGS_DECONTAMINATION_PLAN_V1' and plan['scope_parameters']==C.PARAMETERS
        and plan['output_cap_bytes']==C.CAP and type(plan['wall_seconds'])is int and 600<=plan['wall_seconds']<=1800
        and plan['wall_seconds']%60==0,'EXACT_FINITE_ONE_STAGE_UNION_PROJECTION')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(args.plan),'--startup-proof',str(args.startup_proof)]
    proof=R.require_startup(args.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,
        expected_execution_argv=argv,expected_source=C.HERE/'run.py',expected_kind='analysis',
        required_references=[Q.pin(args.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];authority=C.meta(req['queue_authority_reference'])
    Q.need(req['node'] in {'compute-0-'+str(n) for n in authority['allowed_nodes']['analysis']} and proof['uid']==1278
        and req['cpus']==16 and req['kind']=='analysis' and req['pilot'] is False and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and req['wall_seconds']==plan['wall_seconds'] and req['estimated_peak_output_bytes']==req['stage_output_cap_bytes']==C.CAP
        and req['data_references']==plan['data_references'] and len(req['data_references'])==1 and not req.get('deferred_authority_references')
        and proof['account_free_bytes']-C.CAP>=200000000000,'FRESH_MAIN16_NO_MEM_ONE_UNION512MIB_ALL_REGISTERED_RESERVATIONS_AND200GB')
    review=C.meta(req['scope']['review']);Q.need(req['scope']['mode']=='BOUNDED_METADATA_PREPARATION'
        and review['accepted_complete_union_only_no_new_graph_or_keys'] is True and review['global_pool_release_authorized'] is False,
        'ROOT_REVIEWED_EXACT_UNION_ONLY_SCOPE')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ORIGINAL_QUALITY_AND_COST_AUTHORITY')
    for path in [*(C.HERE/n for n in C.FILES),*C.OLD]:Q.need(Q.pin(path) in req['source_references'],'ALL_NEW_AND_REUSED_SOURCE_BYTES')
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if name.startswith('workflows.expansion') and path and Path(path).suffix=='.py':Q.need(Q.pin(path) in req['source_references'],'ACTUAL_IMPORTED_EXPANSION_SOURCE:'+name)
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'ACTUAL_PRIMARY_ARGV_NOT_FAKE_ENTRY')
    return proof
