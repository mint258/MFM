"""D2 actual64TRAIN head-only acceptance, then the sole registered D configuration."""
import collections,copy,json,pathlib,time
import numpy as np
import torch
from resources import REPO,CONTROL,MEAN,TRAIN,load,save,guard
from phychem_mfm.phase1.p_recipe_data import PRecipeDataset,dataset_configuration
from phychem_mfm.phase1.v2_s_training import s_model
from phychem_mfm.phase1.v31_loader import collate_samples
from phychem_mfm.phase1.v31_training import V31PDModel
from phychem_mfm.model.v3_heads import _pool


def branch_losses(prediction,target,valid):
    return [float((prediction[valid[:,i],i]-target[valid[:,i],i]).square().mean()) if valid[:,i].any() else None for i in range(2)]


def frozen_features(model,samples,names):
    output={};torch.set_num_threads(3)
    for route in sorted({model.routes[n] for n in names}):
        good=[i for i,s in enumerate(samples) if route==21 or (s['pos_perturbed'] is not None and np.isfinite(s['pos_perturbed']).all())]
        pooled={mode:torch.zeros((len(samples),512),dtype=torch.float32) for mode in ['mean','sum']}
        with torch.no_grad():
            for start in range(0,len(good),32):
                indices=good[start:start+32];working=[samples[i] for i in indices]
                if route==22:working=[dict(s,pos=s['pos_perturbed']) for s in working]
                batch=collate_samples(working);h=model.encoder.encode_atoms(batch)
                for mode in pooled:pooled[mode][indices]=_pool(h,batch.batch,len(indices),mode)
                guard()
        for name in names:
            if model.routes[name]==route:output[name]=pooled[model.head_by_name[name].pooling]
    return output


