"""Actual saved-object aggregation boundaries; standard library, no native calls."""
import copy
import unittest
from ..uff3_candidate_v1 import core as C
from . import report_metrics as M,validation as V
from .test_closure import fixture


class ReportMetricsTests(unittest.TestCase):
    def test_exact_timing_unknown_sparse_internal_candidates_and_legacy(self):
        aggregate=M.Accumulator()
        def append(args,journal=None):
            source,cache,packet,manifest,events=args
            saved=dict(V.packet(*args),molecule_id=C.molecule_id(source),manifest_reference={'path':'manifest'},
                cache_reference={'path':'cache'},packet_reference={'path':'packet'},events_reference={'path':'events'})
            before=C.canonical([args,saved])
            item=M.extract(source,manifest,cache,packet,events if journal is None else journal,saved)
            wrapped=dict(saved,**{M.METADATA_KEY:item})
            self.assertEqual(M.evidence(wrapped),saved)
            self.assertEqual(before,C.canonical([args,saved]))
            aggregate.append(item)
            return item
        def timing(op,identifier,wall,cpu,returned=True,error=None):
            return dict(operation=op,identifier=identifier,wall_nanoseconds=wall,process_CPU_nanoseconds=cpu,
                returned=returned,error_type=error)
        args=list(fixture(3));source,cache,packet,manifest,events=args
        cache['optimizer_calls']=30;cache['embedded_candidate_ids']=list(range(30))
        cache['attempts']=[dict(candidate_id=i,status='SUCCESS'if i<3 else'NATIVE_REJECTED',
            candidate=dict(optimizer_code=0 if i<3 else 1,stereo_valid=True))for i in range(30)]
        cache.pop('cache_content_sha256');cache['cache_content_sha256']=C.sha(C.canonical(cache))
        packet['candidate_cache_sha256']=cache['cache_content_sha256']
        packet.pop('packet_content_sha256');packet['packet_content_sha256']=C.sha(C.canonical(packet))
        manifest.update(producer_job_id='new',worker_wall_seconds=2.5,worker_CPU_seconds=1.25,native_generation_wall_seconds=1.)
        events[:]=[dict(phase='molecule_intent'),dict(phase='graph_return',native_call_timing=timing('prepare',None,100,50)),
            dict(phase='embedding_intent'),dict(phase='embedding_return',native_call_timing=timing('embed',None,200,80))]
        for i in range(30):
            events.extend([dict(phase='optimizer_intent',candidate_id=i),
                dict(phase='optimizer_return',candidate_id=i,native_call_timing=timing('optimize',i,10,3))])
        for i in range(3):
            events.extend([dict(phase='descriptor_intent',conformer_id=i),dict(phase='descriptor_return',
                conformer={'conformer_id':i},native_call_timing=timing('d3',i,2,1))])
        events.append(dict(phase='packet_closed',packet=copy.deepcopy(packet)))
        full=append(args)
        self.assertEqual(full['row']['embedded_candidates_recorded'],30)
        self.assertEqual(full['row']['actual_conformers'],3)
        self.assertEqual(len(full['calls']),35)
        sparse=append(fixture(2));self.assertEqual(sparse['row']['record_classes'],['KNOWN_SPARSE_POSITIVE_DELIVERY_NOT_FAILURE'])
        legacy_args=list(fixture(1));legacy_args[3].update(producer_job_id='legacy',closed_cache_reused_without_UFF=True)
        legacy_args[4][:]=[dict(phase='closed_cache_adopted_without_native_calls'),dict(phase='descriptor_intent',conformer_id=0),
            dict(phase='descriptor_return',conformer={'conformer_id':0}),dict(phase='packet_closed',packet=copy.deepcopy(legacy_args[2]))]
        legacy=append(legacy_args)
        self.assertEqual(legacy['calls'],[]);self.assertIsNone(legacy['row']['legacy_clock_seconds']['worker_wall_seconds'])
        zero_args=list(fixture(0,True))
        zero_args[4][:]=[dict(phase='molecule_intent'),dict(phase='cache_closed',native_call_timings_without_matching_return=[
            timing('prepare',None,7,3,False,'ValueError')]),dict(phase='packet_closed',packet=copy.deepcopy(zero_args[2]))]
        zero=append(zero_args)
        self.assertEqual(zero['row']['delivery_bin'],'0');self.assertIn('OBSERVED_NATIVE_CALL_EXCEPTION',zero['row']['record_classes'])
        source=fixture()[0];manifest=dict(schema='PUBCHEM_UFF3_INTERRUPTED_MOLECULE_V1',source=source,
            source_identity_sha256=C.source_identity(source),state='INTERRUPTED_NO_AUTOMATIC_SCIENCE_RETRY')
        saved=dict(V.interrupted(source,manifest),molecule_id=C.molecule_id(source))
        unknown=M.extract(source,manifest,None,None,None,saved);aggregate.append(unknown)
        self.assertIsNone(unknown['row']['actual_conformers']);self.assertEqual(unknown['row']['physical_delivered_rows'],0)
        total=next(row for row in aggregate.summaries()if row['group_type']=='all')
        self.assertEqual(total['delivery_molecules'],{'0':1,'1':1,'2':1,'3':1,'UNKNOWN':1})
        self.assertEqual(total['known_actual_conformer_denominator'],6)
        self.assertEqual(total['native_call_timings']['optimize']['wall_nanoseconds'],300)
        self.assertEqual(total['native_call_timings']['optimize']['process_CPU_nanoseconds'],90)
        self.assertEqual(total['native_call_timings']['prepare']['raised_calls'],1)
        old=next(row for row in aggregate.summaries()if row['group_type']=='producer_job'and row['producer_job_id']=='legacy')
        self.assertIsNone(old['native_call_timings']['prepare']['wall_nanoseconds'])
        self.assertIsNone(old['stored_worker_or_generation_clocks']['worker_wall_seconds']['total_seconds_decimal'])


if __name__=='__main__':unittest.main()
