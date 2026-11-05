"""Exact registered-N1 typed layout with original acceptance in metadata_json."""
import json,struct,tempfile,unittest
from pathlib import Path
from . import prepare as P
from .run import checked_conformer

class LegacyGeometrySchema(unittest.TestCase):
    def test_publisher_metadata_restores_declared_state_without_default_or_ordinary_reclassification(self):
        import pyarrow as pa,pyarrow.parquet as pq
        top={'molecule_id':'opaque:M','sprime_conf_idx':1,'geometry_id':'frozen:N1:G',
            'atomic_numbers':[6,1],'coordinates':[[1.0000000000000002,-0.0,0.],[2.,0.,0.]],
            'atom_order_sha256':'existing-order','geometry_sha256':'existing-geometry','uff_energy_kcal_mol':1.25}
        metadata={k:v for k,v in top.items() if k not in ('coordinates','atomic_numbers')}
        metadata.update(status='SUCCESS',converged=True,source_record_id='authoritative:anchor',
            geometry_source='uff_sprime',origin='data_v1_n1_pprime2',ordinary_sprime_member=False,
            usage_domain='pprime_extra',ordinary_target_N_unchanged=1,new_UFF_or_QM_calls=0)
        stored=dict(top,metadata_json=json.dumps(metadata))
        shape=pa.schema([('molecule_id',pa.string()),('sprime_conf_idx',pa.int64()),('geometry_id',pa.string()),
            ('atomic_numbers',pa.list_(pa.int64())),('coordinates',pa.list_(pa.list_(pa.float64(),3))),
            ('atom_order_sha256',pa.string()),('geometry_sha256',pa.string()),('uff_energy_kcal_mol',pa.float64()),('metadata_json',pa.string())])
        with tempfile.TemporaryDirectory() as temporary:
            filename=Path(temporary)/'extra_geometries.float64.parquet'
            pq.write_table(pa.Table.from_pylist([stored],schema=shape),filename)
            locator={'molecule_id':'opaque:M','sprime_conf_idx':1,'geometry_id':'frozen:N1:G',
                'source_path':str(filename),'source_row_index':0,'source_format':'parquet','usage_domain':'registered_pprime_extra'}
            P.close_parquet_layout();P.parquet_group.cache_clear()
            try:result=P.geometry(locator)
            finally:P.close_parquet_layout();P.parquet_group.cache_clear()
            self.assertEqual((result['status'],result['converged'],result['source_record_id']),('SUCCESS',True,'authoritative:anchor'))
            self.assertIs(result['ordinary_sprime_member'],False);self.assertEqual(result['usage_domain'],'pprime_extra')
            for value,expected in zip(result['coordinates'][0],top['coordinates'][0]):self.assertEqual(struct.pack('<d',value),struct.pack('<d',expected))
            conf=checked_conformer(dict(locator,native_anchor_record_id='authoritative:anchor',original_sprime_conf_idx=1,
                physical_geometry_json=json.dumps(result)),{'z':[6,1],'native_atom_order_sha256':'existing-order'})
            self.assertEqual(conf['coordinates'],top['coordinates']);self.assertIs(conf['ordinary_sprime_member'],False)
            with self.assertRaisesRegex(ValueError,'DECLARATION_REQUIRED'):P.declared_geometry(top,locator)
            with self.assertRaisesRegex(ValueError,'GEOMETRY_NOT_ACTUALLY_USABLE'):
                P.declared_geometry(dict(stored,metadata_json=json.dumps(dict(metadata,converged=False))),locator)
            with self.assertRaisesRegex(ValueError,'METADATA_CONFLICT:molecule_id'):
                P.declared_geometry(dict(stored,metadata_json=json.dumps(dict(metadata,molecule_id='wrong'))),locator)
            with self.assertRaisesRegex(ValueError,'N1_EXTRA_CANNOT_BECOME_ORDINARY'):
                P.declared_geometry(stored,dict(locator,usage_domain='ordinary'))
