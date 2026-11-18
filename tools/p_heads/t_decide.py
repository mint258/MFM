"""Use the original paired bootstrap draws; materialize only triggered seed1 configs."""
import argparse,copy,pathlib
import numpy as np
from h_resources import REPO,CONTROL,guard,load,save
from t_prepare_configuration import fresh

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
    return fresh(configuration,arm,seed=1)

def config_path(path):
    p=pathlib.Path(path)
    return p if p.is_absolute() else REPO/p
def main():
    p=argparse.ArgumentParser();p.add_argument('--configuration',required=True)
    p.add_argument('--reference-configuration');p.add_argument('--reference-seed1-configuration');a=p.parse_args();guard(force=True)
    c=load(a.configuration);arm=c['arm']
    if arm not in ('T1','T2','T3','T4','T5','T2_confirm') or c['seed']!=0:raise ValueError('Only authorized seed0 arms')
    binding=c.get('p_heads_reference',{})
    base_path=a.reference_configuration or binding.get('seed0_configuration')
    if base_path is None:
        if arm in ('T1','T2_confirm'):raise ValueError('Explicit current-recipe reference binding required')
        base_path='configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/B3.json'
    base=load(config_path(base_path))
    result_path=REPO/'results/p_heads/T'/(arm+'_deltas.json')
    if result_path.exists():
        cached=load(result_path)
        if cached.get('arm')!=arm or any(not all(k in cached.get('results',{}).get(r,{}) for k in ('delta','ci95','candidate','reference')) for r in ('R1','R3')):
            raise ValueError('Existing seed0 result does not match the requested arm')
        if cached.get('reference_configuration') and config_path(cached['reference_configuration']).resolve()!=config_path(base_path).resolve():
            raise ValueError('Existing seed0 reference configuration differs')
        results=copy.deepcopy({r:cached['results'][r] for r in ('R1','R3')})
    else:
        candidate=load(pathlib.Path(c['output'])/'readout/scores.json');reference=load(pathlib.Path(base['output'])/'readout/scores.json')
        results={r:paired(candidate[r],reference[r]) for r in ('R1','R3')}
    trigger=single(results['R3'])=='seed1_required' and arm!='T2_confirm';needed=[]
    external=binding.get('reuse_external_seed1',arm=='T1')
    external_path=a.reference_seed1_configuration or binding.get('seed1_configuration')
    reference_seed1=None
    if trigger:
        target=REPO/'configs/p_heads/T'/(arm+'_seed1.json')
        if not target.exists():save(target,seed1(c,arm))
        needed.append(str(target))
        if external:
            if external_path:reference_seed1=load(config_path(external_path))
        else:
            target=REPO/'configs/p_heads/T'/'B3_seed1.json'
            if not target.exists():save(target,seed1(base,'B3'))
            reference_seed1=load(target);needed.append(str(target))
    for readout,r in results.items():
        r['seed0_verdict']=single(r)
        if not trigger:r['verdict']=single(r) if single(r)!='seed1_required' else ('tie' if arm=='T2_confirm' else 'tie_no_R1_trigger')
    outcome=dict(arm=arm,reference_configuration=str(base_path),reference_arm=base['arm'],
        seed1_triggered=trigger,requested_configurations=needed,results=results,
        status='SEED1_REQUIRED' if trigger else ('COMPLETE_CONFIRMATION_SEED0' if arm=='T2_confirm' else 'COMPLETE_SEED0'))
    if trigger:
        outcome.update(reference_seed1_reused_external=external,reference_seed1_configuration=external_path,
            external_reference_pending=external and reference_seed1 is None)
        cx=load(REPO/'configs/p_heads/T'/(arm+'_seed1.json'))
        if cx['arm']!=arm or cx['seed']!=1:raise ValueError('Canonical candidate must match arm and seed1')
        cp=pathlib.Path(cx['output'])/'readout/scores.json'
        bp=None if reference_seed1 is None else pathlib.Path(reference_seed1['output'])/'readout/scores.json'
        missing=[r for r in ('R1','R3') if 'seed1' not in results[r]]
        if missing and bp is not None and cp.exists() and bp.exists():
            cc,bb=load(cp),load(bp)
            for readout in missing:results[readout]['seed1']=paired(cc[readout],bb[readout])
        if all('seed1' in results[r] for r in ('R1','R3')):
            for readout,r in results.items():r['verdict']=both(r,r['seed1'])
            noise=abs(results['R3']['reference']-results['R3']['seed1']['reference'])
            outcome.update(status='COMPLETE_TWO_SEEDS',reference_R3_training_noise=noise)
            if base['arm']=='B3':outcome['B3_R3_training_noise']=noise
    outcome['current_best_confirmation_required']=arm=='T2' and results['R3'].get('verdict')=='win'
    if outcome['current_best_confirmation_required']:
        outcome['confirmation']='One fresh3M seed0 on published CURRENT_BEST, reference reused; root coordinates preparation/submission'
    save(result_path,outcome)
    print(outcome,flush=True)
if __name__=='__main__':main()