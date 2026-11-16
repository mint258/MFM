"""Work A: frozen5000VAL, specified checkpoints only, no model training."""
import argparse,csv,fcntl,json,os,pathlib,sys,time,subprocess,traceback,gc
import numpy as np
import torch
from resources import REPO,R,CONTROL,OLD,load,save,guard
from composition_statistics import folds,ridge_oof,bootstrap_weights,cev_values,cvf_values,eev_values,summary,total_ss,conformer_moments,ratio
sys.path.insert(0,str(REPO/'tools/p_recipe'))
from diagnose import validation_indices,load_representation_encoder,representation_layers
from checkpoint_paths import evaluation_checkpoint
from phychem_mfm.phase1.v31_loader import MFM4Dataset,collate_samples
from phychem_mfm.phase1.p_recipe_data import PRecipeDataset
from phychem_mfm.phase1.v2_s_training import s_model

RESULTS=REPO/'results/p_followup/A_collapse_composition'

def setup():
    indices=np.asarray(validation_indices(),dtype=np.int64);assert len(indices)==5000 and len(set(indices))==5000
    base=load(REPO/'configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/M1.json')
    geometry=MFM4Dataset(base['root'],split='FULL',geometry_only=True,k=10,molecule_indices=indices)
    norms=load(OLD/'normalizations_TRAIN.json');basis=sorted({int(z) for spec in norms.values() for z in (spec.get('element_reference') or {}).get('basis',[])})
    rows=[];owners=[];x=[];element_ids=[];element_owners=[];element_count=[];element_rows=[];zs=[]
    for i,mi in enumerate(indices):
        m=geometry.record('M',int(mi));z=m[1];choices=geometry.choices(int(mi));assert 0<len(choices)<=10
        counts={int(v):int((z==v).sum()) for v in np.unique(z)};zs.append(z)
        x.append([counts.get(v,0) for v in basis]+[len(z),int((z>1).sum())]);mapping={}
        for v,n in counts.items():
            mapping[v]=len(element_ids);element_ids.append(v);element_owners.append(i);element_count.append(n*len(choices))
        element_rows.append(mapping)
        for ci in choices:rows.append((int(mi),int(ci)));owners.append(i)
        if i%1000==0:guard();print('A_PANEL',i,flush=True)
    geometry.close();owners=np.asarray(owners);first=np.flatnonzero(np.r_[True,np.diff(owners)!=0]);assert len(first)==5000
    return dict(indices=indices,rows=rows,owners=owners,first=first,X=np.asarray(x,np.float64),basis=basis,element_ids=np.asarray(element_ids),element_owners=np.asarray(element_owners),element_count=np.asarray(element_count,np.float64),element_rows=element_rows,Z=zs,base=base)

def resolve(name,entry):
    entry=dict(entry)
    if name in ('C','D'):
        path=REPO/'configs/p_followup'/('C_dedup.json' if name=='C' else 'D_decomposition.json')
        if path.exists():entry['configuration']=str(path)
    if entry.get('configuration'):
        c=load(entry['configuration'])
        # The same M1 configuration can progress naturally to its exact endpoint.
        try:entry['checkpoint']=str(evaluation_checkpoint(c,3000000));entry['status']='EXISTS';entry['reason']=None
        except FileNotFoundError as e:entry.update(checkpoint=None,status='MISSING',reason=str(e))
    return entry

def target_reader(name,payload,entry,panel):
    if name=='P0-S':return None,'S condition has no trained P scalar targets'
    c=load(entry['configuration']) if entry.get('configuration') else payload.get('configuration',{})
    needed=['training_view','normalizations']
    if not all(c.get(k) for k in needed):return None,'Exact checkpoint target parameters unavailable; no substituted recipe'
    try:
        ds=PRecipeDataset(panel['base']['root'],split='FULL',training_view=c['training_view'],normalizations=load(c['normalizations']),label_parameters=c.get('label_parameters'),conformer_decomposition=c.get('conformer_decomposition'),source='PM7',k=10,molecule_indices=panel['indices'])
    except (OSError,ValueError,KeyError) as e:return None,str(e)
    return ds,None

