"""Tiny native wire/mask/coverage and exact median/MAD oracles, never production scope."""
import copy
import hashlib
import json
import struct
import tempfile
import threading
from pathlib import Path
import unittest
from . import coverage,quantiles
from ..common import reference,dump_new,load


class D27Source(unittest.TestCase):
    def fixture(self,root,duplicate=False):
        import numpy as np
        import pyarrow as pa
        import pyarrow.parquet as pq
        from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K
        from workflows.data_v1_final.labels.streaming_v1 import calibration as C
        fields={fid:{'field_id':fid,'field_key':'fixture.'+str(fid),'source_path':'fixture'+str(fid)}for fid in range(27)}
        arrays={}
        for key,dtype,shape in [('fit','u1',(2,)),('owner','u1',(2,32)),('role','u1',(2,)),('atoms','<u4',(2,)),('group','<u2',(2,))]:
            arr=np.memmap(root/(key+'.bin'),dtype=dtype,mode='w+',shape=shape);arr[:]=0;arrays[key]=arr
        arrays['fit'][:]=[1,0];arrays['atoms'][:]=2
        for i in range(2):arrays['owner'][i]=np.frombuffer(hashlib.sha256(('fixture'+str(i)).encode()).digest(),dtype='u1')
        windows=[]
        for task,fids in [(0,list(range(20))),(1,list(range(20,27)))]:
            family='D20'if task==0 else'D3';rows=[]
            for physical in range(2):
                i=0 if duplicate else physical;entries=[]
                for fid in fids:
                    vals=[2.,6.]if fid==24 else[float(fid+1)]
                    entries.append({'field':fields[fid],'field_id':fid,'field_key':fields[fid]['field_key'],
                        'source_path':fields[fid]['source_path'],'values_float64':vals,'atom_indices':[0,1]if fid==24 else None,
                        'source_value_mask':[True]*len(vals),'value_mask':[True]*len(vals),
                        'source_reasons':[],'new_reasons':[],'review_reasons':[]})
                row={'row_kind':'task','record_ordinal':i,'task_code':task,'record_id':'fixture'+str(i),'role_code':0,
                    'file_id':task,'physical_row':physical,'row_group':0,'row_within_group':physical,
                    'owner_sha256':arrays['owner'][i].tobytes(),**K.pack_entries(entries),
                    'compact_mask_json':K.binary_json_dumps(K.B.compact.encode(i,task,entries)),'base_json':'','base_f64':b''}
                row['view_sha256']=K.row_signature(row);rows.append(row)
            part_path=root/(family+'.parquet');pq.write_table(pa.Table.from_pylist(rows,schema=K.schema(pa)),part_path)
            part={'reference':reference(part_path),'row_kind':'task','task_code':task,'rows':2,
                'typed_stream_sha256':hashlib.sha256(b''.join(r['view_sha256']for r in rows)).hexdigest()}
            source={'file_id':task,'family':family,'source_job_id':123}
            window={'source_reference':source,'physical_row_lo':0,'physical_row_hi':2,'parts':[part],'all_part_reopen_bits_verified':True}
            wpath=root/(family+'.json');dump_new(wpath,window)
            windows.append({**window,'window_reference':reference(wpath)})
        for arr in arrays.values():arr.flush()
        coverage.WORK.update(root=root,stop=threading.Event(),codec=K,calibration=C,arrays=arrays,byid=fields)
        return {'group_index':0,'source_job_id':123,'expected_records':2,'windows':windows}

    def tearDown(self):coverage.WORK.clear()

    def test_actual_codec_and_masks_preserve_atomic_weight_and_exclude_held_record(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);g=self.fixture(root);ref=coverage.group((g,'FIXTURE_NOT_A_FULL_COMMON_REFERENCE'))
            group=load(ref['path']);self.assertEqual(group['records'],2)
            self.assertEqual(group['fields']['0']['leaves'],1)
            self.assertEqual(group['fields']['24']['leaves'],2)
            out=quantiles.field((24,[group['fields']['24']],'FIXTURE_NOT_A_FULL_COMMON_REFERENCE'))
            actual=load(out['path']);self.assertEqual((actual['median'],actual['MAD'],actual['TRAIN_n'],actual['MAD_n']),(4.,2.,2,2))
            self.assertEqual(len({p['input_F64_sha256']for p in actual['passes']}),1)

    def test_duplicate_canonical_record_cannot_be_hidden_by_matching_row_counts(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);g=self.fixture(root,duplicate=True)
            with self.assertRaisesRegex(ValueError,'Duplicate canonical'):coverage.group((g,'FIXTURE_DUPLICATE'))

    def test_membership_only_component_keeps_descriptor_failures_in_the_full_census(self):
        from ..exact_nn_cached_v1.test_alpha_common import fixture
        from .membership import component
        p=fixture();p['result']['geometry_bodies_transported_or_revalidated']=False
        p['result']['actual_worker_proofs']=[{'path':'/fixture-worker-'+str(i)}for i in range(16)]
        p['result']['HOLD_MIDs']=119;p['result']['strict5_rows']=1196003
        p['result']['status']='SOURCE_GRAPH_HOLD_NOT_A_SUBSET_REFERENCE'
        self.assertEqual(component(p)['expected_all_common_census']['molecules'],1196122)
        p['result']['scan']['all_common_observed_census']['molecules']=1196003
        with self.assertRaisesRegex(ValueError,'Complete original'):component(p)
    def test_exact_even_median_MAD_matches_independent_sorted_fraction_oracle(self):
        from fractions import Fraction
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);self.fixture(root);values=[-3.,-0.,1.,7.]
            p=root/'oracle.f64';p.write_bytes(struct.pack('<4d',*values));ref={**reference(p),'leaves':4}
            result=load(quantiles.field((0,[ref],'FIXTURE_ORACLE'))['path'])
            def median(xs):
                xs=sorted(Fraction.from_float(x)for x in xs);return float((xs[(len(xs)-1)//2]+xs[len(xs)//2])/2)
            med=median(values);mad=median([abs(x-med)for x in values])
            self.assertEqual((result['median'],result['MAD'],result['TRAIN_n']),(med,mad,4))


if __name__=='__main__':unittest.main()
