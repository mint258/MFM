"""Run a registered D arm and its final native readouts; defer bootstrap to CPU.

The submitter owns preregistration, P-freeze/9M dependencies, conditional arm
decisions and continuous storage admission. This entry point submits no jobs.
It reuses the training and evaluation adapters rather than a second loop.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform
import threading


def final_readout(configuration, checkpoint_resolver):
    samples = configuration["samples"]
    if tuple(configuration.get("evaluation_samples", (samples,))) != (samples,):
        raise ValueError("D uses only its registered final downstream readout endpoint")
    return dict(configuration, checkpoint=str(checkpoint_resolver(configuration, samples)),
        output=str(Path(configuration["output"]) / "readout"),
        features=str(Path(configuration["output"]) / ("features_" + str(samples))),
        persist_features=configuration.get("persist_final_features", False), store=configuration["readout_store"],
        reference_manifest=configuration["reference_manifest"])


def run(configuration, *, trainer=None, evaluator=None, checkpoint_resolver=None,
        publish=None):
    from .training import prepare_runtime
    if not configuration.get("d_recipe", {}).get("enabled", False):
        raise ValueError("This entry point requires the explicit D adapter")
    configuration = prepare_runtime(configuration)
    # Resolve required readout inputs before any training is started.
    if not configuration.get("readout_store") or not configuration.get("reference_manifest"):
        raise ValueError("Explicit existing development store and frozen random reference required")
    samples = configuration["samples"]
    if tuple(configuration.get("evaluation_samples", (samples,))) != (samples,):
        raise ValueError("D uses only its registered final downstream readout endpoint")
    if trainer is None:
        from .training import train as trainer
    if evaluator is None:
        from .evaluate import run as evaluator
    if checkpoint_resolver is None:
        from tools.p_recipe.checkpoint_paths import evaluation_checkpoint as checkpoint_resolver
    if publish is None:
        publish = publish_summary
    summary = closed_training_summary(configuration)
    if summary is not None and summary.get("status") == "COMPLETE":
        return summary
    if summary is None:
        summary = trainer(configuration)
    if summary.get("status") == "HANDOFF_SAVED":
        return summary
    if (summary.get("status") not in ("TRAINING_COMPLETE_EVALUATION_PENDING",
            "GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS", "COMPLETE")
            or summary.get("samples") != samples):
        raise ValueError("Final readouts require the completed registered training budget")
    readout = final_readout(configuration, checkpoint_resolver)
    # The existing producer owns its closed manifest. An infrastructure resume
    # consumes it instead of extracting H0 or fitting the same probes again.
    if not (Path(readout["output"]) / "predictions.json").is_file():
        evaluator(readout)
    result = dict(summary, status="GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS",
        statistics_complete=False, predictions=str(Path(readout["output"]) / "predictions.json"))
    publish(Path(configuration["output"]) / "summary.json", result, configuration)
    return result


def closed_training_summary(configuration):
    path = Path(configuration["output"]) / "summary.json"
    if not path.is_file():
        return None
    summary = json.loads(path.read_text(encoding="utf-8"))
    if summary.get("status") not in ("TRAINING_COMPLETE_EVALUATION_PENDING",
            "GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS", "COMPLETE"):
        return None
    if summary.get("samples") != configuration["samples"] or summary.get("run") != configuration["run"]:
        raise ValueError("Closed training summary belongs to a different registered run or endpoint")
    original = json.loads((path.parent / "configuration.json").read_text(encoding="utf-8"))
    if original["d_recipe"]["scientific_binding"] != configuration["d_recipe"]["scientific_binding"]:
        raise ValueError("Closed training scientific configuration differs; do not rerun or relabel it")
    return summary


@contextmanager
def gpu_telemetry(configuration, *, module=None):
    """Reuse the existing whole-card sampler with the D results prefix."""
    from .training import ResultRoot
    if module is None:
        from tools.p_recipe import native_run as module
    original = module.REPO
    stop = threading.Event()
    telemetry = dict(configuration, training_budget=configuration["samples"],
        gpu_uuid=os.environ["CUDA_VISIBLE_DEVICES"].split(",")[0])
    def capture():
        while not stop.is_set():
            try:
                module.REPO = ResultRoot(Path(__file__).resolve().parents[2])
                module.record_gpu_telemetry(telemetry)
            except Exception as error:
                print("D GPU telemetry unavailable: " + str(error), flush=True)
            finally:
                # The sampler can outlive a bounded join during an NFS stall.
                # Keep its D prefix until that call has actually returned.
                module.REPO = original
            stop.wait(30)
    monitor = threading.Thread(target=capture, daemon=True)
    try:
        monitor.start()
        yield
    finally:
        stop.set()
        monitor.join(timeout=12)


def publish_summary(path, value, configuration):
    from workflows.data_d_descriptors.storage import guard
    guard(path.parent, peak_bytes=configuration["storage_peak_bytes"])
    pending = Path(str(path) + ".partial")
    with pending.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    arguments = parser.parse_args()
    configuration = json.loads(Path(arguments.configuration).read_text(encoding="utf-8"))
    node = platform.node().split(".")[0]
    allowed = {"compute-0-" + str(index) for index in (*range(8), 20, 22)}
    native = configuration.get("execution") == "native_SSH"
    if node not in allowed or (native and node not in ("compute-0-20", "compute-0-22")):
        raise RuntimeError("D GPU entry requires an allowed node; native execution is limited to 20/22")
    if not native and not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Slurm execution requires its real job allocation")
    from workflows.data_d_descriptors.storage import guard
    guard(Path(configuration["output"]).parent, peak_bytes=configuration["storage_peak_bytes"])
    with gpu_telemetry(configuration):
        result = run(configuration)
    print(json.dumps(result, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