def subset_outer(valid,n):
    ids=np.flatnonzero(valid);mapping=np.full(n,-1,dtype=int);mapping[ids]=np.arange(len(ids))
    return [mapping[part[valid[part]]] for part in folds(n)]

def targets_summary(values,valid,owners,first,X,weights,metadata=None):
    details={};cev_num=np.zeros(len(weights));cev_den=np.zeros(len(weights));cvf_num=np.zeros(len(weights));cvf_den=np.zeros(len(weights))
    for name,a in values.items():
        meta=(metadata or {}).get(name,dict(physical_field=name,component=0,loss_weight=1.))
        factor=meta['loss_weight']
        mask=valid[name]&np.isfinite(a);fraction=float(mask.mean())
        if fraction<.99:details[name]=dict(included=False,valid_fraction=fraction,**meta);continue
        first_valid=mask[first];y=a[first][first_valid,None]
        pred,_=ridge_oof(X[first_valid],y,outer=subset_outer(first_valid,len(X)))
        w=weights[:,first_valid];ce=cev_values(y,pred,w)
        var=ratio(total_ss(w,y,np.square(y).sum(-1),np.ones(len(y))),w@np.ones(len(y)))
        h=a[mask,None];o=owners[mask];dummy=np.zeros((len(X),1));cv,_=cvf_values(h,o,dummy,weights)
        sums,sq,n,within=conformer_moments(h,o,len(X));good=n>=2;n=np.where(good,n,0.);sums=np.where(good[:,None],sums,0.);sq=np.where(good,sq,0.)
        variance=ratio(total_ss(weights,sums,sq,n),weights@n)
        cev_num+=factor*np.nan_to_num(ce*var);cev_den+=factor*np.nan_to_num(var);cvf_num+=factor*np.nan_to_num(cv*variance);cvf_den+=factor*np.nan_to_num(variance)
        details[name]=dict(included=True,valid_fraction=fraction,CEV=summary(ce),CVF=summary(cv),variance_first=float(var[0]),**meta)
    ce=ratio(cev_num,cev_den);cv=ratio(cvf_num,cvf_den)
    return dict(fields=details,variance_weighted_CEV=summary(ce),variance_weighted_CVF=summary(cv),included_fields=sum(v['included'] for v in details.values()),included_physical_fields=len({v['physical_field'] for v in details.values() if v['included']}),component_policy='D t1/t2 use separate actual masks and each half the original physical-field weight; per-component99%valid threshold'),dict(target_CEV=ce,target_CVF=cv)

