"""One synthetic equivalence fixture for selected rows and Pprime UID lookup."""
import copy,math,pathlib,struct,tempfile,unittest
from unittest.mock import patch
import pyarrow as pa
import pyarrow.parquet as pq
from . import source_bridge as S


class SourceLinearLookupCheck(unittest.TestCase):
    def test_selected_rows_and_uff_candidate_lookup_preserve_original_semantics(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=pathlib.Path(temporary)/'toy.parquet'
            values=[{'ordinal':i,'value':float('nan') if i%17==0 else -0.0 if i==31 else i/10.,'text':'opaque-'+str(i)} for i in range(53)]
            pq.write_table(pa.Table.from_pylist(values),path,row_group_size=11);before=path.read_bytes()
            real_parquet=pq.ParquetFile;observations=[]
            class TrackedFile:
                def __init__(self,filename,**kwargs):
                    self.file=real_parquet(filename,**kwargs);self.event={'open':kwargs,'batches':[],'closed':False};observations.append(self.event)
                def iter_batches(self,**kwargs):
                    self.event['options']=kwargs
                    for batch in self.file.iter_batches(**kwargs):self.event['batches'].append(batch.num_rows);yield batch
                def close(self):self.file.close();self.event['closed']=True
            def original_read_selected(filename,positions,columns=None):
                table=pq.ParquetFile(filename,pre_buffer=False);positions=set(positions);lo=0
                try:
                    for batch in table.iter_batches(batch_size=16,columns=columns,use_threads=False):
                        hi=lo+batch.num_rows
                        for pos in sorted(p for p in positions if lo<=p<hi):yield pos,batch.slice(pos-lo,1).to_pylist()[0]
                        lo=hi
                        if positions and lo>max(positions):break
                finally:table.close()
            def exact(records):
                return [(position,[(key,struct.pack('<d',value) if isinstance(value,float) else value)for key,value in row.items()])for position,row in records]
            cases=[([52,0,32,17,31,31,-1,-100,999,5],None),([33,1,33,16,-1],['ordinal','value']),
                   ([-7,-2],None),([],None),([90,100],['value']),({17:'metadata',2:'metadata'},['value'])]
            with patch.object(pq,'ParquetFile',TrackedFile):
                for selected,columns in cases:
                    unchanged=copy.deepcopy(selected)
                    expected=list(original_read_selected(path,selected,columns));old_event=copy.deepcopy(observations[-1])
                    actual=list(S.read_selected(path,selected,columns));new_event=observations[-1]
                    self.assertEqual(exact(actual),exact(expected));self.assertEqual(new_event,old_event)
                    self.assertEqual(selected,unchanged);self.assertTrue(new_event['closed'])
                    self.assertEqual(new_event['open'],{'pre_buffer':False})
                    self.assertEqual(new_event['options'],{'batch_size':16,'columns':columns,'use_threads':False})
                selected=list(S.read_selected(path,[52,0,17,31,32,5,17,-1,999]))
                self.assertEqual([position for position,_ in selected],[0,5,17,31,32,52])
                self.assertTrue(math.isnan(selected[0][1]['value']));self.assertTrue(math.isnan(selected[2][1]['value']))
                self.assertEqual(struct.pack('<d',selected[3][1]['value']),struct.pack('<d',-0.0))
                stream=S.read_selected(path,[0,52]);next(stream);stream.close();self.assertTrue(observations[-1]['closed'])
            self.assertEqual(path.read_bytes(),before)
            bases={('m','pm7','native'):{'geometry_id':'duplicate'},
                   ('other','uff_sprime','2'):{'geometry_id':'duplicate'},
                   ('m','uff_sprime','d5-diagnostic:alias'):{'geometry_id':'alias','ordinary_sprime':False},
                   ('m','uff_sprime','7'):{'geometry_id':'duplicate'},
                   ('m','pm7','native-alias'):{'geometry_id':'alias'},
                   ('m','uff_sprime','Pprime-source:duplicate'):{'geometry_id':'duplicate','ordinary_sprime':False},
                   ('m','uff_sprime','1'):{'geometry_id':'unique'}}
            unchanged=copy.deepcopy(bases);lookup=S.uff_candidate_index(bases)
            for mid,gid in [('m','duplicate'),('m','alias'),('other','duplicate'),('m','unique'),('m','missing')]:
                original=[key for key,base in bases.items() if key[0]==mid and key[1]=='uff_sprime' and base['geometry_id']==gid]
                self.assertEqual(lookup.get((mid,gid),[]),original)
                if len(original)==1:self.assertEqual(S.pprime_candidate_key(lookup,mid,7,gid),original[0])
                else:
                    with self.assertRaises(ValueError) as error:S.pprime_candidate_key(lookup,mid,7,gid)
                    self.assertEqual(str(error.exception),'ACTUAL_PPRIME_PHYSICAL_GEOMETRY_MUST_BE_UNAMBIGUOUS:'+repr((mid,7,gid)))
            self.assertEqual(lookup[('m','duplicate')],[('m','uff_sprime','7'),('m','uff_sprime','Pprime-source:duplicate')])
            self.assertEqual(S.pprime_candidate_key(lookup,'m',7,'alias'),('m','uff_sprime','d5-diagnostic:alias'))
            self.assertEqual(bases,unchanged)


if __name__=='__main__':unittest.main()
