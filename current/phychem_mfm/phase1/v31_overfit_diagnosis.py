"""User-requested M2 diagnosis on the one immutable 4526238 overfit set."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import torch

from .v2_disk import save_metadata_json
from .v2_s_training import s_model
from .v31_loader import MFM4Dataset
from .v31_m2 import FieldMoments
from .v31_training import V31PDModel, torch_affine


BASELINE = Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/M2_overfit_4526238')


def write_rows(path, rows):
    from .v2_disk import CheckedWriter, filesystem_status, require_capacity
    import io
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    data = buffer.getvalue().encode('utf-8')
    path = Path(path)
    require_capacity(filesystem_status(path.parent), len(data), 1)
    with path.open('xb') as file:
        CheckedWriter(file, path.parent, len(data)).write(data)


def dataset_and_models(device, baseline=BASELINE, *, output_parameterization='raw',
                       head_hidden_dim=64, forms='H1'):
    c = json.loads((baseline / 'configuration.json').read_text())
    dataset = MFM4Dataset(c['root'], training_view=json.loads(Path(c['training_view']).read_text()),
        normalizations=json.loads(Path(c['normalizations']).read_text()))
    torch.manual_seed(c['seed'])
    torch.set_num_threads(1)
    structural, _ = s_model('C1-0', 'three')
    pd = V31PDModel(structural.encoder, dataset.view, output_parameterization=output_parameterization,
                    head_hidden_dim=head_hidden_dim, forms=forms)
    combined = torch.nn.ModuleDict(dict(structural=structural, pd=pd)).to(device)
    return c, dataset, combined, pd


def fixed_set(dataset, configuration, path):
    """The original choice call occurs once; all later runs load this file."""
    import pyarrow.parquet as pq
    rng = np.random.default_rng(configuration['seed'])
    indices = rng.choice(dataset.indices, 1000, replace=False)
    table = pq.read_table(dataset.directory / 'id_map.parquet',
        columns=['molecule_index', 'molecule_id'], filters=[('record_kind', '=', 'M')])
    mids = {r['molecule_index']: r['molecule_id'] for r in table.to_pylist()}
    rows = [dict(molecule_index=int(i), molecule_id=mids[int(i)],
                 conformer_index=int(dataset.choices(int(i))[0])) for i in indices]
    value = dict(baseline_job=4526238, seed=0, source='PM7', records=1000,
                 sampling_rng_after_original_choice=rng.bit_generator.state, molecules=rows)
    save_metadata_json(value, path)
    return value


def read_fixed(dataset, fixed):
    return [dict(dataset.read(row['molecule_index'], row['conformer_index']), molecule_id=row['molecule_id'])
            for row in fixed['molecules']]


def normalization(model, name):
    definition = model.definitions[name]
    return definition.get('normalization', model.view.normalizations.get(name))


@torch.no_grad()
def field_evaluation(model, samples, batch_size=8, *, detail=False, residual_sink=None,
                     criterion_reference=None):
    model.eval()
    moments, stored, matches = FieldMoments(), {}, {}
    for start in range(0, len(samples), batch_size):
        batch = samples[start:start + batch_size]
        predictions = model.predict(batch)
        original = model.original_predictions(predictions, batch)
        for name, raw_prediction in original.items():
            y = np.concatenate([s['targets'][name].raw for s in batch])
            p = raw_prediction.cpu().numpy()
            moments.add(name, p, y)
            reference = None if criterion_reference is None else criterion_reference[name]
            if reference is not None and reference['legal_values'] is not None:
                legal = np.asarray(reference['legal_values'])
                valid = ~np.isnan(y)
                chosen = legal[np.abs(p[valid,None]-legal[None,:]).argmin(-1)]
                matches[name] = matches.get(name,0) + int((chosen==y[valid]).sum())
            if residual_sink is not None and name in residual_sink:
                offset = 0
                for sample in batch:
                    target = sample['targets'][name]
                    end = offset + len(target.raw)
                    prediction = p[offset:end]
                    valid = target.valid
                    score = float(np.sqrt(np.mean((prediction[valid]-target.raw[valid])**2))) if valid.any() else -1.
                    if score >= 0:
                        def json_array(array):
                            a = np.asarray(array)
                            return np.where(np.isfinite(a),a,None).tolist()
                        residual_sink[name].append(dict(molecule_id=sample['molecule_id'],
                            molecule_index=sample['molecule_index'], conformer_index=sample['conformer_index'],
                            original_label=json_array(target.raw), prediction=json_array(prediction),
                            mask=valid.tolist(), molecule_RMSE=score,
                            pair_index=None if target.pair_index is None else target.pair_index.tolist()))
                    offset = end
                residual_sink[name].sort(key=lambda r:r['molecule_RMSE'],reverse=True)
                del residual_sink[name][20:]
            if detail:
                target = np.concatenate([s['targets'][name].values for s in batch])
                # This is the exact pre-existing loss path, without another forward.
                loss_p = torch_affine(predictions[name], normalization(model, name)).cpu().numpy()
                item = stored.setdefault(name, dict(y=[], p=[], z=[], loss_p=[]))
                for key, value in [('y', y), ('p', p), ('z', target), ('loss_p', loss_p)]:
                    item[key].append(value)
    rows = moments.results()
    model.train()
    if not detail:
        for row in rows:
            x = moments.rows[row['field']]
            row['RMSE'] = float(np.sqrt(x['sse'].sum() / x['n'].sum())) if x['n'].sum() else None
            if criterion_reference is not None:
                reference = criterion_reference[row['field']]
                count=row['valid_components']
                accuracy=matches.get(row['field'],0)/count if reference['legal_values'] is not None and count else None
                passed=(None if count<200 else accuracy>=.95 if accuracy is not None
                        else row['RMSE']<=reference['threshold'])
                row.update(proposed_criterion=reference['kind'],proposed_pass=passed,
                    proposed_accuracy=accuracy,proposed_RMSE_threshold=reference['threshold'],
                    epsilon_abs=reference['epsilon'],epsilon_source=reference['epsilon_source'],
                    proposed_criterion_approved=False)
        return rows
    return rows, moments, {name: {k: np.concatenate(v) for k, v in values.items()}
                           for name, values in stored.items()}


def comparison_matches(actual, expected):
    if actual is None or expected is None:
        return actual is None and expected is None
    return abs(actual - expected) <= max(1e-4, 1e-3 * abs(expected))


def finish_phase0_summary(output, baseline=BASELINE):
    """Finish an interrupted JSON publication from the already closed CSV only."""
    from scipy.stats import spearmanr
    output = Path(output)
    with (output / 'phase0_fields.csv').open() as file:
        rows = list(csv.DictReader(file))
    with (baseline / 'losses.csv').open() as file:
        dynamics = list(csv.DictReader(file))
    norms = np.array([float(r['preclip_norm']) for r in dynamics])
    finite = [r for r in rows if r['R2']]
    spearman = float(spearmanr([float(r['R2']) for r in finite],
        [np.log10(max(abs(float(r['center'])),float(r['scale']))) for r in finite]).statistic)
    tail = dynamics[-2000:]
    summary = dict(status='PHASE0_EVALUATED_A_DEFINITION_PENDING', fields=len(rows),
        failed_fields=sum(r['original_pass']=='False' for r in rows),
        P_fields=sum(r['P_flag']=='True' for r in rows), C_flags=sum(r['C_flag']=='True' for r in rows),
        spearman_R2_log10_max_center_scale=spearman, E1_required_by_spearman=spearman<=-.3,
        clipped_fraction=float((norms>1).mean()), median_preclip_norm=float(np.median(norms)),
        final2000_log_loss_slope_per_update={g:float(np.polyfit([int(r['updates']) for r in tail],
            np.log([float(r[g]) for r in tail]),1)[0]) for g in ('D','P')},
        label_std_method='sqrt(sum(component-centered M2)/valid_components), ddof0; matches baseline R2 denominator',
        A_definition='Missing trigger in user guide; requested from user; never inferred',
        inference_passes=1, training_updates=0, publication_recovery='closed CSV and baseline logs only; no new forward or label reads')
    save_metadata_json(summary, output / 'summary.json')
    print(json.dumps(summary),flush=True)
    return summary


def proposal_reference(model,samples,phase0_csv):
    """Unapproved side-by-side proposal, never a replacement for R2>=.95."""
    with Path(phase0_csv).open() as file:
        statistics={r['field']:r for r in csv.DictReader(file)}
    columns={c['field_key']:c for cs in model.view.schema['columns'].values() for c in cs}
    references={}
    for field in model.registry.fields:
        row=statistics[field.name]
        meta=columns.get(field.name,{})
        resolution=next((meta[k] for k in ('numeric_resolution','quantization_step','absolute_resolution','output_resolution')
                         if isinstance(meta.get(k),(int,float)) and meta[k]>0),None)
        epsilon=1e-3*float(row['scale']) if resolution is None else float(resolution)
        legal=None
        if int(row['unique_values'])<=10:
            values=np.concatenate([s['targets'][field.name].raw for s in samples])
            legal=np.unique(values[~np.isnan(values)]).tolist()
        references[field.name]=dict(legal_values=legal,epsilon=epsilon,
            epsilon_source='fallback_1e-3_D4_scale' if resolution is None else 'source_registry_resolution',
            threshold=max(epsilon,.224*float(row['label_std'])),
            kind='report_only_n_lt_200' if int(row['valid_components'])<200 else
                 'nearest_legal_accuracy_ge_095' if legal is not None else 'RMSE_max_epsilon_0224_sigma')
    return references


def run_controlled(*, fixed_path, output, experiment, updates, output_parameterization='normalized',
                   clip=1., lr=3e-4, family=None, head_hidden_dim=64, resume=None,
                   device='cuda', baseline=BASELINE):
    """One expressly listed E1/E2/E3/E4 run, preserving the original identities."""
    import time
    from .v2_disk import save_checkpoint
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    forms = 'H3' if experiment=='E4' else 'H1'
    c,dataset,combined,pd = dataset_and_models(device,baseline,
        output_parameterization=output_parameterization,head_hidden_dim=head_hidden_dim,forms=forms)
    fixed = json.loads(Path(fixed_path).read_text())
    if fixed['baseline_job']!=4526238 or fixed['records']!=1000:
        raise ValueError('Use the one published original overfit set')
    samples = read_fixed(dataset,fixed)
    proposals=proposal_reference(pd,samples,Path(fixed_path).parent/'phase0_fields.csv')
    active = tuple(f.name for f in pd.registry.fields if family is None or f.family==family)
    if not active:
        raise ValueError('Family has no originally enabled fields')
    groups = tuple(g for g in ('D','P') if any(pd.by_name[n].group==g for n in active))
    rng = np.random.default_rng(0)
    rng.bit_generator.state = fixed['sampling_rng_after_original_choice']
    parameters = list(combined.parameters())
    optimizer = torch.optim.AdamW(parameters,lr=lr,betas=(.9,.95))
    start, prior_seconds, norms = 0,0.,[]
    if resume:
        state = torch.load(resume,map_location=device,weights_only=True)
        combined.load_state_dict(state['model'])
        optimizer.load_state_dict(state['optimizer'])
        start = state['updates']
        rng.bit_generator.state = state['rng']
        torch.set_rng_state(state['torch_rng'].cpu())
        torch.cuda.set_rng_state(state['cuda_rng'].cpu())
        prior_seconds = state.get('elapsed_seconds',0.)
        norms = state.get('preclip_norms',[])
    recipe = dict(experiment=experiment,baseline_job=4526238,fixed_set=str(fixed_path),
        output_parameterization=output_parameterization,lr=lr,betas=[.9,.95],clip=clip,batch_size=8,
        planned_updates=updates,seed=0,family=family,head_hidden_dim=head_hidden_dim,head_form=forms,
        active_fields=list(active),groups=groups,resume=resume,
        source_root=c['root'],training_view=c['training_view'],normalizations=c['normalizations'])
    save_metadata_json(recipe,output/'configuration.json')
    started=time.monotonic()
    metrics=None
    residuals={n:[] for n in active} if experiment=='E4' else None
    status='CONTROLLED_RUN_COMPLETE'
    with (output/'losses.csv').open('x',newline='',buffering=1) as log, \
         (output/'per_head_history.csv').open('x',newline='',buffering=1) as history:
        writer=csv.DictWriter(log,fieldnames=['updates','samples','total','D','P','preclip_norm','seconds'])
        writer.writeheader()
        hwriter=csv.DictWriter(history,fieldnames=['updates','field','valid_components','R2','MAE','passed','RMSE',
            'proposed_criterion','proposed_pass','proposed_accuracy','proposed_RMSE_threshold',
            'epsilon_abs','epsilon_source','proposed_criterion_approved','trained'])
        hwriter.writeheader()
        for step in range(start+1,updates+1):
            batch=[samples[int(i)] for i in rng.integers(1000,size=8)]
            optimizer.zero_grad(set_to_none=True)
            loss=pd.loss(pd.predict(batch,groups=groups,fields=active),batch,groups=groups,fields=active)
            loss.total.backward()
            norm=torch.nn.utils.clip_grad_norm_(parameters,clip)
            optimizer.step()
            norms.append(float(norm))
            writer.writerow(dict(updates=step,samples=step*8,total=float(loss.total.detach()),
                D=float(loss.groups['D'].detach()) if 'D' in loss.groups else None,
                P=float(loss.groups['P'].detach()) if 'P' in loss.groups else None,
                preclip_norm=float(norm),seconds=prior_seconds+time.monotonic()-started))
            timed_out=time.monotonic()-started>4*3600
            if step%500==0 or step==updates or timed_out:
                metrics=field_evaluation(pd,samples,8,residual_sink=residuals if step==updates else None,
                                         criterion_reference=proposals)
                for row in metrics:
                    hwriter.writerow(dict(updates=step,**row,trained=row['field'] in active))
                print(json.dumps(dict(experiment=experiment,family=family,updates=step,
                    active_passed=sum(r['passed'] for r in metrics if r['field'] in active),
                    active_fields=len(active),seconds=time.monotonic()-started)),flush=True)
            if timed_out:
                status='OVERFIT_UNRESOLVED_USER_4H_TIMEBOX'
                break
    save_checkpoint(dict(model=combined.state_dict(),optimizer=optimizer.state_dict(),configuration=recipe,
        updates=step,rng=rng.bit_generator.state,torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state(),
        preclip_norms=norms,elapsed_seconds=prior_seconds+time.monotonic()-started),output/'final.pt')
    summary=dict(recipe,status=status,actual_updates=step,actual_samples=step*8,
        seconds=prior_seconds+time.monotonic()-started,process_seconds=time.monotonic()-started,
        clipped_fraction=float((np.array(norms)>clip).mean()),median_preclip_norm=float(np.median(norms)),
        active_passed=sum(r['passed'] for r in metrics if r['field'] in active),
        active_failed_fields=[r for r in metrics if r['field'] in active and not r['passed']],
        all_133_final_metrics=metrics,gpu_peak_bytes=torch.cuda.max_memory_allocated())
    if residuals is not None and step==updates:
        failures={r['field'] for r in summary['active_failed_fields']}
        if failures:
            save_metadata_json(dict(missing_numeric_encoding='null with original boolean mask',
                fields={n:v for n,v in residuals.items() if n in failures}),output/'residual_top20.json')
    save_metadata_json(summary,output/'summary.json')
    dataset.close()
    print(json.dumps({k:summary[k] for k in ('experiment','status','actual_updates','active_passed','family')}),flush=True)
    return summary


def phase0(output, *, device='cuda', baseline=BASELINE):
    from scipy.stats import spearmanr
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    c, dataset, combined, pd = dataset_and_models(device, baseline)
    fixed = fixed_set(dataset, c, output / 'overfit_set_4526238.json')
    samples = read_fixed(dataset, fixed)
    checkpoint = torch.load(baseline / 'final.pt', map_location=device, weights_only=True)
    combined.load_state_dict(checkpoint['model'])
    rows, moments, arrays = field_evaluation(pd, samples, c['batch_size'], detail=True)
    with (baseline / 'per_head_metrics.csv').open() as file:
        previous = {r['field']: (float(r['R2']) if r['R2'] else None) for r in csv.DictReader(file)}
    mismatches = [dict(field=r['field'], actual=r['R2'], expected=previous.get(r['field']))
                  for r in rows if r['field'] not in previous or not comparison_matches(r['R2'], previous[r['field']])]
    if set(previous) != {r['field'] for r in rows} or len(rows) != 133 or mismatches:
        save_metadata_json(dict(status='STOP_FIXED_SET_METRICS_MISMATCH', mismatches=mismatches),
                           output / 'summary.json')
        raise ValueError('Stage0 fixed-set check failed; user decision required before further experiments')
    save_metadata_json(dict(status='PASS', fields=133, tolerance='max(1e-4 absolute,1e-3 relative)',
        max_absolute_R2_difference=max(abs(r['R2'] - previous[r['field']]) for r in rows
            if r['R2'] is not None)), output / 'fixed_set_check.json')
    details = []
    for metric in rows:
        name = metric['field']
        values, m = arrays[name], moments.rows[name]
        spec, field = normalization(pd, name), pd.by_name[name]
        y, p, z, loss_p = (np.asarray(values[k], dtype=np.float64) for k in ('y','p','z','loss_p'))
        valid = ~np.isnan(y)
        n = int(valid.sum())
        variance = float(m['m2'].sum() / n) if n else float('nan')
        std = np.sqrt(variance)
        rmse = float(np.sqrt(m['sse'].sum() / n)) if n else float('nan')
        bias = float((p[valid] - y[valid]).mean()) if n else float('nan')
        p_mean = np.divide(np.where(valid,p,0).sum(0),valid.sum(0),out=np.zeros(y.shape[-1]),where=valid.sum(0)>0)
        p_std = float(np.sqrt(np.where(valid,(p-p_mean)**2,0).sum()/n)) if n else float('nan')
        scale = float(np.asarray(spec['scale']).reshape(-1)[0])
        center = float(np.asarray(spec['center']).reshape(-1)[0])
        norm_mse = float(((loss_p[valid] - z[valid])**2).mean()) if n else float('nan')
        r2_loss = 1 - norm_mse * scale**2 / variance if variance > 0 else None
        unique, counts = np.unique(y[valid], return_counts=True)
        mode = float(counts.max()/n) if n else None
        pipeline = (metric['R2'] is not None and r2_loss is not None and
                    abs(r2_loss-metric['R2']) > max(1e-3,1e-2*(1-metric['R2'])))
        criterion = n < 200 or len(unique) <= 10 or (mode is not None and mode >= .9) or std/scale < .1
        details.append(dict(field=name, group=field.group, family=field.family, level=field.level,
            representation=field.representation, route=pd.routes[pd.selections[name][0]],
            has_element_reference=spec.get('element_reference') is not None,
            center=center, scale=scale, abs_center_over_scale=abs(center)/scale, log10_scale=np.log10(scale),
            valid_components=n, label_std=std, std_over_scale=std/scale, unique_values=len(unique),
            mode_fraction=mode, max_abs_z=float(np.max(np.abs(z[valid]))) if n else None,
            R2=metric['R2'], MAE=metric['MAE'], RMSE=rmse,
            RMSE_over_std=rmse/std if std>0 else None, mean_bias_over_std=bias/std if std>0 else None,
            pred_std_over_label_std=p_std/std if std>0 else None, normalized_MSE=norm_mse,
            R2_loss=r2_loss, delta_R2=r2_loss-metric['R2'] if r2_loss is not None else None,
            P_flag=pipeline, A_flag='PENDING_USER_MISSING_DEFINITION', C_flag=criterion,
            main_class='P' if pipeline else 'A_DEFINITION_PENDING',
            original_pass=metric['passed']))
    write_rows(output / 'phase0_fields.csv', details)
    with (baseline / 'losses.csv').open() as file:
        dynamics = list(csv.DictReader(file))
    norms = np.array([float(r['preclip_norm']) for r in dynamics])
    slopes = {}
    for group in ('D','P'):
        tail = dynamics[-2000:]
        slopes[group] = float(np.polyfit([int(r['updates']) for r in tail],
            np.log([float(r[group]) for r in tail]),1)[0])
    finite = [r for r in details if r['R2'] is not None and np.isfinite(r['R2'])]
    spearman = float(spearmanr([r['R2'] for r in finite],
        [np.log10(max(abs(r['center']),r['scale'])) for r in finite]).statistic)
    summary = dict(status='PHASE0_EVALUATED_A_DEFINITION_PENDING', fields=133,
        failed_fields=sum(not r['original_pass'] for r in details),
        P_fields=int(sum(r['P_flag'] for r in details)), C_flags=int(sum(r['C_flag'] for r in details)),
        spearman_R2_log10_max_center_scale=spearman, E1_required_by_spearman=spearman<=-.3,
        clipped_fraction=float((norms>1).mean()), median_preclip_norm=float(np.median(norms)),
        final2000_log_loss_slope_per_update=slopes,
        label_std_method='sqrt(sum(component-centered M2)/valid_components), ddof0; matches baseline R2 denominator',
        A_definition='Missing trigger in user guide; requested from user; never inferred',
        inference_passes=1, training_updates=0)
    save_metadata_json(summary, output / 'summary.json')
    dataset.close()
    print(json.dumps(summary), flush=True)
    return summary
