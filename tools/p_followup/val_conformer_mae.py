"""D3 descriptive original-unit conformer-difference MAE on the frozen VAL subset."""
import argparse,fcntl,os,pickle,subprocess,sys,time
import numpy as np
import torch
from resources import REPO,R,CONTROL,OLD,load,save,guard
sys.path.insert(0,str(REPO/'tools/p_recipe'))
from checkpoint_paths import evaluation_checkpoint
from conformer_mae_math import paired_error
from phychem_mfm.phase1.p_recipe import selected_training_fields
from phychem_mfm.phase1.p_recipe_data import PRecipeDataset,original_predictions
from phychem_mfm.phase1.v2_s_training import s_model
from phychem_mfm.phase1.v31_training import V31PDModel
from phychem_mfm.phase1.v31_loader import encode_samples


def panel():
    # B3's closed identity mapping is reused; no new source identity scan.
    with (CONTROL/'B3_frozen_current_identities.pkl').open('rb') as stream:records=pickle.load(stream)['VAL']
    pairs=load(OLD/'pairs.json')['VAL']['conformer']
    return records,pairs


def predictions(c,records,device,expected_fields=99):
    checkpoint=evaluation_checkpoint(c,3000000)
    payload=torch.load(checkpoint,map_location='cpu',weights_only=True)
    if int(payload['clock']['samples_consumed'])!=3000000:raise ValueError('D3 requires the exact 3M endpoint')
    data=PRecipeDataset(c['root'],split='FULL',training_view=c['training_view'],normalizations=load(c['normalizations']),
        label_parameters=c.get('label_parameters'),conformer_decomposition=c.get('conformer_decomposition'),
        source='PM7',k=10,molecule_indices=sorted({r[3] for r in records}))
    structural,_=s_model('C1-0','three');structural.encoder.backbone.activation_checkpointing=False
    pd=V31PDModel(structural.encoder,data.view,forms=c['head_form'],pooling='registry',p_recipe=c['p_recipe'],conformer_decomposition=c.get('conformer_decomposition'))
    model=torch.nn.ModuleDict(dict(structural=structural,pd=pd));model.load_state_dict(payload['model'],strict=True)
    del payload;model.to(device).eval();fields=selected_training_fields(pd.registry,c['p_recipe'],c.get('fields'))
    if len(fields)!=expected_fields:raise ValueError('Conformer MAE must report all expected source training fields')
    allowed={int(mi):set(map(int,data.choices(int(mi)))) for mi in data.indices}
    output={};skipped=0
    usable=[r for r in records if r[4] in allowed[r[3]]];skipped=len(records)-len(usable)
    with torch.no_grad():
        for start in range(0,len(usable),32):
            rows=usable[start:start+32];samples=[data.read(mi,ci) for mid,rid,oldci,mi,ci in rows]
            batch,h=encode_samples(samples,pd.encoder,device=device)
            pred=pd.predict(samples,groups=('P',),fields=fields,clean_features=h,clean_batch=batch)
            restored=original_predictions(pd,pred,samples,data.label_parameters)
            if set(restored)!=set(fields):raise ValueError('Native reconstruction omitted training fields')
            pointers={name:0 for name in restored}
            for (mid,rid,oldci,mi,ci),sample_index in zip(rows,range(len(rows))):
                entries={}
                for name,value in restored.items():
                    target=samples[sample_index]['original_targets'][name]
                    a=pointers[name];b=a+target.raw.shape[0];pointers[name]=b
                    prediction=value[a:b].detach().cpu().double().numpy()
                    truth=target.raw.astype(np.float64);valid=target.valid.copy()
                    if prediction.shape!=truth.shape:raise ValueError((name,'prediction/native target shape differs'))
                    entries[name]=(prediction,truth,valid,None if target.pair_index is None else target.pair_index.copy())
                output[(mid,int(oldci))]=entries
            if any(pointers[n]!=len(restored[n]) for n in pointers):raise ValueError('Native prediction/sample boundaries differ')
            if start%1024==0:guard();print('D3_NATIVE_FORWARD',c['arm'],start,len(usable),flush=True)
    metadata={n:dict(unit=pd.definitions[n].get('unit','source_registry_unit'),level=pd.definitions[n]['level']) for n in restored}
    data.close();del model,pd,structural
    if device=='cuda':torch.cuda.empty_cache()
    return output,dict(checkpoint=str(checkpoint),samples=3000000,records=len(usable),records_outside_current_allowed_k10=skipped,fields=metadata)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--device',choices=['cpu','cuda'],default='cuda')
    parser.add_argument('--comparison',choices=['D','Dprime'],default='D');args=parser.parse_args()
    guard(force=True);torch.set_num_threads(2 if args.device=='cuda' else 16)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    lock=None
    if args.device=='cuda':
        gpu=os.environ['CUDA_VISIBLE_DEVICES'].split(',')[0]
        used,total=map(float,subprocess.check_output(['nvidia-smi','--id='+gpu,'--query-gpu=memory.used,memory.total','--format=csv,noheader,nounits'],text=True).strip().split(','))
        if used/total>.30:raise RuntimeError('GPU admission changed')
        lock=(R/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(gpu+'.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.comparison=='D':
        reference,candidate='C','D';reference_file='C_dedup.json';candidate_file='D_decomposition.json';expected_fields=99
    else:
        reference,candidate='M2','Dprime';reference_file='M2_reference.json';candidate_file='Dprime_M2_seed0_continued.json';expected_fields=109
    stem=args.comparison;started=time.monotonic();records,pairs=panel();results={};provenance={}
    for arm,file in [('C',reference_file),('D',candidate_file)]:
        results[arm],provenance[arm]=predictions(load(REPO/'configs/p_followup'/file),records,args.device,expected_fields)
    totals={};used_pairs=0;unavailable_pairs=0
    for pair in pairs:
        ka=(pair['molecule_id'],int(pair['a']));kb=(pair['molecule_id'],int(pair['b']))
        if not all(ka in results[a] and kb in results[a] for a in ['C','D']):unavailable_pairs+=1;continue
        used_pairs+=1
        names=results['C'][ka].keys() & results['D'][ka].keys() & results['C'][kb].keys() & results['D'][kb].keys()
        for name in names:
            ca,cb=results['C'][ka][name],results['C'][kb][name];da,db=results['D'][ka][name],results['D'][kb][name]
            errors=paired_error(ca,cb,da,db)
            if not errors['observations']:continue
            row=totals.setdefault(name,dict(C_absolute_error=0.,D_absolute_error=0.,observations=0,conformer_pairs=0,molecules=set()))
            for key,value in errors.items():row[key]+=value
            row['conformer_pairs']+=1;row['molecules'].add(pair['molecule_id'])
        guard()
    fields={}
    if set(provenance['C']['fields'])!=set(provenance['D']['fields']):raise ValueError('Compared field sets differ')
    for name,meta in sorted(provenance['C']['fields'].items()):
        row=totals.get(name,dict(observations=0,conformer_pairs=0,molecules=set()));n=row['observations']
        fields[name]={reference+'_MAE':row['C_absolute_error']/n if n else None,candidate+'_MAE':row['D_absolute_error']/n if n else None,
            candidate+'_minus_'+reference:(row['D_absolute_error']-row['C_absolute_error'])/n if n else None,
            'observations':n,'conformer_pairs':row['conformer_pairs'],'molecules':len(row['molecules']),**meta}
    result=dict(status='COMPLETE',scope=f'All {expected_fields} common {reference}/{candidate} P training fields, frozen VAL conformer pairs within current allowed k10; source atom order and directed pair endpoints preserved',
        raw_target='Current existing F32 labels promoted to F64; sidecar off in both arms',descriptive_only=True,seed=0,
        frozen_records=len(records),requested_pairs=len(pairs),used_pairs=used_pairs,unavailable_pairs=unavailable_pairs,
        provenance={reference:provenance['C'],candidate:provenance['D']},fields=fields,seconds=time.monotonic()-started)
    save(REPO/f'results/p_followup/{stem}_VAL_conformer_MAE.json',result)
    lines=[f'# {candidate}：VAL同分子构象差的原单位MAE','',
        f'复用既有冻结VAL子集及构象对，通过B3已完成的物理身份映射定位当前D6记录，只保留采样器实际允许k10的交集。使用{reference}/{candidate}各自seed0精确3M检查点及实际loader、预测还原路径，sidecar均关闭。参考差来自现存F32原始标签转F64；两臂共享原始标签、mask及有限预测交集。按现有存储字段报告全部{expected_fields}个共同P训练字段，保留loader已有的同MID原子顺序；稀疏原子对按有向端点交集对齐。MAE按两臂共同有效的分量加权，无有效分量的字段记NA。只作描述，不加显著性检验或采纳门槛。',
        '',f'冻结记录{len(records)}；既有构象对{len(pairs)}，实际使用{used_pairs}，不在当前允许交集的对{unavailable_pairs}。',
        '',f'|字段|单位|层级|有效分量|构象对|分子|{reference} MAE|{candidate} MAE|{candidate}−{reference}|','|---|---|---|---:|---:|---:|---:|---:|---:|']
    # Full precision stays in JSON; use compact values in the per-field report.
    def point(value):return 'NA' if value is None else f'{value:.8g}'
    for name,row in fields.items():
        cells=[name,row['unit'],row['level'],str(row['observations']),str(row['conformer_pairs']),str(row['molecules']),
               point(row[reference+'_MAE']),point(row[candidate+'_MAE']),point(row[candidate+'_minus_'+reference])]
        lines.append('|'+'|'.join(cells)+'|')
    lines+=['',f'表中数值按8位有效数字展示，全精度结果保留在results/p_followup/{stem}_VAL_conformer_MAE.json。']
    (REPO/f'docs/p_followup/{stem.upper()}_VAL_CONFORMER_MAE.md').write_text('\n'.join(lines)+'\n')
    print('D3_NATIVE_COMPLETE',args.comparison,used_pairs,len(fields),flush=True)
if __name__=='__main__':main()
