"""New source-view boundaries; the previously validated scientific objects stay original."""
import unittest


class SourceViews(unittest.TestCase):
    def test_00_actual_config_uses_original_canonical_ledger_from_worktree(self):
        from pathlib import Path
        from .context import bind_original_namespace
        ref=dict(path='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/conformers/formal_cpu_auto_v3.json',
          bytes=3597,sha256='49567f12d439dc98697acec3c1034e2341c739781f6237d5959f59ddc32bef74')
        repo=bind_original_namespace(ref)
        from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as F
        value=F.config(ref)
        self.assertEqual(F.REPO,repo);self.assertEqual(F.RUN,repo.parent)
        self.assertEqual(F.LEDGER,Path(value['attempt_ledger_root']))
        self.assertEqual(F.BASE,Path(value['external_output_root']))
        self.assertIn(repo,Path(F.__file__).absolute().parents)

    def test_10_fresh_main_original_style_spawn_before_DATA(self):
        import json,os,subprocess,sys,tempfile
        from pathlib import Path
        checkout=Path(__file__).absolute().parents[3]
        with tempfile.TemporaryDirectory(prefix='common_source_spawn_') as folder:
            out=Path(folder)/'proof';env=dict(os.environ)
            env['PYTHONPATH']=str(checkout)+os.pathsep+env.get('PYTHONPATH','')
            result=subprocess.run([sys.executable,'-B','-m','workflows.expansion.expansion_common_reference_v1.run',
              '--source-spawn-fixture',str(out)],cwd=checkout,env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
            value=json.loads((out/'receipt.json').read_text());self.assertEqual(value['status'],'PASS')
            self.assertFalse(value['original_dataset_DATA_read']);self.assertEqual(value['workers'],16)

    def test_20_manifest_decimal_count_transport_is_exact_above_2pow53(self):
        import json
        from decimal import Decimal
        from .context import common_manifest_json
        number=2**53+123456789
        source=dict(schema='COMMON_POPULATION_PRODUCER_V1',roles=[dict(effective_role='TRAIN',molecules=3,
          pm7_records=Decimal(number),uff_records=Decimal('123456789012345678901234567890'))],other_count=7)
        parsed=json.loads(json.dumps(common_manifest_json(source)))
        self.assertEqual(parsed['roles'][0]['pm7_records'],number)
        self.assertEqual(parsed['roles'][0]['uff_records'],123456789012345678901234567890)
        self.assertIsInstance(source['roles'][0]['pm7_records'],Decimal)
        other=dict(schema='UNRELATED_MANIFEST',roles=[dict(pm7_records=Decimal('1.25'))])
        self.assertIs(common_manifest_json(other),other)

    def test_21_manifest_rejects_fractional_or_nonfinite_decimal_counts(self):
        from decimal import Decimal
        from .context import common_manifest_json
        for number in ('1.000000000000000001','NaN','Infinity','-Infinity'):
            with self.subTest(number=number),self.assertRaises(ValueError):
                common_manifest_json(dict(schema='COMMON_POPULATION_PRODUCER_V1',roles=[dict(pm7_records=Decimal(number),uff_records=1)]))

    def test_unchanged_scientific_objects_and_unknown_exclusion(self):
        from workflows.data_v1_final.conformers.postprocess_day_v1 import common as M
        from workflows.data_v1_final.conformers.formal_cpu_auto_finalize_mapping_v2 import finalize as F
        self.assertIs(M.membership,F.membership);self.assertIs(M.merge_counts,F.merge_counts);self.assertIs(M.exclusion_gates,F.exclusion_gates)
        base=dict(effective_role='TRAIN',S_usable_conformers=2,S_conformers=2,records=2,Sprime_status='SUCCESS',merged_uff_count=2)
        self.assertTrue(M.membership(base)['common_population'])
        self.assertFalse(M.membership(dict(base,fill_status='EXECUTION_UNRESOLVED'))['common_population'])
        self.assertFalse(M.membership(dict(base,effective_role='FULL'))['common_population'])
        self.assertFalse(M.membership(dict(base,merged_uff_count=1))['common_population'])

    def test_original_merge_never_counts_old_replacement_rows_twice(self):
        from workflows.data_v1_final.conformers.formal_cpu_auto_finalize_mapping_v2.finalize import merge_counts
        rows=[dict(origin='accepted_sprime',kernel_sprime_conf_idx=0,seed=2,candidate_id=None),
              dict(origin='data_v1_fill_10N',kernel_sprime_conf_idx=1,seed=3,candidate_id=7)]
        self.assertEqual(merge_counts(1,rows,2),2)
        with self.assertRaises(ValueError):merge_counts(1,rows+[rows[1]],3)
        with self.assertRaises(ValueError):merge_counts(2,[rows[1]],3)

    def test_actual_source_graph_selector_preserves_difference_and_multiple_graph_hold(self):
        from workflows.expansion.common_molecular_fp_candidate_v1 import selection as S,projection as P,contracts as C
        row={k:None for k in C.REQUIRED_IDENTITY_COLUMNS};row.update(molecule_id='actualMID',record_id='actualREC',smiles=' C[C@H](O)N ',canonical_smiles='CC(O)N',
            QC_key_reproduction_mismatch_accepted_difference=True,QC_other_layer_accepted_difference=True)
        chosen=S.select(row)
        self.assertEqual(chosen['source_smiles_for_original_template'],'C[C@H](O)N')
        self.assertTrue(chosen['original_identity']['QC_key_reproduction_mismatch_accepted_difference'])
        first=dict(isomeric_smiles='CCO',full_key='AAAAAAAAAAAAAA-BBBBBBBBBB-C',ecfp4_2048_hex='00'*256,generic_murcko='',generic_ring_systems=[])
        second=dict(first,isomeric_smiles='COC',full_key='CCCCCCCCCCCCCC-DDDDDDDDDD-E')
        result=P.reduce_variants('actualMID','TRAIN',2,[dict(status='FEATURES_DERIVED',features=f) for f in (first,second)])
        self.assertEqual(result['status'],'HOLD');self.assertIsNone(result['strict5_projection'])


if __name__=='__main__':unittest.main()
