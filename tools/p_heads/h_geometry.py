"""H1 wrapper reusing work A's panel, encoder route and registered geometry math."""
import argparse,fcntl,importlib.util,json,os,pathlib,sys,time
import numpy as np
import torch
from h_resources import REPO,CONTROL,R,guard,load,save,watchdog
FOLLOW=R/'MFM_p_followup_20261117'
sys.path.insert(0,str(FOLLOW/'tools/p_followup'))
sys.path.insert(0,str(FOLLOW/'tools/p_recipe'))
spec=importlib.util.spec_from_file_location('p_heads_work_A',FOLLOW/'tools/p_followup/collapse_composition.py')
A=importlib.util.module_from_spec(spec)
# Keep work A's enhanced loader in its own namespace, including when another
# H wrapper already imported the older mainline diagnose module in this process.
_ds=importlib.util.spec_from_file_location('p_heads_A_diagnose',FOLLOW/'tools/p_recipe/diagnose.py')
_diag=importlib.util.module_from_spec(_ds);_ds.loader.exec_module(_diag)
_previous=sys.modules.get('diagnose');sys.modules['diagnose']=_diag
try:spec.loader.exec_module(A)
finally:
 if _previous is not None:sys.modules['diagnose']=_previous
 else:sys.modules.pop('diagnose',None)
A.guard=guard
from composition_statistics import bootstrap_weights,ridge_oof,cev_values,cvf_values,eev_values,summary
from phychem_mfm.phase1.v31_loader import MFM4Dataset,collate_samples
from checkpoint_paths import evaluation_checkpoint


def prediction_verdict(eev,cvf,cev):
 metrics=[summary(eev),summary(cvf),summary(cev)]
 lower=[v['ci95'][0] if v['ci95'] else float('-inf') for v in metrics]
 upper=[v['ci95'][1] if v['ci95'] else float('inf') for v in metrics]
 support=eev[0]>=.05 and cvf[0]>=0 and cev[0]>=.05 and all(v>0 for v in lower)
 crosses=all(lo<=0<=hi for lo,hi in zip(lower,upper));opposite=all(v['value'] is not None and v['value']<0 for v in metrics)
 return dict(verdict='SUPPORT' if support else 'NOT_SUPPORT' if crosses or opposite else 'PARTIAL_SUPPORT',EEV_M1_minus_B3=metrics[0],CVF_B3_minus_twice_M1=metrics[1],CEV_M1_minus_B3=metrics[2])


