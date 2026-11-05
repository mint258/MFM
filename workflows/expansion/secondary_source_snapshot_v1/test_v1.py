"""New3 pure in-memory asset boundaries, before extraction and original Budget."""
import hashlib,io,stat,unittest,zipfile
from . import assets as A,contracts as C


class Boundaries(unittest.TestCase):
    def test_paths_symlink_duplicate_and_extra_members_rejected_before_extract(self):
        for path in ('/x','../x','x/../y','x//y','./x','.git/config','x\\y','C:/x','x\0y'):
            with self.assertRaises(ValueError):C.safe_relative(path)
        C.safe_relative('docs/中文 source.md')
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as z:
            info=zipfile.ZipInfo('a.py');info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,'outside')
        with zipfile.ZipFile(io.BytesIO(raw.getvalue())) as z:
            with self.assertRaises(ValueError):A.member_inventory(z,{'a.py':{'bytes':7}})
        for names in (('a.py','extra.py'),()):
            raw=io.BytesIO()
            with zipfile.ZipFile(raw,'w') as z:
                for name in names:z.writestr(name,b'')
            with zipfile.ZipFile(io.BytesIO(raw.getvalue())) as z:
                with self.assertRaises(ValueError):A.member_inventory(z,{'a.py':{'bytes':0}})

    def test_independent_git_universe_catches_manifest_omission_and_empty_source_is_legal(self):
        root='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository'
        paths=['tools/check_repository.py','docs/SOURCE_MANIFEST.json','pkg/__init__.py'];sha=hashlib.sha256(b'').hexdigest()
        manifest={'schema':'ROOT_MAIN_GIT_LISTED_SOURCE_SNAPSHOT_ASSETS_V1','origin_endpoint':'202.38.247.57:22','origin_uid':1278,
          'origin_source_root':root,'files':[{'relative_path':p,'origin_reference':{'path':root+'/'+p,'bytes':0,'sha256':sha}} for p in paths]}
        universe={'schema':'MAIN_GIT_LISTED_SOURCE_UNIVERSE_V1','source_endpoint':'202.38.247.57:22','uid':1278,
          'git_list_returncode':0,'git_list_argv':['git','ls-files','--cached','--others','--exclude-standard','-z'],'paths':paths}
        self.assertEqual(len(C.entries(manifest,universe)),3)
        missing=dict(manifest,files=manifest['files'][:-1])
        with self.assertRaises(ValueError):C.entries(missing,universe)
        with self.assertRaises(ValueError):C.entries(manifest,dict(universe,paths=paths+['new_untracked.py']))
        with self.assertRaises(ValueError):C.entries(dict(manifest,files=manifest['files']+[manifest['files'][0]]),universe)

    def test_current_SHA_and_frame_not_size_only_or_stale_claim(self):
        digest=hashlib.sha256(b'original').hexdigest();ref={'bytes':8,'sha256':digest}
        before=(1,2,8,3,4,1264,stat.S_IFREG|0o444)
        A.stable_claim(before,before,8,digest,ref)
        for after,count,value in ((before,8,hashlib.sha256(b'changed!').hexdigest()),(before,7,digest),
          ((1,2,8,9,4,1264,before[-1]),8,digest),((1,9,8,3,4,1264,before[-1]),8,digest),
          ((1,2,8,3,9,1264,before[-1]),8,digest)):
            with self.assertRaises(ValueError):A.stable_claim(before,after,count,value,ref)


if __name__=='__main__':unittest.main()
