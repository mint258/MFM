"""Generate spec14 through frozen prep13; preserve identical duplicate old refs."""
from __future__ import annotations
import argparse,ast,copy,os
from pathlib import Path
from types import SimpleNamespace
import wp5_prepare_runtime_freeze_v13 as F

PREPARER_SHA="0394b97a51bb12a17b30446259f412456885c58536904dfc21100501b077a568"

def add_unique_consistent(files,entry):
    hits=[item for item in files if item["path"]==entry["path"]]
    if hits:
        if any((item["sha256"],item["bytes"])!=(entry["sha256"],entry["bytes"]) for item in hits):
            raise ValueError("OLD_SOURCE_SHA_OR_BYTES_WOULD_CHANGE:"+entry["path"])
    else:
        files.append(copy.deepcopy(entry))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    if args.check:
        ast.parse(Path(__file__).read_text());print("G4_SPEC_ADAPTER_AST_PASS_NO_WRITE_NO_SCI");return
    if os.getuid()!=1278:raise ValueError("EXACT_OWN_UID1278_REQUIRED")
    if F.digest(F.__file__)!=PREPARER_SHA:raise ValueError("FROZEN_PREP13_SOURCE_DIFFERS")
    original_add=F.add_unique;original_save=F.save
    def save_with_adapter(path,value):
        if Path(path)!=F.SPEC:raise ValueError("ONLY_NEW_SPEC14_OUTPUT_ALLOWED")
        value=copy.deepcopy(value)
        add_unique_consistent(value["files"],F.ref(Path(__file__).resolve(),"G4_duplicate_consistent_ref_adapter"))
        old=F.load(F.OLD_SPEC,F.OLD_SPEC_SHA)
        if value["files"][:len(old["files"])]!=old["files"]:
            raise ValueError("OLD151_REFERENCE_DICTS_NOT_EXACTLY_PRESERVED")
        original_save(path,value)
    try:
        F.add_unique=add_unique_consistent;F.save=save_with_adapter
        F.spec_mode(SimpleNamespace())
    finally:
        F.add_unique=original_add;F.save=original_save

if __name__=="__main__":main()
