"""User-requested read-only exports and isolated frozen-feature diagnostic replay.

Never calls a producer/scorer, encoder forward, bootstrap, or CV search. Legacy
R1 predictions not persisted by v1 are reconstructed with its saved chosen alpha;
the recorded errors and CV arrays are copied verbatim and never recomputed.
"""
import argparse
from dataclasses import replace
import csv
import gzip
import inspect
import json
import os
from pathlib import Path
import socket
import tarfile
import time

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import torch

from v2_evaluate_s import RememberedStore
from v2_archive_wandb import actual_capacity_check
from phychem_mfm.phase1.v2_disk import save_metadata_parquet, save_metadata_json
from phychem_mfm.phase1.v3_dev_evaluation import (
    TaskSpec, task_rows, _arrays, _Ridge, _prediction, error, nonlinear_probe,
)
from phychem_mfm.phase1.v3_dev_evaluation_v2 import BASE, DATASETS, _cached_rows
from phychem_mfm.phase1.v3_latent_evaluation import cached_rows, z_rows
from phychem_mfm.phase1.v3_dev_membership import GroupedTrainingView
from phychem_mfm.phase1 import v3_dev_readouts

PROJECT = Path('/share/home/zixiao/descriptor_analysis')
REPO = PROJECT / 'MFM_model_v3'
CONTROL = PROJECT / 'runs/model_v31_20261105'
LATENT = Path('/lfshome/zixiao/model_v31_20261105/LATENT_V3_20261111')
PART = 3 * 1024**2


def clean_detail(value):
    if isinstance(value, dict):
        return {k: clean_detail(v) for k, v in value.items() if k != 'state_dict'}
    if isinstance(value, (tuple, list)):
        return [clean_detail(v) for v in value]
    if isinstance(value, torch.Tensor):
        return value.tolist()
    return value


def distribution(values):
    values = np.asarray(values, dtype=np.float64)
    q = [0., .01, .05, .25, .5, .75, .95, .99, 1.]
    return dict(count=len(values), mean=float(values.mean()),
                std_population=float(values.std()),
                quantiles={str(p): float(v) for p, v in zip(q, np.quantile(values, q))})


def prediction_rows(packed, native_rows, task, readout, provenance, source):
    sizes = {r.source_member_uid or r.molecule_uid: len(r.h0) for r in native_rows}
    atoms = {r.source_member_uid or r.molecule_uid: r.source_atom_ids.tolist() for r in native_rows}
    ids = packed.get('source_record_uids') or packed['molecule_uids']
    offsets = {}
    output = []
    for i, uid in enumerate(ids):
        atom = None
        if task.output_level == 'atom':
            atom = atoms[uid][offsets.get(uid, 0)]
            offsets[uid] = offsets.get(uid, 0) + 1
        output.append(dict(task=task.task_id, readout=readout,
            molecule_id=packed['molecule_uids'][i], source_member_id=uid,
            atom_id=atom, atom_count=sizes[uid],
            prediction=float(packed['predictions'][i]), truth=float(packed['targets'][i]),
            valid=bool(packed['valid'][i]), role='train_inner_validation',
            prediction_provenance=provenance, source=source))
    return output


