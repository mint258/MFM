"""D3 descriptive original-unit conformer-difference MAE on the frozen VAL subset."""
import argparse,fcntl,os,pickle,subprocess,sys,time
import numpy as np
import torch
from resources import REPO,R,CONTROL,OLD,load,save,guard
sys.path.insert(0,str(REPO/'tools/p_recipe'))
from checkpoint_paths import evaluation_checkpoint
from phychem_mfm.phase1.p_recipe_data import PRecipeDataset,original_predictions
from phychem_mfm.phase1.v2_s_training import s_model
from phychem_mfm.phase1.v31_training import V31PDModel
from phychem_mfm.phase1.v31_loader import encode_samples


def panel():
    # B3's closed identity mapping is reused; no new source identity scan.
    with (CONTROL/'B3_frozen_current_identities.pkl').open('rb') as stream:records=pickle.load(stream)['VAL']
    pairs=load(OLD/'pairs.json')['VAL']['conformer']
    return records,pairs


def predictions(c,records,device):
    checkpoint=evaluation_checkpoint(c,3000000)
    payload=torch.load(checkpoint,map_location='cpu',weights_only=True)
    if int(payload['clock']['samples_consumed'])!=3000000:raise ValueError('D3 requires the exact 3M endpoint')
    data=PRecipeDataset(c['root'],split='FULL',training_view=c['training_view'],normalizations=load(c['normalizations']),
        label_parameters=c.get('label_parameters'),conformer_decomposition=c.get('conformer_decomposition'),
        source='PM7',k=10,molecule_indices=sorted({r[3] for r in records}))
    structural,_=s_model('C1-0','three');structural.encoder.backbone.activation_checkpointing=False
    pd=V31PDModel(structural.encoder,data.view,forms=c['head_form'],pooling='registry',p_recipe=c['p_recipe'],conformer_decomposition=c.get('conformer_decomposition'))
    model=torch.nn.ModuleDict(dict(structural=structural,pd=pd));model.load_state_dict(payload['model'],strict=True)
    del payload;model.to(device).eval();fields=load(REPO/'configs/p_followup/D_parameters_accepted.json')['candidate_fields']
    allowed={int(mi):set(map(int,data.choices(int(mi)))) for mi in data.indices}
    output={};skipped=0
    usable=[r for r in records if r[4] in allowed[r[3]]];skipped=len(records)-len(usable)
    with torch.no_grad():
        for start in range(0,len(usable),32):
            rows=usable[start:start+32];samples=[data.read(mi,ci) for mid,rid,oldci,mi,ci in rows]
            batch,h=encode_samples(samples,pd.encoder,device=device)
            pred=pd.predict(samples,groups=('P',),fields=fields,clean_features=h,clean_batch=batch)
            restored=original_predictions(pd,pred,samples,data.label_parameters)
            for (mid,rid,oldci,mi,ci),sample_index in zip(rows,range(len(rows))):
                entries={}
                for name,value in restored.items():
                    target=samples[sample_index]['original_targets'][name]
                    a,b=(int(batch.ptr[sample_index]),int(batch.ptr[sample_index+1])) if target.level=='atom' else (sample_index,sample_index+1)
                    prediction=value[a:b].detach().cpu().double().numpy()
                    truth=target.raw.astype(np.float64);valid=target.valid.copy()
                    if prediction.shape!=truth.shape:raise ValueError((name,'prediction/native target shape differs'))
                    entries[name]=(prediction,truth,valid)
                output[(mid,int(oldci))]=entries
            if start%1024==0:guard();print('D3_NATIVE_FORWARD',c['arm'],start,len(usable),flush=True)
    metadata={n:dict(unit=pd.definitions[n].get('unit','source_registry_unit'),level=pd.definitions[n]['level']) for n in restored}
    data.close();del model,pd,structural
    if device=='cuda':torch.cuda.empty_cache()
    return output,dict(checkpoint=str(checkpoint),samples=3000000,records=len(usable),records_outside_current_allowed_k10=skipped,fields=metadata)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--device',choices=['cpu','cuda'],default='cuda');args=parser.parse_args()
    guard(force=True);torch.set_num_threads(2 if args.device=='cuda' else 16)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    lock=None
    if args.device=='cuda':
        gpu=os.environ['CUDA_VISIBLE_DEVICES'].split(',')[0]
        used,total=map(float,subprocess.check_output(['nvidia-smi','--id='+gpu,'--query-gpu=memory.used,memory.total','--format=csv,noheader,nounits'],text=True).strip().split(','))
        if used/total>.30:raise RuntimeError('GPU admission changed')
        lock=(R/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(gpu+'.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    started=time.monotonic();records,pairs=panel();results={};provenance={}
    for arm,file in [('C','C_dedup.json'),('D','D_decomposition.json')]:
        results[arm],provenance[arm]=predictions(load(REPO/'configs/p_followup'/file),records,args.device)
    totals={};used_pairs=0;unavailable_pairs=0
    for pair in pairs:
        ka=(pair['molecule_id'],int(pair['a']));kb=(pair['molecule_id'],int(pair['b']))
        if not all(ka in results[a] and kb in results[a] for a in ['C','D']):unavailable_pairs+=1;continue
        used_pairs+=1
        names=results['C'][ka].keys() & results['D'][ka].keys() & results['C'][kb].keys() & results['D'][kb].keys()
        for name in names:
            ca,cb=results['C'][ka][name],results['C'][kb][name];da,db=results['D'][ka][name],results['D'][kb][name]
            if ca[1].shape!=cb[1].shape:raise ValueError((name,'same-MID target order/shape differs'))
            # Original physical labels and masks must be shared between the paired arms.
            if not all(np.array_equal(c[i],d[i],equal_nan=True) for c,d in [(ca,da),(cb,db)] for i in [1,2]):raise ValueError((name,'C/D original targets differ'))
            valid=ca[2]&cb[2]&np.isfinite(ca[1])&np.isfinite(cb[1])
            valid=valid&np.isfinite(ca[0])&np.isfinite(cb[0])&np.isfinite(da[0])&np.isfinite(db[0])
            if not valid.any():continue
            reference=ca[1]-cb[1];row=totals.setdefault(name,dict(C_absolute_error=0.,D_absolute_error=0.,observations=0,conformer_pairs=0,molecules=set()))
            for arm,a,b in [('C',ca,cb),('D',da,db)]:row[arm+'_absolute_error']+=float(np.abs((a[0]-b[0]-reference)[valid]).sum())
            row['observations']+=int(valid.sum());row['conformer_pairs']+=1;row['molecules'].add(pair['molecule_id'])
        guard()
    fields={}
    for name,row in sorted(totals.items()):
        n=row['observations'];fields[name]=dict(C_MAE=row['C_absolute_error']/n,D_MAE=row['D_absolute_error']/n,
            D_minus_C=(row['D_absolute_error']-row['C_absolute_error'])/n,observations=n,conformer_pairs=row['conformer_pairs'],molecules=len(row['molecules']),**provenance['C']['fields'][name])
    result=dict(status='COMPLETE',scope='All33 C molecular scalar candidates, frozen VAL conformer pairs within current allowed k10',
        raw_target='Current existing F32 labels promoted to F64; sidecar off in both arms',descriptive_only=True,
        frozen_records=len(records),requested_pairs=len(pairs),used_pairs=used_pairs,unavailable_pairs=unavailable_pairs,
        provenance=provenance,fields=fields,seconds=time.monotonic()-started)
    save(REPO/'results/p_followup/D_VAL_conformer_MAE.json',result)
    lines=['# D3：VAL同分子构象差的原单位MAE','','复用既有冻结VAL子集及构象对，通过B3已完成的物理身份映射定位当前D6记录，只保留采样器实际允许k10的交集。使用C/D各自精确3M检查点及实际loader、预测还原路径，sidecar均关闭。参考差来自现存F32原始标签转F64；两臂共享原始标签、mask及有限预测交集。按字段报告D1候选的全部33个C分子级标量（含入选与未入选字段），MAE按有效构象对加权。只作描述，不加显著性检验或采纳门槛。',
        '',f'冻结记录{len(records)}；既有构象对{len(pairs)}，实际使用{used_pairs}，不在当前允许交集的对{unavailable_pairs}。',
        '','|字段|单位|层级|有效分量|构象对|分子|C MAE|D MAE|D−C|','|---|---|---|---:|---:|---:|---:|---:|---:|']
    for name,row in fields.items():lines.append(f"|{name}|{row['unit']}|{row['level']}|{row['observations']}|{row['conformer_pairs']}|{row['molecules']}|{row['C_MAE']:.8g}|{row['D_MAE']:.8g}|{row['D_minus_C']:.8g}|")
    (REPO/'docs/p_followup/D_VAL_CONFORMER_MAE.md').write_text('\n'.join(lines)+'\n')
    print('D3_NATIVE_COMPLETE',used_pairs,len(fields),flush=True)
if __name__=='__main__':main()
