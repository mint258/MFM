"""Necessary checks for U-label support, role routing and numeric missingness."""
import unittest
import numpy as np
from .projected_source import assemble_entries
from .run import split_role,compare_arrays,channel_codes


def schema():
    return {'columns':{'d20':[],'mol_labels':[],'atom_labels':[{}],'atom_vectors':[],'pair_labels':[]},
            'target_layout':{'atom':{'array_name':'atom_labels','column_indices':[0]}},
            'role_codebook':{'TRAIN':0,'VAL':1,'FULL':2}}


def records():
    answer=[]
    for source,gid in [('pm7','p'),('uff_sprime','u')]:
        metadata={'molecule_id':'m','effective_role':'TRAIN','geometry_source':source,
                  'native_record_id':'native' if source=='pm7' else None,
                  'sprime_conf_idx':7 if source=='uff_sprime' else None,
                  'parent_geometry_id':None,'view_id':None,'available_base_order_ranks':{'fixed_random':0}}
        arrays={'atomic_numbers':np.array([6,1],dtype='i4'),'native_bond_index':np.array([[0],[1]],dtype='i4'),
                'native_bond_order':np.array([1],dtype='u1'),'positions_A':np.array([[0,0,0],[1,0,0]],dtype='f8')}
        descriptor={'kind':'geometry','geometry_source':source,'path':source+'/geometry','is_holdout':False}
        answer.append({'descriptor':descriptor,'gid':gid,'metadata':metadata,'arrays':arrays})
        if source=='uff_sprime':
            answer.append({'descriptor':dict(descriptor,kind='labels',path=source+'/label'),'gid':gid,'metadata':dict(metadata),
                           'arrays':{'values/atom':np.array([0.25,9.0],dtype='f8'),'valid/atom':np.array([1,0],dtype='u1')}})
    return answer


class StreamChecks(unittest.TestCase):
    def test_uff_source_labels_cast_once_and_original_invalid_mask(self):
        item=assemble_entries('m',records(),schema())
        self.assertEqual(len(item['p_records']),1);self.assertEqual(len(item['u_records']),1)
        values=item['u_records'][0]['arrays'][24]
        self.assertEqual(values.dtype,np.dtype('<f4'));self.assertEqual(values[0,0],0.25)
        self.assertTrue(np.isnan(values[1,0]));self.assertTrue(np.isnan(item['p_records'][0]['arrays'][24]).all())
        self.assertEqual(item['u_records'][0]['identity']['sprime_conf_idx'],7)

    def test_full_routine_routing_and_no_training_leakage(self):
        self.assertEqual(split_role('TRAIN'),('TRAIN',False));self.assertEqual(split_role('VAL'),('FULL',True))
        self.assertEqual(split_role('FULL'),('FULL',False))
        with self.assertRaises(ValueError):split_role('embargo')

    def test_numeric_gate_combines_absolute_relative_and_exact_nan(self):
        reference={23:np.array([0,1e5,np.nan],dtype='<f4')}
        compare_arrays({23:np.array([5e-7,1e5+0.05,np.nan],dtype='<f4')},reference)
        with self.assertRaisesRegex(ValueError,'NAN_MASK'):
            compare_arrays({23:np.array([0,1e5,0],dtype='<f4')},reference)
        with self.assertRaisesRegex(ValueError,'VALUE'):
            compare_arrays({23:np.array([1e-3,1e5,np.nan],dtype='<f4')},reference)

    def test_shared_r73_codes_include_U_and_preserve_order(self):
        record={'arrays':{},'r73_channels':[('s','p',None),('p','s','sigma'),('s','p',None)]}
        book=['__ABSENT__'];codes={};channel_codes(record,book,codes)
        self.assertEqual(record['arrays'][32].tolist(),[[1,2,0],[2,1,3],[1,2,0]])
        self.assertEqual(book,['__ABSENT__','s','p','sigma'])


if __name__=='__main__':unittest.main()
