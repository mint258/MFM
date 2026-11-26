"""Reuse the user-approved running G1 as B0 without starting another trainer."""
import argparse
import json
from pathlib import Path

from execution_ledger import locked_ledger, read, write

REPO=Path(__file__).resolve().parents[2]


def baseline_configuration(base):
    source_path=Path(base['reuse_baseline_configuration'])
    source=read(source_path)
    if (source['samples'],source['batch_size'],source['lr'],source['activation_checkpointing']) != (
            base['screening_samples'],32,3e-4,False):
        raise ValueError('The reused baseline differs from the user-approved G1 setup')
    result=dict(source,arm='B0',round=1,stage=2,components=[],
                study_revision=base['study_revision'],baseline_reused=True,
                baseline_source_study_revision=source.get('study_revision'),
                baseline_source_configuration=str(source_path),
                baseline_protocol_exception=base['baseline_clip_exception'])
    return result


def refresh(base_path,study_directory):
    base=read(base_path)
    cfg=baseline_configuration(base)
    directory=Path(study_directory)/'round1'
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/'B0.json'
    previous=read(target) if target.is_file() else None
    write(target,cfg)
    clip=Path(cfg['output'])/'clip_calibration.json'
    if clip.is_file():
        destination=REPO/'results/p_recipe/training'/cfg['run']/'clip_calibration.json'
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(clip.read_text())
    plan_path=directory/'plan.json'
    if plan_path.is_file():
        plan=read(plan_path)
        sizes=plan.setdefault('batch_size_by_run',{})
        if previous:sizes.pop(previous['run'],None)
        sizes[cfg['run']]=32
        plan.update(reused_baseline_run=cfg['run'],reused_baseline_source_configuration=base['reuse_baseline_configuration'],
                    baseline_protocol_exception=base['baseline_clip_exception'])
        write(plan_path,plan)
    with locked_ledger() as ledger:
        for name,record in ledger['runs'].items():
            if name.startswith(base['reuse_baseline_family_prefix']):
                record['screening_reuse_attribution']=dict(study_revision=base['study_revision'],round=1)
    return cfg


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-configuration',required=True)
    parser.add_argument('--study-directory',required=True)
    args=parser.parse_args()
    cfg=refresh(args.base_configuration,args.study_directory)
    print(json.dumps(dict(run=cfg['run'],output=cfg['output'],reused=True)),flush=True)
