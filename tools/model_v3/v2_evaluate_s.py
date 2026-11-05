"""Evaluate a taskbook-v2 S checkpoint on the frozen TRAIN-only dev panel."""
from dataclasses import replace
import argparse
import json
from pathlib import Path
import time

import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.phase1.v2_s_training import s_model
from phychem_mfm.phase1.v3_dev_store import TrainOnlyPackedStore
from phychem_mfm.phase1.v3_dev_membership import GroupedTrainingView
from phychem_mfm.phase1.v3_dev_panel import MoleculeH0
from phychem_mfm.phase1.v3_dev_evaluation import (
    TaskSpec, task_rows, ridge_probe, nonlinear_probe, compare_panel,
)


class History:
    disabled = False
    def __init__(self, stream, prefix):
        self.stream, self.prefix = stream, prefix
    def log(self, row, *, step, commit):
        self.stream.write(json.dumps(dict(cell=self.prefix, step=step, **row)) + '\n')


class RememberedStore(TrainOnlyPackedStore):
    def __init__(self, path):
        super().__init__(path, verify_digests=False)
        self.cache = {}
    def get(self, dataset_id, member_index):
        key = (dataset_id, member_index)
        if key not in self.cache:
            self.cache[key] = super().get(dataset_id, member_index)
        return self.cache[key]


def encode_view(encoder, view, *, batch_size=32):
    members = [(index, view.get(index, role=role))
               for role in ('train', 'train_inner_validation') for index in view.view(role)]
    members = [(index, sample) for index, sample in members if sample.geometry_ready]
    output = []
    with torch.no_grad():
        for start in range(0, len(members), batch_size):
            selected = members[start:start + batch_size]
            batch = Batch.from_data_list([Data(x=sample.x.reshape(-1, 1), pos=sample.pos)
                                          for _, sample in selected]).cuda()
            h0 = encoder.encode_atoms(batch).detach().cpu().float()
            offset = 0
            for index, sample in selected:
                n = len(sample.x)
                output.append(MoleculeH0(sample.member_uid, index, h0[offset:offset+n],
                                         sample.source_atom_ids))
                offset += n
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--validation-index')
    parser.add_argument('--store', default='/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/selected_train_store_4520421/native_store/training_store.json')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).absolute().parents[2]
    panel = json.loads((repo / 'configs/dev_panel_v1.json').read_text())
    store = RememberedStore(args.store)
    views = {dataset: GroupedTrainingView(store, dataset,
        'official' if dataset == 'expansionrx' else '0', store.group_map)
        for dataset in ('expansionrx', 'cyp_isoform', 'qm9')}
    tasks = [TaskSpec(**{key: item[key] for key in
             ('task_id', 'dataset_id', 'field', 'output_level', 'error_metric', 'pooling')})
             for item in panel['tasks']]
    checkpoint = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    config = checkpoint['configuration']
    torch.set_num_threads(16)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    started = time.monotonic()
    predictions = {'candidate': {}, 'reference': {}}
    details = {}
    with (output / 'readout_history.jsonl').open('w', buffering=1) as history:
        for label, seed in (('reference', 20261025), ('candidate', config['seed'])):
            torch.manual_seed(seed)
            model, _ = s_model(config['distance_bias'], config['views'])
            if label == 'candidate':
                model.load_state_dict(checkpoint['model'])
            encoder = model.encoder.cuda().eval()
            if label == 'candidate' and args.validation_index:
                from phychem_mfm.phase1.v2_s_validation import validate_s
                validation = validate_s(model, args.validation_index, views=config['views'])
                (output / 'pretraining_validation.json').write_text(json.dumps(validation, indent=2) + '\n')
            for dataset, view in views.items():
                cached = encode_view(encoder, view)
                # H0 is computed once and reused by every task/readout.
                torch.save(cached, output / (label + '_' + dataset + '_h0.pt'))
                for task in (task for task in tasks if task.dataset_id == dataset):
                    train = task_rows(view, cached, task, role='train')
                    valid = task_rows(view, cached, task, role='train_inner_validation')
                    for readout in ('ridge', 'linear64_relu'):
                        key = task.task_id + '/' + readout
                        if readout == 'ridge':
                            prediction, detail = ridge_probe(train, valid, task)
                        else:
                            prediction, detail = nonlinear_probe(train, valid, task, device='cuda',
                                tracker=History(history, label + '/' + key))
                        predictions[label][key] = prediction
                        details[label + '/' + key] = {k: v for k, v in detail.items() if k != 'history'}
                del cached
            del encoder, model
            torch.cuda.empty_cache()
    identity = config['distance_bias'] + ':' + config['views']
    summary = compare_panel(predictions['candidate'], predictions['reference'],
        architecture_sha256=identity, reference_architecture_sha256=identity)
    summary.update(seconds=time.monotonic()-started, checkpoint=args.checkpoint,
                   consumed_samples=checkpoint['clock']['samples_consumed'], details=details,
                   source_roles=['train', 'train_inner_validation'], downstream_TEST_read=False)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({key: summary[key] for key in ('complete', 'mean_normalized_improvement', 'seconds')}))


if __name__ == '__main__':
    main()
