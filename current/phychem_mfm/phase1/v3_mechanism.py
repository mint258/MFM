"""Taskbook-v3 report-only functional-group probes on existing X/z caches.

Canonical SMARTS and native TRAIN structure mappings are required external inputs.
This producer never encodes a checkpoint or opens downstream target values.
"""
from __future__ import annotations

import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .v3_dev_panel import ALLOWED_ROLES, molecule_folds


STRATA = (('heavy_atoms_le20', 0, 20), ('heavy_atoms_21_35', 21, 35),
          ('heavy_atoms_gt35', 36, None))


def canonical_patterns(document):
    from rdkit import Chem
    if not document.get('source'):
        raise ValueError('The existing data-line SMARTS source must be named')
    rows = document['groups']
    if len(rows) != 28 or len({row['id'] for row in rows}) != 28:
        raise ValueError('Exactly the existing 28 distinct functional groups are required')
    result = []
    for row in rows:
        query = Chem.MolFromSmarts(row['smarts'])
        if query is None:
            raise ValueError('Invalid canonical SMARTS: ' + row['id'])
        result.append((row['id'], query))
    return result


def structure_records(document):
    if document.get('source_population') != 'TRAIN' or not document.get('source'):
        raise ValueError('An explicit source-bound TRAIN structure map is required')
    result = {}
    for row in document['records']:
        if row['role'] not in ALLOWED_ROLES:
            raise ValueError('Structure map includes an excluded source role')
        key = row['dataset_id'], row['member_index']
        if key in result:
            raise ValueError('Duplicate native structure member')
        result[key] = row
    return result


def feature_population(view, payload, structures, patterns, *, with_z):
    """Join selected TRAIN cache rows to the canonical bonded structure once."""
    from rdkit import Chem
    cached = {r['member_index']: r for r in payload['records']}
    if len(cached) != len(payload['records']):
        raise ValueError('Duplicate cached native member')
    populations = {}
    labels = {}
    for role in ALLOWED_ROLES:
        rows = []
        for index in view.view(role):
            if index not in cached:
                continue  # same unavailable-geometry omissions as the frozen panel
            feature = cached[index]
            structure = structures[view.dataset_id, index]
            group = view.molecule_group(index)
            if (structure['role'] != role or structure['full_inchikey'] != group
                    or feature['molecule_uid'] != structure['member_uid']):
                raise ValueError('TRAIN role, full molecule or native cache identity differs')
            if group not in labels:
                mol = Chem.MolFromSmiles(structure['smiles'])
                if mol is None or Chem.MolToInchiKey(mol) != group:
                    raise ValueError('Bonded structure and native full-molecule identity differ')
                labels[group] = (np.array([mol.HasSubstructMatch(q) for _, q in patterns],
                                          dtype=np.int64), int(mol.GetNumHeavyAtoms()))
            x = feature['h0'].detach().cpu().numpy()
            if x.ndim != 2 or not len(x) or not np.isfinite(x).all():
                raise ValueError('Frozen atom features are unavailable')
            values = {'mean_H': x.astype(np.float64).mean(0)}
            if with_z:
                z = feature.get('z')
                if z is None:
                    raise ValueError('A3 z must be supplied by the same existing cache pass')
                values['z'] = z.detach().cpu().numpy().astype(np.float64).reshape(-1)
                if not np.isfinite(values['z']).all():
                    raise ValueError('Nonfinite frozen z')
            y, heavy = labels[group]
            rows.append(dict(group=group, member_uid=feature['molecule_uid'],
                             member_index=index, features=values, y=y, heavy_atoms=heavy))
        populations[role] = rows
    if not all(populations.values()):
        raise ValueError('Both original TRAIN inner populations must be available')
    if ({r['group'] for r in populations['train']}
            & {r['group'] for r in populations['train_inner_validation']}):
        raise ValueError('Full-molecule group leakage across TRAIN inner roles')
    return populations


