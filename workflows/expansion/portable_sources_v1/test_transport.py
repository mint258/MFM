"""Metadata-only actual-file transport verification with original refs retained."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from ..common import reference
from .transport import Transport


class TransportTests(unittest.TestCase):
    def test_real_replica_verified_and_same_size_mtime_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);replica=root/'replica';replica.write_bytes(b'abc')
            local=reference(replica);origin={**local,'path':'/original-endpoint/immutable/source'}
            body={'schema':'PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1','status':'VERIFIED_REPLICAS_CLOSED',
                'destination':{'endpoint':'fixture','uid':os.getuid()},'replicas':[{'origin_endpoint':'original-fixture',
                'origin_uid':34567,'source_reference':origin,'replica_reference':local}]}
            manifest=root/'manifest.json';manifest.write_text(json.dumps(body));transport=Transport(reference(manifest),'fixture',os.getuid())
            self.assertEqual(transport.verify(origin),replica)
            self.assertEqual(origin['path'],'/original-endpoint/immutable/source')
            old=replica.stat();replica.write_bytes(b'xyz');os.utime(replica,ns=(old.st_atime_ns,old.st_mtime_ns))
            with self.assertRaises(ValueError):transport.verify(origin)

    def test_actual_uid_and_original_byte_identity_are_mandatory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);replica=root/'replica';replica.write_bytes(b'abc');local=reference(replica)
            origin={**local,'path':'/original/source','sha256':hashlib.sha256(b'xyz').hexdigest()}
            body={'schema':'PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1','status':'VERIFIED_REPLICAS_CLOSED',
                'destination':{'endpoint':'fixture','uid':os.getuid()},'replicas':[{'origin_endpoint':'origin',
                'origin_uid':34567,'source_reference':origin,'replica_reference':local}]}
            manifest=root/'manifest.json';manifest.write_text(json.dumps(body));ref=reference(manifest)
            with self.assertRaises(ValueError):Transport(ref,'fixture',os.getuid()+1)
            with self.assertRaises(ValueError):Transport(ref,'fixture',os.getuid())


if __name__=='__main__':unittest.main()
