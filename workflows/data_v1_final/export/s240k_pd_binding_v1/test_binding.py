"""One synthetic identity-only binding fixture; no production data or LMDB."""
import copy,json,pathlib,tempfile,unittest
from unittest.mock import patch
import pyarrow as pa
import pyarrow.parquet as pq
from . import run as R


class S240kPDBindingCheck(unittest.TestCase):
    def test_identity_only_binding_preserves_order_gaps_and_late_d6_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);subset=root/'original_S240k.parquet';srecords=root/'S_records.parquet'
            srecords.write_bytes(b'closed identity-index reference, never opened by binding')
            pq.write_table(pa.Table.from_pylist([{'molecule_id':mid,'forbidden_label':123.} for mid in ('m3','m1','m2','m4')]),subset)
            member=root/'members.parquet'
            def members(path,values):
                pq.write_table(pa.Table.from_pylist([dict(molecule_id=mid,effective_role=role,common_population=flag,forbidden_coords='must never project') for mid,role,flag in values]),path)
            members(member,[('m1','TRAIN',True),('m2','VAL',True),('m3','TRAIN',True)])
            common=root/'common.json';common.write_text(json.dumps({'status':'COMMON_POPULATION_V1_FROZEN','membership_tables':[R.I.ref(member)]}))
            template=root/'P_template.json';template.write_text(json.dumps({'root':None,'subset_path':str(subset),'source':'PM7','training_view':'original_view','normalizations':'original_routes'}))
            summary=root/'S_summary.json';summary.write_text(json.dumps({'status':'READY','molecules':4,'records':30,'path':str(srecords)}))
            plan={'subset_path':str(subset),'s_records':str(srecords),'s_summary':str(summary),'p_template':str(template),
                  'common':str(common),'expected_molecules':4,'expected_data_version':'final-toy',
                  'd6_manifest':str(root/'D6'/'manifest.json'),'output_root':str(root/'gaps')}
            observed=[];original_rows=R.rows
            def identity_rows(path,columns):
                observed.append((str(path),tuple(columns)));self.assertNotIn('forbidden_label',columns);self.assertNotIn('forbidden_coords',columns)
                self.assertNotEqual(str(path),str(srecords));return original_rows(path,columns)
            with patch.object(R,'rows',side_effect=identity_rows):first=R.prepare(plan)
            self.assertEqual(first['status'],'NOT_READY');self.assertIsNone(first['bindings']['P']['root']);self.assertIsNone(first['bindings']['D']['root'])
            self.assertIn('FINAL_D6_MANIFEST_NOT_PUBLISHED',first['not_ready_reasons'])
            table=pq.read_table(first['membership_binding']['table']['path']).to_pylist()
            self.assertEqual([row['molecule_id']for row in table],['m3','m1','m2','m4'])
            self.assertEqual([row['subset_ordinal']for row in table],[0,1,2,3])
            self.assertEqual([row['binding_status']for row in table],['COMMON_TRAIN','COMMON_TRAIN','NOT_TRAIN','MISSING_FROM_FINAL_COMMON'])
            self.assertEqual(first['membership_binding']['table']['records'],4);self.assertFalse(first['intersection_applied'])
            self.assertEqual(observed,[(str(subset),('molecule_id',)),(str(member),tuple(R.MEMBERSHIP_COLUMNS))])
            # A separate valid toy population verifies late root binding without replay.
            valid=root/'valid_members.parquet';members(valid,[(mid,'TRAIN',True)for mid in ('m1','m2','m3','m4')])
            valid_common=root/'valid_common.json';valid_common.write_text(json.dumps({'status':'COMMON_POPULATION_V1_FROZEN','membership_tables':[R.I.ref(valid)]}))
            ready_plan=dict(plan,common=str(valid_common),output_root=str(root/'valid'))
            before=R.prepare(ready_plan);self.assertEqual(before['status'],'NOT_READY')
            updated_template=json.loads(template.read_text());updated_template.update(root='resource-root-after-D6',output='new-run-output')
            template.write_text(json.dumps(updated_template));unchanged_template=template.read_text()
            final=pathlib.Path(plan['d6_manifest']);final.parent.mkdir()
            final.write_text(json.dumps({'format':'v3.1/MFM4','data_version':'final-toy','split_roots':{'TRAIN':'one_shared_TRAIN','FULL':'one_shared_FULL'}}))
            with patch.object(R,'rows',side_effect=AssertionError('closed membership binding reread')):
                ready=R.prepare(ready_plan);still_gaps=R.prepare(plan)
            self.assertEqual(ready['status'],'READY');self.assertEqual(ready['root'],str(final.parent))
            self.assertEqual(ready['bindings']['P'],ready['bindings']['D'])
            self.assertEqual(ready['bindings']['P']['subset_path'],str(subset));self.assertFalse(ready['new_LMDB_or_dataset_copy'])
            self.assertEqual(still_gaps['status'],'NOT_READY');self.assertIsNone(still_gaps['root'])
            self.assertFalse(ready['original_S']['record_positions_reused_as_D6_indices'])
            self.assertEqual(template.read_text(),unchanged_template)
            updated_template['subset_path']='different_population.parquet';template.write_text(json.dumps(updated_template))
            with self.assertRaisesRegex(ValueError,'P_TEMPLATE_IS_NOT_THE_ORIGINAL_S240K_SUBSET'):
                R.prepare(ready_plan)


if __name__=='__main__':unittest.main()
