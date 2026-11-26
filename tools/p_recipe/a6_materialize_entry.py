"""A6 original-source TRAIN materialization; old native frames are byte-copied."""
import argparse
import json
import os
from pathlib import Path
import time

from finetune_entry import CooperativeStop,set_actual_deadline
from finetune_statistics_entry import require_cpu_admission,atomic_json
from finetune import ContinuationRequired


def run(c):
    if c.get("ready") is not True:
        raise ValueError("A6 materialization must be explicitly activated")
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);require_cpu_admission(c)
        from phychem_mfm.phase1.v3_dev_store import bound_json
        from phychem_mfm.phase1.v3_selected_training_store import (
            binding,write_json,load_context,FrozenSelectedDecoder,close_context)
        from a6_native_reuse import ClosedNativeReuse
        from a6_store_publish import publish_reusing_selected_store
        prepared=bound_json(c["preparation"]["path"],c["preparation"]["sha256"])
        if (prepared["status"]!="PREPARED_TARGET_OPAQUE"
                or prepared["counts"]!={"train":30000,"train_inner_validation":2048}
                or not prepared["all_original_evaluation_members_unchanged"]
                or not prepared["old8192_nested"]):
            raise ValueError("Sealed30000/2048 population required")
        output=Path(c["output"]);output.mkdir(parents=True,exist_ok=True)
        if (output/"primary_complete.json").exists():
            raise ValueError("Closed A6 materialization must be reused")
        started=time.monotonic();last_guard=0.;decoder=None;context=None
        def check():
            nonlocal last_guard
            now=time.time()
            if (stop.requested or now+c["work_unit_seconds"]>=float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"])
                    or now+c["work_unit_seconds"]>=c["implementation_started_at"]+14400):
                raise ContinuationRequired("A6 safe stop within fourhour implementation limit")
            if time.monotonic()-last_guard>=5:
                require_cpu_admission(c);last_guard=time.monotonic()
        try:
            check()
            sources=bound_json(prepared["original_sources"]["path"],prepared["original_sources"]["sha256"])
            panel=bound_json(prepared["panel"]["path"],prepared["panel"]["sha256"])
            plan=bound_json(prepared["plan"]["path"],prepared["plan"]["sha256"])
            context=load_context(sources,panel,check)
            reuse=ClosedNativeReuse(prepared["old_store"])
            decoder=FrozenSelectedDecoder(context,plan,check);decoder.prepare()
            original_contracts=prepared["source_contracts"]
            for dataset,ref in original_contracts.items():
                if binding(ref["path"])!=ref:
                    raise ValueError("Original role contract binding changed")
            final=output/"native_store";final.mkdir(exist_ok=False)
            def close():
                close_context(context,decoder)
            result=publish_reusing_selected_store(plan,context["native"],decoder.decode,
                output=final,request_ref=c["preparation"],source_contracts=original_contracts,
                definitions=context["definitions"],protocol=context["protocol"],
                reuse=reuse,workers=c["cpus"],check=check,close_source=close)
            reused=sum((d,row["member_index"]) in reuse.rows for d,rows in plan["records"].items() for row in rows)
            new=result["records"]-reused
            result.update(job=os.environ["SLURM_JOB_ID"],status="COMPLETE",counts=prepared["counts"],
                old_native_records_reused=reused,new_records_decoded=new,
                original_decoder_numeric_calls=len(decoder.decoded),
                old_FP64_FP32_bytes_preserved=True,TEST_records_decoded=0,
                new_geometry=False,seconds=time.monotonic()-started,
                original_evaluation_identity_unchanged=True,source_validation=c["source_validation"])
            if len(decoder.decoded)!=new:
                raise ValueError("Only newly selected records may be decoded")
            atomic_json(output/"primary_complete.json",result)
            print(json.dumps(result),flush=True)
            return 0
        except ContinuationRequired as exc:
            atomic_json(output/"unresolved.json",dict(status="UNRESOLVED",reason=str(exc),
                job=os.environ["SLURM_JOB_ID"],seconds=time.monotonic()-started,
                partial_output_retained=True,partial_store_not_consumable=True))
            return 0


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",required=True)
    args=p.parse_args()
    raise SystemExit(run(json.loads(Path(args.configuration).read_text())))
