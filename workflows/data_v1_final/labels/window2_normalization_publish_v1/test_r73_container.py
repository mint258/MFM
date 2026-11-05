"""One new raw-container versus approved pair-sum metadata fixture only."""
import unittest
from .run import build_dataset
from workflows.data_v1_final.export.v31_stream_v1.derived_pair import augment_schema


class R73ContainerRouteTests(unittest.TestCase):
    def test_raw_r73_is_diagnostic_only_derived_scalars_keep_their_own_series(self):
        raw={'field_id':40,'field_key':'P.pm7_A.r73.value','registry_id':73,'task':'pm7_A',
            'level':'pair','component':'value','source_path':'values.r73','element_reference_eligible':False,
            'loss_enabled':True,'loss_status':'ACTUAL_TARGET_CONDITION_SOURCE_ENABLED',
            'physical_policy_status':'ACTUAL_TARGET_CONDITION_SOURCE_ENABLED'}
        target={'target_id':'raw-r73','kind':'scalar','level':'pair','wire_kind':'SOURCE_ORDERED_RECORDS_V1',
            'members':[{'field_key':raw['field_key'],'registry_id':73,'component':'value','source_path':'values.r73'}]}
        schema={'fields':[raw],'target_layout':{'raw-r73':{'array_name':'r73_ordered','kind':'scalar',
            'column_indices':[0],'mapping_target':target}},'columns':{'pair_labels':[]},
            'array_definitions':{'27':{'shape':['pairs',0]}}}
        augment_schema(schema)  # Same already-approved D6 metadata builder.
        fields=[raw,*schema['derived_training_fields']]
        rows=[]
        for field,mean,scale in ((raw,100.,90.),(fields[1],1.,2.),(fields[2],3.,4.)):
            rows.append({'key':str(field['field_id'])+'/raw','source_field_key':field['field_key'],
                'source_field_id':field['field_id'],'field_id':900+field['field_id'],
                'n':5,'mean':mean,'std_ddof0':scale,'lower':-1.,'upper':200.,'status':'DEFINED'})
        result=build_dataset('P_D',fields,{'series':rows},{},schema,{}, {'path':'existing-policy.json'})
        container=result['targets']['raw-r73']
        self.assertEqual(container['status'],'RAW_CONTAINER_STATISTICS_ONLY')
        self.assertFalse(container['normalizer_ready']);self.assertNotIn('scale',container)
        self.assertEqual(container['raw_series_keys'],['40/raw'])
        self.assertTrue(container['original_loss_enabled'])
        self.assertEqual(container['source_loss_policy'][raw['field_key']]['physical_policy_status'],raw['physical_policy_status'])
        self.assertEqual(result['field_series'][raw['field_key']]['series']['40/raw']['std_ddof0'],90.)
        for name,fid,mean,scale in (('sigma',146,1.,2.),('pi',147,3.,4.)):
            tid=schema['derived_r73_pair_targets'][name]['target_id'];route=result['targets'][tid]
            self.assertEqual(route['series_key'],str(fid)+'/raw')
            self.assertEqual((route['center'],route['scale']),(mean,scale))
            self.assertTrue(route['normalizer_ready']);self.assertIn(tid,container['derived_training_target_ids'])
            self.assertNotEqual(route['scale'],90.)


if __name__=='__main__':unittest.main()