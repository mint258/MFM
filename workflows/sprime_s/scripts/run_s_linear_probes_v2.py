"""Stage59 partitions: four scaffold datasets plus one official Expansion split."""
import argparse,csv,hashlib,json,multiprocessing as mp,os,time
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
from prepare import ROOT,save,sha

DATASETS=['qm7','qm9','cyp_isoform','az_exactsom','expansionrx']
TASKS={'qm7':['target_atomization_energy'],'qm9':['A','B','C','mu','alpha','homo','lumo','gap','r2','zpve','U0','U','H','G','Cv'],
 'cyp_isoform':['1A2','2A6','2B6','2C19','2C8','2C9','2D6','2E1','3A4'],'az_exactsom':['exact_som'],
 'expansionrx':['LogD','LogS','Log_HLM_CLint','Log_MLM_CLint','Log_Caco_Papp_AB','Log_Caco_ER','Log_Mouse_PPB','Log_Mouse_BPB','Log_Mouse_MPB']}

def init_probe_worker():
    import torch,pyarrow as pa
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    pa.set_cpu_count(1);pa.set_io_thread_count(1)

def partition_roles(rows,request):
    if request.get('development_roles') is not None:
        assert request.get('scope')=='DEVELOPMENT_TRAIN_ONLY_ROLE_FIXTURE'
        roles=request['development_roles'];assert set(roles)=={row['record_id'] for row in rows}
        assert all(value in ['train','test'] for value in roles.values())
        return roles,'development private train-source-only role fixture'
    if request['dataset']!='expansionrx':
        fold=request['fold']
        return {row['record_id']:('test' if row['fold']==fold else 'validation' if row['fold']==(fold+1)%10 else 'train') for row in rows},'original ten scaffold rotations'
    assert request['fold']==0
    policy=json.loads((ROOT/'configs/s_probe_protocol_v2.json').read_text())
    roles={}
    for ref in policy['expansion_official_sources']:
        assert sha(ref['path'])==ref['sha256']
        with Path(ref['path']).open(newline='') as stream:
            count=sum(1 for _ in csv.DictReader(stream))
        assert count==ref['rows']
        roles.update({'expansionrx:'+Path(ref['path']).name+':'+str(i):ref['role'] for i in range(1,count+1)})
    assert set(roles)=={row['record_id'] for row in rows},'Official native membership differs'
    return roles,'Stage59 original log_train_data.csv / official_test.csv; no extra inner split'

