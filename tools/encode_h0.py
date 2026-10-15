#!/usr/bin/env python3
"""Export shared-backbone H0 from XYZ files and an external checkpoint."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'current'))


def load_encoder(checkpoint, configuration, device):
    import torch
    from phychem_mfm.factory import build_model

    payload = torch.load(checkpoint, map_location='cpu', weights_only=True)
    if 'model_state' in payload and 'model_config' in payload:
        spec = payload['model_config']
        config = {
            'architecture': {'task_route_per_task': payload['task_route_per_task']},
            'backbone': spec['backbone_config'],
            'expert': spec['expert_config'],
            'head': spec['head_config'],
        }
        state = payload['model_state']
    elif 'model' in payload and 'config_sha256' in payload:
        import hashlib
        if configuration is None:
            raise ValueError('S-runner checkpoint requires --configuration with its original JSON')
        raw = Path(configuration).read_bytes()
        if hashlib.sha256(raw).hexdigest() != payload['config_sha256']:
            raise ValueError('Configuration SHA256 does not match the S checkpoint')
        config = json.loads(raw)['model']
        state = payload['model']
    else:
        raise ValueError('Unsupported checkpoint schema; use the checkpoint-specific original loader')
    model = build_model(config)
    model.load_state_dict(state, strict=True)
    model.to(device).eval()
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True, type=Path)
    parser.add_argument('--configuration', type=Path)
    parser.add_argument('--xyz-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--batch-size', type=int, default=1)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--pooling', choices=('mean', 'sum'), default='mean')
    args = parser.parse_args()
    if args.batch_size < 1 or (args.limit is not None and args.limit < 1):
        parser.error('--batch-size and --limit must be positive')
    if args.output.suffix != '.npz':
        parser.error('--output must end in .npz')
    if args.output.exists():
        parser.error('--output already exists; choose a new path')

    import numpy as np
    import torch
    from torch_geometric.data import Data
    from torch_geometric.loader import DataLoader
    from phychem_mfm.data.dataset_infer import MoleculeDataset

    device = torch.device(args.device)
    model = load_encoder(args.checkpoint, args.configuration, device)
    dataset = MoleculeDataset(str(args.xyz_root), end_idx=args.limit)
    atoms, graphs, offsets = [], [], [0]
    with torch.inference_mode():
        for batch in DataLoader(dataset, batch_size=args.batch_size, shuffle=False):
            inputs = Data(x=batch.x, pos=batch.pos, batch=batch.batch, ptr=batch.ptr).to(device)
            h0 = model.encode_atoms(inputs)
            pooled = h0.new_zeros((batch.num_graphs, h0.shape[-1]))
            pooled.index_add_(0, inputs.batch, h0)
            if args.pooling == 'mean':
                counts = (inputs.ptr[1:] - inputs.ptr[:-1]).to(h0.dtype)
                pooled = pooled / counts[:, None]
            atoms.append(h0.cpu().numpy())
            graphs.append(pooled.cpu().numpy())
            for count in (batch.ptr[1:] - batch.ptr[:-1]).tolist():
                offsets.append(offsets[-1] + count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        np.savez_compressed(stream, atom_h0=np.concatenate(atoms), graph_h0=np.concatenate(graphs),
                            graph_ptr=np.asarray(offsets, dtype=np.int64),
                            file_paths=np.asarray(dataset.file_paths, dtype=str))
    print(json.dumps({'graphs': len(dataset), 'atoms': offsets[-1], 'output': str(args.output)}))


if __name__ == '__main__':
    main()
