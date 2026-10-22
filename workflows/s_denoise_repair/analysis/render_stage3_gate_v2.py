"""One-page Stage3 gate table from complete, provenance-bound measurements."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--gate',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--performance-reference',type=Path)
    args=parser.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-'+str(n) for n in [2,8,9,10,11,12,13,14,15,16,17,18,19]]
    assert args.gate.is_relative_to(ROOT/'reports') and args.output_dir.is_relative_to(ROOT/'reports')
    gate=json.loads(args.gate.read_text());assert gate['status'] in ['ALL_STAGE3_GATES_PASS','STAGE3_GATES_NOT_ALL_PASSED']
    assert [m['seed'] for m in gate['measurements']]==[0,1]
    for item in gate['scientific_inputs']:assert sha(item['path'])==item['sha256']
    perf=None
    if args.performance_reference:
        ref=json.loads(args.performance_reference.read_text());assert sha(ref['path'])==ref['sha256']
        perf=json.loads(Path(ref['path']).read_text())
        assert perf['official_training_updates_added']==0
        raw_performance_status=perf['status']
        if raw_performance_status=='PRESELECTION_PAIRED_COMPUTE_CROSSOVER_COMPLETE_PARAMETERS_BITEXACT_UNCHANGED':
            assert perf['candidate_group']==gate['selected'] and perf['LR_selection_made_by_this_probe'] is False
            case='candidate'
        else:
            assert raw_performance_status=='PAIRED_COMPUTE_CROSSOVER_COMPLETE_PARAMETERS_BITEXACT_UNCHANGED'
            case='selected'
        assert perf['source_binding_sha256']==gate['source_binding']['sha256']
        selected_results=[]
        for item in gate['scientific_inputs']:
            path=Path(item['path'])
            if path.name!='result.json':continue
            value=json.loads(path.read_text())
            if isinstance(value,dict) and value.get('status')=='D3_CONDITION_COMPLETE' and value.get('condition')==gate['selected'] and value.get('seed')==0:selected_results.append(value)
        assert len(selected_results)==1 and perf['checkpoints'][case]==selected_results[0]['checkpoint'],'PERFORMANCE_CHECKPOINT_DIFFERS_FROM_GATED_CONDITION'
        # Display-only alias; the original performance document and its SHA remain unchanged.
        if case=='candidate':perf={**perf,'throughput_selected_over_A0':perf['throughput_candidate_over_A0']}
    ms=gate['measurements'];first=ms[0]
    both=lambda function:'\n'.join('s'+str(m['seed'])+': '+function(m) for m in ms)
    rows=[['Denoising',both(lambda m:f"{m['local_rmse_A']:.6f} A"),f"Both < lookup\n{first['lookup_FULL2000_RMSE_A']:.6f} A",'denoising'],
          ['Shared gradient',both(lambda m:f"{100*m['gradient_fraction']:.3f}%"),'Each >= 10%\nFinal20 TRAIN batches','gradient'],
          ['A5 vs multitask',both(lambda m:f"{100*m['interference_relative_gap']:.3f}%"),'Each absolute gap\n<= 10% of multitask','interference'],
          ['Other tasks vs A0',both(lambda m:f"element {100*m['masked_element_accuracy_delta_vs_matched_A0']:+.4f} pp;\nbond {100*m['bond_accuracy_delta_vs_matched_A0']:+.4f} pp"),'Both accuracy deltas\n>= 0, matched seeds','other_tasks'],
          ['Full-epoch cost',both(lambda m:f"{m['estimated_GPU_hours']:.3f} GPU h"),'Each estimate <= 15 h\nLoader + all overhead','cost']]
    args.output_dir.mkdir(parents=True,exist_ok=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig=plt.figure(figsize=(8.27,11.69));axis=fig.add_axes([.04,.35,.92,.48]);axis.axis('off')
    table=axis.table(cellText=[[a,b,c,'PASS' if gate['gates'][d] else 'FAIL'] for a,b,c,d in rows],
        colLabels=['Gate','Measured (two seeds)','Predeclared rule','Result'],cellLoc='left',colWidths=[.18,.39,.29,.14],bbox=[0,0,1,1])
    table.auto_set_font_size(False);table.set_fontsize(8)
    heights=[.08,.15,.15,.15,.25,.15]
    for index,height in enumerate(heights):
        for column in range(4):table[index,column].set_height(height)
    for i,row in enumerate(rows,1):table[i,3].set_facecolor('#d7efdf' if gate['gates'][row[3]] else '#f4d6d6')
    fig.text(.05,.95,'S denoising repair: Stage3 gate',fontsize=16)
    fig.text(.05,.915,'Selected '+gate['selected']+'; two seeds, 4,000 optimizer updates each.',fontsize=10)
    fig.text(.05,.88,'ALL FIVE PASS' if all(gate['gates'].values()) else 'FULL TRAINING BLOCKED BY GUIDE GATE',fontsize=12,color='#28603d' if all(gate['gates'].values()) else '#9a2828')
    notes=[f"New full FULL lookup: {gate['lookup_FULL_RMSE_A']:.6f} A; historical guide reference: 0.042 A.",
        'TRAIN: 10,000 molecules / 91,893 records; FULL evaluation: 2,000 molecules / 18,486 records.',
        'All source conformers retained. Final fixed endpoint; no early-checkpoint selection.',
        'Gradient shares: mean per-batch weighted norm / sum of three task norms; all backbone parameters.',
        'A5 gap uses absolute difference. Accuracy differences are absolute percentage points (pp).',
        'Cost is an estimate, not a completed full epoch. Actual GPU hardware:']
    notes += [f"  s{m['seed']}: {m['GPU_model']}; D3 train incl. loader {m['records_per_second']:.2f} records/s; peak tensor {m['peak_allocated_bytes']/2**20:.1f} MiB." for m in ms]
    if perf:
        notes += [f"Paired same-GPU crossover: new/A0 compute throughput = {perf['throughput_selected_over_A0']:.4f};",
            f"peak allocated VRAM delta = {perf['allocated_VRAM_delta_bytes']/2**20:+.1f} MiB; reserved delta = {perf['reserved_VRAM_delta_bytes']/2**20:+.1f} MiB.",
            'Crossover excludes loader/transfer; actual D3 rate is used for the full-epoch projection.']
    fig.text(.05,.31,'\n'.join(notes),va='top',fontsize=8,linespacing=1.5)
    fig.text(.05,.035,'Source and actual parent accounting are SHA-bound in the gate JSON. This page makes no downstream convergence claim.',fontsize=7)
    fig.savefig(args.output_dir/'Stage3_gate.pdf');fig.savefig(args.output_dir/'Stage3_gate.png',dpi=150);plt.close(fig)
    labels=['去噪能力','共享梯度占比','A5多任务差距','其他任务准确率','每轮成本估算']
    text=['# 第3步实测门槛', '', '最优组：'+gate['selected']+'；每个种子4000次更新。', '',
        '| 门槛 | 两种子实测 | 判定 |','|---|---|---|']
    for label,row in zip(labels,rows):
        text.append('| '+label+' | '+row[1].replace('\n','；')+' | '+('通过' if gate['gates'][row[3]] else '不通过')+' |')
    text += ['',f"新人口完整FULL查表RMSE：{gate['lookup_FULL_RMSE_A']:.6f} Å；D3的FULL2000查表RMSE：{first['lookup_FULL2000_RMSE_A']:.6f} Å；历史参考0.042 Å。",'',
        '成本为估算，含数据加载、验证、检查点保存读回与分段启动开销；准确率差用百分点。此页不代表已完成全量训练或下游收敛检验。']
    (args.output_dir/'Stage3_gate.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    record=dict(status='COMPLETE_MEASUREMENT_GATE_PAGE_RENDERED_AWAITING_VISUAL_REVIEW',job_id=os.environ['SLURM_JOB_ID'],performance_selected_checkpoint_verified=bool(perf),gate=dict(path=str(args.gate),sha256=sha(args.gate)),
        renderer_sha256=sha(__file__),PDF_sha256=sha(args.output_dir/'Stage3_gate.pdf'),performance_reference=None if not args.performance_reference else dict(path=str(args.performance_reference),sha256=sha(args.performance_reference)))
    (args.output_dir/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(status=record['status'],gates=gate['gates'],output=str(args.output_dir))))


if __name__=='__main__':main()
