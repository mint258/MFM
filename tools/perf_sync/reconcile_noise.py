"""Align epsilon_loss with PR8 using the already collected S0 loss pairs."""
import csv
import json
import sys
from collections import defaultdict

from regression import REPO, SCRATCH, capacity


def main():
    capacity()
    report=REPO/'results/perf_sync/gpu_20261118'
    raw=SCRATCH/'gpu_20261118'
    if '--refresh-flags' in sys.argv:
        for name in ('S1','S2','S3','S4_encoder','S4_encoder_heads','S5'):
            path=report/f'{name}_numerical.json';result=json.loads(path.read_text())
            for row in result['comparisons']:
                row['B_pass']=row['PR8_field_gate_pass'] and row['PR8_gradient_gate_pass']
            if all(r['B_pass'] for r in result['comparisons'])!=result['B_single_step_pass']:
                raise RuntimeError('Whole-item decision changed')
            path.write_text(json.dumps(result,indent=2)+'\n')
        print('PR8 per-case flags aligned; all whole-item decisions unchanged',flush=True)
        return
    noise=json.loads((report/'S0_noise.json').read_text())
    archive=report/'S0_noise_original_combined_norm.json'
    if archive.exists():raise RuntimeError('Noise reanalysis already performed; retain result')
    archive.write_text(json.dumps(noise,indent=2)+'\n')
    pairs=defaultdict(dict)
    for row in csv.DictReader((raw/'S0_field_losses.csv').open()):
        pairs[(row['weights'],int(row['batch']),row['field'])][int(row['repeat'])]=float(row['loss'])
    floors=defaultdict(float);fields=defaultdict(set)
    for (weights,batch,field),values in pairs.items():
        if set(values)!={0,1}:raise RuntimeError('Incomplete original S0 pair')
        key=(weights,batch);fields[key].add(field)
        floors[key]=max(floors[key],abs(values[0]-values[1])/max(abs(values[0]),1e-30))
    for row in noise['records']:
        row['epsilon_loss_combined_norm_original']=row['epsilon_loss']
        row['epsilon_loss']=floors[(row['weights'],row['batch'])]
    noise['epsilon_loss']=max(floors.values())
    noise['loss_noise_definition']='PR8 max(abs(old1-old2)/max(abs(old1),1e-30)); taskbook gate10*epsilon*(1+abs(loss))'
    noise['reanalysis']='Original loss pairs reused; no GPU/model replay. Earlier combined-norm result archived.'
    (report/'S0_noise.json').write_text(json.dumps(noise,indent=2)+'\n')
    summary=[]
    for name in ('S1','S2','S3','S4_encoder','S4_encoder_heads','S5'):
        path=report/f'{name}_numerical.json';result=json.loads(path.read_text())
        observed=defaultdict(set);valid=defaultdict(lambda:True)
        for row in csv.DictReader((raw/f'{name}_field_deviations.csv').open()):
            key=(row['weights'],int(row['batch']));observed[key].add(row['field'])
            valid[key]&=float(row['absolute_difference'])<=10*noise['epsilon_loss']*(1+abs(float(row['baseline'])))
        old=result['B_single_step_pass']
        for row in result['comparisons']:
            key=(row['weights'],row['batch'])
            row['original_stricter_B_pass']=row['B_pass']
            row['field_coverage_equal']=observed[key]==fields[key]
            row['PR8_field_gate_pass']=bool(valid[key] and row['field_coverage_equal'])
            row['PR8_gradient_gate_pass']=row['grad_relative']<=10*noise['epsilon_grad']
            row['B_pass']=row['PR8_field_gate_pass'] and row['PR8_gradient_gate_pass']
        required=all(r['PR8_field_gate_pass'] and r['PR8_gradient_gate_pass'] for r in result['comparisons'])
        if required and not old:
            raise RuntimeError('Previously failed case now needs its unused-parameter evidence; do not silently promote')
        if required!=old:raise RuntimeError('Inspect changed whole-item decision before publication')
        result['epsilon_loss_original_combined_norm']=result['epsilon_loss']
        result['epsilon_loss']=noise['epsilon_loss']
        result['reanalysis']='PR8 loss normalization, preserved CSV only; entire-item decision unchanged'
        path.write_text(json.dumps(result,indent=2)+'\n')
        summary.append(dict(item=name,B_single_step_pass=old,field_coverage_equal=all(r['field_coverage_equal'] for r in result['comparisons'])))
    (report/'noise_reanalysis.json').write_text(json.dumps(dict(epsilon_loss=noise['epsilon_loss'],epsilon_grad=noise['epsilon_grad'],items=summary),indent=2)+'\n')
    print(json.dumps(dict(epsilon_loss=noise['epsilon_loss'],epsilon_grad=noise['epsilon_grad'],items=summary)),flush=True)


if __name__=='__main__':main()
