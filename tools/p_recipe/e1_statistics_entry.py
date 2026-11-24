"""E1 CPU finalization: original R1/probe scores, exact E1 provenance."""
import argparse,json,os
from pathlib import Path
import i1_statistics_entry as shared
from e1_readout_entry import make_readout
from finetune_statistics_entry import fingerprint

def validate_source(original,c):
    source_path=Path(c["source_configuration"])
    source=json.loads(source_path.read_text())
    expected=make_readout(source,source_path,c["output"],original["store"])
    if original!=expected or c["original_run"]!=expected["run"]:
        raise ValueError("E1 original frozen configuration changed")
    if fingerprint(expected["checkpoint"])!=c["checkpoint_identity"]:
        raise ValueError("E1 source checkpoint changed")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",type=Path,required=True)
    a=p.parse_args();c=json.loads(a.configuration.read_text())
    if os.environ.get("CUDA_VISIBLE_DEVICES")!="":raise ValueError("CPU-only required")
    raise SystemExit(shared.run(c,validate_source=validate_source))
