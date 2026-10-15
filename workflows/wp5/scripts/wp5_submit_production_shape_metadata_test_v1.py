"""Root-only submission of a single owned production-shaped METADATA fixture."""
import ast, hashlib, json, os, socket, subprocess, time
from pathlib import Path
from wp5_submit_formal_v11 import atomic, digest
R=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
F=R/'gates/metadata_queue_production_shape/production_shape_r12_v2_20261012_run1'
S=R/'scripts/wp5_queue_production_shape_v1.sbatch'
H=R/'scripts/wp5_queue_production_shape_v1.py'
C=R/'scripts/wp5_runner_v12_candidate_v2.py'
W={f'compute-0-{n}':c for n,c in ((12,80),(13,16),(14,64),(17,168),(18,64),(19,104))}
OUT=R/'submission/production_shape_r12_v2_test_v1'
def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    assert digest(H)=='13b8cf1ffe57701824f4f787a96b38e515e17bbd1d323134ed9398c7cbb19c67'
    assert digest(S)=='04699865fe4a72cdb62cc9ced971f0677e12d167153987e84dc906dbb2193a9b'
    assert digest(C)=='ef75862fc8b1a27bf19e6fd108b789a57540421a95a51e2121c1d2af290f2957'
    ast.parse(H.read_text());ast.parse(C.read_text())
    p=subprocess.run(['bash','-n',str(S)],stdin=subprocess.DEVNULL,capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    OUT.mkdir(exist_ok=False)
    result={'schema':'WP5_PRODUCTION_SHAPE_METADATA_TEST_SUBMISSION_V1','status':'SUBMITTING',
        'start':time.time(),'fixture':str(F),'writers_by_node':W,'actual_planned_writers':sum(W.values()),
        'sources':[{'path':str(p),'sha256':digest(p)} for p in (S,H,C)],
        'production_writes':False,'QM':False,'scientific_attempts':False,'jobs':[],'error':None}
    target=OUT/'submitted_jobs.json';atomic(target,result)
    env=dict(os.environ,WP5_METADATA_FIXTURE=str(F),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    def submit(role,node,cpus,mem,dependency=None,extra=()):
        environment=dict(env,WP5_METADATA_MODE=role)
        name='wp5_shape_r12v2_'+role+'_'+node.rsplit('-',1)[1]
        command=[PY,'-B',str(R/'scripts/submit_wp5_job_v2.py'),'--script',str(S),'--name',name,'--node',node,
            '--cpus',str(cpus),'--memory-gb',str(mem),'--time','00:20:00','--kind','resource','--allow-pending']
        if dependency:command+=['--dependency',dependency]
        command+=list(extra)
        p=subprocess.run(command,env=environment,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
        if p.returncode:raise RuntimeError(name+':'+p.stderr)
        receipt=json.loads(p.stdout);row={**receipt,'role':role,'cpus':cpus,'memory_gib':mem,'dependency':dependency,'extra':list(extra)}
        result['jobs'].append(row);atomic(target,result);print(json.dumps(row),flush=True);return row['job_id']
    try:
        init=submit('backup','compute-0-12',16,32,extra=['--writers-json',json.dumps(W,separators=(',',':'))])
        ids=[]
        for node,cpus in W.items():
            ids.append(submit('node',node,cpus,96 if cpus>128 else 64,'afterok:'+init,
                extra=['--runner12',str(C),'--workers',str(cpus),'--total-seconds','1000']))
        submit('verify','compute-0-12',16,32,'afterany:'+':'.join(ids))
        result.update(status='ALL_BACKUP_SIX_NODES_AND_VERIFY_SUBMITTED',end=time.time());atomic(target,result)
    except BaseException as error:
        result.update(status='PARTIAL_METADATA_TEST_SUBMISSION',error=repr(error));atomic(target,result);raise
if __name__=='__main__':main()