def feature_rows(rows, task, n_ref, *, observed_only=False):
    # Match the original feature-normalization population, including masked
    # endpoints: labels do not select the frozen optimization feature subset.
    if observed_only:
        rows=[r for r in rows if bool((r.candidate_mask & r.supervision_mask).any())]
    h_mean = np.stack([r.h0.double().mean(0).numpy() for r in rows])
    h_sum = np.stack([r.h0.double().sum(0).numpy() for r in rows])
    arrays = {'H0_mean': h_mean, 'H0_sum': h_sum,
              'X_atom': np.concatenate([r.h0.numpy() for r in rows]).astype(np.float64),
              'X_R2': np.concatenate((h_mean, h_sum / n_ref), axis=1)}
    if rows[0].graph_features is not None:
        arrays['z'] = np.stack([r.graph_features.double().numpy() for r in rows])
    if observed_only and task.output_level=='atom':
        arrays['X_observed_atom']=np.concatenate([
            r.h0[r.candidate_mask & r.supervision_mask].numpy() for r in rows]).astype(np.float64)
    output = []
    for name, values in arrays.items():
        std = values.std(0)
        threshold = max(1e-12, 1e-4 * float(np.median(std)))
        low = int((std < threshold).sum())
        for dim, (m, s, lo, hi) in enumerate(zip(values.mean(0), std, values.min(0), values.max(0))):
            output.append(dict(task=task.task_id, feature=name, dimension=dim,
                count=len(values), molecule_count=len(rows), mean=float(m), std=float(s),
                minimum=float(lo), maximum=float(hi), low_std_threshold=threshold,
                low_std_dimensions=low, median_std=float(np.median(std)),
                role='train', scope='observed_task_members' if observed_only else 'all_frozen_optimization_members',
                n_ref=float(n_ref)))
    return output


class Export:
    def __init__(self, output, *, resume_static=False):
        self.output = output
        self.files = []
        self.capacity = actual_capacity_check(output)
        self.capacity(2_000_000_000, 2000)
        output.mkdir(parents=True, exist_ok=resume_static)

    def add(self, relative, rows=None, value=None, text=None):
        path = self.output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if rows is not None:
            save_metadata_parquet(pa.Table.from_pylist(rows), path)
        elif text is not None:
            with path.open('x') as stream:
                stream.write(text)
        else:
            save_metadata_json(value, path)
        entry = dict(path=relative, source=str(path), bytes=path.stat().st_size)
        self.files.append(entry)
        return entry

    def status(self, phase, **kwargs):
        # This is producer state, never an independent export readback.
        value = dict(phase=phase, time=time.time(), job=os.environ.get('SLURM_JOB_ID'),
                     files=len(self.files), bytes=sum(f['bytes'] for f in self.files), **kwargs)
        state = CONTROL / 'MODEL_V3_DIAGNOSTICS_20261112.state.json'
        tmp = state.with_suffix('.next')
        tmp.write_text(json.dumps(value) + '\n')
        tmp.replace(state)
        print(json.dumps(value), flush=True)

    def manifest(self, name, **kwargs):
        self.add(name, value=dict(schema='MODEL_V3_READ_ONLY_DIAGNOSTICS_20261112',
            selection_use=False, original_scores_recomputed=False,
            original_training_or_rules_modified=False,
            export_review_or_second_readback_performed=False,
            files=list(self.files), total_bytes=sum(r['bytes'] for r in self.files), **kwargs))


def cells(*, reference_z_only=False):
    if reference_z_only:
        references=[dict(name='random_z_'+profile, stage='reference_z', legacy=None,
                directory=str(LATENT/'readout_cache'/('reference_z_'+profile)),
                cache=str(LATENT/'readout_cache'/('reference_z_'+profile)/'features'))
                for profile in ('pma_k8_write0','lite_k8_write0')]
        references.append(dict(name='random_C1-0_R1_v2_reference',stage='reference_R1',legacy=None,
            directory=str(LATENT/'readout_cache/base_reference_R1'),
            cache=str(BASE/'h0_cache/random__C1-0__three')))
        return references
    c1 = json.loads((REPO / 'results/model_v3_c1_final.json').read_text())['rows']
    output = []
    for row in c1:
        checkpoint = Path(row['checkpoint'])
        output.append(dict(name=row['candidate']+'_'+row['condition'], stage='C1',
            directory=str(Path(row['summary']).parent),
            cache=str(BASE/'h0_cache'/(checkpoint.parent.name+'__'+checkpoint.stem)),
            legacy=json.loads(Path(row['summary']).read_text())['legacy_summary']))
    # One logical random control group retains all three existing matched profiles.
    for candidate in ('C1-0', 'C1-a', 'C1-b'):
        source = next(r for r in output if r['name'] == candidate+'_S')
        output.append(dict(name='random_'+candidate, stage='reference',
            directory=str(BASE/'reference'/candidate),
            cache=str(BASE/'h0_cache'/('random__'+candidate+'__three')),
            legacy=source['legacy']))
    plan = json.loads((CONTROL/'LATENT_V3_20261111/plan.json').read_text())
    for run in plan['runs']:
        directory = Path(run['evaluation_output'])
        if run['stage'] not in ('T0', 'T1') or not (directory/'producer_complete.json').exists():
            continue
        m = json.loads((directory/'predictions.json').read_text())
        checkpoint = Path(m['checkpoint'])
        output.append(dict(name=run['stage']+'_'+run['arm']+'_'+run['condition'],
            stage=run['stage'], directory=str(directory),
            cache=str(LATENT/'readout_cache'/(checkpoint.parent.name+'__'+checkpoint.stem)),
            legacy=json.loads((Path(m['reused_X_summary_directory'])/'summary.json').read_text())['legacy_summary']
                   if m.get('reused_X_summary_directory') else None))
    return output