def forward_geometry(name,checkpoint,panel,weights,device,layers):
 started=time.monotonic();encoder,payload=A.load_representation_encoder(checkpoint,device=device)
 config=payload.get('configuration',{});clock=payload.get('clock',{})
 samples=clock.get('samples_consumed',payload.get('samples'))
 if samples is not None and samples!=3000000:raise ValueError('H requires exact 3M checkpoint')
 if name=='B3' and not config.get('p_recipe',{}).get('pma_pooling'):raise ValueError('B3 checkpoint lacks PMA condition')
 data=MFM4Dataset(panel['base']['root'],split='FULL',geometry_only=True,k=10,molecule_indices=panel['indices'])
 n=len(panel['rows']);cache=CONTROL/('H1_mean_'+name+'.npy');guard()
 means=np.lib.format.open_memmap(cache,mode='w+',dtype=np.float32,shape=(n,len(layers),512))
 atom_sums=np.zeros((len(panel['element_ids']),len(layers),512),np.float64);atom_square=np.zeros(atom_sums.shape[:2],np.float64)
 white={}
 first=set(panel['first'].tolist())
 with torch.no_grad():
  for start in range(0,n,32):
   batch_samples=[data.read(mi,ci) for mi,ci in panel['rows'][start:start+32]];batch=collate_samples(batch_samples,device=device)
   outputs=A.representation_layers(encoder,batch)
   features=np.stack([outputs[layer-3].detach().cpu().double().numpy() for layer in layers],axis=1)
   ptr=batch.ptr.cpu().tolist()
   for j,(a,b) in enumerate(zip(ptr,ptr[1:])):
    row=start+j;owner=int(panel['owners'][row]);v=features[a:b];z=batch_samples[j]['Z'];means[row]=v.mean(0).astype(np.float32)
    for element,key in panel['element_rows'][owner].items():
     part=v[z==element];atom_sums[key]+=part.sum(0);atom_square[key]+=np.square(part).sum((0,2))
     if row in first and 6 in layers:
      h=part[:,layers.index(6)]
      state=white.setdefault(str(element),dict(count=0,sum=np.zeros(512),square=np.zeros(512)))
      state['count']+=len(h);state['sum']+=h.sum(0);state['square']+=np.square(h).sum(0)
   if start%1024==0:guard();means.flush();print('H1_FORWARD',name,start,n,flush=True)
 means.flush();data.close();del encoder,payload
 if device=='cuda':torch.cuda.empty_cache()
 metrics={};boots={}
 for index,layer in enumerate(layers):
  guard();y=np.asarray(means[panel['first'],index],np.float64);pred,alphas=ridge_oof(panel['X'],y)
  ce=cev_values(y,pred,weights);cv,res=cvf_values(np.asarray(means[:,index],np.float64),panel['owners'],pred,weights)
  ee=eev_values(atom_sums[:,index],atom_square[:,index],panel['element_count'],panel['element_owners'],panel['element_ids'],weights)
  metrics[str(layer)]={k:summary(v) for k,v in [('CEV',ce),('CVF',cv),('CVF_res',res),('EEV',ee)]}
  metrics[str(layer)]['ridge_alphas']=alphas
  boots.update({str(layer)+'_'+k:v for k,v in [('CEV',ce),('CVF',cv),('CVF_res',res),('EEV',ee)]})
 guard();np.savez_compressed(CONTROL/('H1_bootstrap_'+name+'.npz'),**boots)
 # Reuse this same first-conformer stream for H3, no extra encoder pass.
 white={z:{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in state.items()} for z,state in white.items()}
 save(CONTROL/('H3_whitening_moments_'+name+'.json'),white)
 del means;cache.unlink()  # Task-authorized own intermediate features only.
 return dict(status='COMPLETE',checkpoint=str(checkpoint),checkpoint_samples=samples,checkpoint_configuration={k:config.get(k) for k in ('condition','samples','seed','p_recipe','label_parameters','batch_size','root','normalizations')},molecules=len(panel['indices']),conformers=n,layers=metrics,seconds=time.monotonic()-started)


