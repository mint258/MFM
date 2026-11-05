"""One tiny owned-storage recovery fixture; no dataset/scientific QA."""
import copy,pathlib,pickle,shutil,sqlite3,tempfile,unittest
from unittest.mock import patch
import lmdb,numpy as np,pyarrow.parquet as pq
from . import run as R,source_bridge as S
from ..pilot_v31_compact_v1.codec import encode_key


class BlockCheckpointCheck(unittest.TestCase):
    def test_block_tail_id_fragments_raw_closed_and_ack_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);output=root/'output';scratch=root/'scratch'
            plan={'output_root':str(output),'working_root':str(scratch),'sample_seed':17,'source_sample_keys':[],
                  'data_version':'toy-storage-only','expected_molecules':{'TRAIN':2,'FULL':0},
                  'expected_conformers':{'TRAIN_P':0,'TRAIN_U':0,'FULL_P':0,'FULL_U':0},'gpu_nodes':[]}
            schema={'array_definitions':{}}
            def item(mid,end=None):
                value={'mid':mid,'role':'TRAIN','common_population':True,
                       'm_arrays':{6:np.asarray([0,0],dtype='<u4'),13:np.asarray([],dtype='u1'),14:np.asarray([],dtype='u1')},
                       'p_records':[],'u_records':[]}
                if end is not None:value['_source_block_end']=end
                return value
            ack0={'committed':False};ack1={'committed':False};calls=[]
            def first_source():
                calls.append(('first',None));yield item('m0',{'number':0,'ack':ack0})
                self.assertTrue(ack0['committed']);yield item('m1')
                raise RuntimeError('toy interruption after raw MID before block checkpoint')
            def resumed_source(start_after=None):
                calls.append(('resume',start_after));self.assertEqual(start_after,0)
                yield item('m1',{'number':1,'ack':ack1})
            def forbidden_source(**kwargs):raise AssertionError('raw_closed source replayed')
            closed_compactions=[]
            def compact(source,destination):
                destination.mkdir();shutil.copyfile(source/'data.mdb',destination/'data.mdb');closed_compactions.append(destination)
            with patch.object(R,'sample_check',return_value={'toy_storage_only':True}) as checker:
                with self.assertRaisesRegex(RuntimeError,'toy interruption'):
                    R.export(copy.deepcopy(plan),{'TRAIN':first_source,'FULL':lambda:iter(())},schema)
                with (output/'producer_checkpoint.pkl').open('rb') as stream:state=pickle.load(stream)
                self.assertEqual(state['indices']['TRAIN'],1);self.assertEqual(state['active']['source_cursor'],0)
                self.assertEqual(len(state['active']['id_fragments']),1)
                work=pathlib.Path(state['active']['work'])
                env=lmdb.open(str(work),readonly=True,lock=False,create=False)
                with env.begin() as transaction:
                    prefix=transaction.get(encode_key('M',0));self.assertIsNotNone(transaction.get(encode_key('M',1)))
                env.close()
                def interrupted_compact(source,destination):
                    destination.mkdir();raise RuntimeError('toy compaction interruption')
                with patch.object(R,'compact_once',side_effect=interrupted_compact):
                    with self.assertRaisesRegex(RuntimeError,'toy compaction interruption'):
                        R.export(copy.deepcopy(plan),{'TRAIN':resumed_source,'FULL':lambda:iter(())},schema)
                self.assertTrue(ack1['committed'])
                with (output/'producer_checkpoint.pkl').open('rb') as stream:closed=pickle.load(stream)
                self.assertEqual(closed['active']['phase'],'raw_closed');self.assertEqual(closed['indices']['TRAIN'],2)
                with patch.object(R,'compact_once',side_effect=compact):
                    result=R.export(copy.deepcopy(plan),{'TRAIN':forbidden_source,'FULL':lambda:iter(())},schema)
                checker.assert_called_once();self.assertEqual(len(closed_compactions),2)
                self.assertEqual(calls,[('first',None),('resume',0)])
                final=pathlib.Path(result['split_roots']['TRAIN']);rows=pq.read_table(final/'id_map.parquet').to_pylist()
                self.assertEqual([row['molecule_id'] for row in rows],['m0','m1'])
                self.assertEqual([row['molecule_index'] for row in rows],[0,1])
                env=lmdb.open(str(final),readonly=True,lock=False,create=False)
                with env.begin() as transaction:
                    self.assertEqual(transaction.get(encode_key('M',0)),prefix)
                    self.assertIsNotNone(transaction.get(encode_key('M',1)));self.assertEqual(transaction.stat()['entries'],2)
                env.close()
                self.assertEqual(result['molecules']['TRAIN'],2)
                self.assertEqual(result['molecules'].get('FULL',0),0)

            # An unacknowledged closed F32 spool survives generator closure;
            # acknowledged consumption closes the reader before unlink. Resume
            # skips already closed sourcejob blocks before submitting any work.
            path=root/'source_block.sqlite';database=sqlite3.connect(path)
            database.execute('CREATE TABLE molecules(mid TEXT PRIMARY KEY,row BLOB)')
            database.execute('INSERT INTO molecules VALUES(?,?)',('todo',pickle.dumps({'mid':'todo'},protocol=5)));database.commit();database.close()
            submitted=[];outer=self
            class Future:
                def result(self):return {'path':str(path),'mids':['todo']}
            class Pool:
                def __init__(self,**kwargs):outer.assertEqual(kwargs['max_workers'],3)
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def submit(self,function,task):submitted.append(task);return Future()
            groups=[{'TRAIN':['already-closed']},{'TRAIN':['todo']}]
            with patch.object(S,'source_molecule_groups',return_value=groups),patch.object(S.cf,'ProcessPoolExecutor',Pool):
                iterator=S.stream_split({'workers':3,'streaming_buffer_blocks':1},None,None,None,'TRAIN',start_after=0)
                pending=next(iterator);self.assertEqual(pending['_source_block_end']['number'],1)
                iterator.close();self.assertTrue(path.is_file())
                iterator=S.stream_split({'workers':3,'streaming_buffer_blocks':1},None,None,None,'TRAIN',start_after=0)
                pending=next(iterator);pending['_source_block_end']['ack']['committed']=True
                with self.assertRaises(StopIteration):next(iterator)
                self.assertFalse(path.exists());self.assertEqual([task[0] for task in submitted],[1,1])


if __name__=='__main__':unittest.main()