def condition(name,entry,panel,weights,device):
    started=time.monotonic();entry=resolve(name,entry)
    if not entry.get('checkpoint') or not pathlib.Path(entry['checkpoint']).is_file():
        return dict(status='MISSING',reason=entry.get('reason','Specified checkpoint unavailable'),source=entry),{}
    encoder,payload=load_representation_encoder(entry['checkpoint'],device=device)
    provenance=['condition','distance_bias','views','samples','subset_molecules','seed','source','head_form','root','training_view','normalizations','label_parameters','conformer_decomposition','batch_size','p_recipe']
    entry['checkpoint_configuration']={k:payload.get('configuration',{}).get(k) for k in provenance if k in payload.get('configuration',{})}

    clock=payload.get('clock',{});expected=6000000 if name.startswith('P0-') else 3000000
    cursor=clock.get('samples_consumed',payload.get('samples'))
    if cursor is not None and int(cursor)!=expected:raise ValueError('Checkpoint sample endpoint differs')
    data,target_reason=target_reader(name,payload,entry,panel)
    if data is None:data=MFM4Dataset(panel['base']['root'],split='FULL',geometry_only=True,k=10,molecule_indices=panel['indices'])
    candidate=[] if data.view is None else [f['name'] for f in data.view.fields if f['group']=='P' and f['level']=='molecule' and f.get('loss_enabled',True)]
    if entry.get('configuration'):
        cfg=load(entry['configuration']);candidate=[n for n in candidate if n not in cfg.get('p_recipe',{}).get('excluded_fields',[])]
    decomposition=getattr(data,'conformer_decomposition',None);decomposed=set() if decomposition is None else set(decomposition.selected)
    columns={}
    for field in candidate:
        for component in range(2 if field in decomposed else 1):
            key=field+('::t'+str(component+1) if field in decomposed else '')
            columns[key]=dict(physical_field=field,component=component,loss_weight=.5 if field in decomposed else 1.)
    n=len(panel['rows']);cache=CONTROL/('A_mean_H_'+name+'.npy');guard()
    means=np.lib.format.open_memmap(cache,mode='w+',dtype=np.float32,shape=(n,4,512))
    atom_sums=np.zeros((len(panel['element_ids']),4,512),np.float64);atom_square=np.zeros((len(atom_sums),4),np.float64)
    target_values={key:np.full(n,np.nan) for key in columns};target_valid={key:np.zeros(n,bool) for key in columns}
    with torch.no_grad():
        for start in range(0,n,32):
            samples=[data.read(mi,ci) for mi,ci in panel['rows'][start:start+32]];batch=collate_samples(samples,device=device)
            selected=representation_layers(encoder,batch);features=np.stack([v.detach().cpu().double().numpy() for v in selected],axis=1)
            pointer=batch.ptr.cpu().tolist();assert features.shape==(pointer[-1],4,512)
            for j,(a,b) in enumerate(zip(pointer,pointer[1:])):
                row=start+j;owner=int(panel['owners'][row]);v=features[a:b];z=samples[j]['Z'];means[row]=v.mean(0).astype(np.float32)
                for element,key in panel['element_rows'][owner].items():
                    part=v[z==element];atom_sums[key]+=part.sum(0);atom_square[key]+=np.square(part).sum((0,2))
                for key,meta in columns.items():
                    t=samples[j]['targets'].get(meta['physical_field']);component=meta['component']
                    if t is not None and t.valid.reshape(-1)[component]:target_values[key][row]=float(t.values.reshape(-1)[component]);target_valid[key][row]=True
            if start%1024==0:guard();means.flush();print('A_FORWARD',name,start,n,flush=True)
    means.flush();data.close();del encoder,payload
    if device=='cuda':torch.cuda.empty_cache()
    X=panel['X'];owners=panel['owners'];first=panel['first'];metrics={};boots={};alphas={}
    for index,layer in enumerate([3,4,5,6]):
        guard();y=np.asarray(means[first,index],np.float64);pred,alpha=ridge_oof(X,y);small,_=ridge_oof(X[:,-2:],y)
        cev=cev_values(y,pred,weights);size=cev_values(y,small,weights)
        h=np.asarray(means[:,index],np.float64);cv,res=cvf_values(h,owners,pred,weights)
        eev=eev_values(atom_sums[:,index],atom_square[:,index],panel['element_count'],panel['element_owners'],panel['element_ids'],weights)
        _,_,vectors=np.linalg.svd(y-y.mean(0),full_matrices=False);pcs=(y-y.mean(0))@vectors[:3].T;pc_results=[]
        for j in range(3):
            pp,_=ridge_oof(X,pcs[:,j:j+1]);pc_results.append(summary(cev_values(pcs[:,j:j+1],pp,weights)))
        metrics[str(layer)]=dict(CEV=summary(cev),CEV_size=summary(size),CVF=summary(cv),CVF_res=summary(res),EEV=summary(eev),PC_R2=pc_results)
        for metric,values in [('CEV',cev),('CEV_size',size),('CVF',cv),('CVF_res',res),('EEV',eev)]:boots[str(layer)+'_'+metric]=values
        alphas[str(layer)]=alpha;print('A_METRICS',name,layer,metrics[str(layer)]['CEV'],flush=True)
    targets,target_boot=targets_summary(target_values,target_valid,owners,first,X,weights,columns) if candidate else (dict(reason=target_reason),{})
    boots.update(target_boot);guard();np.savez_compressed(CONTROL/('A_bootstrap_'+name+'.npz'),**boots)
    # Explicitly task-authorized disposal of this producer's temporary means.
    del means;cache.unlink()
    return dict(status='COMPLETE',source=entry,checkpoint_samples=cursor,records=n,molecules=len(X),layers=metrics,selected_alphas=alphas,target_reference=targets,seconds=time.monotonic()-started,mean_cache_removed=True,encoder_route='structural encoder before any shared projector; layer6 out_norm,3-5 intermediates'),boots

