"""One toy metadata/controller fixture; no subprocess, Slurm or real signals."""
import copy,unittest
from . import lustre_non_native_writer_guard as G

class LustreWriterGuard(unittest.TestCase):
    def test_strict_quota_fresh_targets_exact_jobs_and_safe_exit(self):
        text='Disk quotas for usr zixiao (uid 1278):\nFilesystem kbytes quota limit grace files quota limit grace\n/lfshome 1098705652 0 2147483648 - 38481903 0 0 -\nuid 1278 is using default file quota setting\n'
        quota=G.parse_quota(text);self.assertEqual(quota['available_bytes'],(2147483648-1098705652)*1024)
        for bad in (text.replace('uid 1278','uid 1'),text.replace('/lfshome','/other'),text.replace('2147483648','0')):
            with self.assertRaises(G.Unsafe):G.parse_quota(bad)
        mount={'target':'/lfshome','source':'toy@net:/fs','fstype':'lustre'}
        target={'path':'/lfshome/toy','mount':mount,'reserve_bytes':0,'reserve_inodes':100,'concurrent_bytes':0,'concurrent_inodes':0}
        profile={'jobs':copy.deepcopy(G.JOBS),'quota_reference':'quota','quota_reserve_bytes':100_000_000_000,'runtime_margin_bytes':8*(1<<30),'runtime_margin_inodes':100,'max_age_seconds':5,
            'nodes':{node:{'reference':node,'targets':[copy.deepcopy(target)]} for node in ('compute-0-19','compute-0-20')}}
        G.validate_profile(profile)
        values={'quota':{'schema':'LUSTRE_USER_QUOTA_AVAILABLE_V1','uid':1278,'filesystem':'/lfshome','observed_time':1000,**quota}}
        for node in profile['nodes']:
            values[node]=G.capacity(profile,node,lambda path:{'mount':mount,'total':10**15,'available':10**14,'inodes':10**8,'root_filesystem':False},1000)
        job=G.JOBS['4526117'];reader=lambda key:values[key]
        self.assertTrue(G.safe(profile,job,reader,1005)[0]);self.assertFalse(G.safe(profile,job,reader,1005.01)[0]);self.assertFalse(G.safe(profile,job,reader,999)[0])
        for key,changed in (('uid',1),('node','compute-0-19')):
            old=values[job['node']][key];values[job['node']][key]=changed
            self.assertFalse(G.safe(profile,job,reader,1001)[0]);values[job['node']][key]=old
        old=values[job['node']]['targets'][0]['inodes'];values[job['node']]['targets'][0]['inodes']=0
        self.assertFalse(G.safe(profile,job,reader,1001)[0]);values[job['node']]['targets'][0]['inodes']=old
        def lookup(key):
            value=G.JOBS[key];return {'JobId':key,'JobName':value['name'],'UserId':'zixiao(1278)','StartTime':value['start_time'],'NodeList':value['node'],'JobState':'RUNNING'}
        signals=[];saved=[];health=[False,'TOY_CAPACITY_UNKNOWN']
        state={'schema':'TWO_NON_NATIVE_WRITER_RECOVERY_V1','uid':1278,'jobs':copy.deepcopy(G.JOBS),'parked':{}}
        control=G.Controller(profile,state,lambda value:saved.append(copy.deepcopy(value)),lookup,lambda job,name:signals.append((job['job_id'],name)),lambda job:tuple(health))
        self.assertEqual(control.tick(),[]);self.assertEqual(signals,[('4526117','STOP'),('4526127','STOP')])
        self.assertTrue(all(value['status']=='STOP_ACKNOWLEDGED' for value in state['parked'].values()))
        report=control.finish();self.assertEqual(len(report['parked_or_uncertain']),2);self.assertEqual(len(signals),2)
        health[:]=[True,'FRESH_SAFE'];report=control.finish();self.assertEqual(report['parked_or_uncertain'],{})
        self.assertEqual(signals[-2:],[('4526117','CONT'),('4526127','CONT')])
        signals.clear();control.finish();self.assertEqual(signals,[]) # never CONT jobs it did not park
        health[:]=[False,'STALE'];control.tick();signals.clear()
        calls={key:0 for key in G.JOBS}
        def expires(job):
            key=job['job_id'];calls[key]+=1;return (calls[key]==1,'BECAME_STALE_BEFORE_CONT')
        control.evaluate=expires;self.assertEqual(len(control.finish()['parked_or_uncertain']),2);self.assertEqual(signals,[])
        wrong=lookup('4526117');wrong['JobId']='4526126'
        control.lookup=lambda key:wrong
        self.assertTrue(control.tick());self.assertEqual(signals,[])
        bad=copy.deepcopy(profile);bad['jobs']['4526126']=copy.deepcopy(job)
        with self.assertRaises(G.Unsafe):G.validate_profile(bad)
    def test_only_own_acknowledged_stopped_transitions_to_cont(self):
        mount={'target':'/lfshome','source':'toy@net:/fs','fstype':'lustre'}
        target={'path':'/lfshome/toy','mount':mount,'reserve_bytes':0,'reserve_inodes':100,'concurrent_bytes':0,'concurrent_inodes':0}
        profile={'jobs':copy.deepcopy(G.JOBS),'quota_reference':'quota','quota_reserve_bytes':100_000_000_000,'runtime_margin_bytes':8*(1<<30),'runtime_margin_inodes':100,'max_age_seconds':5,
            'nodes':{node:{'reference':node,'targets':[copy.deepcopy(target)]} for node in ('compute-0-19','compute-0-20')}}
        for ownership,status,safe in (('STOP_ACKNOWLEDGED','STOPPED',True),('STOP_ACKNOWLEDGED','STOPPED',False),('STOP_REQUESTED','STOPPED',True),(None,'STOPPED',True),('STOP_ACKNOWLEDGED','SUSPENDED',True)):
            signals=[];state={'schema':'TWO_NON_NATIVE_WRITER_RECOVERY_V1','uid':1278,'jobs':copy.deepcopy(G.JOBS),'parked':{}}
            if ownership:state['parked']['4526127']={'job':copy.deepcopy(G.JOBS['4526127']),'status':ownership}
            def lookup(key):
                job=G.JOBS[key]
                return {'JobId':key,'JobName':job['name'],'UserId':'zixiao(1278)','StartTime':job['start_time'],'NodeList':job['node'],'JobState':status if key=='4526127' else 'COMPLETED'}
            control=G.Controller(profile,state,lambda value:None,lookup,lambda job,name:signals.append((job['job_id'],name)),lambda job:(safe,'FRESH_SAFE' if safe else 'STALE'))
            report=control.finish();self.assertEqual(report['errors'],[])
            expected=[('4526127','CONT')] if ownership=='STOP_ACKNOWLEDGED' and status=='STOPPED' and safe else []
            self.assertEqual(signals,expected)
            if expected:self.assertNotIn('4526127',state['parked'])
            elif ownership:self.assertIn('4526127',report['parked_or_uncertain'])