"""Report actual FULL/ROUTINE and seen-molecule/heldout-conformer diagnostics."""
import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq
import torch

from phychem_mfm.phase1.v31_loader import MFM4Dataset
from phychem_mfm.phase1.v31_training import V31PDModel
from phychem_mfm.phase1.v31_validation import validate_v31
from phychem_mfm.phase1.v2_s_training import s_model


def select_molecules(dataset, subset):
    if subset:
        ids = pq.read_table(subset, columns=['molecule_id']).column(0).to_pylist()
        indices = dataset.indices_from_ids(list(dict.fromkeys(ids)))
        dataset.indices, dataset._index_set = indices, set(map(int, indices))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--unseen-root')
    parser.add_argument('--train-root')
    parser.add_argument('--unseen-split', default='FULL')
    parser.add_argument('--unseen-subset', help='Optional ROUTINE molecule-ID Parquet within FULL')
    parser.add_argument('--train-subset', help='Seen TRAIN molecule IDs; defaults to checkpoint subset')
    parser.add_argument('--batch-size', type=int, default=4)
    args = parser.parse_args()
    checkpoint = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    config = checkpoint['configuration']
    groups = tuple(g for g in ('S','D','P') if g in config.get('condition','S'))
    kwargs = dict(source=config.get('source','PM7'))
    if any(g != 'S' for g in groups):
        kwargs.update(training_view=config['training_view'],
                      normalizations=json.loads(Path(config['normalizations']).read_text()))
    train = MFM4Dataset(args.train_root or config['root'], diagnostic=True, **kwargs)
    unseen = MFM4Dataset(args.unseen_root or config['root'], split=args.unseen_split, **kwargs)
    subset = args.train_subset or config.get('subset_path') or config.get('D5_index')
    if not subset and config.get('TRAIN_molecules') == 240_000:
        raise ValueError('Supply the actual training proxy IDs for seen-molecule diagnostics')
    select_molecules(train, subset)
    select_molecules(unseen, args.unseen_subset)
    structural, _ = s_model(config['distance_bias'], config['views'])
    pd = V31PDModel(structural.encoder, train.view, forms=config.get('head_form','H1'),
                    pooling=config.get('pooling','registry')) if any(g != 'S' for g in groups) else None
    if any(key.startswith('structural.') for key in checkpoint['model']):
        models = torch.nn.ModuleDict(dict(structural=structural, **({} if pd is None else {'pd':pd})))
        models.load_state_dict(checkpoint['model'])
    else:
        structural.load_state_dict(checkpoint['model'])
    structural.cuda()
    if pd is not None:
        pd.cuda()
    role = 'ROUTINE' if args.unseen_subset else 'FULL'
    result = validate_v31({role:unseen,'TRAIN_UNSEEN_CONFORMATION':train}, pd_model=pd,
        structural_model=structural, groups=groups, views=config['views'], batch_size=args.batch_size)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as file:
        json.dump(dict(checkpoint=args.checkpoint, populations=result, selection_use=False), file, indent=2)
        file.write('\n')
    train.close()
    unseen.close()
    print(json.dumps({name:value['records'] for name,value in result.items()}))


if __name__ == '__main__':
    main()
