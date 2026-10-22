"""Actual LMDB reads with spawn workers, unconsumed prefetch and sampler restore."""
import hashlib
import json

from runtime import ROOT, native_components, old_configuration, save, setup_imports


def main():
    setup_imports()
    import torch
    from data import SelectedIndex, SelectedCounts, SelectedViewsDataset
    from phychem_mfm.phase1.full_corpus_loader import BlockAtomBatchSampler, make_prefetch_loader, close_prefetch_iterator
    torch.set_num_threads(8)
    parent, original, _ = native_components("train", seed=17, epoch_noise=True)
    index = SelectedIndex(parent, [0, 1, 7, 18, 95, 100, 1001, 9001])
    dataset = SelectedViewsDataset(index, native_transport=original.native_transport,
        native_transport_binding=original.native_transport_binding, seed=17, noise_seed_includes_epoch=True,
        subset_map_close_uses_local_index=True, **old_configuration()["views"])
    counts = SelectedCounts(dataset.index)
    options = {**old_configuration()["sampler"], "max_molecules": 2}

    def signature(corpus):
        batch = corpus.encoder_batch
        result = {}
        for graph in range(batch.num_graphs):
            if int(batch.sample_type_id[graph]) != 1:
                continue
            key = batch.pretrain_base_key[graph]
            pos = batch.pos[batch.batch.eq(graph)].contiguous().numpy().tobytes()
            result[key] = hashlib.sha256(pos).hexdigest()
        return result

    def consume(sampler, stop_after=None):
        iterator = iter(make_prefetch_loader(dataset, sampler, num_workers=2, prefetch_factor=2, pin_memory=False))
        values = {}
        try:
            for n, corpus in enumerate(iterator):
                values.update(signature(corpus))
                sampler.commit_batch(corpus.logical_indices)
                if stop_after is not None and n + 1 == stop_after:
                    break
        finally:
            close_prefetch_iterator(iterator)
        return values

    try:
        sampler = BlockAtomBatchSampler(counts, seed=17, epoch=0, **options)
        epoch0 = consume(sampler)
        sampler.advance_epoch()
        epoch1 = consume(sampler)
        assert epoch0.keys() == epoch1.keys() and all(epoch0[k] != epoch1[k] for k in epoch0)
        partial = BlockAtomBatchSampler(counts, seed=17, epoch=0, **options)
        first = consume(partial, stop_after=1)
        state = partial.state_dict()
        restored = BlockAtomBatchSampler(counts, seed=17, epoch=0, **options)
        restored.load_state_dict(state)
        continued = consume(restored)
        assert not first.keys() & continued.keys()
        assert {**first, **continued} == epoch0, "GUIDE_STOP_EPOCH_NOISE_RESUME_MISMATCH"
        again = BlockAtomBatchSampler(counts, seed=17, epoch=0, **options)
        assert consume(again) == epoch0
        save(ROOT / "reports/epoch_workers_v3.json", {
            "status": "REAL_SPAWN_EPOCH_NOISE_AND_RESUME_PASS", "real_records": len(epoch0),
            "num_workers": 2, "unconsumed_prefetch_discarded": True,
            "same_epoch_repeat_byte_identical": True, "resumed_noise_byte_identical": True,
            "next_epoch_all_records_different": True, "sampler_saved_state": state,
            "subset_map_close_uses_local_index": True,
        })
    finally:
        dataset.close()


if __name__ == "__main__":
    main()