def hypotheses(conditions):
    rules=load(REPO/'configs/p_followup/A_preregistration.json');out=[]
    for rule in rules['hypotheses']:
        left,right=rule['left'],rule['right'];row=dict(rule)
        if any(conditions.get(k,{}).get('status')!='COMPLETE' for k in (left,right)):
            row.update(verdict='MISSING',reason='At least one specified condition unavailable');out.append(row);continue
        with np.load(CONTROL/('A_bootstrap_'+left+'.npz')) as a,np.load(CONTROL/('A_bootstrap_'+right+'.npz')) as b:
            if rule['id']=='A-H5':delta=(a['6_CEV']-a['3_CEV'])-(b['6_CEV']-b['3_CEV']);reference=b['6_CEV'][0]
            else:
                key='6_'+('CVF_res' if rule['metric'].startswith('CVF_res') else 'CEV');delta=a[key]-b[key];reference=b[key][0]
        if not np.isfinite(delta[0]) or not np.isfinite(reference):
            row.update(verdict='UNCERTAIN',reason='Metric not defined for constant/degenerate representation');out.append(row);continue
        s=summary(delta);ci=s['ci95'];threshold=max(.10,float(reference)*.20)
        verdict=('SUPPORT' if ci and ci[0]>0 and s['value']>=threshold else 'NOT_SUPPORT' if ci and (ci[1]<.05 or ci[1]<=0) else 'UNCERTAIN')
        row.update(delta=s,reference=float(reference),support_effect_threshold=threshold,verdict=verdict);out.append(row)
    return out

