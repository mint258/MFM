"""One tiny reversible-private-BLOB fixture; no production arrays/LMDB/benchmark."""
import concurrent.futures as cf
import copy,json,pathlib,pickle,sqlite3,tempfile,unittest,zlib
from contextlib import ExitStack
from unittest.mock import patch
import numpy as np
from . import source_bridge as S,prepare_runtime as P
from ..pilot_v31_compact_v1.codec import encode,encode_key


class SpoolCompressionCheck(unittest.TestCase):
    def test_lossless_mixed_spool_stream_and_final_codec_bytes(self):
        floats=np.asarray([0x7ff8000000001234,0x8000000000000000,0x3ff0000000000000,0x7ff0000000000000],dtype='<u8').view('<f8').reshape(2,2)
        integers=np.asarray([[-7,2],[0,2**40]],dtype='<i8');mask=np.asarray([[True,False],[False,True]],dtype=bool)
        payload={'floats':floats,'same_floats':floats,'integers':integers,'mask':mask,'nested':[floats,mask]}
        raw=pickle.dumps(payload,protocol=5);packed=S.spool_dumps(payload,'zlib1')
        self.assertEqual(S.spool_dumps(payload),raw);self.assertEqual(S.spool_dumps(payload,None),raw)
        self.assertTrue(packed.startswith(S.SPOOL_ZLIB1_MAGIC));self.assertEqual(zlib.decompress(packed[len(S.SPOOL_ZLIB1_MAGIC):]),raw)
        for blob in (raw,packed):
            decoded=S.spool_loads(blob);self.assertEqual(list(decoded),list(payload))
            for key in ('floats','integers','mask'):
                self.assertEqual(decoded[key].dtype,payload[key].dtype);self.assertEqual(decoded[key].shape,payload[key].shape)
                self.assertEqual(decoded[key].tobytes(),payload[key].tobytes())
            self.assertIs(decoded['floats'],decoded['same_floats']);self.assertIs(decoded['floats'],decoded['nested'][0]);self.assertIs(decoded['mask'],decoded['nested'][1])
        for value in ('gzip','zlib2',False,1):
            with self.assertRaisesRegex(ValueError,'UNKNOWN_SOURCE_SPOOL_COMPRESSION'):S.spool_dumps(payload,value)
        for broken in (S.SPOOL_ZLIB1_MAGIC+b'not-zlib',packed[:-3]):
            with patch.object(S.pickle,'loads',side_effect=AssertionError('corrupt tagged bytes must not fall back')):
                with self.assertRaises(zlib.error):S.spool_loads(broken)
        def record(rid):
            return {'identity':{'geometry_source':'pm7','native_record_id':rid},
                    'arrays':{21:np.asarray([[0.,-0.,1.],[np.nan,2.,3.]],dtype='<f4'),24:np.asarray([[np.nan],[-0.]],dtype='<f4'),
                              31:np.asarray([0,1],dtype='<u4'),32:np.asarray([[1,2,0],[2,1,3]],dtype='<u2'),
                              33:np.asarray([0,1],dtype='u1'),34:np.asarray([np.nan,-0.],dtype='<f4')},
                    'r73_channels':[('s','p',None),('p','s','sigma')]}
        expected={'mid':'mid_b','m_arrays':{6:np.asarray([2,0],dtype='<u2')},'p_records':[record('native-2'),record('native-1')],'u_records':[]}
        expected_records=[encode(value['arrays']) for value in expected['p_records']]
        expected_keys={(mid,rid):encode_key('P',mi,ci) for mi,mid in enumerate(('mid_b','mid_a')) for ci,rid in enumerate(('native-2','native-1'))}
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);shared=root/'shared';private=root/'private'
            identities=root/'identities.sqlite';cache=root/'cache.sqlite'
            with sqlite3.connect(identities) as db:
                db.executescript('CREATE TABLE members(mid TEXT,role TEXT,common INTEGER); CREATE TABLE orders(mid TEXT,row TEXT); CREATE TABLE held(mid TEXT,src TEXT,physical TEXT); CREATE TABLE geometries(mid TEXT,src TEXT,physical TEXT,gid TEXT,ordinary INTEGER,pointer TEXT);')
                db.execute('INSERT INTO members VALUES(?,?,?)',('mid_b','TRAIN',1));db.execute('INSERT INTO orders VALUES(?,?)',('mid_b',json.dumps({'pm7_orders_json':'{}','sprime_orders_json':'{}'})))
            db.close()
            with sqlite3.connect(cache) as db:db.execute('CREATE TABLE pp(mid TEXT,conf INTEGER,task TEXT,path TEXT,row INTEGER,gid TEXT)')
            db.close()
            plan={'source_working_root':str(shared),'source_spool_root':str(private),'source_spool_compression':'zlib1','source_index':'mock-index','workers':1}
            state={'plan':plan,'index':{'database':{'path':str(identities)}},'cache':{'database':{'path':str(cache)}},'schema':{},'fields':{},'source_sample_keys':set(),
                   'normalization':{'inputs':{'field_map_reference':{}},'statistics':{'r73_derived_reference':{},'mask_overrides_reference':{}}},'source_groups':{}}
            piece_blobs=[];assembled=[]
            def inject(*args,**kwargs):
                with sqlite3.connect(S.STATE['spool_path']) as db:
                    for compression,gid in ((None,'old-piece'),('zlib1','new-piece')):
                        plan['source_spool_compression']=compression
                        meta={'molecule_id':'mid_b','geometry_source':'pm7','native_record_id':gid}
                        S.add_piece(db,'mid_b',gid,'labels',meta,{'values/toy':np.asarray([np.nan,-0.],dtype='<f4'),'valid/toy':np.asarray([0,1],dtype='u1')},False)
                    piece_blobs.extend(row[0] for row in db.execute('SELECT row FROM pieces ORDER BY rowid'))
                db.close();plan['source_spool_compression']='zlib1';return iter(())
            def assemble(mid,entries,schema):assembled.extend(entries);return copy.deepcopy(expected)
            with ExitStack() as stack:
                stack.enter_context(patch.dict(S.STATE,state,clear=True))
                stack.enter_context(patch.object(S,'locators_for_mids',side_effect=inject))
                stack.enter_context(patch.object(S,'iter_source_rows',return_value=iter(())))
                stack.enter_context(patch.object(S,'assemble_entries',side_effect=assemble))
                reference=S.work((0,['mid_b'],'TRAIN'))
            self.assertTrue(piece_blobs[0].startswith(bytes((128,5))));self.assertTrue(piece_blobs[1].startswith(S.SPOOL_ZLIB1_MAGIC))
            self.assertEqual([entry['gid']for entry in assembled],['old-piece','new-piece'])
            for entry in assembled:
                self.assertEqual(entry['arrays']['values/toy'].tobytes(),np.asarray([np.nan,-0.],dtype='<f4').tobytes())
            database=pathlib.Path(reference['path']);marker=shared/'TRAIN/block_0000000.json'
            with sqlite3.connect(database) as db:
                encoded=db.execute('SELECT row FROM molecules WHERE mid=?',('mid_b',)).fetchone()[0];self.assertTrue(encoded.startswith(S.SPOOL_ZLIB1_MAGIC))
                first=S.spool_loads(encoded);second=copy.deepcopy(first);second['mid']='mid_a'
                db.execute('INSERT INTO molecules VALUES(?,?)',('mid_a',S.spool_dumps(second)))
                self.assertEqual(db.execute('SELECT count(*) FROM pieces').fetchone()[0],0)
            db.close();reference['mids']=['mid_b','mid_a'];S.I.save(marker,reference);marker_bytes=marker.read_bytes()
            class Pool:
                def __init__(self,**kwargs):pass
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def submit(self,function,task):
                    future=cf.Future();future.set_result(function(task));return future
            # Existing closed ref wins; no source/index is reopened. Reading
            # needs no compression hint because every new BLOB is self-tagged.
            read_plan=dict(plan,source_spool_compression=None)
            groups=[{'TRAIN':['mid_b','mid_a'],'FULL':[]}]
            with patch.dict(S.STATE,{'plan':read_plan},clear=True),patch.object(S,'identity_db',side_effect=AssertionError('closed spool source replayed')),patch.object(S,'source_molecule_groups',return_value=groups),patch.object(S.cf,'ProcessPoolExecutor',Pool):
                early=S.stream_split(read_plan,None,None,None,'TRAIN');self.assertEqual(next(early)['mid'],'mid_b');early.close();self.assertTrue(database.is_file())
                stream=S.stream_split(read_plan,None,None,None,'TRAIN');items=[next(stream),next(stream)]
                self.assertEqual([item['mid']for item in items],['mid_b','mid_a'])
                for mi,item in enumerate(items):
                    self.assertEqual([r['identity']['native_record_id']for r in item['p_records']],['native-2','native-1'])
                    for ci,r in enumerate(item['p_records']):
                        self.assertEqual(encode(r['arrays']),expected_records[ci]);self.assertEqual(encode_key('P',mi,ci),expected_keys[(item['mid'],r['identity']['native_record_id'])])
                self.assertTrue(database.is_file());items[-1]['_source_block_end']['ack']['committed']=True
                with self.assertRaises(StopIteration):next(stream)
            self.assertFalse(database.exists());self.assertEqual(marker.read_bytes(),marker_bytes)
            runtime=root/'runtime';runtime.mkdir();path=root/'plan.json'
            old={'runtime_metadata_root':str(runtime),'source_spool_compression':None};changed=dict(old,source_spool_compression='zlib1')
            path.write_text(json.dumps(changed));(runtime/'bound_plan.json').write_text(json.dumps({'plan_path':str(path),'plan':old}))
            self.assertEqual(P.prepare(path),changed)


if __name__=='__main__':unittest.main()
