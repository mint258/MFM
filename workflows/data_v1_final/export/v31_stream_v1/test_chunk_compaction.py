"""One toy byte/storage fixture; no datasets, SSH, real compact or numeric QA."""
import copy,io,json,pathlib,shlex,shutil,subprocess,tempfile,unittest
from unittest.mock import patch
import pyarrow.parquet as pq
import numpy as np
from . import chunk_compaction as C,run as R


class ChunkCompactionCheck(unittest.TestCase):
    def test_one_stream_remote_guard_concat_resume_and_external_idmap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);raw=root/'raw';raw.mkdir();(raw/'data.mdb').write_bytes(b'raw-file-upper-bound'*4)
            data=bytes(range(55));network={};events=[];compact_calls=[];commands=[]
            class Guard:
                def wait(self,path,bytes_needed=0,inodes_needed=0):events.append((str(path),bytes_needed,inodes_needed))
            guard=Guard()
            local={'directory':str(root/'local'),'capacity_bytes':24}
            remote={'directory':'/tmp/toy_chunks','capacity_bytes':len((raw/'data.mdb').read_bytes())-24,'node':'compute-0-21',
                    'repository':'/share/home/zixiao/toy-repo','python':'/python','guard_plan':'/share/toy-node21-guard.json'}
            plan={'chunk_compaction':{'enabled':True,'targets':[local,remote],'chunk_bytes':16}}
            def arguments(argv):
                commands.append(argv);self.assertEqual(argv[:4],['ssh','-T','-o','BatchMode=yes']);self.assertNotIn('-n',argv)
                self.assertEqual(argv[4],'compute-0-21');words=shlex.split(argv[-1]);i=words.index(C.MODULE)
                return words[i+1],dict(zip(words[i+2::2],words[i+3::2]))
            class Capture(io.BytesIO):
                def __init__(self,callback):super().__init__();self.callback=callback
                def close(self):
                    if not self.closed:self.callback(self.getvalue())
                    super().close()
            outer=self
            class Process:
                pid=43210;returncode=0
                def __init__(self,argv,**kwargs):
                    self.args=argv
                    if argv[0]=='toy-mdb-copy':
                        outer.assertEqual(argv,['toy-mdb-copy','-c',str(raw)]);compact_calls.append(argv);self.stdout=io.BytesIO(data)
                    else:
                        action,options=arguments(argv);path=options['--path']
                        if action=='receive':
                            outer.assertEqual(options['--plan'],remote['guard_plan']);self.stdout=io.BytesIO()
                            def closed(payload):
                                outer.assertLessEqual(len(payload),int(options['--limit']));network[path]=payload
                                self.stdout=io.BytesIO(json.dumps({'path':path,'bytes':len(payload)}).encode())
                            self.stdin=Capture(closed)
                        elif action=='read':self.stdout=io.BytesIO(network[path])
                        else:raise AssertionError(action)
                def wait(self):return 0
            def preflight(argv,text):
                action,options=arguments(argv);self.assertEqual(action,'admit');self.assertTrue(text)
                self.assertEqual(int(options['--limit']),remote['capacity_bytes']);return json.dumps({'admitted':True,'path':options['--path'],'bytes':int(options['--limit'])})
            def cleanup(argv,check):
                action,options=arguments(argv);self.assertEqual(action,'cleanup');self.assertTrue(check)
                network.pop(options['--path'],None)
            catalog=root/'catalog.json';destination=root/'shared'/'data.mdb'
            with patch.object(C.shutil,'which',return_value='toy-mdb-copy'),patch.object(C.subprocess,'Popen',Process),patch.object(C.subprocess,'check_output',side_effect=preflight),patch.object(C.subprocess,'run',side_effect=cleanup),patch.object(C,'process_witness',return_value='toy-start'):
                result=C.compact(plan,raw,catalog,guard);self.assertEqual(result['phase'],'CHUNKS_CLOSED')
                self.assertEqual(result['total_bytes'],len(data));self.assertEqual(len(compact_calls),1)
                self.assertEqual([ref['ordinal'] for ref in result['chunks']],list(range(len(result['chunks']))))
                self.assertEqual(sum(ref['bytes'] for ref in result['chunks']),len(data))
                (raw/'data.mdb').unlink() # only this toy raw, after full chunks C0
                self.assertEqual(C.compact(plan,raw,catalog,guard)['phase'],'CHUNKS_CLOSED');self.assertEqual(len(compact_calls),1)
                original=C.chunk_reader
                def interrupted(ref):
                    if ref['ordinal']==1:raise RuntimeError('toy interruption after first concat checkpoint')
                    return original(ref)
                with patch.object(C,'chunk_reader',side_effect=interrupted):
                    with self.assertRaisesRegex(RuntimeError,'toy interruption'):C.concatenate(catalog,destination,guard)
                state=C.read(catalog);self.assertEqual(state['concat']['next_chunk'],1)
                with pathlib.Path(state['concat']['partial']).open('ab') as partial:partial.write(b'uncheckpointed-tail')
                finished=C.concatenate(catalog,destination,guard);self.assertEqual(finished['phase'],'COMPLETE')
                self.assertEqual(destination.read_bytes(),data);self.assertEqual(len(compact_calls),1)
                old=root/'local'/'old-user-file';old.write_bytes(b'preserve')
                C.cleanup(catalog,guard);self.assertEqual(old.read_bytes(),b'preserve');self.assertEqual(network,{})
                self.assertTrue(all(not pathlib.Path(ref['path']).exists() for ref in finished['chunks'] if not ref['target'].get('node')))
                self.assertEqual(C.concatenate(catalog,destination,guard)['phase'],'COMPLETE')
                self.assertEqual(C.compact(plan,raw,catalog,guard)['phase'],'COMPLETE');self.assertEqual(len(compact_calls),1)
                incomplete=copy.deepcopy(finished);incomplete['phase']='INCOMPLETE';C.save(root/'incomplete.json',incomplete)
                with self.assertRaisesRegex(ValueError,'ROOT_CONFIRMED_DEAD_ATTEMPT'):C.compact(plan,raw,root/'incomplete.json',guard)
                self.assertTrue(events);self.assertTrue(commands)
                with self.assertRaisesRegex(ValueError,'ONLY_OWNED_CHUNK_PATH'):C.remove_chunk(old,8,finished['attempt'])

            # Storage-only external ID path: ordinary relative readers follow
            # the split symlink, while only one actual shared ID file exists.
            output=root/'export';scratch=root/'write';plan={'output_root':str(output),'working_root':str(scratch),
                'sample_seed':3,'source_sample_keys':[],'data_version':'toy','gpu_nodes':[],'id_map_storage':'external_symlink',
                'expected_molecules':{'TRAIN':1,'FULL':0},'expected_conformers':{'TRAIN_P':0,'TRAIN_U':0,'FULL_P':0,'FULL_U':0}}
            item={'mid':'original-opaque-id','role':'TRAIN','common_population':True,
                  'm_arrays':{6:np.asarray([0,0],dtype='<u4'),13:np.asarray([],dtype='u1'),14:np.asarray([],dtype='u1')},'p_records':[],'u_records':[]}
            def compact(source,target):target.mkdir();shutil.copyfile(source/'data.mdb',target/'data.mdb')
            with patch.object(R,'compact_once',side_effect=compact),patch.object(R,'sample_check',return_value={'toy':True}) as checker:
                result=R.export(plan,{'TRAIN':lambda:iter([item]),'FULL':lambda:iter(())},{'array_definitions':{}});checker.assert_called_once()
            split=pathlib.Path(result['split_roots']['TRAIN']);physical=pathlib.Path(result['id_map_physical_paths']['TRAIN'])
            self.assertTrue((split/'id_map.parquet').is_symlink());self.assertEqual((split/'id_map.parquet').resolve(),physical)
            self.assertEqual(pq.read_table(split/'id_map.parquet')['molecule_id'].to_pylist(),['original-opaque-id'])
            self.assertEqual(list(output.glob('*_id_fragments/*.parquet')),[])


if __name__=='__main__':unittest.main()
