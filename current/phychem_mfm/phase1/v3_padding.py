"""Declared smaller-bucket/exact-local-sort candidate, retaining all records.

Batch regrouping may change an optimizer trajectory. This is an opt-in candidate
that requires the same 20-batch/500-update checks as other A-class proposals.
"""
from .full_corpus_loader import BlockAtomBatchSampler
from .identity import canonical_hash


class LocallySortedAtomBatchSampler(BlockAtomBatchSampler):
    def __init__(self, index, *, exact_atom_sort=False, **kwargs):
        if type(exact_atom_sort) is not bool:
            raise ValueError("exact_atom_sort must be a boolean")
        super().__init__(index, **kwargs)
        self.exact_atom_sort = exact_atom_sort
        if exact_atom_sort:
            self.contract = {**self.contract, "schema_version": "model_v3_exact_local_atom_sort_v1",
                             "within_block_order": "stable_sort_exact_atom_count_after_seeded_shuffle"}
            self.contract_sha256 = canonical_hash(self.contract)

    def _ordered_block(self, block_position):
        order = super()._ordered_block(block_position)
        if self.exact_atom_sort:
            order = sorted(order, key=lambda index: self.index.ref(index).native_n_atoms)
        return order
