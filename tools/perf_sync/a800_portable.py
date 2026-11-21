"""Reuse the released per-record zstd reader; retain current target processing."""
import importlib.util
from pathlib import Path

from phychem_mfm.phase1 import p_recipe_data as current

RELEASE = Path('/share/home/202264640132/precision_20261115/source/current/phychem_mfm/phase1/p_recipe_data.py')
spec = importlib.util.spec_from_file_location('phychem_mfm.phase1.a800_released_reader', RELEASE)
released = importlib.util.module_from_spec(spec)
spec.loader.exec_module(released)


class PortableDataset(current.PRecipeDataset):
    compressed_lmdb = True
    record = released.PRecipeDataset.record

    def __init__(self, *args, compressed_lmdb=True, **kwargs):
        if not compressed_lmdb:
            raise ValueError('This benchmark reads the existing compressed release')
        super().__init__(*args, **kwargs)


def install():
    current.PRecipeDataset = PortableDataset
    current.dataset_configuration = released.dataset_configuration
