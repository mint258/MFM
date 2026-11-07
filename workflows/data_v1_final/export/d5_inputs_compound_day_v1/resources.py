"""Finite current-account resource checks and one parent-owned derived DATA ledger."""
from __future__ import annotations
import hashlib,json,os,pathlib,sqlite3,stat,threading,time
from workflows.data_v1_final.export.d5_materialize_cpu_v1 import resources as Original
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as OBS
from workflows.data_v1_final.labels.normalization_compact_runtime_v2.runtime import wall_clock,remaining_wall
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import quota_provider as Provider
from . import contract as C
frame=Original.frame;literal=Original.literal;RESERVE=16<<30


class Authority:
    """CPU-created refs are transitive DATA, never fabricated small/C0 parents."""
    def __init__(self,path,initial):
        self.db=sqlite3.connect(path);self.db.execute('CREATE TABLE refs(path TEXT PRIMARY KEY,bytes INTEGER,sha TEXT)')
        for r in initial:self.add(r)
    def add(self,r):
        r=C.reference(r);prior=self.db.execute('SELECT bytes,sha FROM refs WHERE path=?',(r['path'],)).fetchone()
        C.need(prior is None or prior==(r['bytes'],r['sha256']),'NO_CONFLICTING_CURRENT_PARENT_DERIVED_DATA_REFERENCE')
        self.db.execute('INSERT OR IGNORE INTO refs VALUES(?,?,?)',(r['path'],r['bytes'],r['sha256']));self.db.commit();return r
    def __contains__(self,r):
        r=C.reference(r);return self.db.execute('SELECT bytes,sha FROM refs WHERE path=?',(r['path'],)).fetchone()==(r['bytes'],r['sha256'])
    def __iter__(self):
        for p,n,h in self.db.execute('SELECT path,bytes,sha FROM refs ORDER BY path'):yield {'path':p,'bytes':n,'sha256':h}
    def close(self):self.db.close()


