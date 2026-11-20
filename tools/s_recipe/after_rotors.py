"""Render the closed rotor producer's required daily line, without new QA."""
import json
import os
from pathlib import Path

from runtime import CONTROL, REPO, capacity, write


def main():
    capacity()
    source = REPO/'configs/s_recipe/rotors.json'
    result = json.loads(source.read_text())
    if result['schema'] != 'S_RECIPE_SOURCE_ROTORS_V1':
        raise ValueError('Expected the closed S rotor producer summary')
    fraction = result['zero_rotor_TRAIN_fraction']
    line = ('旋转索引已完成（4537414）；无可旋转键TRAIN分子比例 '
            +format(fraction, '.6%')+'，RDKit运行版本 '+result['rdkit_version']
            +'；数值直接取自 configs/s_recipe/rotors.json，未重读或复算旧数据。')
    daily = REPO/'docs/s_recipe/daily/2026-11-20.md'
    content = daily.read_text()
    marker = '进行中：CPU17索引4537414。'
    if marker in content:
        content = content.replace(marker, line)
    elif line not in content:
        content += '\n'+line+'\n'
    pending = daily.with_suffix('.md.next')
    pending.write_text(content)
    pending.replace(daily)
    state = json.loads((CONTROL/'current_state.json').read_text())
    state.update(rotor_completed=True, rotor_summary=str(source),
        rotor_phase='4537414 completed; source-pointer/SMILES binding and all source-order rotor plans closed',
        zero_rotor_TRAIN_fraction=fraction, rotor_rdkit_version=result['rdkit_version'],
        rotor_document_job=os.environ['SLURM_JOB_ID'])
    write(CONTROL/'current_state.json', state)
    print(json.dumps(dict(source=str(source), daily_line=line,
                          consumer_job=os.environ['SLURM_JOB_ID'])), flush=True)


if __name__ == '__main__':
    main()
