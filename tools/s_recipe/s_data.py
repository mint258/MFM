"""S-only geometry/topology transport and paired molecule sampling."""
from collections import OrderedDict
from pathlib import Path
import json
import sqlite3

import numpy as np
import pyarrow.parquet as pq

from phychem_mfm.phase1.v31_loader import MFM4Dataset, decode_mfm4, record_key


def paired_choices(rng, rows, source, *, seed, start, count):
    """Molecule RNG is unaffected by geometry counts or augmentation draws.

    Conformer RNG is keyed by the consumed ordinal, so checkpointing, worker
    prefetch and PM7/UFF having different conformer counts cannot desynchronize
    candidate/control molecule draws.
    """
    molecules = rng.integers(len(rows), size=count)
    result = []
    for offset, molecule in enumerate(molecules):
        ordinal = start + offset
        row = rows[int(molecule)]
        conformer_rng = np.random.default_rng(np.random.SeedSequence([seed, ordinal, 0x53434F4E]))
        conformer = int(conformer_rng.choice(row[source]))
        result.append((int(row['molecule_index']), conformer, ordinal))
    return result


class GeometryDataset:
    """Read only Z, bond graph and geometry; never decode physical targets."""
    def __init__(self, root, population, *, source, validation=False, rotor_index=None):
        self.source = source
        self.population = json.loads(Path(population).read_text())
        self.rows = pq.read_table(self.population['validation' if validation else 'train']).to_pylist()
        self.transport = MFM4Dataset(root, split='FULL' if validation else 'TRAIN',
                                    geometry_only=True, molecule_indices=[])
        self.cache = OrderedDict()
        self.split = 'FULL' if validation else 'TRAIN'
        self.rotors = (sqlite3.connect('file:'+str(Path(rotor_index).resolve())+'?mode=ro', uri=True)
                       if rotor_index else None)

    def _record(self, kind, molecule, conformer=None):
        if kind == 'M' and molecule in self.cache:
            self.cache.move_to_end(molecule)
            return self.cache[molecule]
        self.transport._open()
        with self.transport._env.begin(buffers=True) as transaction:
            payload = transaction.get(record_key(kind, molecule, conformer))
            if payload is None:
                raise KeyError((kind, molecule, conformer))
            arrays = decode_mfm4(payload, array_ids={1, 2, 3} if kind == 'M' else {21})
        if kind == 'M':
            self.cache[molecule] = arrays
            if len(self.cache) > 256:
                self.cache.popitem(last=False)
        return arrays

    def read(self, choice):
        molecule, conformer, ordinal = choice
        topology = self._record('M', molecule)
        geometry = self._record('P' if self.source == 'PM7' else 'U', molecule, conformer)
        result = dict(molecule_index=molecule, conformer_index=conformer, ordinal=ordinal,
                      geometry_source=self.source, Z=topology[1], bonds=topology[2],
                      bond_order=topology[3], pos=geometry[21])
        if self.rotors is not None:
            from noise import Rotor
            row = self.rotors.execute('SELECT plan FROM rotors WHERE split=? AND molecule_index=?',
                                      (self.split, molecule)).fetchone()
            if row is None:
                raise KeyError(('Missing precomputed source rotor plan', self.split, molecule))
            result['rotors'] = tuple(Rotor(int(r['fixed']), int(r['pivot']), tuple(r['moving']))
                                     for r in json.loads(row[0]))
        return result

    def close(self):
        self.transport.close()
        if self.rotors is not None:
            self.rotors.close()


def init_reader(root, population, source, rotor_index=None):
    global DATA
    import torch
    torch.set_num_threads(1)
    DATA = GeometryDataset(root, population, source=source, rotor_index=rotor_index)


def read_choice(choice):
    return DATA.read(choice)
