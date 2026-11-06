"""One new write-boundary guard-order/parity regression; synthetic data only."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from . import histogram_io as H,statistics as T,temporary as Temp
from ..window2_normalization_v1 import io as I,run as Original
from ..normalization_compact_runtime_v3 import codec as K

class HistogramIO(unittest.TestCase):
    def test_parity_readonly_batches_and_all_physical_write_denials(self):
        import pyarrow as pa,pyarrow.parquet as pq
        ledger=[];handles=[];real_open=H.open_raw;real_replace=os.replace
        class Denied(RuntimeError):pass
        class Guard:
            deny=staticmethod(lambda path,b,n:False)
            def wait(self,path,bytes_needed=0,inodes_needed=0):
                path=str(path);ledger.append(('guard',path,bytes_needed,inodes_needed))
                if self.deny(Path(path),bytes_needed,inodes_needed):raise Denied('TOY_WRITE_DENIED')
        guard=Guard()
        class Runtime:
            def __init__(self):self.guard=guard
            def wait(self,path=None):ledger.append(('runtime_wait',str(path)));guard.wait(path)
        runtime=Runtime()
        class Raw:
            def __init__(self,path):
                self.path=str(path);self.raw=real_open(path);handles.append(self);ledger.append(('create',self.path))
            @property
            def closed(self):return self.raw.closed
            def tell(self):return self.raw.tell()
            def write(self,data):
                selftest.assertLessEqual(len(data),H.CHUNK)
                selftest.assertEqual(ledger[-1],('guard',self.path,len(data),0))
                ledger.append(('write',self.path,len(data)));return self.raw.write(data)
            def close(self):
                if not self.raw.closed:ledger.append(('close',self.path));self.raw.close()
        selftest=self
        def open_raw(path):
            self.assertEqual(ledger[-1],('guard',str(path),0,1));return Raw(path)
        def replace(source,target):
            self.assertEqual(ledger[-1],('guard',str(target),0,1));ledger.append(('rename',str(target)))
            real_replace(source,target)
        with tempfile.TemporaryDirectory() as folder,patch.object(Temp,'activate',return_value=runtime),patch.object(H,'open_raw',side_effect=open_raw),patch.object(H.os,'replace',side_effect=replace):
            root=Path(folder);fields=[{'field_id':0,'field_key':'P.toy','source_path':'toy','level':'molecule','element_reference_eligible':False,'unit':None}]
            # Set up source/field metadata without replacing the original IO.
            with patch.object(H.os,'replace',real_replace):field_ref=I.save(root/'fields.json',fields)
            rows=[]
            for index in range(65):
                entry={'field_id':0,'values_float64':[(index-32)/13.],'atom_indices':None,'source_value_mask':[True],'value_mask':[index%11!=0],'source_reasons':[],'new_reasons':[],'review_reasons':[]}
                rows.append(dict(record_id=str(index),molecule_id=str(index),fit_eligible=index%9!=0,atomic_numbers=[6],calc_type='toy',**K.pack_entries([entry])))
            part=root/'typed.parquet';pq.write_table(pa.Table.from_pylist(rows),part)
            group={'group_index':4,'source_job_id':'toy-σ','typed_parts':[I.ref(part)]}
            cfg={'statistics_purpose':'normalization_quantiles','field_map_reference':field_ref,'element_basis':[6],'_temporary_runtime':{}}
            stage=T.Original.initial_stage(cfg,fields);stage['element_basis']=[6]
            old=root/'old';old.mkdir();new=root/'new';new.mkdir()
            # Baseline retains the original unproxied JSON publisher.
            with patch.object(H.os,'replace',real_replace):a=I.load_data(T.group_pass((cfg,stage,str(old),group)))
            self.assertEqual(sum(e[0]=='runtime_wait' and e[1]==str(old/'group_0004') for e in ledger),3)
            original_io=T.Original._group_pass.__globals__['I'];original_sink=T.Original._group_pass.__globals__['ParquetSink']
            ledger.clear();b=I.load_data(T.group_pass((dict(cfg,histogram_guard_writes_only=True),stage,str(new),group)))
            self.assertIs(T.Original._group_pass.__globals__['I'],original_io);self.assertIs(T.Original._group_pass.__globals__['ParquetSink'],original_sink)
            self.assertEqual((new/'group_0004/report.json').read_bytes(),(json.dumps(b,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode('utf-8'))
            self.assertFalse(any(e[0]=='runtime_wait' and e[1]==str(new/'group_0004') for e in ledger))
            for key in ('task_rows','field_counts','role_task_counts','series_mass','energy_TSQR','moments','joint'):self.assertEqual(a[key],b[key])
            for name in stage['queries']:self.assertEqual(Original.histogram_rows([a],name),Original.histogram_rows([b],name))
            self.assertTrue(any(e[0]=='write' and e[1].endswith('.parquet') for e in ledger));self.assertTrue(any(e[0]=='rename' for e in ledger))
            self.assertTrue(all(h.closed for h in handles))
            self.assertFalse(H.enabled({},'normalization_quantiles'))
            for purpose in ('element_reference','normalization_moments'):self.assertFalse(H.enabled({'histogram_guard_writes_only':True},purpose))
            # Creation denial must not truncate/create a file or acquire an FD.
            create=root/'deny_create';guard.deny=lambda p,b,n:p==create
            count=len(handles)
            with self.assertRaises(Denied):H.File(create,guard)
            self.assertFalse(create.exists());self.assertEqual(len(handles),count)
            # A second physical chunk is denied before any of its bytes appear.
            big=root/'deny_chunk';guard.deny=lambda p,b,n:p==big and b>0 and p.stat().st_size>=H.CHUNK
            stream=H.File(big,guard)
            try:
                with self.assertRaises(Denied):stream.write(b'x'*(2*H.CHUNK+1))
            finally:stream.close()
            self.assertEqual(big.stat().st_size,H.CHUNK);self.assertTrue(stream.closed)
            # Footer/destructor writes still traverse guarded File.write.
            guard.deny=lambda p,b,n:False;footer=root/'footer.parquet';instances=[]
            class Writer:
                def __init__(self,target,*args,**kwargs):self.target=target;instances.append(self);target.write(b'H')
                def write_table(self,table):self.target.write(b'D')
                def close(self):
                    guard.deny=lambda p,b,n:p==footer and b>0
                    self.target.write(b'FOOTER')
            sink=H.Sink(pa.schema([('n',pa.int64())]),1,guard);sink.add([{'n':1}])
            with patch.object(pq,'ParquetWriter',Writer):
                with self.assertRaises(Denied):sink.close(footer)
            self.assertEqual(footer.read_bytes(),b'HD');self.assertTrue(instances[0].target.closed)
            with self.assertRaises(ValueError):instances[0].close()
            self.assertEqual(footer.read_bytes(),b'HD')
            # JSON is also bounded; denial leaves only the already written partial.
            jsonpath=root/'deny_json.json';partial=jsonpath.with_name(jsonpath.name+'.writing')
            guard.deny=lambda p,b,n:p==partial and b>0 and p.stat().st_size>=H.CHUNK
            with self.assertRaises(Denied):H.IO(guard).save(jsonpath,{'text':'a'*(2*H.CHUNK)})
            self.assertFalse(jsonpath.exists());self.assertEqual(partial.stat().st_size,H.CHUNK)
            self.assertTrue(all(h.closed for h in handles))
            # Rename denial keeps the prior visible file, with no open buffer/FD.
            visible=root/'visible.json';visible.write_bytes(b'OLD');guard.deny=lambda p,b,n:p==visible
            renamed=sum(e[0]=='rename' for e in ledger)
            with self.assertRaises(Denied):H.IO(guard).save(visible,{'new':1})
            self.assertEqual(visible.read_bytes(),b'OLD');self.assertEqual(sum(e[0]=='rename' for e in ledger),renamed)
            self.assertTrue(all(h.closed for h in handles))
            with self.assertRaisesRegex(AttributeError,'UNSUPPORTED_HISTOGRAM_IO_API'):getattr(H.IO(guard),'open')