def _fit_prediction(x, y, held_x, alpha):
    from sklearn.linear_model import LogisticRegression
    if len(np.unique(y)) != 2:
        return None, 'optimization_single_class'
    center, scale = x.mean(0), x.std(0)
    scale[scale < 1e-12] = 1.0
    model = LogisticRegression(C=1.0/alpha, solver='liblinear', max_iter=1000,
                               tol=1e-4, random_state=0)
    model.fit((x-center)/scale, y)
    if int(np.max(model.n_iter_)) >= model.max_iter:
        return None, 'solver_not_converged'
    prediction = model.decision_function((held_x-center)/scale)
    if not np.isfinite(prediction).all():
        return None, 'nonfinite_prediction'
    return prediction, None


def _auc(y, scores):
    from sklearn.metrics import roc_auc_score
    return None if len(np.unique(y)) != 2 else float(roc_auc_score(y, scores))


def logistic_probe(train, validation, group_column, representation, *, alphas, folds, seed):
    """Select L2 strength on exactly R1's molecule folds; report held-out strata."""
    x = np.stack([r['features'][representation] for r in train])
    vx = np.stack([r['features'][representation] for r in validation])
    y = np.array([r['y'][group_column] for r in train])
    vy = np.array([r['y'][group_column] for r in validation])
    assignment = molecule_folds([r['group'] for r in train], folds=folds, seed=seed)
    fold_ids = np.array([assignment[r['group']] for r in train])
    scores, failures = {}, {}
    for alpha in alphas:
        values, reasons = [], []
        for fold in range(folds):
            fit, held = fold_ids != fold, fold_ids == fold
            prediction, reason = _fit_prediction(x[fit], y[fit], x[held], alpha)
            auc = None if prediction is None else _auc(y[held], prediction)
            values.append(None if auc is None else 1.0-auc)
            reasons.append(reason or ('validation_single_class' if auc is None else None))
        scores[str(alpha)], failures[str(alpha)] = values, reasons
    usable = {float(a): float(np.mean(v)) for a, v in scores.items()
              if all(x is not None for x in v)}
    detail = dict(inner_cv_errors=scores, unavailable_fold_reasons=failures,
                  folds=folds, seed=seed, fit_scope='train',
                  validation_role='train_inner_validation',
                  normalization_fit_scope='each_optimization_fold_only',
                  objective='sum_binary_logloss + alpha/2 * L2; liblinear intercept convention',
                  class_weight=None)
    if not usable:
        return dict(status='UNAVAILABLE', reason='no_strength_has_five_available_fold_metrics',
                    selected_alpha=None, strata=None, **detail)
    chosen = min(usable, key=lambda a: (usable[a], a))
    prediction, reason = _fit_prediction(x, y, vx, chosen)
    if prediction is None:
        return dict(status='UNAVAILABLE', reason=reason, selected_alpha=chosen,
                    strata=None, **detail)
    heavy = np.array([r['heavy_atoms'] for r in validation])
    strata = {}
    for name, lower, upper in STRATA:
        keep = (heavy >= lower) & (True if upper is None else heavy <= upper)
        auc = _auc(vy[keep], prediction[keep])
        strata[name] = dict(auroc=auc, records=int(keep.sum()),
            molecule_groups=len({r['group'] for r, k in zip(validation, keep) if k}),
            positives=int(vy[keep].sum()), negatives=int(keep.sum()-vy[keep].sum()),
            unavailable_reason=None if auc is not None else 'fewer_than_two_classes')
    return dict(status='COMPLETE', selected_alpha=chosen, strata=strata, **detail)


