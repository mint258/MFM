"""Original pointer preparation inside the single parent, checkpoints not jobs."""
import json,pathlib
from . import contract as C,runtime as I


class Prepare:
    def __init__(self,plan,value,original,census,proof,out,budget):
        self.plan,self.value,self.original,self.census,self.proof,self.out,self.budget=plan,value,original,census,proof,pathlib.Path(out),budget
        self.source=None;self.headers={}
    def check(self):C.need(self.budget.observe() is None,self.budget.stop or 'STOP_NEW_INPUT_PREPARATION')
    def canonical(self):
        if self.source is None:self.source=I.canonical_source(self.value,self.proof,self.plan['source_mapping_review_reference'],self.out,self.check)
        return self.source
    def batch(self,bid):
        import duckdb,pyarrow as pa
        db=self.census.db;members=db.execute("SELECT k,mid,meta FROM metas WHERE bid=? AND state='ELIGIBLE_UNCLAIMED_AFTER_ORDINARY_SOURCE_CENSUS' ORDER BY mid",(bid,)).fetchall()
        if not members:return None,[]
        self.check();source=self.canonical();directory=self.out/'internal_prepared'/bid;directory.mkdir(parents=True,exist_ok=False,mode=0o700)
        # Original prepare_mapping columns and record ordering, copied IO only.
        # No oldCLI/resource globals and no optimizer are invoked here.
        duck=duckdb.connect();duck.execute('SET threads='+str(self.plan['cpus']));duck.execute("SET memory_limit='12GB'")
        duck.register('selected',pa.table({'molecule_id':[row[1] for row in members]}))
        columns=('record_id','molecule_id','source_path','real_index','record_payload_sha256','total_atoms','energy_raw','smiles',
            'QC_molecule_chirality_conflict','QC_molecule_ez_conflict')
        try:rows=duck.execute('SELECT '+','.join('r.'+n for n in columns)+' FROM read_parquet('+C.F.q(source['path'])+
            ') r JOIN selected USING(molecule_id) ORDER BY r.molecule_id,r.record_id').fetch_arrow_table().to_pylist()
        finally:duck.close()
        pointers={mid:[] for key,mid,meta in members}
        for row in rows:pointers[row['molecule_id']].append(row)
        tasks=[];provenance=[]
        for key,mid,raw in members:
            self.check();meta=json.loads(raw);prior=list(db.execute('SELECT row,locator,identity FROM baseline WHERE mid=? ORDER BY idx',(mid,)))
            previous=[json.loads(row[0]) for row in prior]
            C.need(len(pointers[mid])==meta['expected_conformers']==meta['S_conformers'] and len({r['record_id'] for r in pointers[mid]})==len(pointers[mid]),'ORIGINAL_PM7_POINTER_COUNT_AND_IDENTITY')
            C.need(len(previous)<meta['expected_conformers'] and len({r['sprime_conf_idx'] for r in previous})==len(previous),'CURRENT_BASELINE_NOT_ALREADY_SUFFICIENT_OR_INDEX_CONFLICT')
            # Immutable original meta/cohort/target/taskkey/seed. Current actual
            # accepted baselines may enrich the old snapshot; their source
            # identities are explicit, never a fabricated per-chunk C0.
            task={'meta':meta,'records':pointers[mid],'existing_conformers':previous}
            tasks.append(task);provenance.append({'task_key':key,'original_snapshot_Sprime_conformers':meta['Sprime_conformers'],
                'actual_current_baseline_rows':len(previous),'source_locators':[json.loads(p[1]) for p in prior],
                'coordinate_identity_keys':[p[2] for p in prior],'source_census_completed_in_real_parent':str(self.proof['job_id'])})
        raw=b''.join(C.F.canonical(task)+b'\n' for task in tasks)
        tasks_ref=self.budget.write(directory/'tasks.jsonl',raw)
        pr=self.budget.write(directory/'baseline_sources.jsonl',b''.join(C.F.canonical(p)+b'\n' for p in provenance))
        header={'schema':'SPRIME_PACKED_INTERNAL_PREPARED_V1','status':'INPUTS_PREPARED_WITHIN_RUNNING_PARENT_NOT_A_CHILD_C0',
            'original_plan_reference':self.plan['original_plan_reference'],'packed_plan_reference':C.small_pin(self.plan['_plan_path']),
            'original_config_reference':self.plan['original_config_reference'],'batch_id':bid,'tasks_reference':tasks_ref,'baseline_sources_reference':pr,
            'formal_source_reference':source,'molecules':len(tasks),'kernel_sha256':C.F.KERNEL_SHA,'native_task_keys_and_seed_domains_changed':False,
            'actual_single_parent_job_id':str(self.proof['job_id']),'actual_allocated_cpus':self.proof['request']['cpus'],
            'original500_is_only_checkpoint':True,'child_Slurm_parent_or_C0_claimed':False,'UFF_QM_calls_during_preparation':0}
        ref=self.budget.write(directory/'prepared.json',C.F.canonical(header)+b'\n');self.headers[bid]=ref
        return ref,tasks
