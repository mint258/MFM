"""One tiny publication fixture: closed local files, exact refs, no group replay."""
import json,shutil,sqlite3,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from . import io as I,scratch as S

class GroupScratch(unittest.TestCase):
    def test_closed_outputs_publish_once_report_last_and_resume_exact_group(self):
        import pyarrow as pa,pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);attempt=root/'shared/pass_0002/attempt_0000';attempt.mkdir(parents=True)
            group={'group_index':7,'source_job_id':'original-job-7'};value=1.0000000000000002
            cfg={'group_scratch_root':str(root/'local'),'statistics_purpose':'normalization_moments',
                'group_producer_inputs':{'inputs':{'coverage_reference':{'path':'/frozen/source','bytes':73}},
                    'stage_reference':{'path':'/shared/pass_0002/stage.json','bytes':101}}}
            closed=[];calls=[]
            def compute(work):
                current,stage,local,owner=work;calls.append(owner['group_index']);out=Path(local)/'group_0007';out.mkdir()
                db=sqlite3.connect(out/'r73_derived.sqlite');db.execute('CREATE TABLE example(value REAL)')
                db.execute('INSERT INTO example VALUES(?)',(value,));db.commit();db.close()
                for name in ('radix_counts','mask_overrides','molecule_field_means'):
                    pq.write_table(pa.table({'value':[value],'mask':[False]}),out/(name+'.parquet'))
                closed.append(True)
                record={'group_index':7,'source_job_id':'original-job-7','statistics_purpose':'normalization_moments',
                    'energy_TSQR':{'0':{'n':3,'unchanged':'original-state'}},'moments':{'0':{'mean':repr(value)}},
                    'r73_derived_reference':dict(I.ref(out/'r73_derived.sqlite'),group_index=7),
                    'radix_histogram':I.ref(out/'radix_counts.parquet'),
                    'mask_override_reference':dict(I.ref(out/'mask_overrides.parquet'),records=1,newly_masked_records=1),
                    'molecule_field_means_reference':I.ref(out/'molecule_field_means.parquet')}
                return I.save(out/'report.json',record)
            copy=shutil.copyfile
            def copying(source,target):
                self.assertEqual(closed,[True]);self.assertFalse((attempt/'group_0007/report.json').exists())
                return copy(source,target)
            with patch.object(S.shutil,'copyfile',side_effect=copying) as transferred:
                reference=S.execute_group((cfg,{},str(attempt),group),compute)
                self.assertEqual(transferred.call_count,4)
            report=I.load(reference['path']);self.assertEqual(calls,[7])
            self.assertEqual(report['energy_TSQR'],{'0':{'n':3,'unchanged':'original-state'}})
            self.assertEqual(report['mask_override_reference']['newly_masked_records'],1)
            for key in S.OUTPUT_REFERENCES:
                published=Path(report[key]['path']);self.assertEqual(published.parent,attempt/'group_0007')
                self.assertEqual(published.stat().st_size,report[key]['bytes'])
            db=sqlite3.connect('file:'+report['r73_derived_reference']['path']+'?mode=ro',uri=True)
            try:self.assertEqual(struct.pack('<d',db.execute('SELECT value FROM example').fetchone()[0]),struct.pack('<d',value))
            finally:db.close()
            copied=pq.read_table(report['molecule_field_means_reference']['path']).to_pylist()[0]
            self.assertEqual(struct.pack('<d',copied['value']),struct.pack('<d',value));self.assertIs(copied['mask'],False)
            # Parent may have stopped after publication but before checkpoint.
            # Same frozen inputs/stage/group reuse the exact already closed ref.
            later=attempt.parent/'attempt_0001';later.mkdir()
            with patch.object(S.shutil,'copyfile',side_effect=AssertionError('CLOSED_FILES_MUST_NOT_RECOPY')):
                reused=S.execute_group((cfg,{},str(later),group),lambda work:self.fail('CLOSED_GROUP_MUST_NOT_RECOMPUTE'))
            self.assertEqual(reused,reference);self.assertFalse((later/'group_0007').exists())
            different=dict(cfg,group_producer_inputs=dict(cfg['group_producer_inputs'],stage_reference={'path':'/different-stage','bytes':101}))
            def new_stage(work):raise RuntimeError('DIFFERENT_STAGE_REQUIRES_ITS_OWN_COMPUTATION')
            with self.assertRaisesRegex(RuntimeError,'DIFFERENT_STAGE_REQUIRES_ITS_OWN_COMPUTATION'):
                S.execute_group((different,{},str(later),group),new_stage)