def write_report(payload):
    """Paper-ready rendering of already computed statistics, without refitting."""
    results=payload['conditions'];claims=payload['hypotheses']
    def point(value):return 'NA' if value is None else f'{value:.5g}'
    def stat(value):
        if not value or value.get('value') is None:return 'NA'
        ci=value.get('ci95');return point(value['value'])+(f" [{point(ci[0])}, {point(ci[1])}]" if ci else '')
    lines=['# A：表示塌缩的组成来源检验','','## 范围与方法','',
        '固定5000个VAL分子，复用diagnose.validation_indices（seed20261112）。组成分析取首允许构象；构象分析覆盖同一分子的全部允许k10构象（每条件47698条记录）。只用指定检查点，P0-S/P为6M，R1-B0/A1、R2-M1/B1为3M；C/D仅在各自指定3M端点可用时补充。未启动额外模型训练。',
        '', '第3–5层取中间输出，第6层取out_norm后输出；B1取共享投影器之前。encoder计算为F32，各构象mean(H)暂存为F32，统计为F64；原子H只流式累计元素矩，不落盘。每个条件完成后删除其mean(H)缓存。',
        '', 'Xc使用既有D4元素参考基底的元素计数，并加入总原子数/重原子数；Xsize只用后两列。按MID做5外折交叉验证，5内折只在外层训练折选择ridge参数（1e-3至1e3，每次乘10），折内拟合标准化及不惩罚的截距。CEV是多输出OOF解释方差1−SSE/SST；CEV_size使用Xsize。PC1–3来自首构象mean(H)的全样本F64 PCA轴，其OOF R²仅作描述。',
        '', 'EEV为按元素分组的原子H组间平方和/原子总平方和。CVF为同分子构象内平方和/总平方和；CVF_res将每个构象减去该MID的组成OOF预测后计算相同比值，均限有至少2个允许构象的分子，并按实际构象记录加权。1000次配对MID bootstrap（seed20261025）重采分子及其全部构象，复用固定OOF预测，不重新拟合。以下区间均为95% percentile CI。',
        '', '## 第6层表示结果','','|条件|状态|CEV|CEV_size|EEV|CVF|CVF_res|','|---|---|---|---|---|---|---|']
    for name,c in results.items():
        m=c.get('layers',{}).get('6',{})
        lines.append('|'+ '|'.join([name,c['status']]+[stat(m.get(k)) for k in ['CEV','CEV_size','EEV','CVF','CVF_res']])+'|')
    lines+=['','## 预注册判定','','支持要求CI下界>0，且点效应≥max(0.10,0.20×右侧参照)；H5参照固定为P0-S第6层CEV。CI上界<0.05或全区间≤0为NOT_SUPPORT，其余为UNCERTAIN。H1与H4同时获支持才允许组成来源/构象压缩的联合声明。',
        '', '|假设|差值定义|效应及95%CI|支持效应阈值|判定|','|---|---|---|---:|---|']
    for h in claims:
        expression=(f"(CEV6−CEV3)({h['left']}) − (CEV6−CEV3)({h['right']})" if h['id']=='A-H5' else f"{h['metric']}({h['left']}) − {h['metric']}({h['right']})")
        lines.append(f"|{h['id']}|{expression}|{stat(h.get('delta'))}|{point(h.get('support_effect_threshold'))}|{h['verdict']}|")
    lines+=['',('H1与H4联合声明获得支持。' if payload['joint_claim_supported'] else 'H1与H4联合声明未获支持，不能据此将P的既有谱塌缩主要归因为组成或构象压缩。')]
    h2=next(h for h in claims if h['id']=='A-H2')
    if h2.get('delta',{}).get('value',0)>0 and h2['verdict']=='NOT_SUPPORT':lines+=['','R1-B0减A1虽为正差，仍未满足预注册支持标准；不将其改判为支持。']
    lines+=['','## 实际训练目标参照','','仅纳入该条件实际训练且有效比例≥99%的P分子标量，使用该检查点实际D4/A1参数，按每字段目标方差加权汇总CEV与CVF。该参照只作描述。',
        '', '|条件|纳入字段数|目标CEV（方差加权）|目标CVF（方差加权）|','|---|---:|---|---|']
    for name,c in results.items():
        t=c.get('target_reference',{});lines.append(f"|{name}|{t.get('included_fields','NA')}|{stat(t.get('variance_weighted_CEV'))}|{stat(t.get('variance_weighted_CVF'))}|")
    lines+=['','D的t1/t2按实际分量mask分别执行99%有效比例门槛，各带原字段一半权重；详细条目同时标明物理字段和分量。S条件没有训练P标量目标，参照为NA；指定C/D条件未完成时也记NA。','','![CEV与CVF_res](../../results/p_followup/A_collapse_composition/composition.svg)',
        '', '逐层指标、PC1–3描述结果、每字段目标参照、精确检查点及参数路径见results/p_followup/A_collapse_composition/summary.json和metrics.csv。缺失条件不由其他运行替换；不追加检验或阈值扫描。组成解释率本身不证明独立化学准确性或迁移收益。']
    guard();(REPO/'docs/p_followup/A_COLLAPSE_COMPOSITION.md').write_text('\n'.join(lines)+'\n')

