"""Opt-in section-5 LightGBM over the same native development members.

Use the existing C1 default model (seed20261025, no tuning). The caller
provides the optimization molecule IDs from the native B/C readout metadata;
this adapter never chooses another split or refits on held-out molecules.
"""
import numpy as np

from .dev_descriptor_readouts import attach_descriptors


def _features(rows, fields, value_source, member_keys):
    attached = attach_descriptors(rows, fields, value_source=value_source, member_keys=member_keys)
    width = len(fields.fields)
    packed = np.stack([row.graph_features.detach().cpu().numpy() for row in attached])
    raw, valid = packed[:, :width], packed[:, width:].astype(bool)
    if not np.isfinite(raw[valid]).all():
        raise ValueError("Observed LightGBM descriptors must be finite")
    # Existing C1 uses native LightGBM missing handling, without imputation.
    return np.where(valid, raw, np.nan)


def run_lightgbm_probe(train, validation, task, train_descriptors, validation_descriptors, *,
                       optimization_molecule_uids, descriptor_value_source, n_jobs,
                       train_member_keys=None, validation_member_keys=None, model_factory=None):
    from phychem_mfm.phase1.v3_dev_evaluation import _validate_molecules, _prediction
    if task.output_level != "graph" or task.error_metric != "mae":
        raise ValueError("The seven primary development tasks require graph regression")
    if type(n_jobs) is not int or n_jobs < 1:
        raise ValueError("Explicit demand-based positive CPU count required")
    train = _validate_molecules(train, task)
    validation = _validate_molecules(validation, task)
    train_ids = {row.molecule_uid for row in train}
    validation_ids = {row.molecule_uid for row in validation}
    selected = set(optimization_molecule_uids)
    if not selected or not selected <= train_ids or train_ids & validation_ids:
        raise ValueError("Existing native optimization TRAIN scope required without validation overlap")
    if tuple(train_descriptors.fields) != tuple(validation_descriptors.fields):
        raise ValueError("Identical TRAIN-frozen descriptor field order required")
    x_train = _features(train, train_descriptors, descriptor_value_source, train_member_keys)
    x_validation = _features(validation, validation_descriptors, descriptor_value_source, validation_member_keys)
    fit_indices, targets = [], []
    for index, row in enumerate(train):
        if row.molecule_uid in selected and bool((row.candidate_mask & row.supervision_mask)[0]):
            fit_indices.append(index)
            targets.append(float(row.targets[0]))
    if not targets:
        raise ValueError("No observed native optimization TRAIN targets")
    if model_factory is None:
        from lightgbm import LGBMRegressor
        model_factory = LGBMRegressor
    # Same learning defaults as benchmark_evaluation/c1_d_lightgbm_moleculeace.sbatch.
    # n_jobs is solely the allocated CPU count; no early stop or parameter search.
    model = model_factory(random_state=20261025, n_jobs=n_jobs, verbosity=-1)
    model.fit(x_train[fit_indices], np.asarray(targets, dtype=np.float64))
    values = np.asarray(model.predict(x_validation), dtype=np.float64)
    prediction = _prediction(task, validation, values)
    metadata = dict(model="LightGBM", seed=20261025, model_parameters=model.get_params(),
        descriptor_fields=list(train_descriptors.fields), descriptor_value_source=descriptor_value_source,
        optimization_molecule_uids=sorted(selected), internal_molecule_uids=sorted(train_ids - selected),
        fit_source_record_uids=[train[i].source_member_uid or train[i].molecule_uid for i in fit_indices],
        fit_records=len(fit_indices), feature_count=x_train.shape[1],
        feature_missing_policy="native_LightGBM_NaN_no_imputation", descriptor_statistics_refitted=False,
        descriptor_loss_clipping=False, hyperparameter_search=False, refit_all_train=False,
        validation_used_for_fit=False, source_store_values_modified=False, encoder_updated=False)
    return prediction, metadata, model
