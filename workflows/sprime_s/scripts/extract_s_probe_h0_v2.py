"""Extract frozen shared H0 from a real endpoint and common UFF geometries."""
import argparse,csv,fcntl,json,os,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--checkpoint-reference',required=True);ap.add_argument('--endpoint',required=True)
    ap.add_argument('--development',action='store_true');args=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-20','compute-0-21','compute-0-22']
    reference=json.loads(Path(args.checkpoint_reference).read_text());assert sha(reference['path'])==reference['sha256']
    assert args.endpoint=='DEV_native_2006' if args.development else args.endpoint in ['B1_seed0_e1','B1_seed1_e1','B3_seed0_e0p25','B3_seed0_e0p5','B3_seed0_e1','B3_seed0_e2','B3_seed0_e3']
    query=lambda options:subprocess.run(['nvidia-smi']+options,capture_output=True,text=True,check=True,timeout=20).stdout
    applications=list(csv.reader(query(['--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits']).splitlines()))
    occupied={r[0].strip() for r in applications};lock=None;selected=None
    directory=PROJECT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'
    for row in csv.reader(query(['--query-gpu=uuid,name,memory.total,memory.free','--format=csv,noheader,nounits']).splitlines()):
        if row[0].strip() in occupied or int(row[3])<.95*int(row[2]):continue
        trial=(directory/(row[0].strip()+'.lock')).open('a')
        try:fcntl.flock(trial,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:trial.close();continue
        selected=row;lock=trial;break
    assert selected is not None,'No currently available own-unlocked GPU'
    os.environ['CUDA_VISIBLE_DEVICES']=selected[0].strip()
    import numpy as np,torch,pyarrow as pa,pyarrow.parquet as pq
    from torch_geometric.data import Data
    from s_model_memory_v1 import build_memory_bounded_model
    torch.set_num_threads(16);torch.set_num_interop_threads(1);pa.set_cpu_count(1);pa.set_io_thread_count(1)
    condition='B1_seed0' if args.development else args.endpoint.split('_e',1)[0]
    config_path=ROOT/'configs/s_runner_development_v8.json' if args.development else ROOT/'formal_s'/(condition+'_v2.json')
    cfg=json.loads(config_path.read_text())
    payload=torch.load(reference['path'],map_location='cpu',weights_only=True)
    assert payload['development_only']==args.development and not payload['scientific_stop']
    if args.development:assert payload['consumed_records']==2006
    assert payload['config_sha256']==sha(config_path)
    model=build_memory_bounded_model(cfg['model']);model.load_state_dict(payload['model'],strict=True)
    for parameter in model.parameters():parameter.requires_grad_(False)
    def tensor_digest():
        import hashlib
        digest=hashlib.sha256()
        for key,value in sorted(model.state_dict().items()):
            digest.update(key.encode());digest.update(value.detach().cpu().contiguous().numpy().tobytes())
        return digest.hexdigest()
    before=tensor_digest();model=model.cuda().eval()
    folder=ROOT/'probe_h0_development'/os.environ['SLURM_JOB_ID'] if args.development else ROOT/'probe_h0_v1'/args.endpoint
    folder.mkdir(parents=True,exist_ok=False)
    summary={'status':'EXTRACTING_NOT_ACCEPTED','endpoint':args.endpoint,'job_id':os.environ['SLURM_JOB_ID'],
        'checkpoint_reference':reference,'gpu_uuid':selected[0].strip(),'gpu_model':selected[1].strip(),
        'gpu_protection':'USER_ACCEPTED_SHARED_GPU_RISK','development_only':args.development,'datasets':{}}
    try:
        for dataset in ['qm7','qm9','cyp_isoform','az_exactsom','expansionrx']:
            data_folder=ROOT/('probe_data_development_v3' if args.development else 'probe_data_v3')
            receipt=json.loads((data_folder/(dataset+'_receipt.json')).read_text())
            assert receipt['status']==('BOUNDED_DEVELOPMENT_ONLY' if args.development else 'DATASET_MEMBERS_AND_COMMON_UFF_GEOMETRY_CLOSED')
            if args.development:assert receipt['processed_members']<=16
            source=Path(receipt['output']['path']);assert sha(source)==receipt['output']['sha256']
            table=pq.read_table(source).sort_by('member_order');rows=table.to_pylist()
            assert len(rows)==receipt['processed_members'] and len({r['record_id'] for r in rows})==len(rows)
            level='atom' if dataset in ['cyp_isoform','az_exactsom'] else 'graph'
            schema=pa.schema([('record_id',pa.string()),('member_order',pa.int32()),('fold',pa.int8()),
                ('geometry_status',pa.string()),('h0',pa.list_(pa.float32())),('h0_rows',pa.int32()),('native_atoms',pa.int32()),
                ('targets',pa.list_(pa.float64())),('candidate_mask',pa.list_(pa.bool_())),('supervision_mask',pa.list_(pa.bool_()))])
            output=folder/(dataset+'.parquet');writer=pq.ParquetWriter(str(output)+'.pending',schema,compression='zstd')
            records=0;ready=0
            for offset in range(0,len(rows),32):
                group=rows[offset:offset+32];valid=[r for r in group if r['geometry_status']=='GEOMETRY_READY']
                features={}
                if valid:
                    counts=[len(r['atomic_numbers']) for r in valid];ptr=np.r_[0,np.cumsum(counts)]
                    batch=Data(x=torch.tensor([z-1 for r in valid for z in r['atomic_numbers']],dtype=torch.long,device='cuda'),
                        pos=torch.tensor(np.concatenate([np.asarray(r['coordinates']).reshape(-1,3) for r in valid]),dtype=torch.float32,device='cuda'),
                        batch=torch.tensor(np.repeat(np.arange(len(valid)),counts),dtype=torch.long,device='cuda'),
                        ptr=torch.tensor(ptr,dtype=torch.long,device='cuda'))
                    with torch.no_grad():h0=model.encode_atoms(batch)
                    assert h0.shape==(sum(counts),384) and torch.isfinite(h0).all()
                    for index,row in enumerate(valid):
                        value=h0[int(ptr[index]):int(ptr[index+1])]
                        if level=='graph':value=value.mean(0,keepdim=True)
                        features[row['record_id']]=value.cpu().numpy();ready+=1
                    del h0,batch
                output_rows=[]
                for row in group:
                    value=features.get(row['record_id']);output_rows.append({key:row[key] for key in ['record_id','member_order','fold','geometry_status','targets','candidate_mask','supervision_mask']}|
                        {'h0':None if value is None else value.ravel().tolist(),'h0_rows':0 if value is None else len(value),
                         'native_atoms':0 if row['atomic_numbers'] is None else len(row['atomic_numbers'])})
                writer.write_table(pa.Table.from_pylist(output_rows,schema=schema));records+=len(group)
            writer.close();Path(str(output)+'.pending').replace(output)
            assert records==len(rows)
            summary['datasets'][dataset]={'path':str(output),'sha256':sha(output),'members':records,'ready_members':ready,
                'output_level':level,'geometry_source_sha256':receipt['output']['sha256']}
            save(folder/'progress.json',summary)
        assert tensor_digest()==before,'FROZEN_ENCODER_STATE_CHANGED'
        summary.update(status='DEVELOPMENT_H0_NATIVE_INTERFACE_PASS' if args.development else 'ALL_FIVE_FROZEN_H0_DATASETS_CLOSED',encoder_state_sha256=before,
            extractor_sha256=sha(__file__),encoder_parameters_and_buffers_unchanged=True)
        save(folder/'receipt.json',summary);print(json.dumps(summary),flush=True)
    finally:lock.close()

if __name__=='__main__':main()
