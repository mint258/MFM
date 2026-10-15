"""Tiny read-only schema/sidecar inspection; no QM, claims, or production access."""
import hashlib, importlib.util, json, os, socket, sys, time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
F=R/'gates/metadata_queue_production_shape/production_shape_r12_v2_20261012_run2_five_nodes'
C=R/'scripts/wp5_runner_v12_candidate_v2.py'
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-13'
assert (F/'signals/R12.bootstrap.ready').exists()
assert hashlib.sha256(C.read_bytes()).hexdigest()=='ef75862fc8b1a27bf19e6fd108b789a57540421a95a51e2121c1d2af290f2957'
spec=importlib.util.spec_from_file_location('metadata_candidate_readonly_probe',C)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.ROOT=F;m.STOP=F/'STOP_NEW_MOLECULES.json'
started=time.monotonic();q=m.Queue(F/'fixture.sqlite',deadline=started+30)
try:
    meta=q._meta();changes=q.db.total_changes;stats=dict(q.db.retry_stats)
    assert changes==0 and not q.db.in_transaction
    assert (int(meta['population_molecules']),int(meta['population_records']))==(1220466,11231854)
finally:q.db.close()
result={'schema':'WP5_R12_NODE13_READONLY_SCHEMA_PROBE_V1','status':'READONLY_SCHEMA_AND_SIDECAR_PASS',
    'time':time.time(),'uid':os.getuid(),'hostname':socket.gethostname(),'pid':os.getpid(),
    'mode':'Tiny read-only metadata inspection; not a Slurm load test',
    'fixture':str(F),'runner':{'path':str(C),'sha256':hashlib.sha256(C.read_bytes()).hexdigest()},
    'elapsed_seconds':time.monotonic()-started,'total_changes':changes,'retry_stats':stats,
    'QM_calls':0,'claims':0,'production_queue_opened':False,'node13_writer_load_test_performed':False}
(F/'node13_readonly_schema_probe.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'hostname':result['hostname'],'elapsed_seconds':result['elapsed_seconds'],'total_changes':changes}))
