"""Fresh-main real spawn of the unchanged original scaffold function, no DATA."""
import concurrent.futures as cf,json,multiprocessing as mp,os,socket,time
from pathlib import Path
from .runtime import need,save,pin
from .context import bind_original_namespace,ensure_spawn_entrypoint


def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    need(os.getuid()==1278 and socket.gethostname().split('.')[0].startswith('compute-0-'),'SOURCE_FIXTURE_COMPUTE_NODE_ONLY')
    need(len(os.sched_getaffinity(0))>=16,'ACTUAL16_AVAILABLE_AFFINITY_CPUS')
    if os.environ.get('SLURM_JOB_ID'):need(int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16,'ACTUAL16_SLURM_CPUS')
    ref=dict(path='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/conformers/formal_cpu_auto_v3.json',bytes=3597,
      sha256='49567f12d439dc98697acec3c1034e2341c739781f6237d5959f59ddc32bef74')
    os.environ['EXPANSION_COMMON_ORIGINAL_CONFIG_REFERENCE']=json.dumps(ref,sort_keys=True)
    bind_original_namespace(ref)
    # This import has the same sys.path side effect as the actual producer.
    from workflows.data_v1_final.conformers.postprocess_day_v1 import common as Original
    from workflows.data_v1_final.conformers.formal_cpu_auto_finalize_mapping_v2 import finalize as Scientific
    need(Original.scaffold_chunk is Scientific.scaffold_chunk,'UNCHANGED_ORIGINAL_SCAFFOLD_FUNCTION_OBJECT')
    checkout=ensure_spawn_entrypoint();rows=[('synthetic_ethanol','CCO'),('synthetic_benzene','c1ccccc1')]
    expected=Original.scaffold_chunk(rows);began=time.monotonic()
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn')) as pool:
        values=list(pool.map(Original.scaffold_chunk,[rows]*32));pids=sorted(pool._processes)
    need(len(pids)==16 and len(values)==32 and all(v==expected for v in values),'FRESH_MAIN_ORIGINAL_STYLE_SPAWN_EXACT_REPLAY')
    return save(out/'receipt.json',dict(schema='EXPANSION_COMMON_FRESH_MAIN_SPAWN_SOURCE_FIXTURE_V1',status='PASS',
      actual_node=socket.gethostname(),actual_uid=os.getuid(),actual_job_id=os.environ.get('SLURM_JOB_ID'),
      actual_created_worker_pids=pids,workers=16,synthetic_tasks=32,original_function_source=pin(Scientific.__file__),
      standalone_checkout=checkout,elapsed_seconds=time.monotonic()-began,original_dataset_DATA_read=False,new_UFF_QM_calls=0))
