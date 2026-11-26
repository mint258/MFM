"""E1 final training hardware from original telemetry only; no GPU queries."""
from cpu_ssh_runtime import execution_handle
import argparse,csv,fcntl,json,os
from pathlib import Path
from e1_hardware import summarize_telemetry
from finetune_entry import CooperativeStop,set_actual_deadline
from finetune_statistics_entry import require_cpu_admission,atomic_json,fingerprint

def run(c):
    if c.get("ready") is not True:raise ValueError("Native terminal source bindings required")
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);require_cpu_admission(c)
        output=Path(c["output"]);output.mkdir(parents=True,exist_ok=True)
        with (output/"owner.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (output/"summary.json").exists():raise ValueError("Reuse closed training hardware")
            rows=[]
            for entry in c["training_runs"]:
                if stop.requested:return 75
                root=Path(entry["output"]);native=json.loads((root/"summary.json").read_text())
                attempt=json.loads((root/("managed_attempt_"+str(entry["job"])+".json")).read_text())
                if (native["samples"]!=3000000 or native["actual_samples"]!=3000000 or
                        native["updates"]!=93750 or native["batch_size"]!=32 or
                        attempt.get("monitor_thread_joined") is not True or
                        attempt.get("FP32") is not True or attempt.get("TF32") is not False):
                    raise ValueError("Original completed single-attempt3M FP32/B32 training required")
                path=root/"managed_gpu_telemetry.jsonl";before=fingerprint(path)
                telemetry=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
                hardware=summarize_telemetry(telemetry,entry["job"],entry["gpu_uuid"])
                if fingerprint(path)!=before:raise ValueError("Original training telemetry not closed")
                family=Path(c["repo"])/"results/p_recipe/training"/entry["run"]/"family_losses.csv"
                rows.append(dict(k=entry["k"],job=entry["job"],node=entry["node"],
                    gpu_uuid=entry["gpu_uuid"],card_type=attempt["card"]["name"],
                    batch_size=32,precision="FP32",samples=3000000,updates=93750,
                    native_seconds=native["seconds"],samples_per_second=3000000/native["seconds"],
                    CUDA_peak_allocated_bytes=native["GPU_peak_bytes"],telemetry=before,
                    family_loss_csv=fingerprint(family),no_new_GPU_samples=True,**hardware))
            cards=[]
            for card in sorted({x["card_type"] for x in rows}):
                values=[x for x in rows if x["card_type"]==card]
                seconds=sum(x["native_seconds"] for x in values)
                duration=sum(x["power_observation_seconds"] for x in values)
                cards.append(dict(card_type=card,batch_size=32,runs=len(values),
                    samples_per_second=sum(x["samples"] for x in values)/seconds,
                    power_time_weighted_mean_watts=sum(x["power_time_weighted_mean_watts"]*x["power_observation_seconds"] for x in values)/duration,
                    native_seconds=seconds,power_observation_seconds=duration))
            result=dict(status="COMPLETE",job=execution_handle(),rows=rows,by_card_type=cards,
                original_I1_method_reused=True,no_new_GPU_samples=True,
                window="Original training including original VAL/checkpoints; later readout/FT excluded")
            atomic_json(output/"hardware.json",result)
            cols=list(cards[0])
            with (output/"by_card_type.csv").open("x",newline="") as stream:
                writer=csv.DictWriter(stream,fieldnames=cols);writer.writeheader();writer.writerows(cards)
                stream.flush();os.fsync(stream.fileno())
            atomic_json(output/"summary.json",dict(status="COMPLETE",job=execution_handle(),runs=len(rows)))
            return 0

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",type=Path,required=True)
    a=p.parse_args()
    if os.environ.get("CUDA_VISIBLE_DEVICES")!="":raise ValueError("CPU-only hardware aggregation required")
    raise SystemExit(run(json.loads(a.configuration.read_text())))
