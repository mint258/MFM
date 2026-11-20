"""Produce only the S taskbook's registered training configurations."""
import argparse
import json
from pathlib import Path

ROOT = Path('/share/home/zixiao/descriptor_analysis')
REPO = ROOT/'MFM_s_recipe'
CONTROL = ROOT/'runs/s_recipe_20261120'


def make(arm, seed=0, samples=3000000, *, components=None):
    registration = json.loads((REPO/'configs/s_recipe/preregistration.json').read_text())
    arms = registration['arms']
    if arm in ('S-M1', 'S-final'):
        if (seed != 0 or not components or
                (arm == 'S-M1' and (samples != 3000000 or len(components) < 2)) or
                (arm == 'S-final' and samples != 9000000)):
            raise ValueError('Only the registered single3M seed0 merge is allowed')
        if set(components)-{'S-N1', 'S-N2', 'S-R1', 'S-R2'} or {'S-N1', 'S-N2'} <= set(components):
            raise ValueError('Unregistered or mutually exclusive merge components')
        specification = dict(arms['S-B0'])
        specification['disabled'] = []
        for component in components:
            item = arms[component]
            if item['noise'] != 'baseline':
                specification['noise'] = item['noise']
            specification['disabled'] += item['disabled']
    else:
        if arm not in arms:
            raise ValueError('Unknown S arm')
        specification = arms[arm]
    if seed not in (0, 1) or samples not in (3000000, 9000000):
        raise ValueError('Only registered seeds/budgets')
    if arm == 'S-G1' and (seed != 0 or samples != 3000000):
        raise ValueError('S-G1 is descriptive3M seed0 only')
    if samples == 9000000 and seed != 0:
        raise ValueError('9M is seed0 only')
    training = registration['training']
    name = arm.replace('-', '_')+'_s'+str(seed)+'_'+str(samples//1000000)+'M'
    return dict(schema='S_RECIPE_TRAINING_V1', run=name, arm=arm, seed=seed, samples=samples,
        stage='S', round=1, source=specification['source'], noise=specification['noise'],
        disabled=specification['disabled'], components=list(components or ([arm] if arm != 'S-B0' else [])),
        batch_size=32, microbatch_size=32, gradient_accumulation=False, activation_checkpointing=False,
        distance_bias='C1-0', views='three', precision='FP32', tf32=False,
        lr=training['lr'], betas=training['betas'], weight_decay=training['weight_decay'],
        clip_calibration=dict(initial_clip=281.7, window_start_samples=60000,
                              calibration_samples=150000, quantile=.99),
        root=json.loads((REPO/'configs/s_recipe/population.json').read_text())['source_root'],
        population=str(REPO/'configs/s_recipe/population.json'),
        initialization=str(CONTROL/('initialization_seed'+str(seed)+'.pt')),
        rotor_index=str(CONTROL/'rotors.sqlite'), workers=14,
        normalization=registration['population']['normalization'],
        output=str(CONTROL/'training'/name),
        evaluation_samples=([1000000, 2000000, 3000000]
                            if arm == 'S-B0' and seed == 0 and samples == 3000000 else [samples]),
        evaluation_store=str(ROOT/'runs/model_v3_20261025/selected_train_store_4520421/native_store/training_store.json'),
        reference_manifest='/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/reference_C1_0/predictions.json',
        statistics_backend='slurm_cpu', speed_switches=dict(activation_checkpointing=False,
            tf32=False, mixed_precision=False, gradient_accumulation=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--arm', required=True)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--samples', type=int, default=3000000)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    configuration = make(a.arm, a.seed, a.samples)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x') as stream:
        stream.write(json.dumps(configuration, indent=2)+'\n')