def original_summaries(cell, manifest):
    directory = Path(cell['directory'])
    result = {p.name: json.loads(p.read_text()) for p in sorted(directory.glob('*summary.json'))}
    if cell.get('legacy'):
        result['legacy_summary_full_unchanged.json'] = json.loads(Path(cell['legacy']).read_text())
    if cell['stage'] == 'reference':
        # Reference native errors were recorded in the matched candidate summaries.
        candidate = BASE/(cell['name'].removeprefix('random_')+'_S_seed0')
        result['recorded_reference_errors_from_matched_summaries'] = {
            p.name: json.loads(p.read_text()) for p in candidate.glob('*_summary.json')}
    if cell['stage'] == 'reference_z':
        arm='T0-3' if 'pma' in cell['name'] else 'T0-4'
        result['recorded_reference_errors_from_original_T0_summaries'] = {
            condition: json.loads((LATENT/('T0_'+arm+'_'+condition+'_seed0')/'dev_eval_v2/R2z_summary.json').read_text())
            for condition in ('S','P')}
    if cell['stage']=='reference_R1':
        result['recorded_reference_errors_from_original_T1_A0_S_R1_summary'] = json.loads(
            (LATENT/'T1_A0_S_seed0/dev_eval_v2/R1_summary.json').read_text())
    result['prediction_manifest_unchanged'] = manifest
    return result


