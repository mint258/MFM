"""One in-memory future/part-order/resume fixture, no Native or benchmark."""
import concurrent.futures as cf
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from .run import PartQueue,commit_part,original
from workflows.data_v1_final.conformers.window2_fill_loader_v1 import run as previous


class FillPipelineTests(unittest.TestCase):
    def test_cross_part_completion_matches_previous_values_atomic_commits_and_resume_skip(self):
        groups={1:['A0','Afast','Atail'],2:['B0','Bfast','B1']}
        metas={part:[{'molecule_id':mid,'S_conformers':2,'ordinal':part*10+i} for i,mid in enumerate(mids)]
            for part,mids in groups.items()}
        statistics={part:[{'molecule_id':m['molecule_id'],'status':'COMPLETE',
            'sprime_unique_ids_json':('[9,3]' if 'fast' in m['molecule_id'] else '[9]')} for m in rows]
            for part,rows in metas.items()}
        bounds={m['molecule_id']:50+i for i,m in enumerate(m for rows in metas.values() for m in rows)}
        loads=[]
        def load(db,selected):
            loads.append([m['molecule_id'] for m in selected])
            return [{'meta':m,'records':[{'record_id':m['molecule_id']+'-native'}],
                'uff':[{'sprime_conf_idx':bounds[m['molecule_id']],'coordinates':[[1.,2.,3.]]}],
                'prior_packet':None} for m in selected]
        def worker(job):
            mid=job['meta']['molecule_id'];kept=json.loads(job['d7']['sprime_unique_ids_json'])
            geometry=[] if len(kept)>=2 else [{'molecule_id':mid,'sprime_conf_idx':job['max_original_attempt_idx']+1,
                'coordinates':[[float(job['meta']['ordinal']),2.,3.]],'status':'SUCCESS'}]
            return {'molecule_id':mid,'target_N':2,'status':'ALREADY_COMPLETE' if not geometry else 'COMPLETE',
                'source_valid':True,'kept_original_sprime_ids':kept,'final_unique_count':2,
                'seed':123,'error':None,'new_conformers':geometry}
        sync=Mock();sync.map.side_effect=lambda function,jobs,chunksize:[function(job) for job in jobs]
        with patch.object(previous,'tasks',side_effect=load),patch.object(original,'safe_fill',side_effect=worker):
            expected={part:previous.part_values(None,metas[part],statistics[part],bounds,sync) for part in groups}
        loads.clear()
        class ControlledPool:
            def __init__(self):self.jobs={}
            def submit(self,function,job):
                future=cf.Future();self.jobs[job['meta']['molecule_id']]=(future,function,job)
                return future
            def finish(self,mid):
                future,function,job=self.jobs[mid];future.set_result(function(job));return future
        with tempfile.TemporaryDirectory() as root:
            out=Path(root);checkpoint=out/'checkpoint.json';parts=[];published=[]
            commit_part(out,0,[{'molecule_id':'old-closed','status':'ALREADY_COMPLETE','new_conformers':[]}],parts,checkpoint)
            def publish(part,values):
                published.append(part);commit_part(out,part,values,parts,checkpoint)
            pool=ControlledPool()
            queue=PartQueue(pool,None,bounds,publish,{0},capacity=4,task_loader=load,worker=worker)
            self.assertFalse(queue.add(0,metas[1],statistics[1]));self.assertEqual(loads,[])
            queue.add(1,metas[1],statistics[1]);queue.submit_waiting()
            queue.add(2,metas[2],statistics[2]);queue.submit_waiting()
            self.assertEqual(len(queue.pending),4)
            self.assertEqual(loads,[['A0','Atail'],['B0','B1']])
            self.assertEqual(published,[])
            queue.collect([pool.finish('B1')])
            self.assertEqual(published,[])
            queue.collect([pool.finish('B0')])
            self.assertEqual(published,[2])
            self.assertFalse((out/'states-000001.parquet').exists())
            self.assertEqual([p['part'] for p in json.loads(checkpoint.read_text())['parts']],[0,2])
            self.assertEqual(set(queue.active),{1})  # Running/unclosed part never called complete.
            queue.collect([pool.finish('Atail'),pool.finish('A0')])
            self.assertEqual(published,[2,1]);self.assertEqual(queue.active,{})
            self.assertEqual(queue.pending,{})
            self.assertEqual([p['part'] for p in parts],[0,1,2])
            import pyarrow.parquet as pq
            for part,values in expected.items():
                expected_states=[{k:v for k,v in value.items() if k!='new_conformers'} for value in values]
                expected_geometry=[row for value in values for row in value['new_conformers']]
                self.assertEqual(pq.read_table(out/('states-%06d.parquet'%part)).to_pylist(),expected_states)
                self.assertEqual(pq.read_table(out/('geometry-%06d.parquet'%part)).to_pylist(),expected_geometry)
            restored=json.loads(checkpoint.read_text())['parts']
            before=list(loads);resumed_pool=ControlledPool()
            resumed=PartQueue(resumed_pool,None,bounds,publish,{r['part'] for r in restored},4,task_loader=load,worker=worker)
            for part in groups:self.assertFalse(resumed.add(part,metas[part],statistics[part]))
            self.assertEqual(loads,before);self.assertEqual(resumed_pool.jobs,{})
            self.assertEqual([r['part'] for r in restored],[0,1,2])


if __name__=='__main__':unittest.main()