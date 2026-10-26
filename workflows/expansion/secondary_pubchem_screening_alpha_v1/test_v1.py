"""Five finite synthetic methods before any real raw/index/reference body IO."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from . import contracts as C,source,kernel,journal,materialize_shards
TEST_ROOT=None
class Budget:
    def check(self,extra=0,drain=False):pass
class Boundaries(unittest.TestCase):
    def test_fixed_uniform_ordinals_without_prefix_or_duplicates(self):
        values=source.sample(1000,100);self.assertEqual(values,source.sample(1000,100));self.assertEqual(len(set(values)),100)
        self.assertEqual(values,sorted(values));self.assertNotEqual(values,list(range(1,101)))
    def test_UTF8_CRLF_final_line_and_empty_smiles_preserve_exact_source(self):
        raw='7\tCé\r\n'.encode();fact=source.row_fact(raw,1,0,0);value=source.record(raw,fact,{})
        self.assertEqual(value['source_smiles'],'Cé');self.assertEqual(value['source_terminator_hex'],'0d0a')
        self.assertEqual(value['source_row_sha256'],hashlib.sha256(raw).hexdigest())
        raw=b'8\t';self.assertEqual(source.record(raw,source.row_fact(raw,2,0,7),{})['source_smiles'],'')
        with self.assertRaises(UnicodeDecodeError):source.row_fact(b'9\tC\xff\n',3,0,9)
    def test_original_funnel_unknown_is_not_an_extra_chemical_exclusion(self):
        original={'ordinal':2,'cid_source_ascii':'2','source_smiles':'synthetic'}
        flags={name:name=='X03' for name in ('X01','X02','X03','X04','X05')}
        self.assertEqual(kernel.funnel({'cid':2,'ordinal':2,'reasons':['X03']},flags,True,{},original)[0],'chemReject')
        self.assertEqual(kernel.funnel({'cid':2,'ordinal':2,'reasons':['PARSE_FAILED']},{'PARSE_FAILED':True},False,{},original)[0],'technicalUnresolved')
        self.assertEqual(kernel.funnel({'cid':2,'ordinal':2,'reasons':['X03']},{'X03':False},True,{},original)[0],'technicalUnresolved')
    def test_durable_complete_result_precedes_typed_parquet_nullable_flags(self):
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            root=Path(folder);original={'ordinal':1,'cid_source_ascii':'1','source_smiles':'synthetic','source_smiles_sha256':'a'*64,'source_part':{}}
            writer=journal.Writer(root,'synthetic',Budget());writer.dispatch(original)
            value={'input':original,'category':'technicalUnresolved','technical_codes':['PARSE_FAILED'],'audit_parse_succeeded':False,
                'audit_flags':{'PARSE_FAILED':True},'legacy_dispatcher_result':{'cid':1,'ordinal':1,'reasons':['PARSE_FAILED']},'errors':{},
                'worker_pid':1,'audit_wall_seconds':.1,'audit_CPU_seconds':.1,'dispatcher_wall_seconds_includes_legacy_X_parse':.2,
                'dispatcher_CPU_seconds_includes_legacy_X_parse':.2}
            writer.complete(original,value)
            events=[json.loads(line) for line in writer.path.read_text().splitlines()]
            self.assertEqual([row['event'] for row in events],['DISPATCH_DURABLE_BEFORE_SUBMIT','COMPLETE_RESULT_DURABLE_BEFORE_PARQUET'])
            self.assertEqual(events[1]['value']['legacy_dispatcher_result'],value['legacy_dispatcher_result'])
            writer.close();saved=pq.read_table(writer.parquet).to_pylist()[0]
            self.assertIsNone(saved['audit_X01']);self.assertEqual(json.loads(saved['full_dispatcher_result_json']),value['legacy_dispatcher_result'])
    def test_full_partition_has_no_overlap_hole_or_missing_tail(self):
        value={'schema':'ALPHA_PUBCHEM_EXCLUSIVE_ORDINAL_MANIFEST_V1','source_raw_sha256':C.RAW_SHA,'population_N':C.N,
            'part_count':C.PARTS,'pool_release_authorized':False,'shards':[
                {'shard_index':0,'first_part':0,'last_part':249,'first_ordinal':1,'last_ordinal':62500000},
                {'shard_index':1,'first_part':250,'last_part':499,'first_ordinal':62500001,'last_ordinal':C.N}]}
        self.assertIs(materialize_shards.validate(value),value)
        bad=copy.deepcopy(value);bad['shards'][1]['first_ordinal']-=1
        with self.assertRaises(ValueError):materialize_shards.validate(bad)
