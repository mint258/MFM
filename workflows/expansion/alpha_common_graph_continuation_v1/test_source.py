"""New transport/FD boundaries; original three semantic cases remain reused."""
import hashlib,json,pathlib,tempfile,unittest
from . import io as I,transport as T


class Guard:
    def check(self,*args,**kwargs):pass


class Boundaries(unittest.TestCase):
    def fixture(self):
        refs=[dict(path='/share/home/zixiao/descriptor_analysis/runs/origin/r%s'%i,bytes=1,sha256=hashlib.sha256(str(i).encode()).hexdigest()) for i in range(36)]
        origin=dict(zip(('origin_common_manifest_reference','origin_roles_manifest_reference','origin_formal_authority_reference'),refs[:3]));origin['origin_graph_input_references']=refs[3:]
        root='/gfshome/alpha/pubchem_expansion_20261103/exact/source_transport'
        rows=[dict(origin_reference=r,destination_reference=dict(r,path=root+'/r%s'%i)) for i,r in enumerate(refs)]
        return origin,rows,root

    def test_exact_bijective33_body_plus3_metadata_transport(self):
        origin,rows,root=self.fixture();mapping=T.bindings(origin,rows,root);self.assertEqual(len(mapping),36)
        self.assertTrue(all(mapping[r['origin_reference']['path']]['path']!=r['origin_reference']['path'] for r in rows))

    def test_changed_SHA_missing_body_or_collapsed_path_cannot_adopt(self):
        origin,rows,root=self.fixture()
        with self.assertRaises(ValueError):T.bindings(origin,rows[:-1],root)
        broken=json.loads(json.dumps(rows));broken[3]['destination_reference']['sha256']='0'*64
        with self.assertRaises(ValueError):T.bindings(origin,broken,root)
        broken=json.loads(json.dumps(rows));broken[-1]=broken[0]
        with self.assertRaises(ValueError):T.bindings(origin,broken,root)

    def test_owned_held_FD_rejects_mutation_after_whole_SHA(self):
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory)/'data';path.write_bytes(b'original');ref=I.pin(path);body=I.Body(ref,Guard())
            self.assertEqual(body.stream.read(),b'original');path.write_bytes(b'changed!!')
            try:
                with self.assertRaisesRegex(ValueError,'IMMUTABLE'):body.check()
            finally:body.stream.close();body.stream=None
