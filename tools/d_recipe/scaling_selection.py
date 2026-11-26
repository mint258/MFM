"""Use the actual P subset in D, retaining P order and the original VAL population.

Default off. This module never chooses new molecules, fits normalization, reads
weights, submits jobs or writes files. Root supplies the original P list and
publishes the returned intersection only after D-final is frozen.
"""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

import numpy as np


COUNTS = {"T5": 250000, "T6": 500000}
AUTHORITY = "docs/d_recipe/USER_DIRECTIVE_20261123B.md"


def _indices(values):
    result = np.asarray(values)
    if (result.ndim != 1 or result.dtype.kind not in "iu" or not len(result)
            or np.any(result < 0) or len(np.unique(result)) != len(result)):
        raise ValueError("A nonempty unique integer molecular-index list is required")
    return result


def actual_intersection(p_selected, d_train):
    p_selected, d_train = _indices(p_selected), _indices(d_train)
    result = p_selected[np.isin(p_selected, d_train)]
    if not len(result):
        raise ValueError("Actual P subset has no original D TRAIN molecules")
    return result.copy()


def plan_subset(best, cold_final, p_source, p_selected, d_train, *, output_root, run_prefix):
    if best.get("status") != "FROZEN" or best.get("recipe_frozen") is not True:
        raise ValueError("D-final must be frozen before molecule scaling")
    if (cold_final.get("arm") != "9M-D-final" or cold_final.get("samples") != 9000000
            or cold_final.get("seed") != 0 or cold_final.get("condition") != "D"
            or cold_final.get("resource_admission_pending") is not True
            or any(cold_final.get(key) for key in ("resume", "handoff_request", "safe_exit_control"))
            or cold_final.get("subset_molecules") is not None
            or cold_final["d_recipe"]["library"] != best["library"]):
        raise ValueError("Use the frozen full-population cold9M final plan, without old runtime state")
    arm = p_source.get("arm")
    if (arm not in COUNTS or p_source.get("subset_molecules") != COUNTS[arm]
            or p_source.get("subset_seed") != 20261112
            or not p_source.get("actual_selected_indices") or not p_source.get("configuration")
            or not p_source.get("corpus") or p_source["corpus"] != cold_final.get("corpus")):
        raise ValueError("An actual frozen P T5/T6 selected-list source is required")
    p_selected = _indices(p_selected)
    if len(p_selected) > COUNTS[arm]:
        raise ValueError("Actual P list exceeds its registered molecule budget")
    selected = actual_intersection(p_selected, d_train)
    output = Path(output_root) / ("P_" + arm + "_molecules_" + str(COUNTS[arm]))
    selection = dict(indices=str(output / "selected_molecule_indices.npy"),
        P_arm=arm, P_configuration=p_source["configuration"],
        P_actual_selected_indices=p_source["actual_selected_indices"],
        P_requested_molecules=COUNTS[arm], P_actual_molecules=len(p_selected),
        subset_seed=20261112, intersection_molecules=len(selected),
        policy="actual_P_order_intersect_original_D_TRAIN", new_resampling=False)
    c = deepcopy(cold_final)
    c.update(run=run_prefix + "D_final_P_" + arm + "_molecules_seed0_9M",
        output=str(output / "training"), subset_molecules=None,
        d_explicit_molecule_selection=selection, molecule_scaling=True,
        scaling_authority=AUTHORITY, descriptive_only=True,
        selection_change_allowed=False, resource_admission_pending=True,
        evaluation_samples=[9000000], source_frozen_arm=best["arm"],
        persist_final_features=False)
    c["clip_calibration"] = dict(calibration_samples=150000,
        window_start_samples=60000, initial_clip=281.7, quantile=.99,
        sample_axis="optimizer_step_start")
    c["d_recipe"]["scientific_binding"]["molecule_selection"] = deepcopy(selection)
    return dict(schema="D_P_ACTUAL_MOLECULE_INTERSECTION_PLAN_V1",
        status="REQUIRES_GUARDED_INTERSECTION_PUBLICATION_AND_RUNTIME_ADMISSION",
        configuration=c, indices=selected, frozen_readout_samples=[3000000, 6000000, 9000000],
        full_finetune_samples=[9000000], jobs_submitted=False)


@contextmanager
def installed_selection(configuration, module, *, loader=np.load):
    selection = configuration.get("d_explicit_molecule_selection")
    if selection is None:
        yield
        return
    if (configuration.get("scaling_authority") != AUTHORITY
            or configuration.get("molecule_scaling") is not True
            or configuration.get("subset_molecules") is not None
            or selection.get("new_resampling") is not False
            or selection.get("policy") != "actual_P_order_intersect_original_D_TRAIN"):
        raise ValueError("Only the authorized actual-intersection selection may override TRAIN")
    if selection != configuration["d_recipe"]["scientific_binding"].get("molecule_selection"):
        raise ValueError("Molecule selection differs from its scientific checkpoint binding")
    indices = _indices(loader(selection["indices"], allow_pickle=False))
    if len(indices) != selection["intersection_molecules"]:
        raise ValueError("Published actual TRAIN selection count differs from the frozen plan")
    previous = module.dataset_configuration

    def selected_reader(config, *, validation=False):
        result = previous(config, validation=validation)
        return result if validation else dict(result, indices=indices)

    try:
        module.dataset_configuration = selected_reader
        yield
    finally:
        module.dataset_configuration = previous
