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
        from ..pilot_v31_compact_v1.assemble import _permutation,_edge_set
        z=np.array([6,6,6,6]);reference=np.array([[0,1],[1,2],[2,3]]);source=np.array([[0,2],[2,1],[1,3]]);codes=np.ones(3,dtype='i4')
        perm,_=_permutation(z,reference,codes,z,source,codes)
        self.assertEqual(_edge_set(perm[source],codes),_edge_set(reference,codes))

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

        # The D6 IO option drops only discarded original-F64 hex provenance;
        # the actual original decoder/component/mask/target functions still run.
        import json
        from unittest.mock import patch
        from ..pilot_family_D3_census_resume_v3 import projection as P,configuration as C
        from ..family_export_day_v1.test_boundaries import compact
        field={'field_id':3,'field_key':'P.pm7_B.r73.value','registry_id':73,'task':'pm7_B','group':'P',
               'source_path':'values.sigma_pi_entries','component':'value','level':'sparse_atom_pair'}
        records=[{'atom_i':1,'basis_i':'P-SIGMA','atom_j':0,'basis_j':'S-SIGMA','value':.125},
                 {'atom_i':0,'basis_i':'P-PI','atom_j':1,'basis_j':'P-PI','value':-.25}]
        entry={'field':field,'field_id':3,'field_key':field['field_key'],'values_float64':[.125,-.25],'atom_indices':[None,None]}
        recipe={'input_kind':'ORIGINAL_REGISTRY_CELL_PARQUET','projection_adapter':'ORIGINAL_COMPONENT_READER_EXPLICIT_PAIR_AND_NULL_IO_V1',
                'components':{field['field_key']:C.component_selector(field,{'fields':{field['field_key']:{}}})}}
        target={'target_id':'raw','wire_kind':'SOURCE_ORDERED_RECORDS_V1','family':'bonding','geometry_source':'pm7','members':[{'field_key':field['field_key'],'registry_id':73}]}
        raw={'total_atoms':2,'values':[{'registry_id':73,'kind':8,'text':json.dumps(records)}]};typed={'compact_mask_json':P.K.binary_json_dumps(compact(3))}
        original,notes=P.projected_target([entry],typed,recipe,raw,2,target)
        self.assertIn('73',notes['original_native_cells_binary_json'])
        with patch.object(P,'native_payload_hex',side_effect=AssertionError('discarded F64 hex must not be built')) as payload:
            efficient,notes=P.projected_target([entry],typed,recipe,raw,2,target,capture_native_payload=False)
            payload.assert_not_called()
        self.assertEqual(notes['original_native_cells_binary_json'],{})
        self.assertEqual(set(original),set(efficient))
        for key in original:self.assertTrue(np.array_equal(original[key],efficient[key],equal_nan=True),key)

    def test_shared_r73_codes_include_U_and_preserve_order(self):
        record={'arrays':{},'r73_channels':[('s','p',None),('p','s','sigma'),('s','p',None)]}
        book=['__ABSENT__'];codes={};channel_codes(record,book,codes)
        self.assertEqual(record['arrays'][32].tolist(),[[1,2,0],[2,1,3],[1,2,0]])
        self.assertEqual(book,['__ABSENT__','s','p','sigma'])

    def test_registered_extra_remains_addressable_outside_ordinary_orders(self):
        import copy
        entries=records();extra=copy.deepcopy(entries[1])
        extra['gid']='extra';extra['metadata']['sprime_conf_idx']=7
        extra['metadata']['storage_physical_alias']='d5-diagnostic:extra'
        extra['metadata']['diagnostic_only']=True;extra['metadata']['excluded_from_all_training']=True
        extra['descriptor']['is_holdout']=True
        extra['metadata']['ordinary_sprime']=False;extra['metadata']['available_base_order_ranks']={}
        extra['arrays']['positions_A'][1,0]=1.5
        entries.append(extra);item=assemble_entries('m',entries,schema())
        self.assertEqual(item['m_arrays'][6].tolist(),[1,2])
        self.assertEqual(item['m_arrays'][8].tolist(),[0])
        self.assertEqual(item['m_arrays'][17].tolist(),[1,0])
        self.assertNotIn(11,item['m_arrays'])
        self.assertEqual([r['identity']['sprime_conf_idx'] for r in item['u_records']],[7,7])
        self.assertEqual(item['m_arrays'][14].tolist(),[0,1])
        self.assertEqual(item['u_records'][1]['identity']['storage_physical_alias'],'d5-diagnostic:extra')
        from .projected_source import apply_pprime_eligibility
        apply_pprime_eligibility(item,{'u':True,'extra':False});self.assertEqual(item['m_arrays'][18].tolist(),[1,0])

    def test_block_channel_dictionary_remaps_without_changing_K_order(self):
        record={'arrays':{32:np.array([[2,1,0],[1,2,0]],dtype='<u2')},'r73_codebook':['__ABSENT__','P-PI','S-SIGMA']}
        book=['__ABSENT__','S-SIGMA'];codes={'S-SIGMA':1}
        channel_codes(record,book,codes)
        self.assertEqual(record['arrays'][32].tolist(),[[1,2,0],[2,1,0]])

    def test_original_FULL_survives_outside_Common(self):
        from .identities import selected
        self.assertTrue(selected('FULL',False));self.assertFalse(selected('TRAIN',False))
        self.assertTrue(selected('VAL',True));self.assertFalse(selected('VAL',False))
        import tempfile
        from pathlib import Path
        import pyarrow as pa,pyarrow.parquet as pq
        from .prepare_runtime import source_pprime_addresses
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'physical.parquet'
            metadata=[{'record_id':rid,'molecule_id':'m','sprime_conf_idx':7,'geometry_id':gid,'fit_eligible':False,
                       'source_record_id':'native','native_atom_order_sha256':'existing-source-witness'}
                      for rid,gid in (('registered','existing-gid'),('unregistered',None))]
            pq.write_table(pa.Table.from_pylist(metadata),source)
            ref={'path':str(source),'bytes':source.stat().st_size}
            result=source_pprime_addresses({'runtime_metadata_root':str(Path(tmp)/'runtime')},{'source_geometry_pointer_tables':[ref]})
            self.assertEqual(result['records'],1)
            table=pq.read_table(result['files'][0]['path']);row=table.to_pylist()[0]
            self.assertEqual(row['source_row_index'],1);self.assertEqual(row['sprime_conf_idx'],7)
            self.assertIsNone(row['original_source_geometry_id']);self.assertTrue(row['excluded_from_all_training'])
            self.assertEqual(row['source_pprime_record_id'],'unregistered')
            self.assertNotIn('positions_A',table.schema.names)
    def test_cached_F64_pair_sums_bind_direction_onsite_and_original_order(self):
        from .derived_pair import bind_cached_pairs,augment_schema
        minimal={'target_layout':{'raw':{'array_name':'r73_ordered','mapping_target':{}}},'fields':[{'registry_id':73,'field_key':'r73','source_path':'values.sigma_pi_entries'}],'columns':{'pair_labels':[]},'array_definitions':{'27':{'shape':['J',0]}}}
        augment_schema(minimal);self.assertEqual(minimal['array_definitions']['27']['shape'],['J',2])
        arrays={'transport/raw/atom_i':np.array([1,0,1,1]),'transport/raw/atom_j':np.array([0,1,0,1])}
        definitions={name:{'field_id':fid,'target_id':name,'raw_target_id':'raw'} for name,fid in (('sigma',146),('pi',147))}
        entries=[{'field_id':fid,'values_float64':[.1+.2,None,.4],'value_mask':[True,False,True],
                  'pair_indices':[[1,0],[0,1],[1,1]]} for fid in (146,147)]
        bind_cached_pairs(arrays,entries,definitions)
        self.assertEqual(arrays['pairs/sigma'].tolist(),[[1,0],[0,1],[1,1]])
        self.assertEqual(arrays['values/sigma'].dtype,np.dtype('<f8'))
        self.assertEqual(arrays['values/sigma'][0],.1+.2);self.assertTrue(np.isnan(arrays['values/sigma'][1]))
        entries[0]['pair_indices'][0]=[0,1]
        with self.assertRaisesRegex(ValueError,'PAIR_ORDER_DIFFERS'):bind_cached_pairs(arrays,entries,definitions)

if __name__=='__main__':unittest.main()
