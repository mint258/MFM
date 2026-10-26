"""Run existing synthetic boundaries in a real CPU job with no memory request."""
import argparse,os,pathlib,socket,time,unittest
from ..queue_v1.shared import ROOT,REPO,load,pin,need,write_new,now

def main():
    p=argparse.ArgumentParser();p.add_argument('--context',type=pathlib.Path,required=True);a=p.parse_args();c=load(a.context)
    for ref in c['source_references']:need(pin(ref['path'])==ref,'EXACT_BOOTSTRAP_SOURCE')
    authority=load(c['resource_authority']['path']);need(pin(c['resource_authority']['path'])==c['resource_authority'],'EXACT_NEW_RESOURCE_AUTHORITY')
    jid=os.environ.get('SLURM_JOB_ID','');node=socket.gethostname().split('.')[0]
    need(os.getuid()==1278 and jid.isdecimal() and node==c['node'] and int(node.rsplit('-',1)[1]) in authority['allowed_nodes']['analysis'],'ACTUAL_OWN_ALLOWED_CPU_JOB')
    need(os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('CUDA_VISIBLE_DEVICES')=='','ACTUAL_CPU16_CPU_ONLY')
    need(authority['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and authority['memory_directives_allowed'] is False,'USER_NEW_MEMORY_POLICY')
    start=time.monotonic();rows=[]
    from ..queue_v1 import run_checks as legacy
    result=legacy.main();rows.append({'stage':'original_queue_recovery_retention_boundaries','expected_tests':22,'returncode':result,'receipt':pin(ROOT/'control/queue_checks'/(jid+'.json'))})
    ok=result==0
    if ok:
        module='workflows.data_v1_final.labels.source_status_v1.test_semantics';suite=unittest.defaultTestLoader.loadTestsFromName(module);need(suite.countTestCases()==8,'EXACT_EIGHT_SOURCE_STATUS_FIXTURES')
        tested=unittest.TextTestRunner(verbosity=2).run(suite)
        ok=tested.wasSuccessful() and tested.testsRun==8 and not tested.skipped
        rows.append({'stage':module,'expected_tests':8,'tests_run':tested.testsRun,'errors':len(tested.errors),'failures':len(tested.failures),'skips':len(tested.skipped)})
    out={'schema':'ACTUAL_CPU_AUTO_MEMORY_BOOTSTRAP_CHECKS_V1','status':'ALL30_SYNTHETIC_BOUNDARIES_PASSED' if ok else 'SYNTHETIC_BOUNDARY_FAILURE_NO_SCIENCE','job_id':jid,'node':node,'uid':os.getuid(),'context':pin(a.context),'resource_authority':c['resource_authority'],'memory_policy':authority['memory_policy'],'actual_memory_environment':{k:os.environ.get(k) for k in ('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU')},'actual_cpu_environment':os.environ.get('SLURM_CPUS_PER_TASK'),'stages':rows,'elapsed_seconds':time.monotonic()-start,'observed_at':now(),'no_scientific_records_read':True,'no_UFF_or_QM_calls':True,'new_auto_memory_adapter_tests_completed':False,'allocated_memory_gib_claimed':None,'forced_signals_sent':False}
    path=ROOT/'control/auto_mem_bootstrap'/(jid+'.json');write_new(path,out);print({'status':out['status'],'receipt':pin(path),'job_id':jid,'node':node,'memory_policy':out['memory_policy']})
    return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())