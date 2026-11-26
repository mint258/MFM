"""Metadata-only cost invariants; no native queries or old scientific results."""
import pytest
from write_weekly_cost_current import cost_records,bucket

def native(rows,extra=()):
 return dict(observed_at=1,rows=rows,explicit_native_analysis_GPU_job_ids=list(extra))
def row(job,seconds=100,node='compute-0-6',state='COMPLETED',start='2026-11-23T00:00:00'):
 return dict(job_id=str(job),job_name='registered_'+str(job),node=node,state=state,elapsed_seconds=seconds,start=start)
def gpu(job,**kwargs):
 return dict(backend='Slurm',node='compute-0-6',job_id=job,kind='F',**kwargs)

def test_CPU_statistics_and_unlisted_GPU_rows_do_not_enter_GPU_total():
 ledger=dict(runs=dict(F1_full=gpu(1),CPU=dict(backend='Slurm',node='compute-0-11',job_id=2,kind='F_STATS')))
 records,skipped,aliases=cost_records(ledger,native({'1':row(1),'2':row(2,node='compute-0-11'),'99':row(99)}))
 assert [r['job_id'] for _,r in records]==[1]
 assert records[0][1]['elapsed_seconds']==100 and bucket(records[0][1])=='analysis_F1'
 assert len(skipped)==1 and not aliases

def test_physical_job_alias_is_counted_once_and_explicit_analysis_supplement_added_once():
 ledger=dict(runs=dict(F1_full=gpu(1),alias=gpu(1)))
 records,skipped,aliases=cost_records(ledger,native({'1':row(1),'3':dict(row(3),job_name='P_A6_readout30000')},extra=['1','3']))
 assert len(records)==2 and len(aliases)==1
 assert sum(r['elapsed_seconds'] for _,r in records)==200
 assert bucket(records[1][1])=='analysis_A6'

def test_historical_handoff_and_lower_bounds_are_preserved():
 ledger=dict(runs=dict(old=gpu(1,stage=2,elapsed_seconds=70),
  confirmation=gpu(2,stage=3,elapsed_seconds=30,allocation_pretraining_seconds=20),
  floor=gpu(3,elapsed_seconds=40,elapsed_seconds_floor=True)))
 records,_,_=cost_records(ledger,native({str(j):row(j) for j in [1,2,3]}))
 assert [r['elapsed_seconds'] for _,r in records]==[70,80,40]

def test_never_allocated_placeholders_and_unproven_roles_are_distinct():
 ledger=dict(runs=dict(queued=gpu(1),unknown=dict(backend='Slurm',job_id=2)))
 records,skipped,_=cost_records(ledger,native({'1':row(1,0,state='CANCELLED',start='Unknown')}))
 assert not records
 assert {x['reason'] for x in skipped}=={'No_native_allocation_start','Unproven_GPU_or_CPU_role'}

def test_cancelled_state_suffix_and_CPU_on_GPU_named_source():
 ledger=dict(runs=dict(cancelled=gpu(1),stats=dict(backend='Slurm',job_id=2,node='compute-0-6',kind='A1_STATS')))
 records,skipped,_=cost_records(ledger,native({'1':row(1,state='CANCELLED by1278'),'2':row(2)}))
 assert len(records)==1 and records[0][1]['state']=='CANCELLED'
 assert skipped[0]['reason']=='CPU_target'
