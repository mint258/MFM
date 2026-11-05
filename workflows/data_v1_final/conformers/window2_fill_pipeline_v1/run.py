"""Pipeline closed D7 parts through one unchanged per-molecule fill pool."""
from __future__ import annotations
import argparse
import collections
import concurrent.futures as cf
import json
import multiprocessing as mp
import os
from pathlib import Path
import time
from workflows.data_v1_final.conformers.window2_population_v1 import fill as original
from workflows.data_v1_final.conformers.window2_fill_runtime_v1.run import already_complete
from workflows.data_v1_final.conformers.window2_fill_loader_v1.run import tasks
from workflows.data_v1_final.conformers.window2_d7_runtime_v1.run import prepare
from workflows.data_v1_final.conformers.window2_source_cache_v1.keep_source_map import install_native_reader


def initialize(science_path):
    original.d7.initialize(science_path)
    install_native_reader(original.d7,os.environ.get('DATA_V1_COMPLETED_SOURCE_CACHE_PLAN'))


def commit_part(out,ordinal,values,parts,checkpoint):
    """Original complete-part data writes and atomic checkpoint publication."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    newrows=[row for value in values for row in value.pop('new_conformers')]
    path=out/('states-%06d.parquet'%ordinal)
    pq.write_table(pa.Table.from_pylist(values),path,compression='zstd')
    record={'part':ordinal,'states':original.info(path,len(values)),'new_geometry':None}
    if newrows:
        geom=out/('geometry-%06d.parquet'%ordinal)
        pq.write_table(pa.Table.from_pylist(newrows),geom,compression='zstd')
        record['new_geometry']=original.info(geom,len(newrows))
    parts.append(record);parts.sort(key=lambda row:row['part'])
    temporary=out/'checkpoint.next.json'
    temporary.write_text(json.dumps({'parts':parts}),encoding='utf-8');os.replace(temporary,checkpoint)
    print(json.dumps({'stage':'Sprime_N_no_new','closed_parts':len(parts),
        'molecules':sum(row['states']['records'] for row in parts),'new_conformers':len(newrows)}),flush=True)
    return record


class PartQueue:
    """Bound submitted work, not science scope; retain only unclosed part results."""
    def __init__(self,pool,db,bounds,commit,finished,capacity,task_loader=None,worker=None):
        self.pool=pool;self.db=db;self.bounds=bounds;self.commit=commit
        self.finished=set(finished);self.capacity=capacity
        self.task_loader=tasks if task_loader is None else task_loader
        self.worker=original.safe_fill if worker is None else worker
        self.active={};self.waiting=collections.deque();self.pending={}

    def contains(self,ordinal):return ordinal in self.finished or ordinal in self.active

    def add(self,ordinal,metas,statistics):
        if self.contains(ordinal):return False
        byid={row['molecule_id']:row for row in statistics};values={};remaining=[]
        for meta in metas:
            mid=meta['molecule_id'];stats=byid[mid]
            if already_complete(meta,stats):
                values[mid]=self.worker({'meta':meta,'d7':stats,'records':[],'uff':[],
                    'max_original_attempt_idx':self.bounds.get(mid,-1)})
            else:remaining.append(meta)
        jobs=self.task_loader(self.db,remaining) if remaining else []
        self.active[ordinal]={'metas':metas,'values':values,'remaining':len(jobs)}
        for job in jobs:
            mid=job['meta']['molecule_id'];job['d7']=byid[mid]
            job['max_original_attempt_idx']=self.bounds.get(mid,-1)
            self.waiting.append((ordinal,job))
        if not jobs:self._commit(ordinal)
        return True

    def _commit(self,ordinal):
        state=self.active[ordinal]
        values=[state['values'][meta['molecule_id']] for meta in state['metas']]
        self.commit(ordinal,values)
        # Only after durable complete-part publication is the ordinal finished.
        self.finished.add(ordinal);del self.active[ordinal]

    def submit_waiting(self):
        while self.waiting and len(self.pending)<self.capacity:
            ordinal,job=self.waiting.popleft()
            future=self.pool.submit(self.worker,job)
            self.pending[future]=(ordinal,job['meta']['molecule_id'])

    def collect(self,done):
        for future in done:
            ordinal,mid=self.pending.pop(future)
            value=future.result()  # A failed/unreturned task cannot close its part.
            state=self.active[ordinal];state['values'][mid]=value;state['remaining']-=1
            if state['remaining']==0:self._commit(ordinal)


def run(plan):
    import pyarrow as pa
    import pyarrow.parquet as pq
    out=Path(plan['output']);out.mkdir(parents=True,exist_ok=True)
    d7plan=original.read(plan['d7_plan'])
    d7plan.update(workspace=plan['workspace'],output=plan['output'],workers=plan['workers'])
    # Existing tested operational wrapper ignores only worker count on resume.
    db,common=prepare(d7plan,plan['workspace'])
    checkpoint=out/'checkpoint.json'
    done=original.read(checkpoint) if checkpoint.exists() else {'parts':[]}
    parts=sorted(done['parts'],key=lambda row:row['part'])
    finished={row['part'] for row in parts}
    d7root=Path(original.read(plan['d7_plan'])['output'])
    bounds=dict(db.execute('SELECT molecule_id,max(sprime_conf_idx) FROM baseline GROUP BY molecule_id').fetchall())
    unloaded=collections.deque();known=set(finished);source_closed=False
    def refresh_sources():
        nonlocal source_closed
        # D7 writes its checkpoint before its manifest; observe closed first.
        source_closed=(d7root/'manifest.json').exists()
        available=original.read(d7root/'checkpoint.json')['parts'] if (d7root/'checkpoint.json').exists() else []
        for reference in available:
            if reference['part'] not in known:
                known.add(reference['part']);unloaded.append(reference)
    refresh_sources()
    def publish(ordinal,values):commit_part(out,ordinal,values,parts,checkpoint)
    with cf.ProcessPoolExecutor(max_workers=plan['workers'],mp_context=mp.get_context('spawn'),
        initializer=initialize,initargs=(d7plan['science_path'],)) as pool:
        queue=PartQueue(pool,db,bounds,publish,finished,capacity=4*plan['workers'])
        while True:
            queue.collect([future for future in queue.pending if future.done()])
            queue.submit_waiting()
            refreshed=False
            # At most one part's unsent full F64 jobs are materialized at once.
            # Load another part whenever submitted slots remain, even if an
            # earlier part still has a long-running molecule.
            while not queue.waiting and len(queue.pending)<queue.capacity:
                if not unloaded:
                    if source_closed or refreshed:break
                    refresh_sources();refreshed=True
                    if not unloaded:break
                reference=unloaded.popleft();ordinal=reference['part']
                if queue.contains(ordinal):continue
                statistics=pq.read_table(reference['path']).to_pylist()
                mids=[row['molecule_id'] for row in statistics]
                db.register('batch',pa.table({'molecule_id':mids}))
                metas=db.execute('SELECT m.* FROM members m JOIN batch USING(molecule_id)').fetch_arrow_table().to_pylist()
                db.unregister('batch')
                queue.add(ordinal,metas,statistics);queue.submit_waiting()
            if source_closed and not unloaded and not queue.active:break
            if queue.pending:
                completed,_=cf.wait(tuple(queue.pending),timeout=30,return_when=cf.FIRST_COMPLETED)
                queue.collect(completed)
            else:time.sleep(30)
    db.close()
    counts=collections.Counter();total=0
    for part in parts:
        for row in pq.read_table(part['states']['path'],columns=['status']).column('status').to_pylist():counts[row]+=1;total+=1
    original.save(out/'manifest.json',{'schema':'SPRIME_N_NO_NEW_FINAL_V1','status':'COMPLETE' if not counts['EXECUTION_UNRESOLVED'] else 'PARTIAL_WITH_EXPLICIT_UNRESOLVED',
        'parts':parts,'molecules':total,'status_counts':dict(counts),'input_common':plan['common'],
        'preserve_source_atom_order':True,'stop_rule':'N consecutive candidates with no new >=0.5A conformer',
        'force_duplicate_fill':False,'content_hashes_computed':False})


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True)
    args=parser.parse_args();run(original.read(args.plan))


if __name__=='__main__':main()