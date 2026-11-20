"""Registered layers3-6 R1/R3 diagnostics from the one cached native forward."""
import argparse
import json
from pathlib import Path

from .diagnostic_forward import registered_endpoint
from .evaluate import existing_evaluator
from .layer_features import cached_features_only, cached_layer_configuration


def _context(configuration, cpu, guard):
    from .resources import DJointGuard, execution_site
    execution_site(configuration, cpu=cpu)
    native = configuration["readout_configuration"]
    registered_endpoint(dict(native, adopted_arm=configuration.get("adopted_arm")))
    guard = DJointGuard(configuration) if guard is None else guard
    output = Path(configuration["output"])
    guard.check(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "summary.json"
    binding = dict(readout_configuration=native, adopted_arm=configuration.get("adopted_arm"))
    state = json.loads(path.read_text()) if path.exists() else None
    if state is not None and state["binding"] != binding:
        raise ValueError("Diagnostic layer state belongs to a different registered condition")
    return native, output, path, binding, state, guard


def _publish(path, payload, guard):
    guard.check(path.parent)
    temporary = path.with_suffix(".partial")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(path)


def run_gpu(configuration, *, evaluator=None, guard=None):
    native, output, path, binding, state, guard = _context(configuration, False, guard)
    if state is not None and state["status"] in ("GPU_LAYER_READOUTS_COMPLETE_WAITING_CPU", "COMPLETE"):
        return state
    original_predictions = Path(native["output"]) / "predictions.json"
    if not original_predictions.is_file():
        raise FileNotFoundError("The original final-layer readout must close first")
    state = dict(binding=binding, status="PREPARING", layers={"6": dict(
        predictions=str(original_predictions), reused_main_readout=True)}, decision_input=False)
    _publish(path, state, guard)
    with existing_evaluator(evaluator) as module, cached_features_only(module):
        for layer in (3, 4, 5):
            target = output / ("layer" + str(layer))
            c = cached_layer_configuration(native, layer, output=target)
            if not (target / "predictions.json").is_file():
                guard.check(target)
                module.run(c)
            state["layers"][str(layer)] = dict(predictions=str(target / "predictions.json"),
                                              reused_main_readout=False)
    state["status"] = "GPU_LAYER_READOUTS_COMPLETE_WAITING_CPU"
    _publish(path, state, guard)
    return state


def run_cpu(configuration, *, evaluator=None, guard=None):
    native, output, path, binding, state, guard = _context(configuration, True, guard)
    if state is not None and state["status"] == "COMPLETE":
        return state
    if state is None or state["status"] != "GPU_LAYER_READOUTS_COMPLETE_WAITING_CPU":
        raise ValueError("Wait for the registered cached-layer readouts")
    main_score = Path(native["output"]) / "scores.json"
    if not main_score.is_file():
        raise FileNotFoundError("Reuse the main final-layer CPU statistics; do not resample them")
    state["layers"]["6"]["scores"] = str(main_score)
    with existing_evaluator(evaluator) as module:
        for layer in (3, 4, 5):
            predictions = Path(state["layers"][str(layer)]["predictions"])
            scores = predictions.parent / "scores.json"
            if not scores.is_file():
                guard.check(scores.parent)
                module.score(predictions, native["reference_manifest"], output / "layer_scores.csv")
            state["layers"][str(layer)]["scores"] = str(scores)
    state.update(status="COMPLETE", statistics_dtype="float64",
                 bootstrap=dict(repetitions=1000, seed=20261025, unit="molecule"),
                 encoder_forward_repeated=False, ordered_layers=[3, 4, 5, 6])
    _publish(path, state, guard)
    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    arguments = parser.parse_args()
    configuration = json.loads(Path(arguments.configuration).read_text())
    phase = configuration["phase"]
    if phase not in ("gpu", "cpu"):
        raise ValueError("Use a separate registered GPU or CPU diagnostic phase")
    print(json.dumps((run_gpu if phase == "gpu" else run_cpu)(configuration)))
