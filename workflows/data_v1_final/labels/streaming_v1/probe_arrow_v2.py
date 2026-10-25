"""Resource-only initializer probe; no real scientific labels are opened."""
from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import tempfile

from support import load,ref,require,save

DRIVER=None


def initialize(driver_path,cfg,plan,barrier,event):
    global DRIVER
    spec=importlib.util.spec_from_file_location("_arrow_probe_scan_v2",driver_path)
    DRIVER=importlib.util.module_from_spec(spec);spec.loader.exec_module(DRIVER)
    DRIVER.init_worker(cfg,plan,{"fields":[]},"/tmp",barrier,event,"profile",{}, {})


def probe_task(path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    DRIVER.WORK["barrier"].wait(timeout=120)
    table=pq.read_table(path,use_threads=True)
    return {"pid":os.getpid(),"arrow_cpu_threads":pa.cpu_count(),"arrow_io_threads":pa.io_thread_count(),
        "OS_threads_observed":len(list(Path("/proc/self/task").iterdir())),"fixture_rows":table.num_rows,
        "fixture_sum":sum(table.column(0).to_pylist()),"fixture_order_preserved":table.column(0).to_pylist()==list(range(128)),
        "OMP_NUM_THREADS":os.environ.get("OMP_NUM_THREADS"),
        "OPENBLAS_NUM_THREADS":os.environ.get("OPENBLAS_NUM_THREADS"),"MKL_NUM_THREADS":os.environ.get("MKL_NUM_THREADS")}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",required=True);p.add_argument("--baseline-config",required=True)
    p.add_argument("--driver");p.add_argument("--output",required=True)
    a=p.parse_args();cfg=load(a.config);base_cfg=load(a.baseline_config)
    driver=Path(a.driver or cfg["scan_driver"]["path"])
    actual=ref(driver)
    if any(actual[k]!=cfg["scan_driver"][k] for k in ("bytes","sha256")):
        raise ValueError("VARIANT_DRIVER_PIN_DIFFERS")
    baseline=driver.with_name("scan.py")
    insertion=b"    import pyarrow as pa\n    pa.set_cpu_count(1)\n    pa.set_io_thread_count(1)\n"
    raw=driver.read_bytes();old=baseline.read_bytes()
    if raw.count(insertion)!=1 or raw.replace(insertion,b"",1)!=old:
        raise ValueError("VARIANT_HAS_MORE_THAN_THE_DECLARED_ARROW_INITIALIZER_INSERTION")
    scientific={k:v for k,v in cfg.items() if k not in {"scan_driver","worker_arrow_limits"}}
    if scientific!=base_cfg or cfg["worker_arrow_limits"]!={"cpu":1,"io":1}:
        raise ValueError("VARIANT_CONFIG_SCIENTIFIC_PARAMETERS_CHANGED")
    if not os.environ.get("SLURM_JOB_ID") or int(os.environ.get("SLURM_CPUS_PER_TASK","0"))<16:
        raise ValueError("PROBE_REQUIRES_16_CPU_SLURM")
    import pyarrow as pa
    import pyarrow.parquet as pq
    context=multiprocessing.get_context("spawn");barrier=context.Barrier(16);event=context.Event()
    with tempfile.TemporaryDirectory(prefix="dv1_arrow_probe_") as directory:
        root=Path(directory)
        mapping=save(root/"field_map.json",[{"field_id":0}])
        fixture=root/"fixture.parquet";pq.write_table(pa.table({"ordinal":list(range(128))}),fixture,row_group_size=8)
        plan={"field_map":mapping}
        with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=initialize,
                initargs=(str(driver),cfg,plan,barrier,event)) as pool:
            rows=list(pool.map(probe_task,[str(fixture)]*16,chunksize=1))
    if len({r["pid"] for r in rows})!=16 or any(r["arrow_cpu_threads"]!=1 or r["arrow_io_threads"]!=1
            or r["fixture_rows"]!=128 or r["fixture_sum"]!=8128 or r["fixture_order_preserved"] is not True for r in rows):
        raise ValueError("ACTUAL_ARROW_WORKER_LIMIT_OR_PARQUET_READ_PROBE_FAILED")
    import numpy as np
    import duckdb
    save(a.output,{"status":"RESOURCE_ONLY_ARROW_V2_PROBE_PASS","job_id":os.environ["SLURM_JOB_ID"],
        "baseline_driver":ref(baseline),"variant_driver":actual,"baseline_config":ref(a.baseline_config),"variant_config":ref(a.config),
        "source_difference":"exactly three initializer lines; removal reproduces baseline bytes",
        "scientific_parameter_difference":False,"actual_workers":16,"workers":rows,
        "scientific_source_bodies_read":False,"full_scientific_tests_repeated":False,
        "dependency_versions":{"pyarrow":pa.__version__,"numpy":np.__version__,"duckdb":duckdb.__version__},
        "OS_thread_limit_claim":"Arrow CPU/IO pool sizes are verified; OS thread counts also include runtime/background threads"})
    print("RESOURCE_ONLY_ARROW_V2_PROBE_PASS",16)


if __name__=="__main__":main()
