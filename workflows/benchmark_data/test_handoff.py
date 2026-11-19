import csv
import json
from pathlib import Path
import tempfile
import unittest
from .handoff import aggregate_counts,flatten,write_counts,pprime_closure

class HandoffTests(unittest.TestCase):
    def test_unknown_graphs_are_separate_from_known_rejection_and_reasons_overlap(self):
        row={'before':10,'domain_eligible':6,'retained':6,'graph_metadata_pending':1,
            'reason_counts_nonexclusive':{'RADICAL':3,'NON_SINGLET':2},'primary_reason_counts':{'RADICAL':3}}
        total=aggregate_counts([row])
        self.assertEqual((total['known_rejected'],total['unresolved']),(3,1))
        self.assertEqual(total['reason_counts_nonexclusive'],{'RADICAL':3,'NON_SINGLET':2})
        with tempfile.TemporaryDirectory() as tmp:
            rows=flatten('PPE1694',{'counts':[row],'domain_filter_complete':False},'source.json')
            target=Path(tmp)/'counts.csv';write_counts(target,rows)
            with target.open() as stream:out=list(csv.DictReader(stream))
            self.assertEqual(out[0]['unresolved'],'1')
            self.assertEqual(out[0]['reason:RADICAL'],'3')
            self.assertEqual(out[0]['primary:RADICAL'],'3')
            self.assertEqual(out[0]['domain_filter_complete'],'False')

    def test_nuclei_are_separate_and_blind_retained_rows_are_not_domain_eligible(self):
        counts=[{'nucleus':'13C','before':5,'domain_eligible':4,'retained':4},
                {'nucleus':'1H','before':3,'domain_eligible':3,'retained':3}]
        out=flatten('NMRShiftDB2',{'counts':counts},'source.json')
        self.assertEqual([r['dataset'] for r in out],['NMRShiftDB2_13C','NMRShiftDB2_1H'])
        blind=aggregate_counts([{'before':10,'domain_eligible':8,'retained':10,'blind_fallback_required':2}])
        self.assertEqual((blind['retained'],blind['known_rejected'],blind['blind_fallback_required']),(10,2,2))

    def test_terminal_outcomes_are_closed_but_failed_records_never_become_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=folder/'producer_fixture.json'
            report={'job':'SYNTHETIC','status':'ALL_QUEUED_PPRIME_TERMINAL','source_all_geometry_complete':True,
                'states':{'PPRIME_READY':3,'PPRIME_PARTIAL_WITH_RECORDED_OUTCOMES':1}}
            path.write_text(json.dumps(report))
            access={'immutable':True,'writers_closed':True,'producer_job':'SYNTHETIC','producer_manifest':str(path)}
            actual=pprime_closure(folder,access)
            self.assertTrue(actual['production_closed']);self.assertFalse(actual['all_ready'])
            report['states']['PENDING']=1;path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'unprocessed'):pprime_closure(folder,access)
            self.assertFalse(pprime_closure(folder,{'immutable':False})['production_closed'])

if __name__=='__main__':unittest.main()