def run(config, *, store_factory):
    """CPU producer; use the original per-dataset panel roles, never pooled splits."""
    import os
    import socket
    import torch
    from .v3_dev_membership import GroupedTrainingView
    from .v3_latent_training import TrainingHistory
    if os.getuid() != 1278 or socket.gethostname().split('.')[0] != 'compute-0-20':
        raise ValueError('Run this report-only CPU producer on the designated node20')
    if config.get('selection_use') is not False:
        raise ValueError('Mechanism probes are report-only')
    output = Path(config['output'])
    output.mkdir(parents=True, exist_ok=True)
    definitions = json.loads(Path(config['smarts_definitions']).read_text())
    structures = structure_records(json.loads(Path(config['structure_map']).read_text()))
    patterns = canonical_patterns(definitions)
    binding = dict(configuration=config, canonical_groups=definitions)
    binding_path = output/'configuration.json'
    if binding_path.exists():
        if json.loads(binding_path.read_text()) != binding:
            raise ValueError('Existing mechanism output belongs to different inputs')
    else:
        binding_path.write_text(json.dumps(binding, indent=2, allow_nan=False)+'\n')
    panel = json.loads(Path('configs/dev_panel_v2.json').read_text())
    policy = panel['readouts']['ridge']
    store = store_factory(config['store'])
    workers = min(16, int(os.environ.get('SLURM_CPUS_PER_TASK', '16')))
    owner = TrainingHistory(output, dict(stage='T1_mechanism', condition='P',
        selection_use=False, source_roles=list(ALLOWED_ROLES)))
    completed = False
    try:
        results = {}
        for arm in ('A0', 'A3'):
            evaluation = Path(config[arm + '_evaluation_output'])
            done = json.loads((evaluation/'producer_complete.json').read_text())
            manifest = json.loads((evaluation/'predictions.json').read_text())
            source = json.loads((evaluation/'configuration.json').read_text())
            if (done.get('statistics_complete') is not True
                    or manifest['arm'] != arm or manifest['stage'] != 'T1'
                    or manifest['condition'] != 'P'
                    or manifest['source_roles'] != list(ALLOWED_ROLES)):
                raise ValueError('Use the completed original T1 P evaluation for this arm')
            checkpoint = Path(source['checkpoint'])
            cache = Path(source['cache_root'])/(checkpoint.parent.name+'__'+checkpoint.stem)
            results[arm] = {}
            for dataset in sorted({t['dataset_id'] for t in panel['tasks']}):
                view = GroupedTrainingView(store, dataset,
                    'official' if dataset == 'expansionrx' else '0', store.group_map)
                payload = torch.load(cache/(dataset+'.pt'), map_location='cpu', weights_only=True)
                populations = feature_population(view, payload, structures, patterns, with_z=arm=='A3')
                train, held = (populations[role] for role in ALLOWED_ROLES)
                results[arm][dataset] = {}
                for representation in ('mean_H', 'z'):
                    if arm == 'A0' and representation == 'z':
                        results[arm][dataset][representation] = dict(status='NOT_APPLICABLE',
                            reason='A0 has no latent module or molecular z')
                        continue
                    def produce_cell(item):
                        column, (group_id, _) = item
                        cell_path = output/'cells'/arm/dataset/representation/(str(column)+'.json')
                        if cell_path.exists():
                            return group_id, json.loads(cell_path.read_text())
                        cell = logistic_probe(train, held, column, representation,
                            alphas=policy['alphas'], folds=policy['inner_folds'], seed=policy['seed'])
                        cell.update(group_id=group_id, group_column=column)
                        cell_path.parent.mkdir(parents=True, exist_ok=True)
                        cell_path.write_text(json.dumps(cell, indent=2, allow_nan=False)+'\n')
                        return group_id, cell
                    rows = {}
                    # Independent canonical groups share immutable cache arrays;
                    # the sbatch wrapper fixes BLAS/OpenMP to one thread per fit.
                    with ThreadPoolExecutor(max_workers=workers) as executor:
                        for group_id, cell in executor.map(produce_cell, enumerate(patterns)):
                            rows[group_id] = cell
                            owner.run.log({'mechanism/completed_cells':len(rows),
                                           'mechanism/available':int(cell['status']=='COMPLETE')})
                    results[arm][dataset][representation] = rows
        report = dict(schema='MODEL_V3_MECHANISM_V1', selection_use=False,
            source_roles=list(ALLOWED_ROLES), downstream_TEST_read=False,
            canonical_smarts_source=definitions['source'],
            smarts_definitions=str(config['smarts_definitions']),
            structure_map=str(config['structure_map']), results=results,
            feature_source='same completed T1 evaluation cache; no reencoding',
            population='original panel members and per-dataset TRAIN inner split; native records retained',
            regularization=policy, checkpoint_evaluation_outputs={
                arm:config[arm+'_evaluation_output'] for arm in ('A0','A3')})
        (output/'summary.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
        completed = True
        return report
    finally:
        owner.close(completed)
