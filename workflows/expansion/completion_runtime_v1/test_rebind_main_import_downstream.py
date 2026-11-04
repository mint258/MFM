"""Pure scheduling transforms against the captured real nine-job metadata; no submission."""
import copy,json,pathlib,re,unittest
from .rebind_main_import_downstream import rewrite,replace_job_tokens,declared_ids,OLD,ROLES
BLUEPRINT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/pubchem_alpha_return_20261103/main_import_pending_blueprint_20261104_v1.json')
class PendingTransform(unittest.TestCase):
    def test_real_pending_nine_scripts_and_six_configs_without_science_changes(self):
        # Replacement IDs are fixtures only. This test never calls Slurm.
        actual=json.loads(BLUEPRINT.read_text());self.assertEqual(len(actual['jobs']),9);self.assertEqual(len(actual['configs']),6)
        before=copy.deepcopy(actual)
        mapping={'1885232':'9900001','1885233':'9900002','inverted_resume_20261104_v1_low11':'fixture_low',
            'inverted_resume_20261104_v1_high5':'fixture_high'}
        for index,item in enumerate(actual['jobs']):
            original=actual['configs'][item['config']]['value'];changed=rewrite(original,mapping)
            self.assertFalse(declared_ids(changed)&set(OLD+['1885232','1885233']))
            destination='/control/fixture_'+ROLES[item['job_id']]+'_config.json'
            body=replace_job_tokens(item['script_body'].replace(item['config'],destination),mapping)
            self.assertFalse(any(re.search(r'(?<![0-9])'+j+r'(?![0-9])',body)for j in OLD))
            self.assertIn('--config '+destination,body)
            self.assertEqual(body.count('--cpus-per-task='),1)
            self.assertIn('export CUDA_VISIBLE_DEVICES=',body)
            self.assertNotIn('202.38.252.202',body)
            mapping[item['job_id']]=str(9910000+index)
        self.assertEqual(actual,before)
    def test_frozen_artifacts_and_actual_proofs_never_relabel(self):
        artifact=dict(path='/exact/partitioned_novelty_ded6679_low11_job_1885213/manifest.json',bytes=10,sha256='1'*64)
        changed=rewrite(dict(reference=artifact,job_id='1885232',original201='1885201'),{'1885232':'9900001'})
        self.assertEqual(changed['reference'],artifact);self.assertEqual(changed['original201'],'1885201')
        self.assertEqual(changed['job_id'],'9900001')
        bound=dict(runtime=dict(job_id='1885232'),plan_reference=artifact,startup_proof_reference=artifact)
        with self.assertRaises(ValueError):rewrite(bound,{'1885232':'9900001'})
        with self.assertRaises(ValueError):rewrite(artifact,{artifact['path']:'/fake'})
if __name__=='__main__':unittest.main()
