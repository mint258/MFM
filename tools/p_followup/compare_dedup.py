"""C3 reuse completed mainline scores and paired bootstrap draws; no probe reruns."""
import csv,pathlib
import numpy as np



def paired_ci(a,b):
    if a['included_tasks']!=b['included_tasks']:raise ValueError('C/M1 primary task membership differs')
    for key in ['groups','seed','samples','confidence']:
        if a['paired_bootstrap'].get(key)!=b['paired_bootstrap'].get(key):raise ValueError('Paired bootstrap metadata differs: '+key)
    x=np.asarray(a['paired_bootstrap']['values'],np.float64);y=np.asarray(b['paired_bootstrap']['values'],np.float64)
    if x.shape!=y.shape or len(x)!=1000:raise ValueError('Paired mainline bootstrap draws differ')
    lower,upper=np.quantile(x-y,[.025,.975]);delta=a['mean_normalized_improvement']-b['mean_normalized_improvement']
    return dict(delta=float(delta),ci95=[float(lower),float(upper)],verdict='win' if lower>0 else 'loss' if upper<0 else 'tie',effect_gate=None,paired_draws=len(x),included_tasks=a['included_tasks'])


def main():
    from resources import REPO,load,save,guard
    guard(force=True);c=load(REPO/'configs/p_followup/C_dedup.json');baseline=load(REPO/'configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/M1.json')
    ca=pathlib.Path(c['output'])/'readout/scores.json';ba=pathlib.Path(baseline['output'])/'readout/scores.json'
    candidate=load(ca);reference=load(ba)
    results={name:paired_ci(candidate[name],reference[name]) for name in ['R1','R3']}
    verdict=results['R3']['verdict'];result=dict(status='COMPLETE',candidate_run=c['run'],baseline_run=baseline['run'],samples=3000000,seed=0,primary='C minus M1 R3',results=results,
        candidate_scores=str(ca),baseline_scores=str(ba),baseline_scope='Provisional M1 with A1 only; pending A4 does not trigger automatic rerun',
        recommendation='Suggest dedup' if verdict in ['win','tie'] else 'Do not recommend dedup',mainline_integration='User confirmation required; no mainline configuration modified')
    save(REPO/'results/p_followup/C_comparison.json',result)
    lines=['# C：去冗余侧线臂最终比较','','状态：3M seed0训练及主线同一R1/R3已完成。独立训练只移除指定10字段，保留99存储字段/87物理头等权。','','复用主线1000次MID配对bootstrap抽样序列，C−M1差值取2.5%/97.5%分位数；不增加效应幅度门槛。主判定只用R3：区间全正win、全负loss，其余tie。R1为副指标。','','|读出|C−M1|95%CI|判定|','|---|---:|---|---|']
    for name,r in results.items():lines.append(f"|{name}|{r['delta']}|{r['ci95']}|{r['verdict']}|")
    lines+=['',result['recommendation']+'。当前证据限M1（A1）基底，主线A4或后续配方变化不自动扩展此结论。实际接入主线由用户确认；本研究未修改主线。','',f'实际原单位VAL MAE见results/p_followup/training/{c["run"]}/VAL_original_units_3000000.csv；仅作描述。']
    (REPO/'docs/p_followup/C_COMPARISON.md').write_text('\n'.join(lines)+'\n');print('C_COMPARISON_COMPLETE',results,flush=True)
if __name__=='__main__':main()