"""Meaningful native immutable-replica and explicit-origin boundary tests."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from .reader import ReplicaVerifier,S,MAIN,ALPHA


class Native(unittest.TestCase):
    root=Path('/gfshome/alpha/codex_data_v1_20261026/control')
    def setup_reader(self,directory):
        path=directory/'source.jsonl';path.write_bytes(b'{"source":"fixture"}\n')
        replica=S.pin(path);source=dict(replica,path='/share/home/zixiao/synthetic_fixture/source.jsonl')
        binding=dict(origin_endpoint=MAIN,origin_uid=1278,source_reference=source,replica_reference=replica)
        plan=dict(schema='ALPHA_ALL10_SOURCE_REPLICA_PLAN_V1',scope_key='alpha_all10_source_replica_v1',endpoint=ALPHA,uid=1264)
        return ReplicaVerifier(plan,[binding]),source,path

    def test_explicit_Main_origin_reads_real_Alpha_replica_and_requires_complete_hash(self):
        with tempfile.TemporaryDirectory(dir=self.root) as name:
            reader,source,path=self.setup_reader(Path(name))
            self.assertEqual(list(reader.rows(source)),[{'source':'fixture'}])
            self.assertEqual(reader.consumption[0]['source_reference'],source)
            self.assertNotEqual(str(path),source['path'])
            path.write_bytes(b'{"source":"changed"}\n')
            with self.assertRaises(ValueError):reader.verify(source)

    def test_symlink_and_undeclared_origin_cannot_become_an_implicit_replica(self):
        with tempfile.TemporaryDirectory(dir=self.root) as name:
            reader,source,path=self.setup_reader(Path(name))
            undeclared=dict(source,path='/share/home/zixiao/other/source.jsonl')
            with self.assertRaises(ValueError):reader.verify(undeclared)
            target=path.with_name('preserved.jsonl');path.rename(target);path.symlink_to(target)
            with self.assertRaises(ValueError):reader.verify(source)


if __name__=='__main__':unittest.main()
