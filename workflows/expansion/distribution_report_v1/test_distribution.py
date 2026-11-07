"""Meaningful report-boundary tests, with no synthetic production completion."""
from pathlib import Path
import tempfile
import unittest
from .aggregate import Moments, completion, ingest_enriched, open_state
from .io import population, reference, write_new
from .functional_groups import FUNCTIONS


class DistributionTests(unittest.TestCase):
    def test_bins_preserve_tails_and_tanimoto_endpoints(self):
        value = Moments('nearest_tanimoto')
        for x in (0.0, 0.5, 1.0):
            value.add(x)
        self.assertEqual(sum(value.bins), 3)
        self.assertEqual(value.bins[0], 0)
        self.assertEqual(value.bins[-1], 0)
        self.assertEqual(list(value.histogram())[-1][-1], 1.0)
        self.assertEqual(value.summary()[:2], (3, .5))
        self.assertEqual(Moments('nearest_tanimoto', value.result()).result(), value.result())
        other = Moments('heavy_atoms')
        other.add(-1)
        other.add(10001)
        self.assertEqual((other.bins[0], other.bins[-1]), (1, 1))

    def test_common_sample_cannot_be_reported_as_complete_common(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authority = root / 'authority.json'
            write_new(authority, {'actual_molecules': 4})
            manifest = root / 'manifest.json'
            write_new(manifest, {'schema': 'EXPANSION_DISTRIBUTION_POPULATION_V1', 'status': 'COMPLETE', 'population': 'v1_common', 'population_scope': 'FULL_DECLARED_POPULATION', 'expected_molecules': 4, 'authority_reference': reference(authority), 'authority_count_pointer': '/actual_molecules', 'is_sample': True, 'population_roles': ['TRAIN', 'VAL'], 'authority_kind': 'FINAL_FULL_COMMON_MEMBERSHIP'})
            with self.assertRaisesRegex(RuntimeError, 'sampled Common'):
                population(manifest)

    def test_full_populations_without_exact_nn_cannot_complete_report(self):
        db = open_state(':memory:')
        try:
            for name, n in [('v1_common', 5), ('pubchem_1m', 1000000), ('R', 1250000), ('N', 1250000)]:
                db.execute('INSERT INTO populations VALUES(?,?,?,1)', (name, '{}', n))
            with self.assertRaisesRegex(RuntimeError, 'exact before/after'):
                completion(db)
        finally:
            db.close()

    def test_task21_baseline_does_not_wait_for_R_N_generation(self):
        from .io import canonical
        with tempfile.TemporaryDirectory() as directory:
            manifest=Path(directory)/'before.json'
            write_new(manifest,{'reference_populations':['v1_common']})
            db=open_state(':memory:')
            try:
                db.execute('INSERT INTO populations VALUES(?,?,?,1)',('v1_common','{}',5))
                db.execute('INSERT INTO populations VALUES(?,?,?,1)',('pubchem_1m','{}',1000000))
                db.execute('INSERT INTO comparisons VALUES(?,?,?,?,1)',('pubchem_to_v1',canonical(reference(manifest)),'pubchem_1m',1000000))
                populations,comparisons=completion(db,baseline_only=True)
                self.assertEqual(set(populations),{'v1_common','pubchem_1m'})
                self.assertEqual(set(comparisons),{'pubchem_to_v1'})
            finally:
                db.close()

    def test_neither_missing_population_nor_small_streams_can_complete(self):
        db = open_state(':memory:')
        try:
            with self.assertRaisesRegex(RuntimeError, 'All four'):
                completion(db)
            for name in ('v1_common', 'pubchem_1m', 'R', 'N'):
                db.execute('INSERT INTO populations VALUES(?,?,?,1)', (name, '{}', 2))
            with self.assertRaisesRegex(RuntimeError, 'size'):
                completion(db)
        finally:
            db.close()

    def test_membership_and_statistics_commit_together(self):
        from .aggregate import load_moments
        db = open_state(':memory:')
        try:
            row = {'molecule_id': 'one', 'full_key': 'VNWKTOKETHGBQD-UHFFFAOYSA-N', 'heavy_atoms': 1, 'molecular_weight_Da': 16.0, 'rings': 0, 'aromatic_rings': 0, 'isotopic_atoms': 0, 'stereocenters': 0, 'logp': 0.0, 'tpsa_A2': 0.0, 'hbd': 0, 'hba': 0, 'rotatable_bonds': 0, 'non_h_composition': '[[6,1]]', 'elements': [6], 'element_combination': '6', 'generic_murcko': '', 'generic_ring_systems': [], 'functional_groups': {f: 0 for f in FUNCTIONS}}
            ingest_enriched(db, 'v1_common', 'molecule_id', [row], load_moments(db, 'v1_common'))
            self.assertEqual(db.execute('SELECT count(*) FROM seen').fetchone()[0], 1)
            self.assertEqual(load_moments(db, 'v1_common')['heavy_atoms'].n, 1)
            self.assertEqual(db.execute("SELECT n FROM counts WHERE kind='scaffold'").fetchone()[0], 1)
        finally:
            db.close()

    def test_fixed_fragment_definitions_and_additive_enrichment_preserve_existing_fields(self):
        from .functional_groups import enrich_batch, recipe
        from ..features_legacy_compatible_v2 import features_candidate
        original = features_candidate(None, 'CCO', None)
        row = {**original, 'molecule_id': 'authoritative-common-member'}
        enriched = enrich_batch(([row], 'molecule_id', False))[0]
        self.assertEqual({key: enriched[key] for key in row}, row)
        self.assertEqual(enriched['functional_groups']['fr_Al_OH'], 1)
        self.assertEqual([d['name'] for d in recipe()['definitions']], list(FUNCTIONS))
        self.assertTrue(all(d['SMARTS'] and d['count_unique'] for d in recipe()['definitions']))

    def test_incomplete_common_descriptor_projection_can_only_be_additively_completed(self):
        from .functional_groups import enrich_batch
        from ..features_legacy_compatible_v2 import features_candidate
        features = features_candidate(None, 'CCO', None)
        strict = {key: features[key] for key in ('full_key', 'generic_murcko', 'generic_ring_systems', 'ecfp4_2048_hex')}
        strict.update(molecule_id='common-member', source_smiles='CCO')
        with self.assertRaisesRegex(RuntimeError, 'descriptors missing'):
            enrich_batch(([strict], 'molecule_id', False))
        enriched = enrich_batch(([strict], 'molecule_id', True))[0]
        self.assertEqual({key: enriched[key] for key in strict}, strict)
        self.assertEqual(enriched['molecular_weight_Da'], features['molecular_weight_Da'])
        wrong = {**strict, 'full_key': 'AAAAAAAAAAAAAA-AAAAAAAAAA-N'}
        with self.assertRaisesRegex(RuntimeError, 'Additive Common descriptor extraction failed'):
            enrich_batch(([wrong], 'molecule_id', True))


if __name__ == '__main__':
    unittest.main()
