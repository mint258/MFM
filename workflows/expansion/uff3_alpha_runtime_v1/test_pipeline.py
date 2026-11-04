"""One metadata-only native path/result/launcher boundary fixture."""
from pathlib import Path
import tempfile
import unittest
from . import prepare_pipeline as P


class PipelineTests(unittest.TestCase):
    def test_actual_epoch_pin_unique_result_and_explicit_launcher_dispatch(self):
        with tempfile.TemporaryDirectory()as folder:
            control=Path(folder);epoch=control/'source_job_216';epoch.mkdir()
            plan=dict(endpoint=P.Q.ENDPOINT,uid=P.Q.UID,output_directory='/gfshome/alpha/fixture/source')
            planref=P.Q.write(epoch/'plan.json',plan)
            proof=dict(job_id='216',endpoint=P.Q.ENDPOINT,uid=P.Q.UID,request={'producer_plan_reference':planref})
            P.Q.write(epoch/'startup.json',proof)
            meta=P.upstream('216','source',control)
            self.assertEqual(meta['plan_reference'],planref)
            self.assertEqual(meta['runtime']['job_id'],'216')
            P.Q.write(epoch/'startup.json',{**proof,'job_id':'217'},replace=True)
            with self.assertRaisesRegex(ValueError,'startup/plan'):P.upstream('216','source',control)
            with self.assertRaises(ValueError):P.literal('216','../source')
            output=control/'small_generation';output.mkdir()
            gen={**meta,'output_directory':str(output)}
            body=dict(runtime={'job_id':'216'},execution_metadata=dict(original_launcher_plan_reference=meta['plan_reference'],
                original_startup_proof_reference=meta['startup_proof_reference']))
            result=P.Q.write(output/'receipt_job216_one.json',body)
            self.assertEqual(P.result_reference(gen,'generation'),result)
            P.Q.write(output/'receipt_job216_two.json',body)
            with self.assertRaisesRegex(ValueError,'Exactly one'):P.result_reference(gen,'generation')
            argv=P.launch_argv('/real/template.json','full','/immutable/layer_entry.py','uff_full',control,
                python='/isolated/python',base='/clean/base',launcher='/actual/node_launcher_rpc_v3_resume.py',rpc='/actual/rpc.py')
            self.assertEqual(argv[:4],['/isolated/python','-I','-B','/actual/node_launcher_rpc_v3_resume.py'])
            self.assertEqual(argv[argv.index('--module')+1],'workflows.expansion.uff3_alpha_runtime_v1.entry')
            self.assertEqual(argv[argv.index('--template')+1],'/real/template.json')
            final=P.launch_argv('/closed/template.json','finalize','/immutable/layer_entry.py','uff_final',control)
            self.assertEqual(final[final.index('--module')+1],'workflows.expansion.uff3_candidate_finalize_v1.entry')
            self.assertNotIn('sbatch',argv+final)


if __name__=='__main__':unittest.main()