def report(results):
 def fmt(v):
  if not v or v.get('value') is None:return 'NA'
  ci=v.get('ci95');return f'{v["value"]:.6g}'+(f' [{ci[0]:.6g}, {ci[1]:.6g}]' if ci else '')
 hypotheses=None
 if results.get('B3',{}).get('status')=='COMPLETE':
  with np.load(CONTROL/'H1_bootstrap_B3.npz') as b,np.load(R/'runs/p_followup_20261116/A_bootstrap_R2-M1.npz') as m:
   hypotheses=prediction_verdict(m['6_EEV']-b['6_EEV'],b['6_CVF']-2*m['6_CVF'],m['6_CEV']-b['6_CEV'])
 payload=dict(conditions=results,hypothesis=hypotheses,bootstrap=dict(repetitions=1000,seed=20261025,unit='molecule',paired=True,refit=False),M1_reused_from=str(FOLLOW/'results/p_followup/A_collapse_composition/summary.json'))
 save(REPO/'results/p_heads/H/H1_geometry.json',payload)
 lines=['# H1：B3 表示几何','','方法：直接调用工作 A 的固定 5000 VAL 分子、实际允许构象、编码器加载和逐层提取工具。组成特征为既有元素计数及总原子数、重原子数，复用 composition_statistics 的五外折/五内折 ridge 组成预测。第 3–5 层取中间输出，第 6 层取 out_norm 后输出。没有训练编码器、额外 PCA 或扫描。','','CEV为首允许构象的mean(H)由分子组成OOF预测解释的方差比例，1−SSE/SST。EEV为按元素分组的原子H组间平方和/原子总平方和。CVF为同分子构象内平方和/总平方和，限至少有两个允许构象的分子。CVF_res先减去每个分子固定的组成OOF预测，再计算相同构象比例。CEV/CVF/CVF_res基于逐构象mean(H)，EEV基于逐原子H。','','1000次配对MID bootstrap（seed=20261025）重采分子并保留其全部构象，固定OOF预测不重新拟合，区间为95%百分位CI。M1所有几何和bootstrap直接引用工作A，不重新运行。','','|条件|层|CEV|EEV|CVF|CVF_res|','|---|---:|---|---|---|---|']
 for name,c in results.items():
  for layer,metrics in c.get('layers',{}).items():lines.append('|'+ '|'.join([name,layer]+[fmt(metrics[k]) for k in ['CEV','EEV','CVF','CVF_res']])+'|')
 lines+=['','|预注册效应|点估计及配对95%CI|门槛|判定|','|---|---|---|---|']
 if hypotheses:
  for label,key,gate in [('EEV(M1)−EEV(B3)','EEV_M1_minus_B3','效应≥0.05且CI下界>0'),('CVF(B3)−2×CVF(M1)','CVF_B3_minus_twice_M1','效应≥0且CI下界>0'),('CEV(M1)−CEV(B3)','CEV_M1_minus_B3','效应≥0.05且CI下界>0')]:
   value=hypotheses[key];ok=value['value']>=(0 if key.startswith('CVF') else .05) and value['ci95'][0]>0
   lines.append(f'|{label}|{fmt(value)}|{gate}|'+('满足' if ok else '不满足')+'|')
  lines+=['','三项联合预注册判定：'+hypotheses['verdict']+'。']
 for name in ('T1','T2'):
  if results.get(name,{}).get('status')=='COMPLETE' and results.get('B3',{}).get('status')=='COMPLETE':
   delta=results[name]['layers']['6']['EEV']['value']-results['B3']['layers']['6']['EEV']['value'];lines+=['',f'{name}相对T0/B3的EEV差为{delta:.6g}，仅作机制描述。']
 if results.get('M2',{}).get('status')=='COMPLETE':
  lines+=['','M2的精确3M检查点已在H执行期间产出，按原范围补充同一5000 VAL分子、47698个允许构象的第3–6层几何，仅作机制描述，不新增显著性检验或独立判定。','','M2运行：Slurm 4535641，compute-0-20，4 CPU，COMPLETED 0:0，8分52秒；producer前向与统计合计522.33秒。截至M2几何完成，H已执行GPU作业累计墙钟5.0148小时，后续T几何另计。']
 lines+=['','局限：组成解释率与构象比例是描述性几何指标，不能单独证明下游效应的因果来源。T1验收未通过，未产生新3M检查点，故其几何缺失；T2/T3及按预注册实际触发的seed1只在各自精确最终3M检查点产出后补充第6层，不分析中间恢复点。']
 guard();(REPO/'docs/p_heads/H1_GEOMETRY.md').write_text('\n'.join(lines)+'\n')

def main():
 p=argparse.ArgumentParser();p.add_argument('--condition',default='B3');p.add_argument('--checkpoint');p.add_argument('--device',default='cuda');args=p.parse_args()
 watchdog();torch.set_num_threads(4);torch.set_float32_matmul_precision('highest');torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 lock=None
 if args.device=='cuda':
  import subprocess
  gpu=os.environ['CUDA_VISIBLE_DEVICES'].split(',')[0]
  used,total=map(float,subprocess.check_output(['nvidia-smi','--id='+gpu,'--query-gpu=memory.used,memory.total','--format=csv,noheader,nounits'],text=True).strip().split(','))
  if used/total>.3:raise RuntimeError('GPU admission changed')
  lock=(R/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(gpu+'.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 CONTROL.mkdir(parents=True,exist_ok=True);panel=A.setup();weights=np.vstack([np.ones((1,5000)),bootstrap_weights(5000)])
 existing=REPO/'results/p_heads/H/H1_geometry.json';results=load(existing)['conditions'] if existing.exists() else {}
 if 'M1' not in results:results['M1']=load(FOLLOW/'results/p_followup/A_collapse_composition/summary.json')['conditions']['R2-M1']
 cfg=load(REPO/'configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/B3.json')
 checkpoint=pathlib.Path(args.checkpoint) if args.checkpoint else evaluation_checkpoint(cfg,3000000)
 results[args.condition]=forward_geometry(args.condition,checkpoint,panel,weights,args.device,[3,4,5,6] if args.condition in ('B3','M2') else [6]);report(results)
 print('H1_COMPLETE',args.condition,flush=True)

if __name__=='__main__':main()
