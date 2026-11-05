"""New metadata binding logic only; no old-statistics tests, source files or fit."""
import unittest
from .run import build_dataset


def fixture():
    fields=[{'field_id':41,'field_key':'energy','registry_id':20,'task':'pm7_A','level':'molecule','element_reference_eligible':True},
        {'field_id':42,'field_key':'gradient','registry_id':58,'task':'pm7_B','level':'atom_vector','element_reference_eligible':False}]
    fields += [{'field_id':50+i,'field_key':'q.'+name,'registry_id':674,'task':'xtb_singlepoint','level':'molecule_tensor','element_reference_eligible':False}
        for i,name in enumerate(('xx','xy','yy','xz','yz','zz'))]
    def row(key,field,mean,std,series_id):
        return {'key':key,'source_field_key':field,'source_field_id':41 if field=='energy' else (42 if field=='gradient' else 50),
            'field_id':series_id,'view':'fixture','n':10,'mean':mean,'std_ddof0':std,'lower':-10.,'upper':100.,'status':'DEFINED'}
    statistics={'series':[row('41/residual','energy',3.,2.,999),row('41/raw','energy',50.,8.,1000),
        row('42/norm','gradient',10.,4.,1001),row('physical/674/xtb_singlepoint/frobenius_norm','q.xx',12.,6.,1002)]}
    models={'41':{'basis':[1,6],'intercept':0.8,'coefficients':[-0.1,-9.0]}}
    schema={'fields':[dict(f,loss_enabled=(False if f['registry_id']==674 else True)) for f in fields],
        'target_layout':{'e':{'kind':'scalar','mapping_target':{'kind':'scalar','members':[{'field_key':'energy'}]}},
            'g':{'kind':'vector','mapping_target':{'kind':'vector','members':[{'field_key':'gradient'}]}},
            'q':{'kind':'symmetric_tensor','mapping_target':{'kind':'symmetric_tensor','members':[{'field_key':f['field_key']} for f in fields if f['registry_id']==674]}}}}
    policy={'r674':{'normalization':{'centering':'FIXED_ZERO','scale':'SERIES_STD_DDOF0','per_head_single_scale':True,
        'series_key_template':'physical/<registry_id>/<task>/frobenius_norm'}}}
    return fields,statistics,models,schema,policy


class PublisherTests(unittest.TestCase):
    def test_scalar_energy_original_field_identity_and_existing_tensor_policy(self):
        fields,statistics,models,schema,policy=fixture()
        value=build_dataset('P_D',fields,statistics,models,schema,policy,{'path':'formal-existing-policy.json'})
        scalar=value['targets']['e']
        self.assertEqual((scalar['series_key'],scalar['center'],scalar['scale']),('41/residual',3.,2.))
        self.assertEqual(scalar['coefficients_by_atomic_number'],{'1':-0.1,'6':-9.0})
        self.assertEqual(scalar['element_reference']['intercept'],0.8)
        self.assertEqual(value['field_series']['energy']['source_field_id'],41)
        self.assertEqual(value['field_series']['energy']['series']['41/residual']['field_id'],999)
        tensor=value['targets']['q']
        self.assertEqual((tensor['center'],tensor['scale']),(0.0,6.0))
        self.assertTrue(tensor['per_head_single_scale']);self.assertFalse(tensor['original_loss_enabled'])
        self.assertEqual(tensor['raw_invariant_mean_status'],'RAW_MEAN_F_REPORT_PENDING')
        self.assertEqual(value['targets']['g']['status'],'FIXED_ZERO_SINGLE_SCALE_POLICY_PENDING')
        self.assertFalse(value['targets']['g']['normalizer_ready'])

    def test_Pprime_independent_and_degenerate_scale_target_local(self):
        import copy
        fields,statistics,models,schema,policy=fixture()
        pm=build_dataset('P_D',fields,statistics,models,schema,policy,{})
        pp=copy.deepcopy(statistics);pp['series'][0].update(mean=30.,std_ddof0=7.)
        independent=build_dataset('Pprime',fields,pp,models,schema,policy,{})
        self.assertEqual(pm['targets']['e']['scale'],2.)
        self.assertEqual((independent['targets']['e']['center'],independent['targets']['e']['scale']),(30.,7.))
        pp['series'][0]['std_ddof0']=0.0
        partial=build_dataset('Pprime',fields,pp,models,schema,policy,{})
        self.assertFalse(partial['targets']['e']['normalizer_ready'])
        self.assertEqual(partial['targets']['e']['status'],'LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE')
        self.assertTrue(partial['targets']['q']['normalizer_ready'])
        unbound=build_dataset('Pprime',fields,statistics,{'41':{'basis':[1,6],'intercept':0.0,'coefficients':None}},schema,policy,{})
        self.assertEqual(unbound['targets']['e']['status'],'LOSS_DISABLED_ELEMENT_REFERENCE_UNBOUND')
        self.assertFalse(unbound['targets']['e']['normalizer_ready'])
        missing=build_dataset('Pprime',[],{'series':[]},{},schema,policy,{})
        self.assertEqual(missing['targets']['e']['status'],'NOT_IN_THIS_STATISTICS_DATASET')
        self.assertNotIn('scale',missing['targets']['e'])

    def test_unimplemented_frozen_recipe_does_not_invent_RMS_or_vector_scale(self):
        fields,statistics,models,schema,policy=fixture()
        binding={'g':{'policy_reference':{'path':'hypothetical-existing-policy.json'},'json_pointer':'/vector',
            'recipe':{'centering':'FIXED_ZERO','scale':'RMS','per_head_single_scale':True}}}
        value=build_dataset('P_D',fields,statistics,models,schema,policy,{},binding)
        self.assertEqual(value['targets']['g']['status'],'FROZEN_PHYSICAL_RECIPE_NOT_SUPPORTED_BY_EXISTING_SERIES')
        self.assertFalse(value['targets']['g']['normalizer_ready'])
        self.assertNotIn('scale',value['targets']['g'])


if __name__=='__main__':unittest.main()