import unittest
import json
import gzip
from unittest.mock import patch
from pathlib import Path
import random
import tempfile
from .producer import physical_mask, validate, selected_sources, accept_shard
from .kernel import generate, select_three


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
    def test_three_prefix_preserves_original_energy_dedup_selection(self):
        from ..uff3_candidate_v1.core import no_fill_order
        rows=[{'candidate_key':str(i),'candidate_id':i,'energy':float(i%7)} for i in range(30)]
        rng=random.Random(17)
        for scale in (.01,.1,.25,.5,1.):
            rng.shuffle(rows)
            distance=lambda a,b:abs(a['candidate_id']-b['candidate_id'])*scale
            actual,expected=select_three(rows,distance),no_fill_order(rows,distance)[:3]
            self.assertEqual([r['candidate_id'] for r in actual],[r['candidate_id'] for r in expected])
            for a,b in zip(actual,expected):
                for key in ('energy','min_rmsd_to_previously_selected_A'):
                    if b[key] is None: self.assertIsNone(a[key])
                    else: self.assertLessEqual(abs(a[key]-b[key]),1e-12+1e-12*abs(b[key]))
        calls=[]
        self.assertEqual(len(select_three(rows,lambda a,b:calls.append((a,b)) or 1.)),3)
        self.assertEqual(len(calls),3)

    def test_interrupted_intent_is_not_retried_and_closed_chunk_is_reused(self):
        from . import producer
        with tempfile.TemporaryDirectory() as folder:
            chunk=Path(folder)/'chunk_000000'; chunk.mkdir()
            with gzip.open(chunk/'packets_old.jsonl.gz','wt') as stream:
                stream.write(json.dumps({'index':0})+'\n')
            other=dict(SOURCE,cid=2,stream_rank=2)
            packet=generate(other,FakeKernel())
            with patch.object(producer,'CONFIG',{'output':folder}), patch.object(producer,'KERNEL',None), \
                 patch.object(producer,'generate',return_value=packet) as compute, \
                 patch.object(producer,'write_packets',return_value=([],{})):
                result=producer.process((0,[SOURCE,other]))
                compute.assert_called_once_with(other,None)
                self.assertEqual(result['states']['INTERRUPTED_NO_RETRY'],1)
                self.assertEqual(result['molecules'],2)
                self.assertEqual(producer.process((0,[SOURCE,other])),result)
                compute.assert_called_once()

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

    def test_weighted_cpu_shards_are_exhaustive_and_disjoint(self):
        groups = [[0,1,2,3], [4,5], [6,7,8], [9]]
        for rank in range(1, 101):
            self.assertEqual(sum(accept_shard(rank, {'shard_count':10,'shard_residues':g}) for g in groups), 1)
        self.assertEqual([sum(accept_shard(r, {'shard_count':10,'shard_residues':g}) for r in range(1,101)) for g in groups], [40,20,30,10])

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
