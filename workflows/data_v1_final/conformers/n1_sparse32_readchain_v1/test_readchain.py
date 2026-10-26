"""Six synthetic bit/pointer/bound boundaries; no dataset, optimizer or QM."""
import math,struct,unittest
from . import common as U
from .signatures import field_signature as signature,compare_signatures
from .main_export import grouping

class ExactReadBoundaries(unittest.TestCase):
    def test_scalar_zero_None_nan_payload_signed_zero_and_container_slots_survive(self):
        a=struct.unpack('>d',bytes.fromhex('7ff8000000000001'))[0]
        b=struct.unpack('>d',bytes.fromhex('7ff8000000000002'))[0]
        value={'zero':0,'false':False,'none':None,'empty':'','bytes':b'\x00','slots':[0,None,float('nan')],'nan':a,'negative_zero':-0.0}
        result=signature(value);self.assertEqual(result['status'],'COMPLETE_TYPED_SIGNATURE')
        entries=result['tree']['entries'];self.assertEqual(len(entries),8)
        self.assertEqual(compare_signatures(result,signature(dict(value))),'EXACT_TYPED_FIELD_BITS_MATCH')
        self.assertEqual(compare_signatures(result,signature(dict(value,nan=b))),'FIELD_SIGNATURE_DRIFT')
        self.assertEqual(compare_signatures(signature(-0.0),signature(0.0)),'FIELD_SIGNATURE_DRIFT')
        self.assertNotEqual(signature(0)['tree'],signature(False)['tree'])

    def test_numpy_dtype_shape_C_order_raw_bits_and_nan_payload_remain_distinct(self):
        import numpy as np
        a=np.array([0x80000000,0x7fc00001,0x00000000,0x3f800000],dtype='<u4').view('<f4').reshape(2,2)
        result=signature(a);self.assertEqual(result['status'],'COMPLETE_TYPED_SIGNATURE')
        self.assertEqual(result['tree']['bytes'],16);self.assertEqual(result['tree']['dtype'],'<f4')
        self.assertEqual(compare_signatures(result,signature(a.copy())),'EXACT_TYPED_FIELD_BITS_MATCH')
        self.assertEqual(compare_signatures(result,signature(a.astype('<f8'))),'FIELD_SIGNATURE_DRIFT')
        self.assertEqual(compare_signatures(result,signature(a.reshape(4))),'FIELD_SIGNATURE_DRIFT')
        changed=a.copy();changed.view('<u4')[0,1]=0x7fc00002
        self.assertEqual(compare_signatures(result,signature(changed)),'FIELD_SIGNATURE_DRIFT')

    def test_torch_native_dtype_bits_and_PyG_to_dict_idx_are_not_reindexed(self):
        import torch
        from torch_geometric.data import Data
        value=torch.tensor([-(1<<31),0x7fc00001],dtype=torch.int32).view(torch.float32)
        result=signature(value);self.assertEqual(result['status'],'COMPLETE_TYPED_SIGNATURE')
        self.assertEqual(result['tree']['bytes'],8)
        self.assertEqual(compare_signatures(result,signature(value.clone())),'EXACT_TYPED_FIELD_BITS_MATCH')
        self.assertEqual(compare_signatures(result,signature(value.to(torch.float64))),'FIELD_SIGNATURE_DRIFT')
        bf=signature(torch.tensor([0.,-0.,1.],dtype=torch.bfloat16));self.assertEqual(bf['status'],'COMPLETE_TYPED_SIGNATURE');self.assertEqual(bf['tree']['bytes'],6)
        data=Data(x=torch.tensor([0,5]),idx=torch.tensor(17),pos=torch.zeros((2,3)),label=None,zero=torch.tensor(0.))
        before=data.to_dict();sig=signature(data)
        self.assertEqual(sig['tree']['kind'],'pyg_Data_to_dict');self.assertEqual(data.idx.item(),17)
        self.assertEqual(list(data.to_dict()),list(before));self.assertEqual(compare_signatures(sig,signature(data.clone())),'EXACT_TYPED_FIELD_BITS_MATCH')
        data.idx=torch.tensor(18);self.assertEqual(compare_signatures(sig,signature(data)),'FIELD_SIGNATURE_DRIFT')

    def test_unsupported_types_cycles_and_objects_never_pass_by_equal_UNKNOWN(self):
        import numpy as np
        class Unsupported:pass
        cyclic=[];cyclic.append(cyclic)
        for value in (Unsupported(),cyclic,np.array([None],dtype=object)):
            result=signature(value);self.assertEqual(result['status'],'UNKNOWN_FIELDS_NOT_EQUIVALENCE')
            self.assertEqual(compare_signatures(result,result),'UNKNOWN_NOT_EQUIVALENT')
            self.assertGreater(result['unknown_fields_total'],0)

    def test_execution_pointer_changes_only_source_path_and_key_keeps_original_index(self):
        origin={'source_path':'/original/a.lmdb','real_index':17,'record_id':'original:17','molecule_id':'m','record_payload_sha256':'a'*64,'idx':-9}
        result=U.execution_pointer(origin,'/explicit/alpha/a.lmdb')
        self.assertEqual(origin['source_path'],'/original/a.lmdb');self.assertEqual(result['idx'],-9)
        self.assertEqual(U.raw_key(result),b'000000017');self.assertEqual(U.raw_key(dict(origin,real_index=1234567890)),b'1234567890')
        self.assertEqual({k:v for k,v in result.items() if k!='source_path'},{k:v for k,v in origin.items() if k!='source_path'})
        for bad in (-1,True,'17',1<<63):
            with self.assertRaises(ValueError):U.raw_key(dict(origin,real_index=bad))

    def test_per_origin_same_key_is_separate_duplicate_stops_and_maps_are_finite(self):
        row=lambda path,index:{'actual_opened_LMDB':path,'origin_pointer':{'real_index':index}}
        groups=grouping([row('/a.lmdb',17),row('/b.lmdb',17)])
        self.assertEqual(len(groups),2);self.assertEqual(sum(map(len,groups.values())),2)
        with self.assertRaises(ValueError):grouping([row('/a.lmdb',17),row('/a.lmdb',17)])
        self.assertEqual(U.map_size(0,4096),16<<20)
        self.assertEqual(U.map_size(U.TOTAL_RAW_CAP,4096),U.MAP_ONE_CAP)
        self.assertEqual(U.map_size(1,4096)%4096,0)
        with self.assertRaises(ValueError):U.map_size(U.TOTAL_RAW_CAP+1,4096)

if __name__=='__main__':unittest.main()