def fit_cell(request):
    import numpy as np,torch,pyarrow as pa,pyarrow.parquet as pq
    from phychem_mfm.model.common import Linear
    dataset=request['dataset'];fold=request['fold'];tasks=TASKS[dataset];dimension=len(tasks)
    atom=dataset in ['cyp_isoform','az_exactsom'];rows=pq.read_table(request['path']).sort_by('member_order').to_pylist()
    assert len({r['record_id'] for r in rows})==len(rows)
    features=[];targets=[];masks=[]
    for row in rows:
        if row['h0'] is None:features.append(None);targets.append(None);masks.append(None);continue
        x=np.array(row['h0'],dtype=np.float32).reshape(row['h0_rows'],384)
        y=np.array(row['targets'],dtype=np.float64).reshape(row['h0_rows'],dimension)
        mask=np.array(row['supervision_mask'],dtype=bool).reshape(row['h0_rows'],dimension)
        mask&=np.array(row['candidate_mask'],dtype=bool).reshape(row['h0_rows'],dimension)&np.isfinite(y)
        assert np.isfinite(x).all()
        features.append(x);targets.append(y);masks.append(mask)
    roles,partition_recipe=partition_roles(rows,request)
    train=[i for i,r in enumerate(rows) if roles[r['record_id']]=='train' and features[i] is not None and masks[i].any()]
    test=[i for i,r in enumerate(rows) if roles[r['record_id']]=='test' and features[i] is not None]
    validation=[i for i,r in enumerate(rows) if roles[r['record_id']]=='validation' and features[i] is not None]
    assert not set(train)&set(test) and not set(train)&set(validation)
    means=np.zeros(dimension);scales=np.ones(dimension);available=np.zeros(dimension,dtype=bool)
    for task in range(dimension):
        observed=[targets[i][:,task][masks[i][:,task]] for i in train]
        values=np.concatenate(observed) if observed else np.empty(0)
        available[task]=len(values)>0
        if len(values) and not atom:
            means[task]=values.mean();scales[task]=values.std(ddof=0)
            if scales[task]==0:scales[task]=1.
    torch.manual_seed(0);head=Linear(384,dimension,bias=True)
    optimizer=torch.optim.AdamW(head.parameters(),lr=.001,betas=(.9,.999),eps=1e-8,weight_decay=.01,amsgrad=False,foreach=False,fused=False)
    # One fixed train-only permutation, paired across all seven encoder endpoints.
    order=np.random.default_rng(fold).permutation(train).tolist();history=[];updates=0
    for epoch in range(20):
        leaf_sum=np.zeros(dimension);counts=np.zeros(dimension,dtype=np.int64)
        for offset in range(0,len(order),32):
            ids=order[offset:offset+32]
            x=torch.from_numpy(np.concatenate([features[i] for i in ids]))
            y64=np.concatenate([targets[i] for i in ids]);mask_np=np.concatenate([masks[i] for i in ids])&available
            mask=torch.from_numpy(mask_np);values=np.where(mask_np,(y64-means)/scales,0.).astype(np.float32)
            y=torch.from_numpy(values);pred=head(x)
            residual=torch.nn.functional.binary_cross_entropy_with_logits(pred,y,reduction='none') if atom else (pred-y).square()
            count=mask.sum(0);leaf=(residual*mask).sum(0)/count.clamp_min(1)
            loss=leaf.sum()/dimension;assert torch.isfinite(loss)
            optimizer.zero_grad(set_to_none=True);loss.backward()
            assert all(torch.isfinite(p.grad).all() for p in head.parameters())
            optimizer.step();updates+=1
            leaf_sum+=(residual.detach().numpy()*mask_np).sum(0);counts+=mask_np.sum(0)
        history.append({'epoch':epoch+1,'raw_normalized_leaf_loss':[float(leaf_sum[t]/counts[t]) if counts[t] else None for t in range(dimension)],
                        'label_counts':counts.tolist(),'optimizer_updates':updates})
    def evaluate(indices):
        score_hash=hashlib.sha256();membership_hash=hashlib.sha256()
        sums=np.zeros(dimension);squares=np.zeros(dimension);counts=np.zeros(dimension,dtype=np.int64)
        eligible=np.zeros(dimension,dtype=np.int64);hits=np.zeros(dimension,dtype=np.int64)
        unknown=np.zeros(dimension,dtype=np.int64);no_positive=np.zeros(dimension,dtype=np.int64)
        with torch.no_grad():
            for i in indices:
                raw_score=head(torch.from_numpy(features[i])).numpy().astype(np.float32)
                score=raw_score.astype(np.float64)
                identity=rows[i]['record_id'].encode();membership_hash.update(len(identity).to_bytes(8,'little'));membership_hash.update(identity)
                membership_hash.update(masks[i].tobytes());score_hash.update(identity);score_hash.update(raw_score.tobytes())
                if atom:
                    for task in range(dimension):
                        if not available[task]:continue
                        candidate=np.array(rows[i]['candidate_mask'],dtype=bool).reshape(len(score),dimension)[:,task]
                        valid=masks[i][:,task];ids=np.flatnonzero(candidate)
                        if not len(ids) or not valid[ids].all():unknown[task]+=1;continue
                        truth=targets[i][:,task]
                        if not np.any(truth[ids]==1):no_positive[task]+=1;continue
                        ranked=ids[np.lexsort((ids,-score[ids,task]))];eligible[task]+=1;hits[task]+=int(truth[ranked[0]]==1)
                else:
                    prediction=score*scales+means
                    valid=masks[i]&available;error=prediction-targets[i]
                    sums+=np.where(valid,np.abs(error),0.).sum(0)
                    squares+=np.where(valid,error*error,0.).sum(0);counts+=valid.sum(0)
        output=[]
        for task,name in enumerate(tasks):
            if not available[task]:metric=None;status='NO_TRAIN_LABELS'
            elif atom:metric=float(hits[task]/eligible[task]) if eligible[task] else None;status='OK' if eligible[task] else 'NO_EVALUABLE_INSTANCES'
            else:metric=float(sums[task]/counts[task]) if counts[task] else None;status='OK' if counts[task] else 'NO_VALID_LABELS'
            output.append({'task':name,'status':status,'primary_metric':metric,'metric_name':'molecule_hit_at_1' if atom else 'MAE',
                'label_count':int(counts[task]),'absolute_error_sum':float(sums[task]),'squared_error_sum':float(squares[task]),
                'RMSE':float(np.sqrt(squares[task]/counts[task])) if counts[task] else None,
                'eligible_instances':int(eligible[task]),'hits':int(hits[task]),'unknown_or_partial':int(unknown[task]),'no_positive':int(no_positive[task])})
        return {'tasks':output,'actual_score_float32_sha256':score_hash.hexdigest(),
                'ordered_record_ids_and_label_masks_sha256':membership_hash.hexdigest(),'records':len(indices)}
    return {'dataset':dataset,'fold':fold,'partition_recipe':partition_recipe,
        'ordered_role_membership_sha256':hashlib.sha256(json.dumps([[row['record_id'],roles[row['record_id']]] for row in rows],separators=(',',':')).encode()).hexdigest(),
        'train_inventory_records':sum(value=='train' for value in roles.values()),'test_inventory_records':sum(value=='test' for value in roles.values()),
        'train_records':len(train),'test_geometry_ready_records':len(test),
        'validation_geometry_ready_records':len(validation),'optimizer_updates':updates,'epochs':20,
        'normalizers':{'means':means.tolist(),'scales':scales.tolist(),'train_label_available':available.tolist(),'fit_scope':'train_only'},
        'fixed_train_order_member_indices':order,
        'fixed_train_order_int32_sha256':hashlib.sha256(np.asarray(order,dtype='<i4').tobytes()).hexdigest(),
        'train_history':history,'test':evaluate(test),'validation':evaluate(validation),
        'readout_weight':head.weight.detach().tolist(),'readout_bias':head.bias.detach().tolist(),
        'feature_source_sha256':request['sha256'],'encoder_trained':False,'readout':'H0 linear, no hidden activation',
        'test_targets_used_for_model_or_endpoint_selection':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--endpoint',required=True);args=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    policy=json.loads((ROOT/'configs/s_probe_protocol_v2.json').read_text())
    assert policy['status']=='STAGE59_DOWNSTREAM_PARTITIONS_AND_PRIMARY_FAMILY_PRESERVED'
    assert sha(policy['frozen_protocol']['path'])==policy['frozen_protocol']['sha256']
    folder=ROOT/'probe_h0_v1'/args.endpoint;receipt=json.loads((folder/'receipt.json').read_text())
    assert receipt['status']=='ALL_FIVE_FROZEN_H0_DATASETS_CLOSED'
    requests=[]
    for dataset in DATASETS:
        ref=receipt['datasets'][dataset];assert sha(ref['path'])==ref['sha256']
        requests.extend({'dataset':dataset,'fold':fold,'path':ref['path'],'sha256':ref['sha256']} for fold in (range(1) if dataset=='expansionrx' else range(10)))
    import wandb
    output=ROOT/'probe_results_v2'/args.endpoint;output.mkdir(parents=True,exist_ok=False)
    tracking=wandb.init(project='phychem-mfm-phase1',mode='offline',dir=str(output),group='S_convergence_linear_probes',name=args.endpoint,
        config={'endpoint':args.endpoint,'encoder_checkpoint':receipt['checkpoint_reference'],'source_sha256':sha(__file__),
                'readout':'linear','epochs':20,'scaffold_folds':list(range(10)),'expansion_split':'original official train/test',
                'readout_seed':0,'geometry':'ETKDGv3+UFF','probe_protocol_sha256':sha(ROOT/'configs/s_probe_protocol_v2.json')})
    results=[];started=time.monotonic();step=0
    with ProcessPoolExecutor(int(os.environ['SLURM_CPUS_PER_TASK'])-1,mp_context=mp.get_context('spawn'),initializer=init_probe_worker) as pool:
        futures=[pool.submit(fit_cell,request) for request in requests]
        for future in as_completed(futures):
            result=future.result();results.append(result)
            for epoch in result['train_history']:
                tracking.log({'dataset':result['dataset'],'fold':result['fold'],**epoch},step=step,commit=True);step+=1
    assert len(results)==41 and len({(r['dataset'],r['fold']) for r in results})==41
    aggregate=[]
    for dataset in DATASETS:
        cells=sorted([r for r in results if r['dataset']==dataset],key=lambda r:r['fold'])
        for index,task in enumerate(TASKS[dataset]):
            values=[cell['test']['tasks'][index]['primary_metric'] for cell in cells]
            aggregate.append({'dataset':dataset,'task':task,'metric_name':cells[0]['test']['tasks'][index]['metric_name'],
                'primary_metric':sum(values)/len(values) if all(v is not None for v in values) else None,
                'status':('OFFICIAL_TEST_CELL_CLOSED' if dataset=='expansionrx' else 'ALL_TEN_SCAFFOLD_CELLS_CLOSED') if all(v is not None for v in values) else 'UNAVAILABLE_CELL_REPORTED',
                'included_in_primary_judgment':dataset+'.'+task not in policy['primary_family_exclusions'],
                'fold_metrics':values,'aggregation':'one original official test cell' if dataset=='expansionrx' else 'fixed equal weight0.1 per original scaffold rotation'})
    tracking.log({'closed_cells':41,'closed_tasks':len(aggregate)},step=step,commit=True);tracking.finish()
    result={'status':'ALL_FORTY_ONE_FROZEN_LINEAR_PROBE_CELLS_CLOSED','endpoint':args.endpoint,'job_id':os.environ['SLURM_JOB_ID'],
        'encoder_checkpoint':receipt['checkpoint_reference'],'feature_receipt_sha256':sha(folder/'receipt.json'),
        'source_sha256':sha(__file__),'cells':sorted(results,key=lambda r:(r['dataset'],r['fold'])),'aggregate':aggregate,
        'tracking_run_id':tracking.id,'tracking_mode':'offline','elapsed_seconds':time.monotonic()-started,
        'no_pretraining_population_overlap_records_deleted':True,'probe_protocol_sha256':sha(ROOT/'configs/s_probe_protocol_v2.json'),
        'primary_tasks':32,'all_reported_tasks':35,'expansion_official_test_rows_used_for_training':False}
    save(output/'receipt.json',result);print(json.dumps({'status':result['status'],'endpoint':args.endpoint,'cells':41}),flush=True)

if __name__=='__main__':main()