class Budget:
    def __init__(self,plan,proof,out):
        self.plan,self.proof,self.out=plan,proof,pathlib.Path(out);self.clock=wall_clock(proof,86400)
        C.Q.write_new(self.out/'wall_clock.json',self.clock);self.retired={};self.lock=threading.RLock()
        self.done=threading.Event();self.thread=None;self.ledger_reference=None;self.last_poll=0;self.last_quota=None;self.observations=0;self.maximum=0
        review=C.meta(plan['root_carveout_review_reference']);self.other=review['total_future_reserved_bytes']-plan['output_cap_bytes'];self.identity=plan['quota_provider_identity_reference']
        C.need(review['parent_output_cap_bytes']>=plan['output_cap_bytes'] and self.other>=0,'ROOT_CURRENT_FUTURE_INCLUDES_PARENT_ONCE')
        self.client=Provider.Client(plan['quota_provider_review_reference'],proof['request']);self.active=self.out
        self.control={'root':str(out),'cap':plan['output_cap_bytes'],'reserve':RESERVE};self.next_poll=0
        self.check(force=True);self.thread=threading.Thread(target=self.poll,daemon=True,name='d5-one-day-quota');self.thread.start()
    def usage(self):
        for attempt in range(3):
            try:return self._usage_once()
            except FileNotFoundError:
                if attempt==2:raise
                time.sleep(0.01)
        raise ValueError('COMPLETE_RESOURCE_INVENTORY_REQUIRED')
    def _usage_once(self):
        # Retired immutable directories are counted once. Active SQLite/open FDs
        # retain the original inode-deduplicating used() implementation.
        total=sum(x['bytes'] for x in self.retired.values())
        def walk(root):
            if str(root) in self.retired:return 0
            children=list(root.iterdir());amount=0
            for p in children:
                s=p.lstat();C.need(s.st_uid==1278 and not stat.S_ISLNK(s.st_mode),'OWN_NEW_OUTPUT_NO_LINKS')
                if stat.S_ISDIR(s.st_mode):
                    if str(p) not in self.retired:amount+=walk(p)
                elif stat.S_ISREG(s.st_mode):amount+=s.st_size
            return amount
        total+=walk(self.out)
        # Include unlinked/open active SQL files using the unchanged original
        # routine. Replacing visible active bytes also preserves inode dedup.
        if self.active!=self.out:
            total+=max(0,Original.used(self.active)-sum(s.st_size for p in self.active.rglob('*') if stat.S_ISREG((s:=p.lstat()).st_mode)))
        return total
    def set_active(self,path):
        with self.lock:
            self.active=pathlib.Path(path);self.active.mkdir(parents=True,exist_ok=False)
            self.control={'root':str(self.active),'cap':max(0,self.plan['output_cap_bytes']-self.usage()),'reserve':RESERVE}
    def retire(self,path):
        with self.lock:
            p=pathlib.Path(path);C.need(p!=self.out and p.is_relative_to(self.out) and str(p) not in self.retired,'RETIRE_NEW_IMMUTABLE_SUBTREE_ONCE')
            self.retired[str(p)]={'bytes':Original.used(p),'frame':list(frame(p.lstat()))}
    def check(self,*,force=False,dispatch=True):
        with self.lock:
            OBS.soft_worker_rss(3<<30)
            if remaining_wall(self.clock,time.monotonic())<=900:OBS.mark_stop('D5_DAY_SOFT_WALL_NO_NEW_DATA_WORK',{'drain_seconds':900})
            if force or time.monotonic()>=self.next_poll:
                self.next_poll=time.monotonic()+1;used=self.usage();self.maximum=max(self.maximum,used)
                C.need(used+RESERVE<self.plan['output_cap_bytes'],'WHOLE_PARENT_CAP_PLUS16G_DRAIN')
            if force or time.monotonic()-self.last_poll>=60:
                self.last_poll=time.monotonic()
                try:
                    v=self.client.observe();self.last_quota=v;self.observations+=1
                    C.need(v['identity_reference']==self.identity==self.client.identity,'EXACT_FINITE_PROVIDER_IDENTITY_NEVER_SWITCHED')
                    remaining=max(0,self.plan['output_cap_bytes']-self.usage())
                    C.need(v['free_bytes']-self.other-remaining>=200000000000,'REAL_ACCOUNT_OTHER_PLUS_OWN_REMAINING_PLUS200GB')
                    s=os.statvfs(C.ROOT);C.need(s.f_bavail*s.f_frsize-self.other-remaining>=200000000000,'REAL_SHARED_DISK_OTHER_PLUS_OWN_PLUS200GB')
                except BaseException as e:
                    OBS.mark_stop('D5_CURRENT_ACCOUNT_UNKNOWN_OR_EXPIRED',{'error_type':type(e).__name__,'error':str(e),'actual_Client_last_attempt':self.client.last});raise
            if dispatch:C.need(not OBS.stop_requested(),'D5_STOP_NEW_WORK_NATURAL_DRAIN_NO_SIGNAL')
    def poll(self):
        while not self.done.wait(60):
            try:self.check(force=True,dispatch=False)
            except BaseException as e:OBS.mark_stop('D5_BACKGROUND_RESOURCE_STOP',{'type':type(e).__name__,'error':str(e)});return
    def finish(self):
        self.done.set()
        if self.thread is not None:self.thread.join(timeout=60)
        C.need(self.thread is None or not self.thread.is_alive(),'CLOSE_FINITE_RESOURCE_MONITOR_WITHOUT_SIGNAL')
        if self.retired:
            from workflows.data_v1_final.export.d5_inputs_builder_v1.io import actual_ref
            p=self.out/'retired_directories.DATA.jsonl'
            with p.open('xb') as f:
                for path,value in sorted(self.retired.items()):f.write((json.dumps({'path':path,**value},sort_keys=True,separators=(',',':'))+'\n').encode())
                f.flush();os.fsync(f.fileno())
            self.ledger_reference=actual_ref(p)
    def legacy_quota(self,out):
        self.check(force=True);v=self.last_quota;C.need(v is not None,'ACTUAL_QUOTA_OBSERVATION_REQUIRED')
        r=C.Q.write_new(pathlib.Path(out)/'actual_legacy_quota.json',{'status':'QUOTA_METADATA_VERIFIED',
            'observed_at_epoch':v['observed_unix_seconds'],'available_bytes':v['free_bytes'],'basis':'ACTUAL_FINITE25H_CLIENT',
            'original_observation':v,'provider_renewed':False})
        return {'quota_receipt':r,'total_declared_new_bytes':self.other+max(0,self.plan['output_cap_bytes']-self.usage())}
    def receipt(self):
        return {'other_future_reserved_bytes':self.other,'whole_parent_bytes':self.usage(),'maximum_observed_bytes':self.maximum,
            'retired_immutable_directories_count':len(self.retired),'retired_directory_ledger_DATA_reference':self.ledger_reference,
            'retired_examples':list(self.retired.items())[:8],'retired_examples_truncated':len(self.retired)>8,'last_actual_quota':self.last_quota,'last_actual_Client_attempt':self.client.last,'quota_observations':self.observations,
            'wall_clock':self.clock,'publisher_renewed':False,'forced_signals_sent':False,'effective_drain_bytes':RESERVE}