def deliver(results):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    RESULTS.mkdir(parents=True,exist_ok=True);claims=hypotheses(results)
    payload=dict(conditions=results,hypotheses=claims,bootstrap=dict(repetitions=1000,seed=20261025,unit='molecule',paired=True,refit=False),joint_claim_supported=all(next(v for v in claims if v['id']==n)['verdict']=='SUPPORT' for n in ['A-H1','A-H4']))
    save(RESULTS/'summary.json',payload);rows=[]
    for name,c in results.items():
        for layer,metrics in c.get('layers',{}).items():
            for metric,value in metrics.items():
                if metric=='PC_R2':continue
                rows.append(dict(condition=name,layer=layer,metric=metric,value=value['value'],ci_lower=value['ci95'][0] if value['ci95'] else None,ci_upper=value['ci95'][1] if value['ci95'] else None))
    with (RESULTS/'metrics.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['condition','layer','metric','value','ci_lower','ci_upper']);writer.writeheader();writer.writerows(rows)
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for name,c in results.items():
        if c.get('status')!='COMPLETE':continue
        layers=[3,4,5,6];axes[0].plot(layers,[c['layers'][str(l)]['CEV']['value'] for l in layers],'-o',label=name)
        v=c['layers']['6']['CVF_res'];k=len(axes[1].lines);axes[1].plot([k],[v['value']],'o');axes[1].set_xticks(range(k+1),[label for label,item in results.items() if item.get('status')=='COMPLETE'][:k+1]);axes[1].vlines(k,*v['ci95']) if v['ci95'] else None
    axes[0].set(xlabel='Encoder layer',ylabel='Composition explained variance (OOF)',xticks=[3,4,5,6]);axes[0].legend();axes[1].set(ylabel='Within-molecule / composition-residual variance');axes[1].tick_params(axis='x',rotation=30);fig.tight_layout();fig.savefig(RESULTS/'composition.svg');fig.savefig(RESULTS/'composition.png',dpi=150);plt.close(fig)
    write_report(payload)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--device',choices=['cpu','cuda'],default='cuda');parser.add_argument('--conditions',nargs='*');parser.add_argument('--report-only',action='store_true');args=parser.parse_args()
    if args.report_only:write_report(load(RESULTS/'summary.json'));return
    guard(force=True);torch.set_num_threads(4 if args.device=='cuda' else 16);lock=None
    if args.device=='cuda':
        gpu=os.environ['CUDA_VISIBLE_DEVICES'].split(',')[0]
        memory=subprocess.check_output(['nvidia-smi','--id='+gpu,'--query-gpu=memory.used,memory.total','--format=csv,noheader,nounits'],text=True).strip().split(',')
        if float(memory[0])/float(memory[1])>.30:raise RuntimeError('GPU admission changed; no model started')
        path=R/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(gpu+'.lock');lock=path.open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    panel=setup();weights=np.vstack([np.ones((1,5000)),bootstrap_weights(5000)]);results={}
    path=RESULTS/'summary.json'
    if path.exists():results=load(path)['conditions']
    entries=load(REPO/'configs/p_followup/A_conditions.json')['conditions'];entries.setdefault('C',{'configuration':str(REPO/'configs/p_followup/C_dedup.json')});entries.setdefault('D',{'configuration':str(REPO/'configs/p_followup/D_decomposition.json')} if (REPO/'configs/p_followup/D_decomposition.json').exists() else {})
    for name,entry in entries.items():
        if args.conditions and name not in args.conditions:continue
        if results.get(name,{}).get('status')=='COMPLETE':continue
        if results.get(name,{}).get('failed_attempts',0)>=2:continue
        try:
            value,_=condition(name,entry,panel,weights,args.device)
        except Exception as error:
            traceback.print_exc();attempts=results.get(name,{}).get('failed_attempts',0)+1
            value=dict(status='UNRESOLVED' if attempts>=2 else 'REPAIR_NEEDED',failed_attempts=attempts,reason=type(error).__name__+': '+str(error),source=entry)
            gc.collect()
            if args.device=='cuda':torch.cuda.empty_cache()
        results[name]=value;deliver(results)
    print('A_REGISTERED_CONDITIONS_COMPLETE',flush=True)
if __name__=='__main__':main()