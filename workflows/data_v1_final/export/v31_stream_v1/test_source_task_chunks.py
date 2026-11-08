"""One metadata-only task-layout/cursor/r73-code fixture; no production data."""
import copy,json,pathlib,tempfile,unittest
from unittest.mock import patch
from . import source_bridge as S,run as R,prepare_runtime as P


class SourceTaskChunkCheck(unittest.TestCase):
    def test_tail_chunks_preserve_prefix_splits_cursors_and_global_codes(self):
        groups=[{'TRAIN':['t%d-a'%i,'t%d-b'%i],'FULL':['f%d-a'%i]}for i in range(18)]
        groups.extend([{'TRAIN':['t18-%d'%i for i in range(5)],'FULL':['f18-%d'%i for i in range(3)]},
                       {'TRAIN':[],'FULL':['f19-%d'%i for i in range(3)]},
                       {'TRAIN':['t20-%d'%i for i in range(3)],'FULL':[]}])
        original=copy.deepcopy(groups);stride=S.SOURCE_TASK_NUMBER_STRIDE;plan={'source_task_molecules':2}
        for split in ('TRAIN','FULL'):
            old=list(S.source_tasks({},groups,split));new=list(S.source_tasks(plan,groups,split))
            expected=[(i,g[split],split)for i,g in enumerate(groups)if g[split]]
            self.assertEqual(old,expected);self.assertEqual(list(S.source_tasks({'source_task_molecules':None},groups,split)),expected)
            self.assertEqual(new[:18],old[:18])
            for i in range(18):self.assertIs(new[i][1],groups[i][split])
            self.assertEqual([mid for _,mids,_ in new for mid in mids],[mid for _,mids,_ in old for mid in mids])
            self.assertTrue(all(number<18 or number>=18*stride for number,_,_ in new))
            self.assertEqual([number for number,_,_ in new],sorted(number for number,_,_ in new))
            self.assertTrue(all(len(mids)<=2 for number,mids,_ in new if number>=18*stride))
        train=list(S.source_tasks(plan,groups,'TRAIN'));full=list(S.source_tasks(plan,groups,'FULL'))
        self.assertEqual([n for n,_,_ in train[18:]],[18*stride,18*stride+1,18*stride+2,20*stride,20*stride+1])
        self.assertEqual([n for n,_,_ in full[18:]],[18*stride,18*stride+1,19*stride,19*stride+1])
        self.assertEqual(list(S.source_tasks(plan,groups,'TRAIN',2)),train[3:])
        self.assertEqual(list(S.source_tasks(plan,groups,'TRAIN',17)),train[18:])
        # Old integer cursor18 represents the WHOLE original group18, not chunk0.
        self.assertEqual(list(S.source_tasks(plan,groups,'TRAIN',18)),train[-2:])
        self.assertEqual(list(S.source_tasks(plan,groups,'TRAIN',18*stride)),train[19:])
        self.assertEqual(list(S.source_tasks(plan,groups,'TRAIN',18*stride+2)),train[-2:])
        self.assertEqual(list(S.source_tasks(plan,groups,'TRAIN',20*stride+1)),[])
        for invalid in (0,-1,True,False,1.5,'2048',{}):
            with self.assertRaisesRegex(ValueError,'SOURCE_TASK_MOLECULES_MUST_BE_POSITIVE_INTEGER_OR_NULL'):
                S.source_tasks({'source_task_molecules':invalid},groups,'TRAIN')
        with self.assertRaisesRegex(ValueError,'ENCODED_SOURCE_CURSOR_REQUIRES_ORIGINAL_CHUNK_HINT'):
            S.source_tasks({},groups,'TRAIN',18*stride)
        R.validate_source_task_resume({},plan,{'source_cursor':2})
        R.validate_source_task_resume(plan,dict(plan),{'source_cursor':18*stride})
        for changed in ({},{'source_task_molecules':3}):
            with self.assertRaisesRegex(ValueError,'ENCODED_SOURCE_CURSOR_CHUNK_HINT_CHANGED'):
                R.validate_source_task_resume(plan,changed,{'source_cursor':18*stride})
        self.assertEqual(groups,original)
        # Real existing channel_codes proves worker-local resets do not change
        # writer-global word insertion or the final numeric channel arrays.
        def global_codes(tasks):
            global_book=['__ABSENT__','known-prefix'];global_lookup={'known-prefix':1};output=[];ordinal=0
            for _,mids,_ in tasks:
                local_book=['__ABSENT__'];local_lookup={}
                for mid in mids:
                    for kind in ('P','U'):
                        record={'arrays':{},'r73_channels':[('s','p',None),('word'+str(ordinal%5),'known-prefix',kind)]}
                        R.channel_codes(record,local_book,local_lookup)
                        record['r73_codebook']=local_book.copy();record.pop('r73_channels')
                        R.channel_codes(record,global_book,global_lookup)
                        output.append((mid,kind,record['arrays'][32].tobytes()));ordinal+=1
            return global_book,output
        self.assertEqual(global_codes(list(S.source_tasks({},groups,'TRAIN'))),global_codes(train))
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);metadata=root/'shared';old_payload=root/'closed-prefix.sqlite';old_payload.write_bytes(b'owned closed prefix')
            physical,marker=S.spool_paths({'source_working_root':str(metadata)},4,'TRAIN');marker.parent.mkdir(parents=True)
            reference={'path':str(old_payload),'mids':groups[4]['TRAIN']};marker.write_text(json.dumps(reference))
            selected=next(task for task in train if task[0]==4)
            with patch.dict(S.STATE,{'plan':dict(plan,source_working_root=str(metadata))},clear=True),patch.object(S.sqlite3,'connect',side_effect=AssertionError('closed prefix reopened')):
                self.assertEqual(S.work(selected),reference)
            self.assertEqual(S.I.load(marker),reference);self.assertEqual(selected[1],groups[4]['TRAIN'])
            runtime=root/'runtime';runtime.mkdir();path=root/'plan.json'
            previous={'runtime_metadata_root':str(runtime),'source_task_molecules':None,'workers':16,'streaming_buffer_blocks':6,'chunk_compaction':{'enabled':False}}
            current=dict(previous,source_task_molecules=2,workers=8,streaming_buffer_blocks=8,chunk_compaction={'enabled':True})
            path.write_text(json.dumps(current));(runtime/'bound_plan.json').write_text(json.dumps({'plan_path':str(path),'plan':previous}))
            self.assertEqual(P.prepare(path),current)


if __name__=='__main__':unittest.main()
