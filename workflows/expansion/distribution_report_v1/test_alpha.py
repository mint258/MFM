"""Native population-only counts and independent Alpha resource dispatch fixtures."""
import csv
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch
from . import __main__ as runtime
from .aggregate import completion,ingest_enriched,load_moments,open_state
from .functional_groups import enrich_batch
from .io import write_new
from .population_tables import export


class AlphaDistribution(unittest.TestCase):
    def test_native_population_tables_preserve_H_only_mass_and_original_functional_groups(self):
        # Explicit tiny synthetic rows, never an accepted production1M manifest.
        ethanol={'full_key':'LFQSCWFLJHTTHZ-UHFFFAOYSA-N','source_smiles':'CCO',
            'heavy_atoms':3,'molecular_weight_Da':46.069,'rings':0,'aromatic_rings':0,
            'isotopic_atoms':0,'stereocenters':0,'logp':-.0014,'tpsa_A2':20.23,
            'hbd':1,'hba':1,'rotatable_bonds':0,'non_h_composition':[[6,2],[8,1]],
            'elements':[6,8],'element_combination':'6,8','generic_murcko':'','generic_ring_systems':[]}
        hydrogen={**ethanol,'full_key':'UFHFLCQGNIYNRP-UHFFFAOYSA-N','source_smiles':'[H][H]',
            'heavy_atoms':0,'molecular_weight_Da':2.016,'logp':0.,'tpsa_A2':0.,'hbd':0,'hba':0,
            'non_h_composition':[],'elements':[],'element_combination':''}
        rows=[{**ethanol,'molecule_id':'fixture_ethanol_1'},
            {**hydrogen,'molecule_id':'fixture_hydrogen'},
            {**ethanol,'molecule_id':'fixture_ethanol_2'}]
        enriched=enrich_batch((rows,'molecule_id',False))
        self.assertEqual([{k:row[k] for k in old} for row,old in zip(enriched,rows)],rows)
        self.assertEqual([row['functional_groups']['fr_Al_OH'] for row in enriched],[1,0,1])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);db=open_state(root/'fixture.sqlite')
            try:
                db.execute('INSERT INTO populations VALUES(?,?,?,1)',('v1_common','{}',3))
                ingest_enriched(db,'v1_common','molecule_id',enriched,load_moments(db,'v1_common'))
                artifacts,groups=export(db,root)
                self.assertEqual(groups,('v1_common',))
                hist=list(csv.DictReader((root/'fixed_histograms_and_bin_ecdf.csv').open()))
                heavy=[row for row in hist if row['field']=='heavy_atoms']
                self.assertEqual(sum(int(row['count']) for row in heavy),3)
                self.assertEqual(float(heavy[-1]['bin_ecdf']),1.)
                fg=list(csv.DictReader((root/'functional_groups.csv').open()))
                alcohol=next(row for row in fg if row['definition']=='fr_Al_OH')
                self.assertEqual((int(alcohol['molecules_present']),int(alcohol['total_unique_matches'])),(2,2))
                summary=json.loads((root/'population_summary.json').read_text())
                self.assertFalse(summary['Common_or_exact_nearest_comparison_claimed'])
                self.assertEqual(summary['scaffold_long_tail']['v1_common']['acyclic_empty_scaffold_molecules'],3)
                self.assertEqual(db.execute("SELECT n FROM counts WHERE kind='element_combination' AND key=''").fetchone()[0],1)
                with self.assertRaises(RuntimeError):completion(db,baseline_only=True)
            finally:db.close()

    def test_alpha_branch_uses_shared_guard_and_never_Main_quota_dispatch(self):
        # Admission is stubbed only for this isolated runtime seam; it is not
        # Alpha admission/accounting evidence and does no scientific ingestion.
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);plan=root/'plan.json'
            write_new(plan,{'schema':'EXPANSION_DISTRIBUTION_PLAN_V1','analysis_version':'FIXTURE_ONLY',
                'runtime_profile_reference':{'fixture_only':True},'workers':1,
                'output_directory':str(root/'output'),'population_manifests':[]})
            guard=MagicMock();actual={'fixture_only':True,'uid':os.getuid()}
            with (patch.dict(os.environ,{'SLURM_JOB_ID':'FIXTURE_NOT_A_JOB'}),
                    patch('workflows.expansion.alpha_runtime_v1.profile.admit',return_value=actual) as admit,
                    patch('workflows.expansion.alpha_runtime_v1.guard.Guard',return_value=guard),
                    patch.object(runtime,'recipe',return_value={'fixture_only':True}),
                    patch.object(runtime,'resources',side_effect=AssertionError('Main resource backend called'))):
                runtime.run(plan,'populations')
            admit.assert_called_once();guard.sample.assert_called();guard.close.assert_called_once()


if __name__=='__main__':unittest.main()
