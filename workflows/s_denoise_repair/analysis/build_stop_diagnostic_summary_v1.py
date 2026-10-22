"""CPU-only final diagnostic STOP summary from closed immutable measurements."""
import argparse,hashlib,json,math,os,socket,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
GUIDE='240b7b8132603517a7640662a5ea75e67371d5633e8a3c723ab148174c0b8fa3'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p),bytes=Path(p).stat().st_size)
def check(row):assert sha(row['path'])==row['sha256'];return Path(row['path'])
def load(p):return json.loads(Path(p).read_text())
def save(p,d):
    with p.open('x') as f:json.dump(d,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phases',nargs='+',required=True);ap.add_argument('--profiles',type=Path,nargs='+',required=True)
    ap.add_argument('--parent-snapshot',type=Path,required=True);ap.add_argument('--gate',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args()
    assert os.getuid()==1278 and os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-'+str(n) for n in [2,8,9,10,11,12,13,14,15,16,17,18,19]]
    assert a.output_dir.is_absolute() and a.output_dir.is_relative_to(R/'reports') and not a.output_dir.exists()
    assert sha(R/'user_repair_guide.md')==GUIDE
    stop=load(R/'GUIDE_STOP.json');assert stop['guide_sha256']==GUIDE and stop['reason'] in ['D3_MESSAGE_LAYER_CAPABILITY_FAILED','STAGE3_GATES_NOT_ALL_PASSED']
    inputs=[ref(R/'GUIDE_STOP.json'),ref(a.gate),ref(a.parent_snapshot),ref(R/'configs/D3_source_binding_v4.json')]
    binding=load(R/'configs/D3_source_binding_v4.json')
    for row in binding['files']:check(row)
    snapshot=load(a.parent_snapshot);assert snapshot['status']=='ACTUAL_SONMI_SACCT_SNAPSHOT' and snapshot['columns']==['State','ExitCode','ElapsedRaw','AllocCPUS']
    assert snapshot['host']=='sonmi' and snapshot['uid']==1278
    raw={row[0]:row[1:] for row in (line.split('|') for line in snapshot['raw_stdout'].splitlines()) if row[0]}
    ledger={};states={}
    for phase in a.phases:
        cp=R/'control'/phase;st=load(cp/'status.json');states[phase]=st['status']
        assert st['status'] in ['D3_PHASE_COMPLETE_AWAITING_SCIENTIFIC_GATE','D3_MESSAGE_LAYER_CAPABILITY_FAILED']
        inputs.extend([ref(cp/'status.json'),ref(cp/'jobs.json')])
        for key,job in load(cp/'jobs.json').items():
            assert key not in ledger;ledger[key]=job;jid=job['job_id']
            assert snapshot['rows'][jid]==raw[jid] and raw[jid][:2]==['COMPLETED','0:0']
    profiles={}
    for p in a.profiles:
        d=load(p);assert d['status']=='COMPLETED_CONDITION_COST_AND_GRADIENT_PROFILES_ONLY_NOT_STAGE3_GATE'
        for row in d['source_references']:check(row)
        inputs.append(ref(p))
        for row in d['rows']:
            key=row['condition']+'_seed'+str(row['seed']);assert key not in profiles;profiles[key]=row
    assert set(profiles)==set(ledger),'Every completed diagnostic must have an actual CPU gradient/cost profile'
    for key,row in profiles.items():assert row['job_id']==ledger[key]['job_id'] and row['actual_parent']==raw[row['job_id']]
    lookup_closure=load(R/'configs/lookup_refit_closure_v1.json');check(lookup_closure['result_reference'])
    lookup=load(lookup_closure['result_reference']['path']);threshold=lookup['metrics']['D3_FULL2000']['lookup_rmse_A']
    inputs.extend([ref(R/'configs/lookup_refit_closure_v1.json'),lookup_closure['result_reference']])
    d1p=check(load(R/'reports/D1_latest.json'));d2p=check(load(R/'reports/D2_latest.json'));d1=load(d1p);d2=load(d2p);inputs.extend([ref(d1p),ref(d2p)])
    assert d1['status']=='D1_COMPLETE' and d1['batches']==200 and d1['optimizer_updates']==0
    assert d2['status']=='D2_COMPLETE' and d2['molecules']==1000
    gate=load(a.gate);assert gate['status']=='STAGE3_GATES_NOT_ALL_PASSED' and not gate['formal_training_authorized_by_gate']
    groups=list(dict.fromkeys(row['condition'] for row in profiles.values()));architecture=[]
    for group in groups:
        rr=[profiles[group+'_seed'+str(s)] for s in [0,1]]
        cfgp=Path(ledger[group+'_seed0']['configuration']);cfg=load(cfgp)
        assert sha(cfgp)==ledger[group+'_seed0']['configuration_sha256'];inputs.append(ref(cfgp))
        active=cfg['loss_policy'].get('structural_tasks');multitask=active is None or 'element' in active
        if group in ['A0','A1'] or not multitask:continue
        values=[row['final']['local_rmse_A'] for row in rr]
        architecture.append(dict(condition=group,local_RMSE_A_by_seed=values,mean_final_RMSE_A=math.fsum(values)/2,
            capability_pass=all(v<threshold for v in values),
            gradient_fraction_by_seed=[row['mean_of_per_batch_shared_gradient_fractions']['denoise_eps_mse'] for row in rr],
            estimated_full_epoch_GPU_h_by_seed=[row['cost']['estimated_GPU_hours'] for row in rr],
            cost_pass=all(row['cost']['estimated_GPU_hours']<=15 for row in rr),
            other_tasks_pass=all(row['final']['masked_element_accuracy']>=profiles['A0_seed'+str(s)]['final']['masked_element_accuracy'] and row['final']['bond_order_accuracy']>=profiles['A0_seed'+str(s)]['final']['bond_order_accuracy'] for s,row in enumerate(rr)),
            matched_A5_measured=any(x in groups for x in ['A5' if group in ['A2','A3','A4'] else group.replace('A4_','A5_')]) if group not in ['A2','A3'] else False))
    best=min(architecture,key=lambda row:row['mean_final_RMSE_A']);a.output_dir.mkdir(parents=True)
    note=['# S 去噪修复诊断结论（按指南停止）','',
        '代码修复和诊断已完成到指南允许的停止点。未通过全部门槛，未启动新的全量 B1/B3、H0 提取或下游探针；不能据此判断全量收敛或建议具体 epoch 数。','',
        '## 已确认的证据','',
        f"- D1：旧 B3 epoch3 的200批共享梯度份额，element={d1['fractions_mean']['element']:.2%}、distance={d1['fractions_mean']['distance']:.2%}、bond-order={d1['fractions_mean']['bond_order']:.2%}；全参数裁剪触发{d1['clip_trigger_fraction_all_parameters']:.2%}。该状态不能代表训练全程，也不能与D3不同状态的末20批混作同一测量。",
        f"- D2：旧式0.1/N神谕可达到局部RMSE {d2['aggregate']['scale0p1_N']['local_rmse_A']:.9f} Å。它反驳约0.1 Å硬下限；自由逐分子权重不等于网络能学会，也不构成经认证最优解。",
        '- D3：新头、新噪声MSE、逐epoch噪声及LR扫描带来明显改善；这组联动修改不能单独证明哪个因素是唯一主因。',
        f"- 最低观测双seed均值来自{best['condition']}：两个seed为{best['local_RMSE_A_by_seed'][0]:.9f}/{best['local_RMSE_A_by_seed'][1]:.9f} Å。这里只报告观测值，不创建新的已获准全量配置。",
        f'- 新TRAIN-only查表：FULL2000 {threshold:.9f} Å；全FULL {lookup["metrics"]["full"]["lookup_rmse_A"]:.9f} Å；旧参考0.042 Å。','',
        '## 新头与消息补救的实测门槛','',
        '| 组 | 局部RMSE：s0 / s1（Å） | 去噪门槛 | 去噪梯度：s0 / s1 | 全量单epoch估计：s0 / s1（GPUh） | 成本门槛 | 其他任务门槛 |','|---|---|---|---|---|---|---|']
    for row in architecture:
        v=row['local_RMSE_A_by_seed'];g=row['gradient_fraction_by_seed'];c=row['estimated_full_epoch_GPU_h_by_seed']
        note.append(f"| {row['condition']} | {v[0]:.6f} / {v[1]:.6f} | {'PASS' if row['capability_pass'] else 'FAIL'} | {g[0]:.2%} / {g[1]:.2%} | {c[0]:.3f} / {c[1]:.3f} | {'PASS' if row['cost_pass'] else 'FAIL'} | {'PASS' if row['other_tasks_pass'] else 'FAIL'} |")
    note+=['','成本为预定公式估计，包含加载、验证、保存和启动开销，不是已经完成的全量epoch时长。两seed各自必须过门槛；不以均值代替。能力失败的消息架构未继续A5，干扰门槛记为未测，不沿用旧架构A5结果。','',
        f"既有完整五项表：{a.gate.name}，对应{gate['selected']}；其A5只对该组有效。当前停止原因：{stop['reason']}。",'',
        '## 代码与测试','',
        '新等变噪声头、denoise_eps_mse、epoch噪声选项、遮蔽原子NLL/准确率和几何/键级指标均以新选项实现，旧默认保留。完整2016项测试、旧v2固定批逐位一致、真实多worker断点与GPU路径检查通过，实际作业与SHA见源码绑定。原LMDB只读，历史配置和证据保留。','',
        '## 待用户决定','',
        '依据原方案停止条件，下一轮需由用户决定是否更改模型/训练预算或验证门槛，再另定冻结方案。本轮不通过时不启动全量，不外推epoch数。',
        '若只允许继续当前门槛，现有诊断不足以授权全量；若讨论新路线，应将新实验与本轮冻结结果分开记录。','']
    (a.output_dir/'诊断结论.md').write_text('\n'.join(note))
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig=plt.figure(figsize=(11.7,8.3));ax=fig.add_axes([.04,.04,.92,.9]);ax.axis('off')
    ax.text(0,1,'S denoising repair: diagnostic STOP',fontsize=19,va='top',weight='bold')
    ax.text(0,.93,'Full training and downstream convergence test: NOT RUN under the guide gates',fontsize=11,color='firebrick')
    lines=[f"Stop reason: {stop['reason']}",
      f"Best observed diagnostic: {best['condition']}, local RMSE {best['local_RMSE_A_by_seed'][0]:.6f} / {best['local_RMSE_A_by_seed'][1]:.6f} A",
      f"New TRAIN-only lookup: FULL2000 {threshold:.6f} A; full FULL {lookup['metrics']['full']['lookup_rmse_A']:.6f} A; old 0.042 A",
      f"D1 old B3 epoch3: distance gradient share {d1['fractions_mean']['distance']:.2%}; 200 batches; clip {d1['clip_trigger_fraction_all_parameters']:.1%}",
      f"D2 old-form oracle achieved {d2['aggregate']['scale0p1_N']['local_rmse_A']:.6f} A: refutes a hard 0.1 A error floor.",
      'Free oracle weights do not prove learnability. The D3 changes do not isolate a single causal factor.',
      'Epoch recommendation: undetermined. No extrapolation from fixed-step D3 diagnostics.']
    ax.text(0,.86,'\n'.join(lines),fontsize=10,linespacing=1.65,va='top')
    cells=[]
    for row in architecture:
        v=row['local_RMSE_A_by_seed'];g=row['gradient_fraction_by_seed'];c=row['estimated_full_epoch_GPU_h_by_seed']
        cells.append([row['condition'],f'{v[0]:.5f} / {v[1]:.5f}','PASS' if row['capability_pass'] else 'FAIL',f'{g[0]:.1%} / {g[1]:.1%}',f'{c[0]:.2f} / {c[1]:.2f}','PASS' if row['cost_pass'] else 'FAIL'])
    table=ax.table(cellText=cells,colLabels=['Group','Local RMSE (A), s0/s1','Capability','Noise gradient, s0/s1','Epoch estimate (h), s0/s1','Cost'],bbox=[0,.19,1,.35],colWidths=[.12,.23,.11,.2,.23,.11],cellLoc='left')
    table.auto_set_font_size(False);table.set_fontsize(8)
    ax.text(0,.13,'Every row: 2 seeds, 4,000 updates, common FULL2000. Epoch costs include all preregistered overhead.\nCapability-failed message variants omit A5; their interference remains unmeasured.\nComplete five-gate table and all raw monitor values are delivered separately. New experiments require a user decision.',fontsize=9,va='top',linespacing=1.6)
    fig.savefig(a.output_dir/'Diagnostic_stop_summary.pdf');fig.savefig(a.output_dir/'Diagnostic_stop_summary.png',dpi=140);plt.close(fig)
    doc=dict(status='FINAL_DIAGNOSTIC_STOP_SUMMARY_NO_FULL_CONVERGENCE_CLAIM',job_id=os.environ['SLURM_JOB_ID'],stop_record=stop,
       phase_states=states,lookup_FULL2000_RMSE_A=threshold,architecture_measurements=architecture,best_observed_diagnostic=best,
       full_training_run=False,epoch_recommendation=None,source_references=inputs+[ref(__file__)],artifacts=[ref(p) for p in sorted(a.output_dir.iterdir())])
    save(a.output_dir/'summary_measurements.json',doc);print(json.dumps(dict(status=doc['status'],output=str(a.output_dir))))
if __name__=='__main__':main()
