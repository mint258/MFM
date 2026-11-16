"""Taskbook-v3 frozen-feature R2/R3 probes; no encoder gradients or TEST roles."""
from __future__ import annotations

import torch
from torch import nn


def pooled_features(h, mask, n_ref):
    clean = torch.where(mask.unsqueeze(-1), h, h.new_zeros(()))
    count = mask.sum(1, keepdim=True).to(h.dtype)
    total = clean.sum(1)
    return torch.cat((total / count, total / n_ref), dim=-1)


class FrozenFeatureProbe(nn.Module):
    """Two affine layers per MLP; R3 atom transform ends in256 channels."""
    def __init__(self, dimension, *, readout, output_level, n_ref, mean, scale,
                 direct_features=False):
        super().__init__()
        self.readout, self.output_level = readout, output_level
        self.n_ref, self.direct_features = float(n_ref), bool(direct_features)
        self.register_buffer('feature_mean', torch.as_tensor(mean, dtype=torch.float32))
        self.register_buffer('feature_scale', torch.as_tensor(scale, dtype=torch.float32))
        if readout == 'R3' and output_level == 'graph':
            self.atom = nn.Sequential(nn.Linear(dimension,256), nn.ReLU(), nn.Linear(256,256))
            self.output = nn.Sequential(nn.Linear(512,256), nn.ReLU(), nn.Linear(256,1))
        else:
            self.atom = None
            width = len(self.feature_mean)
            self.output = nn.Sequential(nn.Linear(width,256), nn.ReLU(), nn.Linear(256,1))

    def forward(self, h, mask, direct=None):
        h = torch.where(mask.unsqueeze(-1), h, h.new_zeros(()))
        if self.direct_features:
            feature = direct
        elif self.atom is not None:
            atom = self.atom((h-self.feature_mean)/self.feature_scale)
            feature = pooled_features(atom, mask, self.n_ref)
        elif self.output_level == 'graph':
            feature = pooled_features(h, mask, self.n_ref)
        else:
            feature = h
        if self.atom is None:
            feature = (feature-self.feature_mean)/self.feature_scale
        return self.output(feature).squeeze(-1)


def _padded(rows, device):
    n = max(len(row.h0) for row in rows)
    h = torch.zeros((len(rows),n,rows[0].h0.shape[1]), device=device)
    mask = torch.zeros((len(rows),n), dtype=torch.bool, device=device)
    for i,row in enumerate(rows):
        h[i,:len(row.h0)] = row.h0.to(device)
        mask[i,:len(row.h0)] = True
    return h,mask


def run_probe(train, validation, task, *, readout, n_ref, seed=0, device='cpu', tracker):
    from .v3_dev_evaluation import _validate_molecules, _prediction
    train,validation = _validate_molecules(train,task),_validate_molecules(validation,task)
    if {r.molecule_uid for r in train} & {r.molecule_uid for r in validation}:
        raise ValueError('Optimization and inner-validation molecules overlap')
    if not callable(getattr(tracker,'log',None)) or getattr(tracker,'disabled',False):
        raise ValueError('Functional explicit tracking required')
    if readout not in ('R2','R3') or n_ref <= 0:
        raise ValueError('Fixed R2/R3 readout and positive optimization N_ref required')
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

        updates = 0
        for epoch in range(30):
            model.train()
            order = torch.randperm(len(retained),generator=rng).tolist()
            for start in range(0,len(order),32):
                rows = tuple(retained[i] for i in order[start:start+32])
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
        model.eval()
        values = []
        with torch.no_grad():
            for start in range(0,len(validation),32):
                predicted,_,_ = batch(validation[start:start+32])
                values.extend((predicted*target_scale+target_mean).cpu().tolist())
        state = {key:value.detach().cpu() for key,value in model.state_dict().items()}
    return _prediction(task,validation,values),dict(readout=readout,epochs=30,
        batch_graphs=32,updates=updates,n_ref=float(n_ref),normalization_fit_scope='train',
        target_mean=target_mean,target_scale=target_scale,encoder_updated=False,
        selection='last_epoch_no_early_stop',state_dict=state)
