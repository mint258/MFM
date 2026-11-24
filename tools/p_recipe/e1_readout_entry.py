"""E1 frozen R1/R3: unchanged native H0/probes and guarded I1 runtime."""
import argparse,json
from pathlib import Path
import i1_readout_entry as shared
from e1_training_entry import validate as validate_training
from finetune_statistics_entry import fingerprint

AUTHORITY="docs/p_recipe/USER_DIRECTIVE_20261123.md"

def make_readout(source,source_path,output,store):
    native=validate_training(source)
    output=Path(output)
    return dict(run=native["run"]+"_frozen_readout",arm=native["arm"],stage=0,round=0,
        study_revision="fixed_20261115",samples=3000000,source_run=native["run"],
        source_configuration=str(source_path),source_training_budget=3000000,
        checkpoint=str(Path(native["output"])/"samples_3000000.pt"),
        checkpoint_resolver="actual_own_budget_terminal_checkpoint",
        layer=6,representation="H0",output=str(output),features=str(output/"features"),
        persist_features=True,R1_backend="slurm_cpu",store=str(store),
        statistics_backend="slurm_cpu",evaluation_samples=[3000000],
        authority=AUTHORITY,bootstrap_samples=1000,bootstrap_seed=20261025,
        new_training=False,new_seeds=False,readout_seed=0)

def validate(c):
    source_path=Path(c["source_configuration"])
    source=json.loads(source_path.read_text())
    expected=make_readout(source,source_path,c["output"],c["readout"]["store"])
    if c["new_training"] is not False or c["new_seeds"] is not False or c["readout"]!=expected:
        raise ValueError("Exact registered E1 frozen readout required")
    if fingerprint(expected["checkpoint"])!=c["checkpoint_identity"]:
        raise ValueError("Actual E1 terminal checkpoint binding changed")
    summary=json.loads((Path(source['output'])/'summary.json').read_text())
    if summary.get('samples')!=3000000 or summary.get('updates')!=93750 or summary.get('status')!='TRAINING_COMPLETE_EVALUATION_PENDING':
        raise ValueError('E1 native terminal3M summary required')
    return expected

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",type=Path,required=True)
    a=p.parse_args();raise SystemExit(shared.run(json.loads(a.configuration.read_text()),validator=validate))
