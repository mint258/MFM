"""One toy delta/checkpoint fixture; no source datasets, recasts, QM or real QA."""
import copy,pathlib,pickle,random,shutil,tempfile,unittest
from unittest.mock import patch
import numpy as np
from .state_journal import Journals
from . import run as R


class StateJournalCheck(unittest.TestCase):
    def test_dirty_deltas_closed_prefix_migration_and_writer_resume(self):
        def entry(number):
            # Preserve even the NaN payload and signed zero as bytes, not values.
            bits=np.asarray([0x80000000,0x7fc00017,0x3f800000+number],dtype='<u4')
            return ('TRAIN',b'P0',{21:bits.view('<f4')},b'M0',{6:np.asarray([1,0],dtype='<u2')},{'within_tolerance':True})
        def same(left,right):
            self.assertEqual(left[:2],right[:2]);self.assertEqual(left[3],right[3]);self.assertEqual(left[5],right[5])
            for group in (2,4):
                self.assertEqual(set(left[group]),set(right[group]))
                for key in left[group]:
                    self.assertEqual(left[group][key].dtype,right[group][key].dtype)
                    self.assertEqual(left[group][key].shape,right[group][key].shape)
                    self.assertEqual(left[group][key].tobytes(),right[group][key].tobytes())
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);journal_root=root/'journal';journal_root.mkdir()
            journal=Journals(journal_root);seen={'opaque-m0'};samples=[entry(0)]
            journal.mark_seen('opaque-m0');journal.sample(0,samples[0]);closed=journal.flush(1,1)
            seen_prefix=pathlib.Path(closed['seen']['path']).read_bytes();sample_prefix=pathlib.Path(closed['samples']['path']).read_bytes()
            self.assertEqual(journal.flush(1,1),closed)
            journal.mark_seen('opaque-m1');journal.sample(0,entry(1));journal.sample(1,entry(2));journal.flush(2,2)
            self.assertTrue(pathlib.Path(closed['seen']['path']).read_bytes().startswith(seen_prefix))
            self.assertTrue(pathlib.Path(closed['samples']['path']).read_bytes().startswith(sample_prefix))
            restored,loaded_seen,loaded_samples=Journals.restore(journal_root,closed)
            self.assertEqual(loaded_seen,seen);same(loaded_samples[0],samples[0])
            self.assertEqual(pathlib.Path(closed['seen']['path']).read_bytes(),seen_prefix)
            self.assertEqual(pathlib.Path(closed['samples']['path']).read_bytes(),sample_prefix)
            restored.mark_seen('opaque-m1');restored.sample(0,entry(1));restored.sample(1,entry(2))
            next_closed=restored.flush(2,2);_,next_seen,next_samples=Journals.restore(journal_root,next_closed)
            self.assertEqual(next_seen,{'opaque-m0','opaque-m1'});same(next_samples[0],entry(1));same(next_samples[1],entry(2))
            self.assertEqual(next_closed['samples']['records'],3);self.assertEqual(next_closed['sample_count'],2)
            legacy=root/'legacy';legacy.mkdir();original_seen=next_seen.copy();original_samples=copy.deepcopy(next_samples)
            migrated=Journals.migrate(legacy,original_seen,original_samples);reference=migrated.flush(2,2)
            _,mseen,msamples=Journals.restore(legacy,reference);self.assertEqual(mseen,original_seen)
            for left,right in zip(msamples,original_samples):same(left,right)

            # Actual tiny writer checkpoint path, with one failed unclosed block.
            output=root/'export';scratch=root/'scratch';seed=91;ack0={'committed':False};ack1={'committed':False};calls=[]
            plan={'output_root':str(output),'working_root':str(scratch),'sample_seed':seed,'source_sample_keys':['p0','p1'],
                  'data_version':'toy-journal','gpu_nodes':[],'expected_molecules':{'TRAIN':2,'FULL':0},
                  'expected_conformers':{'TRAIN_P':2,'TRAIN_U':0,'FULL_P':0,'FULL_U':0}}
            def molecule(number,block=None):
                result={'mid':'m%d'%number,'role':'TRAIN','common_population':True,
                        'm_arrays':{6:np.asarray([1,0],dtype='<u2'),13:np.asarray([0],dtype='u1'),14:np.asarray([],dtype='u1')},
                        'p_records':[{'arrays':{21:entry(number)[2][21].copy()},'identity':{'native_record_id':'p%d'%number,'geometry_id':'g%d'%number},
                                      'source_F64_cast_comparison':{'within_tolerance':True}}],'u_records':[]}
                if block is not None:result['_source_block_end']=block
                return result
            def first():
                calls.append('first');yield molecule(0,{'number':0,'ack':ack0})
                self.assertTrue(ack0['committed']);yield molecule(1)
                raise RuntimeError('toy interruption before block closure')
            def resume(start_after=None):
                calls.append(('resume',start_after));self.assertEqual(start_after,0)
                yield molecule(1,{'number':1,'ack':ack1})
            def compact(source,target):target.mkdir();shutil.copyfile(source/'data.mdb',target/'data.mdb')
            with patch.object(R,'compact_once',side_effect=compact),patch.object(R,'sample_check',return_value={'toy_closed':True}) as check:
                with self.assertRaisesRegex(RuntimeError,'toy interruption'):R.export(copy.deepcopy(plan),{'TRAIN':first,'FULL':lambda:iter(())},{'array_definitions':{}})
                with (output/'producer_checkpoint.pkl').open('rb') as stream:state=pickle.load(stream)
                self.assertNotIn('seen',state);self.assertNotIn('samples',state)
                self.assertEqual(state['journal_state']['seen_count'],1);self.assertEqual(state['journal_state']['sample_count'],1)
                self.assertEqual(state['rng_state'],random.Random(seed).getstate())
                result=R.export(copy.deepcopy(plan),{'TRAIN':resume,'FULL':lambda:iter(())},{'array_definitions':{}})
                check.assert_called_once();self.assertTrue(ack1['committed']);self.assertEqual(calls,['first',('resume',0)])
            with (output/'producer_checkpoint.pkl').open('rb') as stream:state=pickle.load(stream)
            self.assertNotIn('seen',state);self.assertNotIn('samples',state)
            _,final_seen,final_samples=Journals.restore(output,state['journal_state'])
            self.assertEqual(final_seen,{'m0','m1'});self.assertEqual(len(final_samples),2)
            self.assertEqual(state['journal_state']['samples']['records'],2)
            for index,sample in enumerate(final_samples):
                self.assertEqual(sample[2][21].dtype,np.dtype('<f4'));self.assertEqual(sample[2][21].tobytes(),entry(index)[2][21].tobytes())
            self.assertEqual(result['molecules']['TRAIN'],2)


if __name__=='__main__':unittest.main()
