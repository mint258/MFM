"""Consume prepared owners and a fresh Root intent, then run the CPU mask pilot.

The original owner plan remains immutable. A new run-local plan refreshes only
the account-quota evidence and records that exact derivation.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from datetime import datetime

from common import read_json, reference, verify_reference, write_json_new
from prepare_owner_manifest import root_guard


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--owner-receipt",required=True)
    p.add_argument("--root-preflight",required=True)
    p.add_argument("--run-root",required=True)
    args = p.parse_args()
    receipt = read_json(args.owner_receipt)
    if receipt["status"]!="PILOT_OWNER_MANIFEST_READY_NOT_SCIENTIFIC_MASK_RUN":
        raise ValueError("OWNER_PREPARATION_NOT_COMPLETE")
    outputs = {Path(ref["path"]).name:ref for ref in receipt["outputs"]}
    for ref in outputs.values():
        verify_reference(ref)
    plan_ref = outputs["mask_plan.json"]
    plan = read_json(plan_ref["path"])
    budget = int(plan["storage_budget"]["total_declared_new_bytes"])
    guard_config = {"workers":16,"max_output_bytes":budget,"quota_reserve_bytes":200_000_000_000}
    # The review must pin the complete owner receipt; its outputs in turn pin
    # the plan, canonical records, and restricted source-file projection.
    preflight = root_guard(args.root_preflight,args.owner_receipt,guard_config)
    root = Path(args.run_root).absolute()
    owner_config = read_json(verify_reference(receipt["config"]))
    allowed = Path(owner_config["external_output_root"])
    if root==allowed or allowed not in root.parents or any(p.is_symlink() for p in (root,*root.parents)):
        raise ValueError("MASK_RUN_ROOT_MUST_BE_NEW_OWNED_EXTERNAL_CHILD")
    root.mkdir(parents=True,exist_ok=False,mode=0o700)
    quota = {"status":"QUOTA_METADATA_VERIFIED","available_bytes":preflight["account_free_bytes"],
        "observed_at_epoch":datetime.fromisoformat(preflight["observed_at"]).timestamp(),
        "raw_evidence":reference(args.root_preflight),"source":"fresh Root mask-job account quota; not df"}
    write_json_new(root/"quota_receipt.json",quota)
    plan["storage_budget"]["quota_receipt"] = reference(root/"quota_receipt.json")
    plan["status"] = "ROOT_REVIEWED_RUNTIME_QUOTA_REFRESH_ONLY"
    plan["derivation"] = {"immutable_owner_plan":plan_ref,"immutable_owner_receipt":reference(args.owner_receipt),
        "root_preflight":reference(args.root_preflight),"scientific_parameters_changed":False,
        "changed_fields":["status","storage_budget.quota_receipt","derivation"]}
    write_json_new(root/"runtime_plan.json",plan)
    from pilot_masks import main as run_pilot
    original = sys.argv
    try:
        sys.argv = [str(Path(__file__).with_name("pilot_masks.py")),"--plan",str(root/"runtime_plan.json"),
            "--output",str(root/"results")]
        result = run_pilot()
        write_json_new(root/"wrapper_receipt.json",{"status":"MASK_PILOT_RETURNED",
            "child_return_code":result,"runtime_plan":reference(root/"runtime_plan.json"),
            "owner_receipt":reference(args.owner_receipt),"root_preflight":reference(args.root_preflight)})
        return result
    except BaseException as exc:
        write_json_new(root/"wrapper_failure.json",{"status":"FAILED_EVIDENCE_PRESERVED",
            "type":type(exc).__name__,"error":str(exc),"runtime_plan":reference(root/"runtime_plan.json")})
        raise
    finally:
        sys.argv = original


if __name__=="__main__":
    raise SystemExit(main())
