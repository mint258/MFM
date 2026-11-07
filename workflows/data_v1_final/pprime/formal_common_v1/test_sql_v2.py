"""SQL fixture v2: provide required pilot_config pin. Production validators unchanged."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from common_v1 import IO,PARENT
from prepare_v1 import plan,materialize,row_group,VERIFIED_SOURCES
sys.path.insert(0,str(PARENT/'retention_v1'))


class FrozenMetadataBinding(unittest.TestCase):
    def test_old_gapped_ids_first_two_n1_pending_and_real_physical_row_resolution(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def js(name,value):return IO.write_json(root/name,value)
            def parquet(name,rows):
                path=root/name;pq.write_table(pa.Table.from_pylist(rows),path);return IO.reference(path)
            source_plan=js('source_plan.json',[{'path':f'/frozen/source{i}.lmdb','shard_id':i} for i in range(11)])
            c={'external_output_root':str(root),'raw_policy':js('policy_fixture.json',{'fixture_only':True}),
               'pilot_config':js('pilot_config_fixture.json',{'fixture_only':True}),
               'max_output_bytes':8*1024**3,'maximum_source_decode_bytes':512*1024**2}
            config=js('config_fixture.json',{'fixture_only':True})
            pilot={'role_manifest':{'sha256':'r'*64},'large_authority_pins':[],'source_plan':source_plan}
            members=[];physical=[];orders=[];native=[];molecules=[];conformers=[]
            for mid,ids,n,role in (('m0',[2,6],2,'TRAIN'),('m1',[1,8],2,'TRAIN'),('m2',[0],1,'VAL')):
                members.append({'molecule_id':mid,'common_population':True,'S_conformers':n,
                    'source_role':'FULL' if role=='VAL' else 'TRAIN','effective_role':role})
                anchor='native:'+mid
                native.append({'record_id':anchor,'molecule_id':mid,'source_path':'/frozen/source6.lmdb',
                    'real_index':len(native),'record_payload_sha256':'p'*64,'heavy_atoms':2,'total_atoms':2,'smiles':'CC'})
                molecules.append({'molecule_id':mid,'file_group':5,'max_heavy_atoms':2})
                ranked=sorted(ids,key=lambda i:(IO.stable_key(20261025,mid,'uff_sprime',i),str(i)))
                for idx in ids:
                    position=len(conformers)
                    conformers.append({'molecule_id':mid,'sprime_conf_idx':idx,'source_record_id':anchor,
                        'coordinates':[[float(idx),0.,0.],[float(idx)+1.,0.,0.]],'atom_order_sha256':'a'*64,
                        'status':'SUCCESS','converged':True,'seed':123})
                    gid=f'uff-fixture:{mid}:{idx}'
                    physical.append({'molecule_id':mid,'geometry_id':gid,'geometry_source':'uff_sprime',
                       'sprime_conf_idx':idx,'original_sprime_conf_idx':idx,'native_anchor_record_id':anchor,
                       'source_format':'parquet','source_row_index':position,'source_member':None,
                       'atom_order_sha256':'a'*64,'seed':123,'candidate_id':None,'geometry_sha256':None})
                    orders.append({'molecule_id':mid,'geometry_id':gid,'geometry_source':'uff_sprime',
                       'method':'fixed_random','rank':ranked.index(idx)})
            coordinates=parquet('source_conformers.parquet',conformers)
            for row in physical:row.update(source_path=coordinates['path'],source_bytes=coordinates['bytes'],source_sha256=coordinates['sha256'])
            member_pin=parquet('members.parquet',members);order_pin=parquet('order.parquet',orders)
            map_pin=parquet('map.parquet',physical)
            pilot['record_index']=parquet('native_index.parquet',native)['path']
            pilot['molecule_index']=parquet('molecules.parquet',molecules)['path']
            protocol=js('protocol_fixture.json',{'fixture_only':True})
            pilot['legacy_contract']=js('contract_fixture.json',{'protocol':protocol})
            common=js('common.json',{'status':'COMMON_POPULATION_V1_FROZEN','membership_tables':[member_pin],
                'roles_manifest_sha256':'r'*64})
            frozen_order=js('orders.json',{'status':'CONFORMER_ORDER_V1_FROZEN','order_tables':[order_pin],
                'common_manifest_sha256':common['sha256'],'seed':20261025,'random_identity_basis':'canonical_sprime_conf_idx'})
            geometry=js('geometry.json',{'status':'CANONICAL_GEOMETRY_MAP_V1_FROZEN','map_tables':[map_pin],
                'common_manifest_sha256':common['sha256'],'order_manifest':frozen_order})
            review=js('pilot_review_fixture.json',{'fixture_only':True})
            gates={'allocated_core_seconds_per_requested_conformer':7.8,'allocated_core_seconds':15600}
            a=argparse.Namespace(config=Path(config['path']),pilot_review=Path(review['path']),
                common_manifest=Path(common['path']),order_manifest=Path(frozen_order['path']),
                geometry_manifest=Path(geometry['path']),audit_identity_manifest=None,output=root/'planned')
            with patch('prepare_v1.pilot_review',return_value=({}, {'retention_policy':c['raw_policy']},gates)):
                plan(a,c,pilot)
                saved=json.loads((a.output/'plan.json').read_text())
                self.assertEqual((saved['common_molecules'],saved['ready_molecules'],saved['pending_two_real_geometries'],saved['requested_records']),(3,2,1,4))
                self.assertEqual(saved['status'],'BASELINE_READY_COMMON_SUBSET_N1_PENDING_NOT_FULL')
                b=argparse.Namespace(config=a.config,plan=a.output/'plan.json',batch_id=0,output=root/'prepared')
                materialize(b,c,pilot)
            rows=[json.loads(line) for line in (b.output/'pairs.jsonl').read_text().splitlines()]
            self.assertEqual({(r['molecule_id'],r['conformer']['sprime_conf_idx']) for r in rows},{('m0',2),('m0',6),('m1',1),('m1',8)})
            self.assertEqual(len({r['once_key'] for r in rows}),4)
            self.assertTrue(all(r['source']['shard_id']==6 and r['source']['file_group']==5 for r in rows))
            self.assertTrue(all(r['record_id']==f"pprime:{r['molecule_id']}:{r['conformer']['sprime_conf_idx']}" for r in rows))
            row_group.cache_clear();VERIFIED_SOURCES.clear()


if __name__=='__main__':
    with patch('subprocess.Popen',side_effect=AssertionError('NO_SUBPROCESS_ALLOWED_IN_METADATA_FIXTURE')):
        unittest.main(verbosity=2)
