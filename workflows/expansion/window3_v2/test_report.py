import json
from pathlib import Path
import tempfile
import unittest
from .report import combine


class Tests(unittest.TestCase):
    def make(self, root, name, n, conf):
        out = root/name; out.mkdir()
        summary={'counts':{'molecules':n,'conformers':conf,'molecule_seconds':1.,'molecule_CPU_seconds':1.},
                 'streams':{'R':n//2,'N':n//2},'states':{'SUCCESS':n},
                 'masks':{'field:R':{'records':n,'newly_masked_records':n//50,'source_missing_records':0}}}
        (out/'summary.json').write_text(json.dumps(summary))
        files=[{'path':str(out/(family+'.parquet')),'size':10,'rows':rows} for family,rows in
               [('D20',n),('source_status',n),('D3',conf),('geometry',conf)]]
        (out/'manifest.json').write_text(json.dumps(files))
        return str(out)

    def test_summary_merge_accepts_report_only_new_masks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            config={'pilot':self.make(root,'pilot',10000,15000),
                    'full_shards':[self.make(root,'full',2490000,4000000)]}
            totals,streams,states,reasons,rates,families,files=combine(config)
            self.assertEqual(totals['molecules'],2500000)
            self.assertEqual(totals['conformers'],4015000)
            self.assertEqual(streams,{'R':1250000,'N':1250000})
            self.assertAlmostEqual(rates[0]['fraction'],.02,places=12)
            self.assertEqual(set(files[0]),{'path','size','rows'})

    def test_incomplete_population_cannot_be_finalized(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            config={'pilot':self.make(root,'pilot',10000,15000),'full_shards':[]}
            with self.assertRaisesRegex(ValueError,'NOT_COMPLETE'):combine(config)


if __name__=='__main__':unittest.main()
