"""One synthetic local-ID-fragment fixture; never read production data."""
import copy,json,pathlib,pickle,shutil,tempfile,unittest
from unittest.mock import patch
import numpy as np
import pyarrow.parquet as pq
from . import run as R,prepare_runtime as P
from .block_checkpoint import IDFragments,id_fragment_root,consume_id_fragments


class LocalIDFragmentsCheck(unittest.TestCase):
    def test_local_fragments_resume_preserves_closed_refs_and_final_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);output=root/'shared_output';local=root/'node20';later=root/'new_hint'
            self.assertEqual(id_fragment_root({},output,root/'raw'/'TRAIN'),output/'TRAIN_id_fragments')
            self.assertEqual(id_fragment_root({'id_fragment_working_root':str(local)},output,root/'raw'/'TRAIN'),local/'TRAIN_id_fragments')
            plan={'output_root':str(output),'working_root':str(root/'raw'),'sample_seed':17,'source_sample_keys':[],
                  'id_fragment_working_root':str(local),'id_map_storage':'external_symlink',
                  'data_version':'toy-local-fragments','expected_molecules':{'TRAIN':2,'FULL':0},
                  'expected_conformers':{'TRAIN_P':0,'TRAIN_U':0,'FULL_P':0,'FULL_U':0},'gpu_nodes':[]}
            schema={'array_definitions':{}};ack0={'committed':False};ack1={'committed':False};calls=[];guards=[]
            class Guard:
                def wait(self,path,bytes_needed=0,inodes_needed=0):guards.append((pathlib.Path(path),bytes_needed,inodes_needed))
            guard=Guard()
            def fragments(path,closed=(),guard=None):return IDFragments(path,closed,guard=Guard())
            def item(mid,number,ack):
                return {'mid':mid,'role':'TRAIN','common_population':True,
                        'm_arrays':{6:np.asarray([0,0],dtype='<u4'),13:np.asarray([],dtype='u1'),14:np.asarray([],dtype='u1')},
                        'p_records':[],'u_records':[],'_source_block_end':{'number':number,'ack':ack}}
            def first():
                calls.append(None);yield item('m0',0,ack0)
                self.assertTrue(ack0['committed']);raise RuntimeError('toy stop after closed local fragment')
            def resumed(start_after=None):
                calls.append(start_after);self.assertEqual(start_after,0);yield item('m1',1,ack1)
            def compact(source,target):target.mkdir();shutil.copyfile(source/'data.mdb',target/'data.mdb')
            consumed=[]
            def consume(active):
                if active['split']=='TRAIN':
                    self.assertEqual(pathlib.Path(active['fragment_root']).parent,local)
                    self.assertTrue(all(pathlib.Path(ref['path']).parent.parent==local for ref in active['id_fragments']))
                    self.assertTrue(pathlib.Path(active['idpath']).is_relative_to(output))
                    consumed.extend(active['id_fragments'])
                consume_id_fragments(active)
            with patch.object(R,'IDFragments',side_effect=fragments),patch.object(R,'sample_check',return_value={'toy':True}) as check:
                with self.assertRaisesRegex(RuntimeError,'toy stop'):
                    R.export(copy.deepcopy(plan),{'TRAIN':first,'FULL':lambda:iter(())},schema)
                with (output/'producer_checkpoint.pkl').open('rb') as stream:state=pickle.load(stream)
                closed=state['active']['id_fragments'][0];self.assertTrue(pathlib.Path(closed['path']).is_file())
                self.assertEqual(pathlib.Path(state['active']['fragment_root']).parent,local)
                plan['id_fragment_working_root']=str(later)
                with patch.object(R,'compact_once',side_effect=compact),patch.object(R,'consume_id_fragments',side_effect=consume):
                    result=R.export(copy.deepcopy(plan),{'TRAIN':resumed,'FULL':lambda:iter(())},schema)
                check.assert_called_once()
            self.assertEqual(calls,[None,0]);self.assertTrue(ack1['committed']);self.assertEqual(consumed[0],closed)
            self.assertTrue(all(not pathlib.Path(ref['path']).exists() for ref in consumed))
            final=pathlib.Path(result['split_roots']['TRAIN']);link=final/'id_map.parquet'
            self.assertTrue(link.is_symlink());self.assertTrue(link.resolve().is_relative_to(output))
            actual=pq.read_table(link).to_pylist()
            expected=[R.identity_row('M',i,None,mid,{},False) for i,mid in enumerate(('m0','m1'))]
            self.assertEqual(actual,expected)
            self.assertTrue(any(path.is_relative_to(local) for path,_,_ in guards))
            self.assertTrue(any(path.is_relative_to(output) and size>0 for path,size,_ in guards))
            # Bound runtime accepts the storage hint without changing scientific fields.
            runtime=root/'runtime';runtime.mkdir();path=root/'plan.json'
            old={'runtime_metadata_root':str(runtime),'id_fragment_working_root':str(local),'science':'fixed'}
            path.write_text(json.dumps(dict(old,id_fragment_working_root=str(later))))
            (runtime/'bound_plan.json').write_text(json.dumps({'plan_path':str(path),'plan':old}))
            bound=P.prepare(path)
            self.assertEqual(bound['id_fragment_working_root'],str(later));self.assertEqual(bound['science'],'fixed')


if __name__=='__main__':unittest.main()
