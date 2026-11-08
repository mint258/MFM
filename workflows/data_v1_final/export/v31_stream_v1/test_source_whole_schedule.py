"""One synthetic encoded-whole scheduling/alias/codec fixture; no dataset QA."""
import concurrent.futures as cf
import copy,json,pathlib,sqlite3,tempfile,unittest
from unittest.mock import patch
import numpy as np
from . import source_bridge as S,run as R,prepare_runtime as P
from ..pilot_v31_compact_v1.codec import encode,encode_key


class SourceWholeScheduleCheck(unittest.TestCase):
    def test_mixed_encoded_whole_aliases_cursors_and_exact_codec_stream(self):
        sizes=[1]*12+[5,3,4,2,3,3,2]
        groups=[{'TRAIN':['m%d_%d'%(i,j)for j in range(n)],'FULL':['f%d_%d'%(i,j)for j in range(n%3)]}for i,n in enumerate(sizes)]
        untouched=copy.deepcopy(groups);stride=S.SOURCE_TASK_NUMBER_STRIDE
        plan={'source_task_molecules':2,'source_task_prefix_groups':12,'source_task_whole_groups':[13,15,16]}
        default={'source_task_molecules':2}
        for split in ('TRAIN','FULL'):
            expected=[]
            for i,g in enumerate(groups):
                if i<18:
                    if g[split]:expected.append((i,g[split],split))
                else:
                    expected.extend((i*stride+k,g[split][lo:lo+2],split)for k,lo in enumerate(range(0,len(g[split]),2)))
            self.assertEqual(list(S.source_tasks(default,groups,split)),expected)
            current=list(S.source_tasks(plan,groups,split))
            self.assertEqual([mid for _,mids,_ in current for mid in mids],[mid for g in groups for mid in g[split]])
            self.assertEqual([number for number,_,_ in current],sorted(number for number,_,_ in current))
            for number,mids,_ in current:
                if number>=stride:
                    group,sub=divmod(number,stride)
                    if group in plan['source_task_whole_groups']:self.assertEqual(sub,0);self.assertEqual(mids,groups[group][split])
                    else:self.assertLessEqual(len(mids),2)
        tail=list(S.source_tasks(plan,groups,'TRAIN',11))
        self.assertEqual([number for number,_,_ in tail],[12*stride,12*stride+1,12*stride+2,13*stride,14*stride,14*stride+1,15*stride,16*stride,17*stride,17*stride+1,18*stride])
        for i,(number,_,_) in enumerate(tail):self.assertEqual(list(S.source_tasks(plan,groups,'TRAIN',number)),tail[i+1:])
        for bad in (dict(plan,source_task_prefix_groups=0),dict(plan,source_task_prefix_groups=True),dict(plan,source_task_whole_groups=[-1]),dict(plan,source_task_whole_groups='13')):
            with self.assertRaises(ValueError):S.source_tasks(bad,groups,'TRAIN')
        with self.assertRaisesRegex(ValueError,'CONFLICTS_WITH_PREFIX'):S.source_tasks(plan,groups,'TRAIN',11*stride)
        with self.assertRaisesRegex(ValueError,'WHOLE_SOURCE_CURSOR_HAS_SUBINDEX'):S.source_tasks(plan,groups,'TRAIN',13*stride+1)
        R.validate_source_task_resume(default,plan,{'source_cursor':11})
        R.validate_source_task_resume(plan,dict(plan,source_task_whole_groups=[16,13,15]),{'source_cursor':13*stride})
        with self.assertRaisesRegex(ValueError,'WHOLE_MODE_CHANGED'):R.validate_source_task_resume(plan,dict(plan,source_task_whole_groups=[]),{'source_cursor':13*stride})
        with self.assertRaisesRegex(ValueError,'WHOLE_MODE_CHANGED'):R.validate_source_task_resume(dict(plan,source_task_whole_groups=[]),plan,{'source_cursor':13*stride})
        self.assertEqual(groups,untouched)
        serial={mid:i for i,mid in enumerate(mid for g in groups for mid in g['TRAIN'])}
        class Pool:
            def __init__(self,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def submit(self,function,task):
                future=cf.Future();future.set_result(function(task));return future
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);old_plan={'source_working_root':str(root/'old-meta'),'source_spool_root':str(root/'old-private'),'workers':2}
            new_plan=dict(plan,source_working_root=str(root/'new-meta'),source_spool_root=str(root/'new-private'),workers=2,streaming_buffer_blocks=2)
            def closed(current,task):
                number,mids,split=task;path,marker=S.spool_paths(current,number,split);path.parent.mkdir(parents=True,exist_ok=True)
                db=sqlite3.connect(path);book=['__ABSENT__'];codes={}
                try:
                    db.execute('CREATE TABLE molecules(mid TEXT PRIMARY KEY,row BLOB)')
                    for mid in mids:
                        i=serial[mid];record={'identity':{'native_record_id':'native-'+mid},'r73_channels':[('s','p',None),('kind'+str(i%4),'known-prefix','sigma')],
                            'arrays':{21:np.asarray([[float(i),-0.,np.nan]],dtype='<f4'),26:np.asarray([[0,0]],dtype='<i2'),27:np.asarray([[np.nan,-0.]],dtype='<f4'),
                                      31:np.asarray([0,0],dtype='<u4'),33:np.asarray([0,2],dtype='u1'),34:np.asarray([np.nan,-0.],dtype='<f4')}}
                        R.channel_codes(record,book,codes);record['r73_codebook']=book.copy();record.pop('r73_channels')
                        item={'mid':mid,'m_arrays':{1:np.asarray([6],dtype='u1'),6:np.asarray([1,0],dtype='<u2')},'p_records':[record],'u_records':[]}
                        db.execute('INSERT INTO molecules VALUES(?,?)',(mid,S.spool_dumps(item)))
                    db.commit()
                finally:db.close()
                ref={'path':str(path),'mids':mids};S.I.save(marker,ref);return path,marker,ref
            for task in S.source_tasks({},groups,'TRAIN',11):closed(old_plan,task)
            aliases={}
            for task in tail:
                number,mids,split=task;group=number//stride
                if group in plan['source_task_whole_groups']:
                    path,legacy,ref=closed(new_plan,(group,mids,split));_,alias=S.spool_paths(new_plan,number,split);S.I.save(alias,ref)
                    aliases[group]=(path,legacy,alias,ref,legacy.read_bytes())
                else:closed(new_plan,task)
            path,legacy,alias,ref,legacy_bytes=aliases[13]
            wrong=dict(ref,mids=list(reversed(ref['mids'])));S.I.save(alias,wrong)
            with patch.dict(S.STATE,{'plan':new_plan},clear=True),patch.object(S,'identity_db',side_effect=AssertionError('closed alias opened source')):
                with self.assertRaisesRegex(ValueError,'CLOSED_SOURCE_BLOCK_MIDS_DIFFER_FROM_REQUESTED'):S.work((13*stride,groups[13]['TRAIN'],'TRAIN'))
                S.I.save(alias,ref);self.assertEqual(S.work((13*stride,groups[13]['TRAIN'],'TRAIN')),ref)
            unlinks=[];real_unlink=pathlib.Path.unlink
            def unlink(path,*args,**kwargs):unlinks.append(str(path));return real_unlink(path,*args,**kwargs)
            def consume(current):
                frames=[];mids=[];book=['__ABSENT__','known-prefix'];codes={'known-prefix':1};prefix=sum(len(g['TRAIN'])for g in groups[:12])
                with patch.dict(S.STATE,{'plan':current},clear=True),patch.object(S,'identity_db',side_effect=AssertionError('closed source replayed')),patch.object(S,'source_molecule_groups',return_value=groups),patch.object(S.cf,'ProcessPoolExecutor',Pool):
                    for mi,item in enumerate(S.stream_split(current,None,None,None,'TRAIN',11),prefix):
                        mids.append(item['mid']);frames.append((encode_key('M',mi),encode(item['m_arrays'])))
                        for ci,record in enumerate(item['p_records']):
                            R.channel_codes(record,book,codes);frames.append((encode_key('P',mi,ci),encode(record['arrays'])))
                        if '_source_block_end'in item:item['_source_block_end']['ack']['committed']=True
                return mids,frames,book
            baseline=consume(old_plan)
            with patch.object(pathlib.Path,'unlink',unlink):actual=consume(new_plan)
            self.assertEqual(actual,baseline)
            for path,legacy,alias,ref,original_marker in aliases.values():
                self.assertEqual(unlinks.count(str(path)),1);self.assertFalse(path.exists());self.assertEqual(legacy.read_bytes(),original_marker)
                self.assertEqual(S.I.load(alias),ref)
            runtime=root/'runtime';runtime.mkdir();bound=root/'plan.json'
            previous={'runtime_metadata_root':str(runtime),'source_task_prefix_groups':18,'source_task_whole_groups':[]}
            changed=dict(previous,source_task_prefix_groups=12,source_task_whole_groups=[13,15,16])
            bound.write_text(json.dumps(changed));(runtime/'bound_plan.json').write_text(json.dumps({'plan_path':str(bound),'plan':previous}))
            self.assertEqual(P.prepare(bound),changed)


if __name__=='__main__':unittest.main()
