"""Actual CPU13 zero-science original Budget observation under a new finite epoch."""
import argparse,pathlib,time,traceback
from . import contract as E
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as A


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True)
    a=p.parse_args();cr=E.G.meta_pin(a.config);cfg=E.refread(cr,'SPRIME_NEW_RESOURCE_EPOCH_CPU_PROBE_CONFIG_V1')
    er=cfg['epoch_reference']
    argv=[E.G.PY,'-B','-m','workflows.data_v1_final.execution.sprime_resource_epoch_v1.probe',
      '--config',str(a.config),'--startup-proof',str(a.startup_proof)]
    required=[cr,er,cfg['original_config_reference'],cfg['quota_reuse_review_reference'],*E.sources()]
    proof=A.require_startup(a.startup_proof,expected_scope_key=E.PROBE_KEY,expected_scope_parameters=E.PROBE_PARAMS,
      expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',required_references=required)
    e,_=E.epoch_inputs(er,active=False)
    E.F.need(proof['request']['node']=='compute-0-13' and proof['request']['cpus']==16
      and proof['request']['wall_seconds']==900 and proof['request']['estimated_peak_output_bytes']==E.PROBE_CAP,
      'EXACT_FINITE_NEW_EPOCH_CPU13_METADATA_PROBE')
    E.F.need(cfg['quota_reuse_review_reference']==e['quota_reuse_review_reference']
      and cfg['output_cap_bytes']==E.PROBE_CAP,'EXACT_NEW_EPOCH_PROBE_CONFIG')
    value=E.F.config(cfg['original_config_reference']);out=E.R.new_output_directory(cfg['output_directory'],value)
    budget=None;failure=None;stop=None;cpu_begin=time.time();cpu_end=None
    try:
        # analysis is honest: no process_task/load_science and no scientific dispatch.
        # Original Budget uses its original analysis cleanup reserve (90s for900s),
        # avoiding the original conformer7200s reserve on a900s metadata probe.
        budget=E.R.Budget(proof,{'quota_reuse_review_reference':e['quota_reuse_review_reference']},value,out)
        cpu_begin=time.time();stop=budget.observe();cpu_end=time.time()
        E.F.need(stop is None,'ORIGINAL_RESOURCE_OBSERVATION_STOP')
        E.F.need(budget.client.identity==e['publisher_identity_reference'],'ACTUAL_CPU_PROBE_IS_NOT_NEW_EPOCH')
    except BaseException as exc:
        failure={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        raise
    finally:
        if cpu_end is None:cpu_end=time.time()
        report=budget.report() if budget is not None else None
        if budget is not None:budget.close_monitor()
        v={'schema':'ACTUAL_NEW_SPRIME_RESOURCE_EPOCH_CPU_PROBE_V1',
          'status':'HEALTHY_ORIGINAL_RESOURCE_OBSERVATION_NOT_SCIENTIFIC_SUCCESS' if failure is None else 'FAILED_RESOURCE_PROBE_NO_SCIENCE_AUTHORITY',
          'epoch_reference':er,'job_id':str(proof['job_id']),'uid':1278,'node':proof['node'],
          'config_reference':cr,'startup_proof_reference':E.G.meta_pin(a.startup_proof),
          'original_budget_report':report,'failure':failure,'budget_constructed':budget is not None,
          'cpu_observation_begin_unix_seconds':cpu_begin,'cpu_observation_end_unix_seconds':cpu_end,
          'new_UFF_QM_calls':0,'scientific_bodies_read':0,'science_primary_or_load_science_called':False,
          'analysis_cleanup_reserve_is_not_a_scientific_recipe_change':True,
          'original_4521922_failure_cause':'UNKNOWN_NOT_RECONSTRUCTED','source_references':E.sources()}
        E.F.need(len(E.F.canonical(v))<2<<20,'SMALL_RESOURCE_PROBE_REPORT_ONLY')
        E.R.write_json_new(out/'resource_probe.json',v)
    return 0


if __name__=='__main__':raise SystemExit(main())
