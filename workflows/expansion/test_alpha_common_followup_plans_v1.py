"""Small stdlib metadata tests; no scheduler, scientific data or acceptance writes."""
import importlib.util
import json
from pathlib import Path
import shlex
import tempfile
import unittest

path=Path(__file__).with_name('alpha_common_followup_plans_v1.py')
spec=importlib.util.spec_from_file_location('followup_builder_source',path)
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class Metadata(unittest.TestCase):
    def test_module_and_tag_are_distinct_and_shell_roundtrip(self):
        argv=M.launcher_argv('/p y/python','/d/launcher',Path('/base'),'/e/entry',M.PACK,
          'common_reference_before',Path('/control'),Path('/a b/template.json'),'/rpc')
        self.assertEqual(argv[argv.index('--module')+1],M.PACK)
        self.assertEqual(argv[argv.index('--tag')+1],'common_reference_before')
        rendered=M.sbatch(argv,Path('/base'),Path('/control'),'common_reference_before')
        self.assertEqual(shlex.split(next(s[5:] for s in rendered.splitlines() if s.startswith('exec '))),argv)
        self.assertNotIn('--mem',rendered);self.assertIn('#SBATCH --time=0',rendered)
        self.assertRaises(ValueError,M.launcher_argv,'py','launch','base','entry','wrong.module','tag','c','p','rpc')

    def test_missing_or_running_c0_refuses_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def saved(name,value):
                path=root/name;path.write_text(json.dumps(value));return M.pin(path)
            parent=dict(endpoint='218.192.171.238:22',uid=1264,JobIDRaw='1885153',State='RUNNING',ExitCode='0:0')
            producer=saved('producer.json',{})
            account=saved('account.json',dict(actual_parents=[parent]))
            review=saved('review.json',dict(schema='ROOT_ALPHA_FULL_COMMON_GRAPH_ACTUAL_ACCEPTANCE_V1',
              status='APPROVED_EXACT_FULL_COMMON_REFERENCE',reviewer='root',producer_receipt=producer,
              actual_parent=parent,actual_accounting_reference=account))
            manifest=dict(status='COMPLETE_ALPHA_FULL_COMMON_REFERENCE',producer_schema='ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1',
              common_molecules=1196122,Main_parent_C0_claimed=False,final_Root_graph_review_reference=review,actual_full_receipt_reference=producer)
            before=set(root.iterdir())
            with self.assertRaisesRegex(ValueError,'Actual Alpha C0'):M.actual_common_parent(manifest)
            self.assertEqual(set(root.iterdir()),before)
            with self.assertRaises(ValueError):M.actual_common_parent({})

    def test_transport_origin_cannot_be_rewritten(self):
        rows=[dict(origin_endpoint='218.192.171.238:22',origin_uid=1264,
          source_reference=dict(path='/main/'+str(i),bytes=1,sha256='a'*64),
          replica_reference=dict(path='/alpha/'+str(i),bytes=1,sha256='a'*64)) for i in range(9)]
        transport=dict(schema='PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1',status='VERIFIED_REPLICAS_CLOSED',
          actual_transport_hash_verification=True,destination=dict(endpoint='218.192.171.238:22',uid=1264),replicas=rows)
        with self.assertRaisesRegex(ValueError,'Main UID1278'):M.original_regression(transport)


if __name__=='__main__':unittest.main()
