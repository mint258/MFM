"""Descriptive D checkpoint readouts through P's existing configuration builder.

Metadata only until actual completed9M sources are supplied. Original9M
endpoint outputs are reused. The caller binds separate GPU/CPU admission.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import re
import sys


AUTHORITY = "docs/d_recipe/USER_DIRECTIVE_20261123B.md"
NATIVE_ARMS = ("9M-D-R0", "9M-D-final")


def points(source):
    if (source.get("condition") != "D" or source.get("arm") not in NATIVE_ARMS
            or source.get("samples") != 9000000 or source.get("seed") != 0):
        raise ValueError("Original registered D seed0 9M source required")
    if source.get("molecule_scaling"):
        selection = source.get("d_explicit_molecule_selection", {})
        if source.get("scaling_authority") != AUTHORITY or selection.get("P_arm") not in ("T5", "T6"):
            raise ValueError("Only the two authorized actual P molecule subsets")
        return (3000000, 6000000)
    return tuple(range(1000000, 9000000, 1000000))


def require_confirmations(closed):
    # Stage1 is already an adopted R1 transfer in this study, hence two native
    # confirmations are required before the supplemental readout group starts.
    if set(closed) != set(NATIVE_ARMS):
        raise ValueError("Both native9M confirmations must be actually complete")
    for arm, record in closed.items():
        if (record.get("arm") != arm or record.get("seed") != 0
                or record.get("samples") != 9000000 or not record.get("run")
                or record.get("status") != "COMPLETE" or record.get("statistics_complete") is not True):
            raise ValueError("Original native9M training/readout/statistics must finish first")


def original_builder():
    path = Path("/share/home/zixiao/descriptor_analysis/MFM_p_recipe/tools/p_recipe/budget_curve.py")
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("d_original_p_budget_curve", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_readout(source, samples, *, closed_confirmations, source_summary,
                 source_configuration, output_root, resolver, module=None):
    require_confirmations(closed_confirmations)
    allowed = points(source)
    if (not source.get("molecule_scaling")
            and source["run"] != closed_confirmations[source["arm"]]["run"]):
        raise ValueError("Native source differs from the completed registered confirmation")
    if samples not in allowed:
        raise ValueError("Only registered intermediate points; reuse the original9M endpoint")
    if (source_summary.get("status") != "COMPLETE"
            or source_summary.get("statistics_complete") is not True
            or source_summary.get("samples") != 9000000
            or source_summary.get("run") != source["run"]):
        raise ValueError("This actual source must have completed its whole9M schedule")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", source["run"]):
        raise ValueError("Source run cannot escape its result scope")
    module = original_builder() if module is None else module
    previous = module.expected_points, module.AUTHORITY, module.STORE
    row = dict(arm=source["arm"], samples=samples, layer=6, representation="H0",
               id=source["run"] + "_" + str(samples), source_configuration=source_configuration)
    try:
        module.expected_points = lambda: [(source["arm"], n) for n in allowed]
        module.AUTHORITY = AUTHORITY
        module.STORE = Path(source["readout_store"])
        c = module.make_configuration(source, row, output_root=output_root, resolver=resolver)
    finally:
        module.expected_points, module.AUTHORITY, module.STORE = previous
    run = source["run"] + "_budget_" + str(samples)
    output = Path(output_root) / run
    c.update(run=run, condition="D", study_revision=source["study_revision"],
        output=str(output), features=str(output / "features_not_persisted"),
        persist_features=False, statistics_backend="ssh_cpu", readout_seed=0,
        reference_manifest=source["reference_manifest"], authority=AUTHORITY,
        source_seed=0, resource_admission_pending=True, selection_change_allowed=False,
        source_scientific_binding=deepcopy(source["d_recipe"]["scientific_binding"]),
        comparison_scope="Within original9M cosine trajectory; not a completed3M budget model")
    return c
