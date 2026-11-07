"""Dedicated mutable SQL scope; includes SQLite, DuckDB WAL and dynamic spill."""
import threading
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.guard import Guard


class QualityBudget:
    def __init__(self,plan,root):
        self.root=Path(root);self.plan=plan;self.done=threading.Event();self.thread=None
        Q.need(self.root==Path(plan['output_scope_root']),'QA dynamic SQL accounting must cover its entire private scope')
        self.guard=Guard(plan,prequery_credit_provider=lambda cutoff:0)
        self.latest=self.guard.receipt()

    def register(self,path):
        path=Path(path)
        Q.need(path==self.root or self.root in path.parents,'Only actual private SQL output')
        self.check()

    def check(self,force=False):
        if force:self.guard.sample()
        self.guard.check();self.latest=self.guard.receipt()
        return self.latest

    def start(self,db):
        def observe():
            while not self.done.wait(1):
                try:self.guard.check()
                except BaseException:db.interrupt();return
        self.thread=threading.Thread(target=observe,daemon=True);self.thread.start()

    def configure(self,db,literal):
        p=self.plan
        Q.need(type(p['sql_memory_bytes'])is int and 0<p['sql_memory_bytes']<p['software_rss_budget_bytes']
            and type(p['spill_cap_bytes'])is int and 0<p['spill_cap_bytes']<p['output_cap_bytes'],
            'Finite actual private QA SQL memory/spill within reviewed budgets')
        db.execute('SET memory_limit='+literal(str(p['sql_memory_bytes'])+'B'))
        db.execute('SET max_temp_directory_size='+literal(str(p['spill_cap_bytes'])+'B'))
        self.start(db)

    def stop_sql_monitor(self):
        self.done.set()
        if self.thread:self.thread.join()

    def close(self):
        self.stop_sql_monitor()
        try:self.check(True)
        finally:self.guard.close()