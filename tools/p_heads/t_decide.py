"""Use the original paired bootstrap draws; materialize only triggered seed1 configs."""
import argparse,copy,pathlib
import numpy as np
from h_resources import REPO,CONTROL,guard,load,save

def paired(candidate,reference):
    if candidate['included_tasks']!=reference['included_tasks']:raise ValueError('Task panel differs')
    for key in ('groups','seed','samples','confidence'):
        if candidate['paired_bootstrap'].get(key)!=reference['paired_bootstrap'].get(key):raise ValueError('Unpaired bootstrap '+key)
    x=np.asarray(candidate['paired_bootstrap']['values']);y=np.asarray(reference['paired_bootstrap']['values'])
    if x.shape!=y.shape or len(x)!=1000:raise ValueError('Need original1000 paired draws')
    return dict(delta=float(candidate['mean_normalized_improvement']-reference['mean_normalized_improvement']),
        ci95=np.quantile(x-y,[.025,.975]).tolist(),candidate=float(candidate['mean_normalized_improvement']),reference=float(reference['mean_normalized_improvement']))

def single(result):
    delta=result['delta'];lower,upper=result['ci95']
    return 'win' if delta>=.06 and lower>0 else 'loss' if delta<=-.06 and upper<0 else 'seed1_required'

def both(zero,one):
    average=(zero['delta']+one['delta'])/2
    gate=max(.03,(zero['reference']+one['reference'])/2*.08)
    if zero['ci95'][0]>0 and one['ci95'][0]>0 and average>=gate:return 'win'
    if zero['ci95'][1]<0 and one['ci95'][1]<0:return 'loss'
    return 'tie'

def seed1(configuration,arm):
    c=copy.deepcopy(configuration)
    for key in ('resume','resume_samples','resume_from_output','attempt','required_gpu_uuid'):c.pop(key,None)
    c.update(seed=1,run='p_heads_'+arm+'_seed1',arm=arm)
    c['output']=str(CONTROL/'training'/c['run']);c['results_directory']='results/p_heads/T'
    c['control_directory']=str(CONTROL/'control')
    c['handoff_request']=str(CONTROL/'control'/(c['run']+'_request.json'))
    c['handoff_ack']=str(CONTROL/'control'/(c['run']+'_ack.json'))
    return c

def main():
    p=argparse.ArgumentParser();p.add_argument('--configuration',required=True);a=p.parse_args();guard(force=True)
    c=load(a.configuration);arm=c['arm']
    if arm not in ('T1','T2','T3') or c['seed']!=0:raise ValueError('Only registered seed0 arms trigger supplements')
    base=load(REPO/'configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/B3.json')
    candidate=load(pathlib.Path(c['output'])/'readout/scores.json');reference=load(pathlib.Path(base['output'])/'readout/scores.json')
    results={r:paired(candidate[r],reference[r]) for r in ('R1','R3')}
    trigger=single(results['R3'])=='seed1_required';needed=[]
    if trigger:
        for source,name in ((c,arm),(base,'B3')):
            target=REPO/'configs/p_heads/T'/(name+'_seed1.json')
            if not target.exists():save(target,seed1(source,name))
            needed.append(str(target))
    for readout,r in results.items():
        r['seed0_verdict']=single(r)
        if not trigger:r['verdict']=single(r) if single(r)!='seed1_required' else 'tie_no_R1_trigger'
    outcome=dict(arm=arm,seed1_triggered=trigger,requested_configurations=needed,results=results,status='SEED1_REQUIRED' if trigger else 'COMPLETE_SEED0')
    if trigger:
        cx=seed1(c,arm);bx=seed1(base,'B3')
        cp=pathlib.Path(cx['output'])/'readout/scores.json';bp=pathlib.Path(bx['output'])/'readout/scores.json'
        if cp.exists() and bp.exists():
            cc,bb=load(cp),load(bp)
            for readout,r in results.items():
                r['seed1']=paired(cc[readout],bb[readout]);r['verdict']=both(r,r['seed1'])
            outcome.update(status='COMPLETE_TWO_SEEDS',B3_R3_training_noise=abs(reference['R3']['mean_normalized_improvement']-bb['R3']['mean_normalized_improvement']))
    save(REPO/'results/p_heads/T'/(arm+'_deltas.json'),outcome)
    print(outcome,flush=True)
if __name__=='__main__':main()