def main():
    started=time.monotonic();guard(force=True);torch.set_num_threads(1);torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    parameters=load(MEAN/'manifest.json')
    if parameters['status']!='D1_COMPLETE':raise ValueError('D1 mean table has not completed')
    initial=REPO/'configs/p_followup/D_parameters.json'
    if load(initial)['selected_fields']!=parameters['selected_fields']:raise ValueError('D1 parameter handoff differs')
    c=copy.deepcopy(load(REPO/'configs/p_followup/C_dedup.json'))
    for k in ['resume','resume_samples','resume_from_output','attempt','replaces_run','predecessor_samples','restart_reason','recovery_reason','handoff_request','handoff_ack','required_gpu_uuid']:c.pop(k,None)
    c.update(arm='D',run='p_followup_20261116_D_decomposition',output=str(TRAIN/'D_decomposition'))
    cfg=dict(c,conformer_decomposition=str(initial));data=PRecipeDataset(**dataset_configuration(cfg))
    rng=np.random.default_rng(20261025);samples=[data.sample(rng) for _ in range(64)]
    structural,_=s_model('C1-0','three');structural.encoder.backbone.activation_checkpointing=False
    pd=V31PDModel(structural.encoder,data.view,forms=c['head_form'],pooling='registry',p_recipe=c['p_recipe'],conformer_decomposition=str(initial))
    pd.encoder.eval()
    for parameter in pd.encoder.parameters():parameter.requires_grad_(False)
    names=list(parameters['selected_fields']);features=frozen_features(pd,samples,names)
    torch.set_num_threads(1);result={};accepted=[]
    for name in names:
        head=pd.heads.field_heads[pd.heads.keys[name]]
        target=torch.as_tensor(np.concatenate([s['targets'][name].values for s in samples]),dtype=torch.float32)
        valid=torch.as_tensor(np.concatenate([s['targets'][name].valid for s in samples]),dtype=torch.bool)
        x=features[name];assert x.shape==(64,512) and head.out_features==2
        with torch.no_grad():before=branch_losses(head(x),target,valid)
        calls=0
        optimizer=torch.optim.LBFGS(head.parameters(),lr=1.,max_iter=2000,max_eval=2000,
            tolerance_grad=1e-12,tolerance_change=1e-15,history_size=100,line_search_fn='strong_wolfe')
        def closure():
            nonlocal calls
            optimizer.zero_grad();prediction=head(x)
            loss=pd.loss({name:prediction},samples,groups=('P',),fields=(name,)).total
            loss.backward();calls+=1;return loss
        if all(v is not None for v in before):optimizer.step(closure)
        state=optimizer.state.get(next(iter(head.parameters())),{});iterations=int(state.get('n_iter',0))
        with torch.no_grad():after=branch_losses(head(x),target,valid)
        passed=all(a is not None and b is not None and (b<.01*a if a>0 else b==0) for a,b in zip(before,after))
        row=dict(initial_losses=before,final_losses=after,relative_losses=[b/a if a is not None and a>0 and b is not None else None for a,b in zip(before,after)],valid_counts=valid.sum(0).tolist(),optimizer_iterations=iterations,closure_calls=calls,passed=passed)
        if iterations>2000:raise ValueError('Head acceptance exceeded registered step budget')
        result[name]=row
        if passed:accepted.append(name)
        print('D2_HEAD',name,row,flush=True);guard()
    final=copy.deepcopy(parameters);final.update(status='D2_ACCEPTED',D0_selected_fields=names,selected_fields=accepted,
        D2_failed_fields=[n for n in names if n not in accepted],D2_test='actual64TRAIN,seed20261025,fresh seed0 encoder frozen,H1 outputs FP32,LBFGS<=2000 iterations per physical field; both branch losses<1%initial')
    destination=REPO/'configs/p_followup/D_parameters_accepted.json';save(destination,final)
    c['conformer_decomposition']=str(destination);assert not c.get('p_f64_sidecar')
    save(REPO/'configs/p_followup/D_decomposition.json',c)
    report=dict(status='COMPLETE',samples=64,selected_fields=names,accepted_fields=accepted,heads=result,
        identities=[dict(molecule_index=s['molecule_index'],conformer_index=s['conformer_index']) for s in samples],encoder_frozen=True,formal_training_reuses_test_weights=False,seconds=time.monotonic()-started)
    save(REPO/'results/p_followup/D2_head_overfit.json',report)
    lines=['# D：构象分解侧线','','状态：D1均值表与D2实际loader逐头验收完成；D3待seed0、3M训练和既定评价。','','用户已明确将此前路径/计数类型失败视为普通工程错误并要求完成D；原日志及历史处置保留，未作为科学阴性证据。','','## D1定义与生成','','从当前F32值转F64，减去M1实际元素参考（A1覆盖及其余原D4参考），在实际允许k10有效构象上计算每MID均值μ。全部D6 split均保存按MI对齐的F64μ、有效数与MID；只有剔除323重复分子后的TRAIN拟合c1=mean(μ)、s1=std(μ,ddof0)，s2为至少2有效构象MID中(y′−μ)的RMS，按有效构象数加权。未重拟合D4/A1，sidecar关闭。',
        '',f"TRAIN拟合{parameters['fit_train_molecules']}分子；生成器固定seed20261025抽1000MID，经实际PRecipeDataset.read逐构象重算μ，一次性检查容差1e-9+1e-9|μ|。完整检查结果见{MEAN/'manifest.json'}。",'',
        '|字段|多有效构象MID比例|s1|s2|10×F32差误差|D0入选|D2通过|','|---|---:|---:|---:|---:|---|---|']
    for name,f in parameters['fields'].items():lines.append(f"|{name}|{f['multi_valid_fraction']}|{f['s1']}|{f['s2']}|{10*f['median_F32_difference_error']}|{f['selected']}|{name in accepted}|")
    lines+=['','入选阈值固定为：多有效构象MID比例≥0.5、s2≥1e-3s1、s2≥10e；零/未定义s1不分解。D2失败字段保留C定义。','','## D2目标、头与真实使用验收','','t1=(μ−c1)/s1；t2=(y′−μ)/s2，只有一个有效构象时t2无效。H1在同一个registry pooled向量输出两个数；每字段loss固定½(MSEt1+MSEt2)，保留原字段总权重和其余Huber/向量loss，99源字段/87物理损失项口径不变。原单位还原为元素参考+c1+s1t1+s2t2，保留original_targets用于MAE。',
        '', '实际loader均匀抽取固定64TRAIN样本，只优化双输出H1，fresh seed0编码器冻结；每字段最多2000个LBFGS迭代，两分支loss分别低于初值1%才通过。该测试的权重不用于正式训练。分解还原、单构象mask、头维度及字段权重/梯度单测已通过。',
        '', '|字段|初始t1/t2 loss|最终t1/t2 loss|相对loss|迭代|通过|','|---|---|---|---|---:|---|']
    for name,r in result.items():lines.append(f"|{name}|{r['initial_losses']}|{r['final_losses']}|{r['relative_losses']}|{r['optimizer_iterations']}|{r['passed']}|")
    lines+=['','D配置仅在C基底上增加conformer_decomposition及运行标识/路径；实际选中字段和参数见D_parameters_accepted.json。后续仅seed0、3M；R3配对95%CI判定D−C，补充D−M1，报告VAL同MID构象差MAE和A-H6；不接入主线。']
    (REPO/'docs/p_followup/D_CONFORMER_DECOMPOSITION.md').write_text('\n'.join(lines)+'\n')
    data.close();print('D2_READY',accepted,flush=True)
if __name__=='__main__':main()