"""Bounded standard-library tests; no actual data, QM, LMDB or Slurm."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from retention_policy_v1 import IO, audit_key, prove_raw, source_audit
from raw_archive import RawSink


class ArchiveFixture:
    FORBIDDEN_INPUT_NAMES={'input.xyz','input.mop'}
    @staticmethod
    def retention(record):return True,'controlled_fixture'
    @staticmethod
    def bundle(files):
        manifest=[{k:f[k] for k in ('name','byte_count','sha256','role')} for f in files]
        body=IO.canonical([dict(m,data=base64.b64encode(f['data']).decode()) for m,f in zip(manifest,files)])
        return body,manifest
    @staticmethod
    def unbundle(body):
        rows=json.loads(body);files=[dict(r,data=base64.b64decode(r['data'])) for r in rows]
        manifest=[{k:r[k] for k in ('name','byte_count','sha256','role')} for r in rows]
        for f in files:
            if hashlib.sha256(f['data']).hexdigest()!=f['sha256']:raise ValueError('fixture corrupt member')
        return files,manifest


class RetentionBoundaries(unittest.TestCase):
    def sources(self):return [{'path':f'/frozen/source{i}.lmdb','shard_id':i} for i in range(11)]
    def pair(self):
        return {'record_id':'pprime:m:2','molecule_id':'m','uff_coordinate_sha256':'c'*64,
          'source':{'molecule_id':'m','source_path':'/frozen/source6.lmdb','shard_id':6,'file_group':5,
                    'heavy_atoms':39,'size_stratum':'21_40','record_id':'anchor','record_payload_sha256':'p'*64},
          'conformer':{'source_record_id':'anchor','sprime_conf_idx':2,'status':'SUCCESS','converged':True}}

    def test_source_shard_and_legacy_engine_group_stay_distinct(self):
        row=source_audit(self.pair(),self.sources())
        self.assertEqual(row['source_shard_id'],6);self.assertEqual(row['legacy_engine_file_group'],5)
        self.assertEqual(row['audit_key_sha256'],audit_key('m',6,'21_40',row['physical_identity'])['audit_key_sha256'])
        self.assertNotEqual(row['audit_key_sha256'],audit_key('m',5,'21_40',row['physical_identity'])['audit_key_sha256'])

    def test_missing_or_changed_source_authority_is_rejected(self):
        with self.assertRaises(ValueError):source_audit(self.pair(),self.sources()[:-1])
        for change in ({'shard_id':5},{'source_path':'/output/new.lmdb'},{'heavy_atoms':None},{'size_stratum':'0_20'}):
            pair=self.pair();pair['source'].update(change)
            with self.assertRaises(ValueError):source_audit(pair,self.sources())

    def test_real_sqlite_gzip_all12_input_output_sha_proof_and_missing_call(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'raw.sqlite';sink=RawSink(path,ArchiveFixture,16<<20)
            tasks=[]
            for calc in IO.TASKS:
                body=('actual-controlled-'+calc).encode();sha=hashlib.sha256(body).hexdigest()
                provenance={'input_bundle_sha256':'b'*64,'input_file_sha256':{'input.xyz':'x'*64}}
                tasks.append({'task':calc,'provenance':provenance})
                sink({'record_id':'r','calc_type':calc,'execution_id':'execution','input_bundle_sha256':'b'*64,
                   'input_file_sha256':{'input.xyz':'x'*64},'source_reference':{'shard_id':6},'file_group':5,
                   'keywordSHA':'k'*64,'files':[{'name':'output.log','role':'output','data':body,'byte_count':len(body),'sha256':sha}]})
            sink.close();worker={'raw_container':IO.reference(path)}
            rows=[{'record_id':'r','source_shard_id':6,'legacy_engine_file_group':5,'retain_all_twelve_raw':True}]
            records=[{'record_id':'r','tasks':tasks}];engine=SimpleNamespace(OUTPUT_ARCHIVE=ArchiveFixture)
            proof=prove_raw([worker],rows,records,engine)
            self.assertEqual(proof['status'],'ALL_REQUIRED_RETAINED_CALLS_SHA_VERIFIED')
            self.assertEqual(proof['verified_calls'],12)
            wrong=copy.deepcopy(records);wrong[0]['tasks'][0]['provenance']['input_bundle_sha256']='bad'
            with self.assertRaises(ValueError):prove_raw([worker],rows,wrong,engine)
            missing=prove_raw([],rows,records,engine)
            self.assertEqual(len(missing['missing']),12)
            failure_only=copy.deepcopy(records);failure_only[0]['tasks'][0]['scope_status']='PROPERTY_FAILED'
            non_audit=[dict(rows[0],retain_all_twelve_raw=False)]
            missing_failed=prove_raw([],non_audit,failure_only,engine)
            self.assertEqual(len(missing_failed['missing']),1)


if __name__=='__main__':unittest.main(verbosity=2)
