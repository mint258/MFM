"""One toy physical-path/canonical-ref fixture; no source arrays or pipeline."""
import json,pathlib,tempfile,unittest
from unittest.mock import patch
from . import source_bridge as S,prepare_runtime as P


class SpoolPathCheck(unittest.TestCase):
    def test_default_override_closed_reference_and_guard_before_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);metadata=root/'canonical';new=root/'guarded-new-spool'
            plan={'source_working_root':str(metadata)}
            physical,marker=S.spool_paths(plan,7,'TRAIN')
            self.assertEqual(physical,metadata/'TRAIN/block_0000007.sqlite')
            self.assertEqual(marker,metadata/'TRAIN/block_0000007.json')
            self.assertEqual(S.spool_paths(dict(plan,source_spool_root=None),7,'TRAIN'),(physical,marker))
            changed=dict(plan,source_spool_root=str(new))
            moved,same_marker=S.spool_paths(changed,7,'TRAIN')
            self.assertEqual(moved,new/'TRAIN/block_0000007.sqlite');self.assertEqual(same_marker,marker)
            self.assertEqual(S.spool_paths(changed,7,'FULL')[1],metadata/'FULL/block_0000007.json')
            marker.parent.mkdir(parents=True);old=root/'closed-old-spool.sqlite';old.write_bytes(b'closed toy spool')
            reference={'path':str(old),'mids':['opaque-b','opaque-a']};marker.write_text(json.dumps(reference))
            class NeverGuard:
                def wait(self,*args,**kwargs):raise AssertionError('closed ref must be reused before new scratch guard/create')
            with patch.dict(S.STATE,{'plan':changed,'disk_guard':NeverGuard()},clear=True),patch.object(S.sqlite3,'connect',side_effect=AssertionError('closed ref must not open/create pipeline DB')):
                self.assertEqual(S.work((7,['opaque-b','opaque-a'],'TRAIN')),reference)
            self.assertFalse(new.exists());self.assertEqual(json.loads(marker.read_text()),reference)
            # Missing toy payload follows the existing unclosed-attempt behavior;
            # stop at connect, before any pipeline/decode/evaluate can execute.
            old.unlink();events=[]
            class Guard:
                def wait(self,path,**kwargs):
                    events.append((pathlib.Path(path),new.exists()))
            def connect(path):
                self.assertEqual(path,moved);self.assertTrue(new.is_dir())
                raise RuntimeError('toy stop before pipeline database')
            with patch.dict(S.STATE,{'plan':changed,'disk_guard':Guard()},clear=True),patch.object(S.sqlite3,'connect',side_effect=connect):
                with self.assertRaisesRegex(RuntimeError,'toy stop before pipeline'):S.work((7,['opaque-b','opaque-a'],'TRAIN'))
            self.assertEqual(events[:2],[(moved,False),(marker,False)])
            self.assertEqual(json.loads(marker.read_text()),reference);self.assertFalse(moved.exists())
            # Bound-runtime metadata stays in place, only the allowed storage
            # hint is refreshed. No producer metadata/source read is reached.
            runtime=root/'runtime';runtime.mkdir();plan_path=root/'plan.json'
            original={'runtime_metadata_root':str(runtime),'source_working_root':str(metadata),'source_spool_root':'old-hint'}
            plan_path.write_text(json.dumps(dict(original,source_spool_root=str(new))))
            (runtime/'bound_plan.json').write_text(json.dumps({'plan_path':str(plan_path),'plan':original}))
            resumed=P.prepare(plan_path);self.assertEqual(resumed['source_spool_root'],str(new))
            self.assertEqual(resumed['source_working_root'],str(metadata))


if __name__=='__main__':unittest.main()