def export_static(exporter, all_cells, views, tasks):
    u0_done = all(c['stage'] in ('reference_z','reference_R1') for c in all_cells)
    for cell in all_cells:
        exporter.capacity(2_000_000_000, 2000)
        directory = Path(cell['directory'])
        manifest = json.loads((directory/'predictions.json').read_text())
        summaries = original_summaries(cell, manifest)
        legacy = summaries.get('legacy_summary_full_unchanged.json')
        details, predicted, features, availability = {}, [], [], []
        for dataset in DATASETS:
            if cell['stage']=='reference_z' and dataset=='cyp_isoform':
                continue
            cache_path = Path(cell['cache'])/(dataset+'.pt')
            # T0 explicitly reuses old frozen X for the two SoM tasks.
            if not cache_path.exists() and cell['stage'] == 'T0':
                condition = cell['name'].rsplit('_', 1)[1]
                c1 = next(c for c in all_cells if c['name'] == 'C1-0_'+condition)
                cache_path = Path(c1['cache'])/(dataset+'.pt')
            payload = torch.load(cache_path, map_location='cpu', weights_only=True)
            cached = cached_rows(payload)
            for task in (t for t in tasks if t.dataset_id == dataset):
                train = task_rows(views[dataset], cached, task, role='train')
                held = task_rows(views[dataset], cached, task, role='train_inner_validation')
                has_z = dataset != 'cyp_isoform' and all(r.z is not None for r in cached)
                z_train = z_rows(train, cached) if has_z else train
                features.extend(feature_rows(z_train, task, payload['n_ref']))
                availability.append(dict(task=task.task_id, z_available=has_z,
                    z_unavailable_reason=None if has_z else 'No molecular z exists in this frozen cache',
                    cache_source=str(cache_path),
                    H0_and_X_note='Native cache h0 is final frozen atom feature X; H0_mean/H0_sum pool it; X_R2=concat(mean,sum/N_ref)'))
                for key, path in manifest['files'].items():
                    if key.rsplit('/', 1)[0] != task.task_id:
                        continue
                    readout = key.rsplit('/', 1)[1]
                    source = torch.load(path, map_location='cpu', weights_only=True)
                    details[key] = dict(source=path, detail=clean_detail(source.get('detail', {})),
                        alias_source=path, original_score_recomputed=False)
                    predicted.extend(prediction_rows(source['prediction'], held, task, readout,
                        'original_persisted_prediction', path))
                # C1/T0 old R1 was score-only. Reconstruct predictions at saved alpha,
                # without CV, error(), compare_panel(), or overwriting any score.
                r1_key = task.task_id+'/R1'
                if r1_key not in manifest['files'] and legacy:
                    label = 'reference' if cell['stage'] == 'reference' else 'candidate'
                    detail = legacy['details'][label+'/'+task.task_id+'/ridge']
                    x, y, mask, _ = _arrays(train, task)
                    model = _Ridge(x[mask], y[mask])
                    values = model.predict(_arrays(held, task)[0], detail['selected_alpha'])
                    p = _prediction(task, held, values)
                    packed = dict(molecule_uids=p.molecule_uids, source_record_uids=p.source_record_uids,
                        targets=p.targets, predictions=p.predictions, valid=p.valid)
                    details[r1_key] = dict(detail=detail, source=cell['legacy'],
                        prediction_status='reconstructed_at_recorded_alpha_original_prediction_not_persisted',
                        original_score_recomputed=False, cv_rerun=False)
                    predicted.extend(prediction_rows(packed, held, task, 'R1',
                        'reconstructed_from_cache_at_original_recorded_alpha_no_rescoring', cell['legacy']))
                if task.task_id == 'qm9.U0' and not u0_done:
                    distributions, raw = {}, []
                    for role, rows in (('train', train), ('train_inner_validation', held)):
                        observed = [r for r in rows if bool((r.candidate_mask & r.supervision_mask).any())]
                        values = [float(r.targets[0]) for r in observed]
                        atom_counts = [len(r.h0) for r in observed]
                        unique, counts = np.unique(atom_counts, return_counts=True)
                        distributions[role] = dict(unit='Ha', source_unit='configs/dev_panel_v2.json qm9.U0',
                            U0=distribution(values), atom_count=distribution(atom_counts),
                            atom_count_histogram={str(n): int(c) for n, c in zip(unique, counts)})
                        for r, y in zip(observed, values):
                            raw.append(dict(role=role, molecule_id=r.molecule_uid,
                                source_member_id=r.source_member_uid, atom_count=len(r.h0), U0=y, unit='Ha'))
                    exporter.add('u0/label_and_atom_count_distributions.json', value=distributions)
                    exporter.add('u0/molecules.parquet', rows=raw)
                    u0_done = True
            del payload, cached
        summaries.update(cell=cell, probe_details_without_state_dict=details,
            feature_availability=availability,
            score_policy='All summary scores, bootstrap arrays, selected alphas and CV errors copied unchanged; no rescoring',
            R0_note='Historical R0 summaries retained; R0 is not a v2 decision readout and its old per-record predictions were not persisted')
        exporter.add('summaries/'+cell['name']+'.json', value=summaries)
        exporter.add('predictions/'+cell['name']+'.parquet', rows=predicted)
        exporter.add('features/'+cell['name']+'.parquet', rows=features)
        exporter.status('STATIC_CELL_EXPORTED', cell=cell['name'])


