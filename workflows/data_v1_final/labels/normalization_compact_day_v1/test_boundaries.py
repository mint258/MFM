"""Three day-only boundaries: original partitions, route gate and large DATA IO."""
import hashlib,os,tempfile,unittest
from pathlib import Path
from . import contract as C,io as I,source_inverse as F

class Boundaries(unittest.TestCase):
    def test_full_prefix_inverse_original171_order_and_committed_cursors(self):
        F.proof()
        groups=[{'group_index':i,'source_job_id':str(i),'label_files':[]} for i in range(171)];C.exact_logical_groups(groups)
        with self.assertRaises(ValueError):C.exact_logical_groups(list(reversed(groups)))
        sources=[{'file_id':0,'rows':20},{'file_id':1,'rows':5}]
        w=[{'file_id':0,'lo':4,'hi':20,'all_part_reopen_bits_verified':True},{'file_id':1,'lo':0,'hi':5,'all_part_reopen_bits_verified':True}]
        self.assertEqual(C.advance(sources,{'0':4},w),{'0':20,'1':5})
        with self.assertRaises(ValueError):C.advance(sources,{'0':4},[dict(w[0],lo=5)])
        with self.assertRaises(ValueError):C.advance(sources,{'0':4},[dict(w[0],all_part_reopen_bits_verified=False)])
        from .prior_hash_stage import layout
        root='/synthetic/actual_hash_stage'
        rows=[{'path':root+'/hash_chunks/hash_chunk_0000.json','bytes':9,'uid':1278,'nlink':1,'mode':33188,'inode':1,'mtime_ns':2,'ctime_ns':3},
              {'path':root+'/verified_files.sqlite','bytes':7,'uid':1278,'nlink':1,'mode':33188,'inode':4,'mtime_ns':5,'ctime_ns':6}]
        inventory={'stage_root':root,'files':rows,'file_count':2,'total_bytes':16}
        self.assertEqual(len(layout(inventory,1)),2)
        with self.assertRaises(ValueError):layout(dict(inventory,files=rows[:1]),1)
        with self.assertRaises(ValueError):layout(dict(inventory,files=[rows[0],rows[0]]),1)

    def test_phase_never_advances_without_exact_original_numeric_output(self):
        from .run import next_route
        from . import project
        from workflows.data_v1_final.labels.normalization_compact_runtime_v3.bindings import quality_stop_fields
        self.assertIs(project.quality_stop_fields,quality_stop_fields)
        self.assertEqual(project.quality_stop_fields({'0':{'newly_masked_records':1}},100,.01),[])
        self.assertEqual(project.quality_stop_fields({'0':{'newly_masked_records':2}},100,.01),['0'])
        with self.assertRaises(ValueError):C.plan({'execution_mode':'FINAL_COMMON_STATS'})
        query={'path':'/synthetic/query.json','bytes':1,'sha256':'a'*64}
        self.assertEqual(next_route(1,{'statistics_purpose':'normalization_quantiles','next_query_stage':query}),(1,query))
        with self.assertRaises(ValueError):next_route(1,{'statistics_purpose':'normalization_quantiles','next_query_stage':None,'exact_tail_reference':None})
        self.assertEqual(next_route(1,{'statistics_purpose':'normalization_quantiles','next_query_stage':None,'exact_tail_reference':query}),(2,None))
        with self.assertRaises(ValueError):next_route(0,{'statistics_purpose':'normalization_moments','next_query_stage':None})
        C.reference({'path':'/synthetic/large.parquet','bytes':512<<20,'sha256':'a'*64})
        for n in (True,0,-1):
            with self.assertRaises(ValueError):C.reference({'path':'/synthetic/large.parquet','bytes':n,'sha256':'a'*64})
        from workflows.data_v1_final.execution import finite_quota_observation_guard_v1 as G
        expected={'path':'/synthetic/identity.json','bytes':1,'sha256':'a'*64}
        class Clock:
            def __init__(self):self.wall=100.;self.mono=1000.;self.waits=[];self.extra=0.
            def wait(self,n):self.waits.append(n);self.wall+=n+self.extra;self.mono+=n+self.extra
        class Client:
            def __init__(self,clock,delta,*,expired=False,wrong=False,status='RUNNING',other=False,second=False):
                self.clock=clock;self.calls=0;self.identity=None;self.second=second;self.other=other
                self.last={'identity_reference':dict(expected,sha256='b'*64) if wrong else expected,
                  'snapshot_reference':{'path':'/synthetic/observation_000001.json','bytes':1,'sha256':'c'*64},
                  'provider_status':status,'observed_unix_seconds':100.+delta,'publisher_expires_unix_seconds':100. if expired else 1000.}
            def observe(self):
                self.calls+=1
                if self.calls==1:raise ValueError('OTHER_FAILURE' if self.other else G.TIME_ERROR)
                if self.second:raise ValueError(G.TIME_ERROR)
                self.identity=expected;return self.last
        for delta in (.25,-.25):
            clock=Clock();client=Client(clock,delta);events=[]
            self.assertIs(G.observe(client,expected_identity_reference=expected,record=events.append,
              wall_clock=lambda:clock.wall,monotonic=lambda:clock.mono,wait=clock.wait),client.last)
            self.assertEqual(client.calls,2);self.assertEqual(sum(clock.waits),max(delta,0))
            self.assertEqual(events[-1]['phase'],'SECOND_ORIGINAL_CLIENT_ACCEPTED')
        for delta,kw in ((-121.,{}),(.2,{'expired':True}),(.2,{'wrong':True}),(.2,{'status':'ERROR'}),(.2,{'other':True})):
            clock=Clock();client=Client(clock,delta,**kw)
            with self.assertRaises(ValueError):G.observe(client,expected_identity_reference=expected,record=lambda v:None,
              wall_clock=lambda:clock.wall,monotonic=lambda:clock.mono,wait=clock.wait)
            self.assertEqual(client.calls,1);self.assertEqual(clock.waits,[])
        clock=Clock();client=Client(clock,.2,second=True);events=[]
        with self.assertRaises(ValueError):G.observe(client,expected_identity_reference=expected,record=events.append,
          wall_clock=lambda:clock.wall,monotonic=lambda:clock.mono,wait=clock.wait)
        self.assertEqual(client.calls,2);self.assertEqual(events[-1]['phase'],'SECOND_ORIGINAL_CLIENT_FAILED_STOP')
        clock=Clock();clock.extra=1.2;client=Client(clock,.2)
        with self.assertRaises(ValueError):G.observe(client,expected_identity_reference=expected,record=lambda v:None,
          wall_clock=lambda:clock.wall,monotonic=lambda:clock.mono,wait=clock.wait)
        self.assertEqual(client.calls,1)
        clock=Clock();client=Client(clock,.2)
        def bad_record(event):raise OSError('SYNTHETIC_RESOURCE_RECORDER_FAILED')
        with self.assertRaises(OSError):G.observe(client,expected_identity_reference=expected,record=bad_record,
          wall_clock=lambda:clock.wall,monotonic=lambda:clock.mono,wait=clock.wait)
        self.assertEqual(client.calls,1)

    def test_cpu_three_mib_whole_fd_sha_and_no_symlink_or_mutation(self):
        from .recovery import safe_old
        with tempfile.TemporaryDirectory(prefix='compact_day_pure_',dir='/tmp') as tmp:
            p=Path(tmp)/'synthetic.bin';p.write_bytes(b'a'*(3<<20));ref=I.pin(p)
            self.assertEqual(I.require(ref),p)
            s=p.stat();expected={'uid':s.st_uid,'nlink':1,'inode':s.st_ino,'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,
              'ctime_ns':s.st_ctime_ns,'dev_on_observation_host_only':-999}
            self.assertEqual(safe_old(str(p),expected,Path(tmp))[0],p)
            from .prior_hash_stage import inherit_entry
            row={'reference':ref,'current_CPU_frame':[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]}
            q,frame=inherit_entry(row,dict(expected,path=str(p)),Path(tmp),'compute-0-18','compute-0-18')
            self.assertEqual(q,ref);self.assertEqual(frame,row['current_CPU_frame'])
            from types import SimpleNamespace
            recorder=SimpleNamespace(root=Path(tmp),quota_events=0)
            event={'schema':'FINITE_QUOTA_NEAR_CLOCK_REREAD_EVENT_V1','phase':'SYNTHETIC_DURABLE_BOUNDARY'}
            I.Budget.record_quota_event(recorder,event)
            receipt=Path(tmp)/'quota_resource_events/event_000001.json'
            self.assertEqual(I.load(I.require(I.pin(receipt))),event)
            with self.assertRaises(OSError):I.Budget.record_quota_event(SimpleNamespace(root=p,quota_events=0),event)
            with self.assertRaises(ValueError):inherit_entry(dict(row,current_CPU_frame=[s.st_dev,s.st_ino,s.st_size+1,s.st_mtime_ns,s.st_ctime_ns]),
              dict(expected,path=str(p)),Path(tmp),'compute-0-18','compute-0-18')
            with self.assertRaises(ValueError):safe_old(str(p),dict(expected,bytes=s.st_size+1),Path(tmp))
            with p.open('r+b') as f:f.write(b'b')
            with self.assertRaises(ValueError):I.require(ref)
            alias=Path(tmp)/'link.bin';alias.symlink_to(p)
            with self.assertRaises(ValueError):I.require(dict(I.pin(p),path=str(alias)))
if __name__=='__main__':unittest.main()
