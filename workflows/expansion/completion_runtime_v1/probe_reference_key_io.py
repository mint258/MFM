"""Bounded seek-versus-memory probe of the same complete immutable key bytes."""
import hashlib,io,json,os,pathlib,random,socket,time
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
B=A/'control/pubchem_expansion_runtime_20261103'
def reference(p):
    raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def main():
    if os.getuid()!=1264 or socket.gethostname().split('.')[0]!='sonmi1' or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))!=16:raise ValueError('Actual Alpha idle CPU allocation only')
    plan_path=B/'node_epochs/main_rescue_resume_20261105_v1_low11_job_1885259/plan.json'
    plan=json.loads(plan_path.read_bytes());packed_ref=plan['reference_manifest'];packed_path=pathlib.Path(packed_ref['path'])
    if reference(packed_path)!=packed_ref:raise ValueError('Complete reference manifest changed')
    packed=json.loads(packed_path.read_bytes());key_ref=packed['keys'];path=pathlib.Path(key_ref['path'])
    began=time.perf_counter();payload=path.read_bytes();sequential=time.perf_counter()-began
    if len(payload)!=key_ref['bytes'] or hashlib.sha256(payload).hexdigest()!=key_ref['sha256'] or len(payload)!=28*1196122:raise ValueError('Whole complete key array differs')
    rng=random.Random(20261105);ordinals=[rng.randrange(1196122)for _ in range(1024)]
    def probe(stream):
        began=time.perf_counter();cpu=time.process_time();values=[]
        for ordinal in ordinals:
            stream.seek(ordinal*28);values.append(stream.read(28))
        return values,dict(wall_seconds=time.perf_counter()-began,process_CPU_seconds=time.process_time()-cpu)
    with path.open('rb')as f:disk,old=probe(f)
    with io.BytesIO(payload)as f:memory,new=probe(f)
    if disk!=memory or any(len(x)!=28 for x in disk):raise ValueError('Original ordered key bytes differ')
    value=dict(schema='PUBCHEM_REFERENCE_KEY_IO_PROBE_V1',actual=dict(endpoint='218.192.171.238:22',uid=os.getuid(),node=socket.gethostname(),job_id=os.environ['SLURM_JOB_ID'],allocated_CPUs=16),source_reference=reference(pathlib.Path(__file__)),reference_manifest=packed_ref,keys=key_ref,sample_size=len(ordinals),sequential_load_wall_seconds=sequential,file_seek=old,memory_seek=new,all_sample_ordered_bytes_equal=True,all_reference_bytes_whole_SHA_verified=True,no_NN_or_recipe_changes=True,full_pipeline_speed_not_measured=True)
    output=B/('reference_key_io_probe_job_'+os.environ['SLURM_JOB_ID']+'.json')
    with output.open('x')as f:json.dump(value,f,sort_keys=True);f.write('\n')
    print(json.dumps(value),flush=True)
if __name__=='__main__':main()