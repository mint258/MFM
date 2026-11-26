"""A1: original R3 numerical recipe with complete-state cooperative continuation.

The original phase1 run_probe stays unchanged. Only update/epoch checkpoint
boundaries and exact source/seed binding are added for new readout seeds.
"""
from pathlib import Path
from dataclasses import replace
import torch
from torch import nn
from phychem_mfm.phase1.v3_dev_readouts import FrozenFeatureProbe, _padded
from finetune import atomic_checkpoint, state_cpu, ContinuationRequired

def run_resumable_probe(train, validation, task, *, readout, n_ref, seed=0, device='cpu', tracker,
              relative_std_floor=False, internal_epoch_selection=False,
              state_path, source_identity, should_stop):
    from phychem_mfm.phase1.v3_dev_evaluation import _validate_molecules, _prediction
    train,validation = _validate_molecules(train,task),_validate_molecules(validation,task)
    if {r.molecule_uid for r in train} & {r.molecule_uid for r in validation}:
        raise ValueError('Optimization and inner-validation molecules overlap')
    if not callable(getattr(tracker,'log',None)) or getattr(tracker,'disabled',False):
        raise ValueError('Functional explicit tracking required')
    if readout != 'R3' or n_ref <= 0:
        raise ValueError('Fixed R2/R3 readout and positive optimization N_ref required')
    internal = ()
    if internal_epoch_selection:
        uids = sorted({r.molecule_uid for r in train})
        order = torch.randperm(len(uids), generator=torch.Generator().manual_seed(20261112)).tolist()
        held_uids = {uids[i] for i in order[:max(1, (len(uids)+9)//10)]}
        internal = tuple(r for r in train if r.molecule_uid in held_uids)
        train = tuple(r for r in train if r.molecule_uid not in held_uids)
    removed_dimensions = 0
    if relative_std_floor:
        std = torch.cat([r.h0.double() for r in train]).std(0, unbiased=False)
        threshold = max(1e-12, 1e-4 * float(torch.quantile(std, .5)))
        keep = std >= threshold
        removed_dimensions = int((~keep).sum())
        def select(rows):
            return tuple(replace(r, h0=r.h0[:, keep]) for r in rows)
        train, validation, internal = select(train), select(validation), select(internal)
    direct = task.output_level == 'graph' and train[0].graph_features is not None
    if direct:
        features = torch.stack([r.graph_features.detach().cpu() for r in train]).double()
    elif task.output_level == 'graph' and readout == 'R2':
        features = torch.stack([torch.cat((r.h0.double().mean(0),r.h0.double().sum(0)/n_ref))
                                for r in train])
    else:
        features = torch.cat([r.h0.double() for r in train])
    feature_mean,feature_scale = features.mean(0),features.std(0,unbiased=False)
    feature_scale = torch.where(feature_scale > 1e-12,feature_scale,torch.ones_like(feature_scale))
    del features
    observed = torch.cat([r.targets[r.supervision_mask & r.candidate_mask].double() for r in train])
    if not len(observed):
        raise ValueError('No observed optimization labels')
    target_mean = float(observed.mean()) if task.error_metric == 'mae' else 0.
    target_scale = float(observed.std(unbiased=False)) if task.error_metric == 'mae' else 1.
    target_scale = target_scale if target_scale > 1e-12 else 1.
    device = torch.device(device)
    devices = [device.index or 0] if device.type == 'cuda' else []
    with torch.random.fork_rng(devices=devices):
        torch.manual_seed(seed)
        if device.type == 'cuda':
            torch.cuda.manual_seed_all(seed)
        model = FrozenFeatureProbe(train[0].h0.shape[1], readout=readout,
            output_level=task.output_level,n_ref=n_ref,mean=feature_mean,scale=feature_scale,
            direct_features=direct).to(device)
        optimizer = torch.optim.AdamW(model.parameters(),lr=1e-3,betas=(.9,.999),
            weight_decay=.01,eps=1e-8,foreach=False,fused=False)
        rng = torch.Generator(device='cpu').manual_seed(seed)
        retained = tuple(r for r in train if bool((r.supervision_mask & r.candidate_mask).any()))

        def batch(rows):
            h,mask = _padded(rows,device)
            feature = torch.stack([r.graph_features for r in rows]).to(device) if direct else None
            predicted = model(h,mask,feature)
            if task.output_level == 'graph':
                y = torch.cat([r.targets for r in rows]).to(device).float()
                valid = torch.cat([r.supervision_mask & r.candidate_mask for r in rows]).to(device)
            else:
                predicted = predicted[mask]
                y = torch.cat([r.targets for r in rows]).to(device).float()
                valid = torch.cat([r.supervision_mask & r.candidate_mask for r in rows]).to(device)
            return predicted,y,valid

        def predict_rows(rows):
            model.eval()
            values = []
            with torch.no_grad():
                for start in range(0, len(rows), 32):
                    predicted, _, _ = batch(rows[start:start+32])
                    values.extend((predicted*target_scale+target_mean).cpu().tolist())
            return _prediction(task, rows, values)

        identity = dict(source=source_identity,task=task.task_id,seed=seed,
            readout=readout,n_ref=float(n_ref),relative_std_floor=relative_std_floor,
            internal_epoch_selection=internal_epoch_selection,
            train=[r.source_member_uid or r.molecule_uid for r in train],
            internal=[r.source_member_uid or r.molecule_uid for r in internal],
            validation=[r.source_member_uid or r.molecule_uid for r in validation])
        state_path = Path(state_path)
        saved = torch.load(state_path,map_location='cpu',weights_only=True) if state_path.exists() else None
        updates, epoch, offset, order, phase = 0, 0, 0, [], 'train'
        best_error, selected_epoch, best_state = float('inf'), 30, None
        if saved is not None:
            if saved['identity'] != identity:
                raise ValueError('R3 complete-state source/seed/native population changed')
            model.load_state_dict(saved['model'])
            optimizer.load_state_dict(saved['optimizer'])
            rng.set_state(saved['shuffle_rng'])
            torch.set_rng_state(saved['torch_rng'])
            if device.type=='cuda':
                torch.cuda.set_rng_state_all(saved['cuda_rng'])
            updates,epoch,offset,order,phase = (saved[k] for k in
                ('updates','epoch','offset','order','phase'))
            best_error,selected_epoch,best_state = (saved[k] for k in
                ('best_error','selected_epoch','best_state'))
        def save():
            atomic_checkpoint(state_path,dict(schema='A1_R3_COMPLETE_STATE_V1',
                identity=identity,model=state_cpu(model),optimizer=optimizer.state_dict(),
                shuffle_rng=rng.get_state(),torch_rng=torch.get_rng_state(),
                cuda_rng=torch.cuda.get_rng_state_all() if device.type=='cuda' else [],
                updates=updates,epoch=epoch,offset=offset,order=order,phase=phase,
                best_error=best_error,selected_epoch=selected_epoch,best_state=best_state))
        def boundary():
            if should_stop():
                save()
                raise ContinuationRequired('Original R3 complete state saved at update boundary')
        while epoch < 30:
            if phase=='train':
                model.train()
                if not order:
                    order = torch.randperm(len(retained),generator=rng).tolist()
                while offset<len(order):
                    boundary()
                    rows = tuple(retained[i] for i in order[offset:offset+32])
                    predicted,y,mask = batch(rows)
                    loss = (nn.functional.mse_loss(predicted[mask],(y[mask]-target_mean)/target_scale)
                            if task.error_metric == 'mae' else
                            nn.functional.binary_cross_entropy_with_logits(predicted[mask],y[mask]))
                    if not bool(torch.isfinite(loss)):
                        raise FloatingPointError('Nonfinite development readout loss')
                    optimizer.zero_grad(set_to_none=True)
                    loss.backward()
                    optimizer.step()
                    tracker.log({'readout/loss':float(loss.detach()),'readout/epoch':epoch,
                                 'readout/observed_labels':int(mask.sum()),'readout/update':updates},
                                step=updates,commit=True)
                    updates += 1
                    offset += len(rows)
                phase='select_epoch'
            boundary()
            if internal_epoch_selection:
                from phychem_mfm.phase1.v3_dev_evaluation import error
                actual_error = error(predict_rows(internal))
                tracker.log({'readout/internal_error': actual_error, 'readout/epoch': epoch},
                            step=updates, commit=True)
                if actual_error < best_error:
                    best_error, selected_epoch = actual_error, epoch+1
                    best_state = {k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
            epoch,offset,order,phase=epoch+1,0,[],'train'
            save()
        boundary()
        if best_state is not None:
            model.load_state_dict(best_state)
        prediction = predict_rows(validation)
        state = {key:value.detach().cpu() for key,value in model.state_dict().items()}
    return prediction,dict(readout=readout,epochs=30,
        batch_graphs=32,updates=updates,n_ref=float(n_ref),normalization_fit_scope='train',
        target_mean=target_mean,target_scale=target_scale,encoder_updated=False,
        selection='internal_train_90_10' if internal_epoch_selection else 'last_epoch_no_early_stop',
        selected_epoch=selected_epoch, internal_split_seed=20261112 if internal_epoch_selection else None,
        removed_dimensions=removed_dimensions, fit_molecules=len({r.molecule_uid for r in train}),
        internal_molecules=len({r.molecule_uid for r in internal}), state_dict=state)
