"""Opt-in E1/subset validation followed by unchanged registered S training."""
import argparse
import json
import os
from pathlib import Path
from checkpoint_binding import SCIENTIFIC_KEYS
from storage_20261122 import CONTROL, REPO


def validate(c, baseline, population):
    kind = c.get('extension_kind')
    if kind == 'E1':
        if (type(c.get('conformer_cap')) is not int or c['conformer_cap'] not in (1, 2, 5)
                or c['samples'] != 3000000 or c['seed'] != 0
                or c.get('extension_authority') != 'docs/s_recipe/USER_DIRECTIVE_20261123.md'
                or population.get('conformer_cap') != c['conformer_cap']
                or population['TRAIN_molecules'] != 1192951):
            raise ValueError('Only registered E1 seed0 cells may enter')
    elif kind == 'molecule_subset':
        if (c['samples'] != 9000000 or c['seed'] != 0
                or c.get('extension_authority') != 'docs/s_recipe/USER_DIRECTIVE_20261123C.md'
                or population.get('P_source_arm') not in ('T5', 'T6')
                or population.get('subset_seed') != 20261112
                or population.get('selection') != 'original_P_selected_MIDs_intersect_S_TRAIN'):
            raise ValueError('Only registered original P subset intersections may enter')
        nominal=250000 if population['P_source_arm']=='T5' else 500000
        if (population.get('original_P_selected_molecules')!=nominal
                or not 0<population['TRAIN_molecules']<=nominal):
            raise ValueError('Report the actual intersection of the original P selected population')
    else:
        raise ValueError('Extension defaults off; no unregistered science')
    for key in (*SCIENTIFIC_KEYS, 'initialization', 'rotor_index', 'evaluation_store', 'reference_manifest'):
        if key != 'population' and c[key] != baseline[key]:
            raise ValueError('Extension changed the frozen training recipe: '+key)
    if Path(c['output']) != CONTROL/'training'/c['run'] or c['run'] == baseline['run']:
        raise ValueError('A new S-owned run/output must preserve the original producer')
    if (population['validation'] != json.loads((REPO/'configs/s_recipe/population.json').read_text())['validation']
            or population['VAL_molecules'] != 5000 or population['VAL_seed'] != 20261112
            or c['batch_size'] != 32 or c['microbatch_size'] != 32
            or c.get('activation_checkpointing') is not False
            or c.get('gradient_accumulation') is not False
            or c.get('precision') != 'FP32' or c.get('tf32') is not False):
        raise ValueError('Fixed original validation and B32 FP32 contract required')
    return c


def run(c, scheduler_record):
    base = REPO/'configs/s_recipe'/('screening/S-R1.json' if c.get('extension_kind') == 'E1'
                                   else 'confirmation/S-final.json')
    validate(c, json.loads(base.read_text()), json.loads(Path(c['population']).read_text()))
    from train_line_storage_20261122 import run as original_training
    return original_training(c, scheduler_record=scheduler_record)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--configuration', type=Path, required=True)
    c = json.loads(p.parse_args().configuration.read_text())
    deadline = json.loads((CONTROL/('deadline_'+os.environ['SLURM_JOB_ID']+'.json')).read_text())
    print(json.dumps(run(c, deadline)), flush=True)
