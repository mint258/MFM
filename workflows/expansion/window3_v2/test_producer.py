import unittest
import json
from pathlib import Path
import random
import tempfile
from .producer import physical_mask, validate, selected_sources
from .kernel import generate


class FakeKernel:
    def __init__(self): self.calls = []
    def prepare(self, source):
        self.calls.append('D20')
        return {'D20': {'names': list(map(str, range(20))), 'values': [1.] * 20, 'valid_mask': [True] * 20},
                'atomic_numbers': [6], 'unassigned_stereo': [], 'uff_supported': True}
    def embed(self, seed, count): self.calls.append(('embed', count)); return [0, 1, 2, 3]
    def optimize(self, cid):
        self.calls.append(('UFF', cid))
        return {'candidate_id': cid, 'coordinates': [[float(cid), 0., 0.]], 'energy': float(cid),
                'optimizer_code': 0, 'stereo_valid': True, 'iterations': 1}
    def distance(self, a, b): return abs(a['candidate_id'] - b['candidate_id']) * .25
    def d3(self, row): self.calls.append('D3'); return {'SASA_atom_A2': [1.]}, []


SOURCE = {'pubchem_version': 'test', 'cid': 1, 'full_key': 'TEST', 'source_smiles': 'C',
          'isomeric_smiles': 'C', 'stream': 'R', 'stream_rank': 1}


class Tests(unittest.TestCase):
    def test_physical_boundaries_and_source_missing(self):
        bounds = {'lower': 0., 'upper': 2., 'lower_exclusive': True}
        self.assertEqual(physical_mask([None, float('nan'), -1., 0., 1., 2., 3.], bounds),
                         ([False, False, True, True, True, True, True], [False, False, False, False, True, True, False]))

    def test_no_fill_no_retry_one_d20_and_actual_d3(self):
        k = FakeKernel(); p = generate(SOURCE, k)
        self.assertEqual([c['candidate_id'] for c in p['conformers']], [0, 2])
        self.assertEqual(p['state'], 'INSUFFICIENT_UNIQUE_CONFORMERS')
        self.assertEqual(k.calls.count('D20'), 1)
        self.assertEqual(k.calls.count('D3'), 2)
        self.assertEqual(k.calls.count(('embed', 30)), 1)
        self.assertEqual(len([c for c in k.calls if isinstance(c, tuple) and c[0] == 'UFF']), 4)
        validate(p)

    def test_misaligned_atom_sasa_is_rejected(self):
        p = generate(SOURCE, FakeKernel())
        p['conformers'][0]['D3']['SASA_atom_A2'] = [1., 2.]
        with self.assertRaisesRegex(ValueError, 'ATOM_SASA_ALIGNMENT'): validate(p)

    def test_zero_embedding_has_no_fallback(self):
        k = FakeKernel(); k.embed = lambda seed, count: []
        p = generate(SOURCE, k)
        self.assertEqual(p['state'], 'EMBED_FAILED')
        self.assertEqual(p['conformers'], [])
        self.assertEqual(k.calls, ['D20'])

    def test_full_shards_exclude_pilot_without_gaps(self):
        rng = random.Random(20261025)
        samples = {s: set(rng.sample(range(1, 1250001), 5000)) for s in ('R', 'N')}
        rows = [dict(SOURCE, stream=s, stream_rank=rank) for s in ('R', 'N')
                for rank in [*range(1, 50), *sorted(samples[s])[:3]]]
        with tempfile.TemporaryDirectory() as folder:
            part = Path(folder)/'part.jsonl'
            part.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            manifest = Path(folder)/'manifest.json'
            manifest.write_text(json.dumps({'source_parts':[{'path':str(part)}]}))
            expected={(r['stream'],r['stream_rank']) for r in rows if r['stream_rank'] not in samples[r['stream']]}
            observed=[]
            for shard in range(3):
                config={'source_manifest':str(manifest),'mode':'full','shard_count':3,'shard_index':shard}
                observed.extend((r['stream'],r['stream_rank']) for r in selected_sources(config))
            self.assertEqual(set(observed), expected)
            self.assertEqual(len(observed), len(expected))


if __name__ == '__main__': unittest.main()