def export_s_logs(exporter):
    configurations = {'C1-0': 'S_C1_0_seed0_v2', 'C1-a': 'S_C1_a_seed0', 'C1-b': 'S_C1_b_seed0_v2'}
    sources = [(name, CONTROL/root/'losses.csv') for name, root in configurations.items()]
    # Stream gzip directly to3MiB parts. No temporary uncompressed copy and no
    # second pass through an exported archive; mirrors the existing W&B delivery.
    class Parts:
        def __init__(self):
            self.total = 0; self.stream = None; self.count = 0; self.in_part = 0
            self.paths = []
        def write(self, data):
            length = len(data)
            while data:
                if self.stream is None:
                    path = exporter.output/'native_s_logs'/('S_seed0_losses_v2.tar.gz.part'+str(self.count).zfill(4))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    self.stream = path.open('xb'); self.paths.append(path); self.count += 1
                take = min(len(data), PART-self.in_part)
                self.stream.write(data[:take]); data=data[take:]
                self.in_part += take; self.total += take
                if self.in_part == PART:
                    self.stream.close(); self.stream=None; self.in_part=0
            return length
        def flush(self):
            if self.stream: self.stream.flush()
    sink = Parts()
    exporter.capacity(sum(p.stat().st_size for _, p in sources)+1024**2, 100)
    with gzip.GzipFile(filename='', fileobj=sink, mode='wb', compresslevel=6, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w|') as archive:
            for name, path in sources:
                archive.add(path, arcname='native_s_logs/'+name+'_S_seed0_losses.csv', recursive=False)
    if sink.stream: sink.stream.close()
    for path in sink.paths:
        exporter.files.append(dict(path=path.relative_to(exporter.output).as_posix(),
            source=str(path), bytes=path.stat().st_size))
    exporter.add('native_s_logs/manifest.json', value=dict(compression='tar+gzip', part_size=PART,
        concatenation='cat S_seed0_losses_v2.tar.gz.part* > S_seed0_losses.tar.gz',
        extraction='tar -xzf S_seed0_losses.tar.gz', original_files_retained=True,
        byte_identical_csv_members=True, source_csvs=[dict(candidate=n, path=str(p), bytes=p.stat().st_size) for n,p in sources],
        parts=[dict(path=p.name, bytes=p.stat().st_size) for p in sink.paths],
        archive_bytes=sink.total, content_readback_performed=False))


def export_observed_feature_statistics(exporter, views, tasks):
    """Requested task-specific optimization populations, separately from the
    original neural-probe feature normalization population (all TRAIN members).
    Reads original caches only; no exported table is opened or reviewed.
    """
    source_cells=json.loads((CONTROL/'MODEL_V3_DIAGNOSTICS_SOURCE_CELLS_20261112.json').read_text())
    source_cells += cells(reference_z_only=True)
    original={c['name']:c for c in source_cells}
    for cell in source_cells:
        exporter.capacity(2_000_000_000, 2000)
        statistics=[]
        for dataset in DATASETS:
            if cell['stage']=='reference_z' and dataset=='cyp_isoform':continue
            path=Path(cell['cache'])/(dataset+'.pt')
            if not path.exists() and cell['stage']=='T0':
                path=Path(original['C1-0_'+cell['name'].rsplit('_',1)[1]]['cache'])/(dataset+'.pt')
            payload=torch.load(path,map_location='cpu',weights_only=True)
            cached=cached_rows(payload)
            for task in (t for t in tasks if t.dataset_id==dataset):
                rows=task_rows(views[dataset],cached,task,role='train')
                if dataset!='cyp_isoform' and all(r.z is not None for r in cached):
                    rows=z_rows(rows,cached)
                statistics.extend(feature_rows(rows,task,payload['n_ref'],observed_only=True))
            del payload,cached
        exporter.add('features_observed/'+cell['name']+'.parquet',rows=statistics)
        exporter.status('OBSERVED_OPTIMIZATION_FEATURES_EXPORTED',cell=cell['name'])


def export_legacy_r0_predictions(exporter, views, tasks, device):
    """Recover unpersisted legacy endpoint predictions at the original recipe.
    No validation error, CV, bootstrap, early stopping or original score is run.
    """
    source_cells=json.loads((CONTROL/'MODEL_V3_DIAGNOSTICS_SOURCE_CELLS_20261112.json').read_text())
    source_cells=[c for c in source_cells if c['stage'] in ('C1','reference')]
    exporter.add('scope.json',value=dict(source_cells=source_cells,readout='R0',
        prediction_status='reconstructed_original_recipe_not_original_persisted_predictions',
        original_scores_recomputed=False,selection_use=False,encoder_updated=False,
        device=device,original_device='cuda',epochs=20,hidden_dim=64,batch_graphs=32,seed=0))
    for cell in source_cells:
        exporter.capacity(2_000_000_000, 2000)
        predictions,details=[],{}
        for dataset in DATASETS:
            path=Path(cell['cache'])/(dataset+'.pt')
            payload=torch.load(path,map_location='cpu',weights_only=True)
            cached=cached_rows(payload)
            for task in (t for t in tasks if t.dataset_id==dataset):
                train=task_rows(views[dataset],cached,task,role='train')
                held=task_rows(views[dataset],cached,task,role='train_inner_validation')
                prediction,detail=nonlinear_probe(train,held,task,seed=0,device=device,tracker=CurveHistory())
                packed=dict(molecule_uids=prediction.molecule_uids,source_record_uids=prediction.source_record_uids,
                    targets=prediction.targets,predictions=prediction.predictions,valid=prediction.valid)
                predictions.extend(prediction_rows(packed,held,task,'R0',
                    'reconstructed_original_R0_recipe_no_rescoring',str(path)))
                details[task.task_id]={k:v for k,v in detail.items() if k!='history'}
                exporter.status('R0_TASK_PREDICTIONS_RECONSTRUCTED',cell=cell['name'],task=task.task_id)
            del payload,cached
        exporter.add('predictions/'+cell['name']+'_R0_reconstructed.parquet',rows=predictions)
        exporter.add('metadata/'+cell['name']+'.json',value=dict(cell=cell,details=details,
            original_scores_recomputed=False,selection_use=False,device=device,original_device='cuda',
            original_summary_directory=cell['directory'],original_prediction_not_persisted=True,
            original_recipe='nonlinear_probe / SourceAlignedH0Readout / Linear64 / ReLU /20epochs /B32 /seed0'))
        exporter.status('R0_CELL_PREDICTIONS_RECONSTRUCTED',cell=cell['name'])


class CurveHistory:
    disabled = False
    def __init__(self):
        self.losses = []; self.weights = []
    def log(self, row, *, step, commit):
        if 'readout/loss' in row:
            self.losses.append(row['readout/loss']); self.weights.append(row['readout/observed_labels'])


def diagnostic_probe():
    # Same original function/hyperparameters/update order. Insert evaluation only
    # after each completed epoch; eval/inference has no RNG or optimizer effects.
    source = inspect.getsource(v3_dev_readouts.run_probe)
    needle = '        model.eval()\n        values = []'
    addition = '''            model.eval()
            epoch_values = []
            with torch.no_grad():
                for first in range(0,len(validation),32):
                    output,_,_ = batch(validation[first:first+32])
                    epoch_values.extend((output*target_scale+target_mean).cpu().tolist())
            epoch_prediction = _prediction(task,validation,epoch_values)
            diagnostic_epoch(epoch, updates, tracker, epoch_prediction)
        model.eval()
        values = []'''
    if source.count(needle) != 1:
        raise ValueError('Original readout source changed; retain original path without modifying it')
    namespace = dict(v3_dev_readouts.__dict__)
    source = source.replace(needle, addition)
    exec(compile(source, '<isolated diagnostic copy of original run_probe>', 'exec'), namespace)
    return namespace


def replay_curves(exporter, all_cells, views, tasks, device):
    namespace = diagnostic_probe()
    for cell in all_cells:
        if cell['stage'] in ('T1','reference_R1'):
            continue  # Explicit request is C1/reference + four T0 cases only.
        exporter.capacity(2_000_000_000, 2000)
        curves, endpoint, unavailable = [], [], []
        manifest = json.loads((Path(cell['directory'])/'predictions.json').read_text())
        for dataset in DATASETS:
            if cell['stage']=='reference_z' and dataset=='cyp_isoform':
                continue
            cache_path = Path(cell['cache'])/(dataset+'.pt')
            if not cache_path.exists():
                condition = cell['name'].rsplit('_', 1)[1]
                original = next(c for c in all_cells if c['name'] == 'C1-0_'+condition)
                cache_path = Path(original['cache'])/(dataset+'.pt')
            cached_payload = torch.load(cache_path, map_location='cpu', weights_only=True)
            cached = cached_rows(cached_payload)
            for task in (t for t in tasks if t.dataset_id == dataset):
                train = task_rows(views[dataset], cached, task, role='train')
                held = task_rows(views[dataset], cached, task, role='train_inner_validation')
                has_z = dataset != 'cyp_isoform' and all(r.z is not None for r in cached)
                names = ['R2', 'R3'] + (['R2z'] if has_z else [])
                if cell['stage']=='reference_z':
                    names=['R2z']  # Existing molecular random controls only.
                if not has_z:
                    unavailable.append(dict(task=task.task_id, readout='R2z',
                        reason='No z for C1/reference; SoM R2z is the predefined X/R2 alias'))
                r2_curve = None
                for name in names:
                    if task.output_level == 'atom' and name == 'R3':
                        curves.extend([dict(r, readout='R3', alias_of='R2') for r in r2_curve])
                        continue
                    fit, valid = (z_rows(train,cached), z_rows(held,cached)) if name == 'R2z' else (train,held)
                    tracker = CurveHistory(); local = []
                    def epoch_callback(epoch, updates, history, prediction):
                        row = dict(task=task.task_id, readout=name, epoch=epoch+1, updates=updates,
                            training_loss_mean_updates=float(np.mean(history.losses)),
                            training_loss_mean_labels=float(np.average(history.losses, weights=history.weights)),
                            observed_labels=sum(history.weights), validation_native_error=error(prediction),
                            error_metric=task.error_metric, training_objective='standardized_MSE' if task.error_metric=='mae' else 'masked_BCE_with_logits',
                            unit='native task label unit' if task.error_metric=='mae' else 'dimensionless',
                            device=device, alias_of=None, selection_use=False)
                        local.append(row); history.losses.clear(); history.weights.clear()
                        exporter.status('CURVE_EPOCH', cell=cell['name'], task=task.task_id, readout=name, epoch=epoch+1)
                    namespace['diagnostic_epoch'] = epoch_callback
                    prediction, detail = namespace['run_probe'](fit, valid, task,
                        readout='R2' if name=='R2z' else name, n_ref=cached_payload['n_ref'],
                        seed=0, device=device, tracker=tracker)
                    curves.extend(local)
                    if name == 'R2': r2_curve = local
                    packed = dict(molecule_uids=prediction.molecule_uids, source_record_uids=prediction.source_record_uids,
                        predictions=prediction.predictions, targets=prediction.targets, valid=prediction.valid)
                    endpoint.extend(prediction_rows(packed, held, task, name,
                        'diagnostic_replay_only_not_original_score', cell['cache']))
                if task.output_level == 'atom':
                    curves.extend([dict(r, readout='R2z', alias_of='R2') for r in r2_curve])
            del cached_payload,cached
        exporter.add('curves/'+cell['name']+'.parquet', rows=curves)
        exporter.add('curves/'+cell['name']+'_diagnostic_endpoint_predictions.parquet', rows=endpoint)
        exporter.add('curves/'+cell['name']+'_metadata.json', value=dict(cell=cell,
            selection_use=False, original_results=cell['directory'], device=device,
            original_device='cuda', epochs=30, seed=0, batch_graphs=32,
            original_recipe_function='v3_dev_readouts.run_probe',
            changes='Only extra inference/native validation error after every epoch; device recorded explicitly',
            original_error_not_recomputed=True, unavailable=unavailable,
            differences_policy='Original scores/predictions are retained separately; diagnostic values never feed decisions'))
        exporter.status('CURVE_CELL_COMPLETE', cell=cell['name'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--device', default='cpu', choices=['cpu','cuda'])
    parser.add_argument('--resume-static', action='store_true',
                        help='Continue after the original static producer completed; metadata only, no exported-content readback')
    parser.add_argument('--reference-z-only', action='store_true',
                        help='Export existing molecular-z and v2 R1 controls; replay only their requested R2z curves from cached features')
    parser.add_argument('--legacy-r0-only',action='store_true',
                        help='Recover missing legacy R0 predictions at its saved recipe without scoring')
    args=parser.parse_args()
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':
        raise ValueError('Export and cached-only computation belong to compute-0-20')
    torch.set_num_threads(int(os.environ.get('SLURM_CPUS_PER_TASK', '8')))
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    exporter=Export(Path(args.output), resume_static=args.resume_static)
    panel=json.loads((REPO/'configs/dev_panel_v2.json').read_text())
    tasks=[TaskSpec(**{k:r[k] for k in ('task_id','dataset_id','field','output_level','error_metric','pooling')}) for r in panel['tasks']]
    store=RememberedStore(PROJECT/'runs/model_v3_20261025/selected_train_store_4520421/native_store/training_store.json')
    views={d:GroupedTrainingView(store,d,'official' if d=='expansionrx' else '0',store.group_map) for d in DATASETS}
    if args.legacy_r0_only:
        export_legacy_r0_predictions(exporter,views,tasks,args.device)
        exporter.manifest('MANIFEST.json',status='ALL_SIX_REQUESTED_EXPORTS_COMPLETE',
            purpose='Legacy R0 predictions reconstruction only; no new scores')
        exporter.status('ALL_SIX_REQUESTED_EXPORTS_COMPLETE')
        return
    all_cells=cells(reference_z_only=args.reference_z_only)
    if args.resume_static:
        # Restore the known completed producer prefix using paths/sizes only.
        # No exported content is opened, recomputed, reviewed or compared.
        names=['scope.json','u0/label_and_atom_count_distributions.json','u0/molecules.parquet']
        names += [folder+'/'+c['name']+suffix for c in all_cells for folder,suffix in
                  (('summaries','.json'),('predictions','.parquet'),('features','.parquet'))]
        exporter.files=[dict(path=n,source=str(exporter.output/n),bytes=(exporter.output/n).stat().st_size) for n in names]
    else:
        exporter.add('scope.json', value=dict(cells=all_cells, tasks=panel['tasks'],
        T1_scope='completed evaluation producer markers at export start only',
        random_control='One logical control group; all three existing architecture-matched random profiles retained',
        original_scores_recomputed=False, downstream_TEST_read=False,
            no_pretraining=True, no_export_review_or_second_readback=True))
        export_static(exporter,all_cells,views,tasks)
    if not args.reference_z_only:
        export_s_logs(exporter)
    else:
        export_observed_feature_statistics(exporter,views,tasks)
    exporter.manifest('STATIC_MANIFEST.json', status='STATIC_EXPORT_COMPLETE', cells=all_cells)
    exporter.status('STATIC_EXPORT_COMPLETE')
    replay_curves(exporter,all_cells,views,tasks,args.device)
    exporter.manifest('MANIFEST.json', status='ALL_SIX_REQUESTED_EXPORTS_COMPLETE', cells=all_cells)
    exporter.status('ALL_SIX_REQUESTED_EXPORTS_COMPLETE')


if __name__=='__main__':
    main()

