"""Finish the existing molecular bootstrap on CPU after D GPU readouts close."""
import argparse
import json
import os
from pathlib import Path
import platform

from .train import closed_training_summary, publish_summary
from .training import prepare_runtime


def finalize(configuration, *, scorer=None, publish=None):
    configuration = prepare_runtime(configuration)
    if not configuration["d_recipe"].get("enabled", False):
        raise ValueError("D statistics require the explicit D adapter")
    output = Path(configuration["output"])
    summary = closed_training_summary(configuration)
    if summary is None:
        raise ValueError("Wait for the registered GPU training and final readouts to close")
    if summary.get("status") == "COMPLETE" and summary.get("statistics_complete") is True:
        return summary
    if summary.get("status") != "GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS":
        raise ValueError("Wait for the registered GPU training and final readouts to close")
    if scorer is None:
        from .evaluate import score as scorer
    if publish is None:
        publish = publish_summary
    readout = output / "readout"
    if not (readout / "scores.json").is_file():
        scorer(dict(configuration, output=str(readout)))
    result = dict(summary, status="COMPLETE", statistics_complete=True,
                  scores=str(readout / "scores.json"))
    publish(output / "summary.json", result, configuration)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    arguments = parser.parse_args()
    node = platform.node().split(".")[0]
    allowed = {"compute-0-" + str(index) for index in range(8, 20)}
    if node not in allowed or not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("D final statistics require an allocated CPU node 8-19")
    if os.environ.get("CUDA_VISIBLE_DEVICES"):
        raise RuntimeError("D CPU statistics must have no visible CUDA devices")
    configuration = json.loads(Path(arguments.configuration).read_text(encoding="utf-8"))
    from workflows.data_d_descriptors.storage import guard
    guard(Path(configuration["output"]), peak_bytes=configuration["storage_peak_bytes"])
    print(json.dumps(finalize(configuration), allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
