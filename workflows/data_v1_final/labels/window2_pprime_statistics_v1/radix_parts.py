"""Opt-in whole-part execution for integer-only P-prime radix stages."""
import collections,concurrent.futures as cf,json,os
from pathlib import Path
from . import statistics as T,temporary as Temp
from ..window2_normalization_v1 import io as I
PURPOSES={'normalization_quantiles','diagnostic_median_MAD'}


def need(value,message):
    if not value:raise ValueError(message)


def enabled(plan,purpose):
    flag=plan.get('shard_radix_typed_parts',False)
    need(type(flag)is bool,'BOOLEAN_RADIX_PART_OPT_IN_REQUIRED')
    return flag and purpose in PURPOSES


def integer(value):
    need(type(value)is int and value>=0,'NONNEGATIVE_INTEGER_RADIX_STATE_REQUIRED')
    return value


def validate(report,group,purpose):
    need(report['group_index']==group['group_index'] and report['source_job_id']==group['source_job_id'] and report['statistics_purpose']==purpose,'ORIGINAL_RADIX_GROUP_IDENTITY')
    for key in ('energy_TSQR','moments','joint'):need(report[key]=={},'FLOAT_STATE_CANNOT_BE_SHARDED:'+key)
    for key in ('r73_derived_reference','mask_override_reference','molecule_field_means_reference'):need(report.get(key)is None,'NONINTEGER_RADIX_OUTPUT_CANNOT_BE_SHARDED:'+key)


def part_pass(work,index,stage_ref):
    # Bind the actual submitted whole-part input without changing its kernel.
    return dict(T.group_pass(work),radix_part_index=index,radix_part_reference=work[3]['typed_parts'][0],radix_stage_reference=stage_ref)

class Shards:
    def __init__(self,cfg,stage_ref,root,groups,runtime):
        need(cfg['statistics_purpose']in PURPOSES,'INTEGER_RADIX_PURPOSE_ONLY')
        self.cfg=cfg;self.stage_ref=stage_ref;self.root=Path(root);self.runtime=runtime
        self.path=self.root/'radix_parts_checkpoint.json'
        inputs={'active_stage_reference':stage_ref,'groups':groups,'statistics_purpose':cfg['statistics_purpose'],'field_map_reference':cfg['field_map_reference']}
        paths=[p['path'] for g in groups for p in g['typed_parts']]
        need(len(paths)==len(set(paths)) and all(g['typed_parts'] for g in groups),'DISJOINT_NONEMPTY_WHOLE_TYPED_PARTS_REQUIRED')
        need(len({str(g['group_index']) for g in groups})==len(groups),'UNIQUE_ORIGINAL_LOGICAL_GROUPS_REQUIRED')
        if self.path.exists():
            self.state=I.load(self.path);need(self.state['inputs']==inputs,'SAME_ACTIVE_STAGE_AND_ORDERED_TYPED_PARTS_FOR_RESUME')
        else:self.state={'inputs':inputs,'closed':{}};self.save()
    def save(self):self.runtime.wait(self.path);I.save(self.path,self.state)
    def binding(self,group,index,reference):
        need(type(reference.get('radix_part_index'))is int and reference.get('radix_part_index')==index and reference.get('radix_part_reference')==group['typed_parts'][index] and reference.get('radix_stage_reference')==self.stage_ref,'EXACT_SUBMITTED_RADIX_PART_BINDING')
    def remaining(self,group):
        closed=self.state['closed'].get(str(group['group_index']),{})
        need(set(closed)<={str(i) for i in range(len(group['typed_parts']))},'SHARD_CHECKPOINT_INDEX_RANGE')
        for key,ref in closed.items():self.binding(group,int(key),ref)
        return [i for i in range(len(group['typed_parts'])) if str(i)not in closed]
    def record(self,group,index,reference):
        need(type(index)is int and 0<=index<len(group['typed_parts']),'ORIGINAL_TYPED_PART_INDEX')
        self.binding(group,index,reference);validate(I.load_data(reference),group,self.cfg['statistics_purpose'])
        closed=self.state['closed'].setdefault(str(group['group_index']),{});key=str(index)
        need(key not in closed or closed[key]==reference,'CONFLICTING_CLOSED_RADIX_PART')
        closed[key]=reference;self.save()
    def merge(self,group):
        need(not self.remaining(group),'ALL_ORIGINAL_PARTS_CLOSED_BEFORE_GROUP_MERGE')
        refs=[self.state['closed'][str(group['group_index'])][str(i)] for i in range(len(group['typed_parts']))]
        if len(refs)==1:
            validate(I.load_data(refs[0]),group,self.cfg['statistics_purpose'])
            return refs[0]
        import pyarrow as pa,pyarrow.parquet as pq
        out=self.root/'radix_merged'/('group_%04d'%group['group_index']);self.runtime.wait(out);out.mkdir(parents=True,exist_ok=True)
        report_path=out/'report.json'
        if report_path.exists():
            report=I.load(report_path);validate(report,group,self.cfg['statistics_purpose'])
            need(report.get('radix_part_reports')==refs and report.get('radix_active_stage_reference')==self.stage_ref,'SAME_CLOSED_RADIX_GROUP_PUBLICATION')
            return I.ref(report_path)
        reports=[I.load_data(ref) for ref in refs];hist=collections.Counter();field=collections.defaultdict(collections.Counter);roles=collections.Counter();series=collections.Counter()
        for report in reports:
            validate(report,group,self.cfg['statistics_purpose'])
            for fid,values in report['field_counts'].items():
                for key,value in values.items():field[fid][key]+=integer(value)
            for key,value in report['role_task_counts'].items():roles[key]+=integer(value)
            for key,value in report['series_mass'].items():series[key]+=integer(value)
            self.runtime.wait(out);pf=pq.ParquetFile(I.require(report['radix_histogram']),pre_buffer=False)
            try:
                for batch in pf.iter_batches(batch_size=8192,use_threads=False):
                    self.runtime.wait(out)
                    for row in batch.to_pylist():hist[(row['query'],row['field_id'],row['node_id'],row['prefix_bits'],row['prefix'])]+=integer(row['n'])
            finally:pf.close()
        schema=pa.schema([('query',pa.string()),('field_id',pa.uint32()),('node_id',pa.string()),('prefix_bits',pa.uint8()),('prefix',pa.uint64()),('n',pa.uint64())])
        path=out/'radix_counts.parquet';self.runtime.wait(path);writer=pq.ParquetWriter(path,schema,compression='zstd');buffer=[]
        try:
            for (query,fid,node,bits,prefix),n in sorted(hist.items()):
                buffer.append(dict(query=query,field_id=fid,node_id=node,prefix_bits=bits,prefix=prefix,n=n))
                if len(buffer)==8192:self.runtime.wait(path);writer.write_table(pa.Table.from_pylist(buffer,schema=schema));buffer=[]
            if buffer:self.runtime.wait(path);writer.write_table(pa.Table.from_pylist(buffer,schema=schema))
        finally:writer.close()
        report=dict(reports[0],pid=os.getpid(),task_rows=sum(integer(r['task_rows']) for r in reports),role_task_counts=dict(roles),field_counts={key:dict(value) for key,value in field.items()},series_mass=dict(series),
            radix_histogram=dict(I.ref(path),records=len(hist)),elapsed_seconds=max(r['elapsed_seconds'] for r in reports),radix_part_reports=refs,radix_active_stage_reference=self.stage_ref,
            radix_execution='WHOLE_EXISTING_PARTS_INTEGER_MERGE; elapsed=max shard elapsed; floating stages unsplit')
        self.runtime.wait(report_path);return I.save(report_path,report)


def run_stage(pool,cfg,stage,stage_ref,stage_root,attempt_root,groups,state,checkpoint):
    """One flat pool; original group checkpoints remain the stage authority."""
    runtime=Temp.activate(cfg['_temporary_runtime'],admit=False)
    store=Shards(cfg,stage_ref,stage_root,groups,runtime);pending={};errors=[]
    def publish(group):
        key=str(group['group_index']);state['groups'][key]=store.merge(group)
        runtime.wait(checkpoint);I.save(checkpoint,state)
        print(json.dumps({'purpose':cfg['statistics_purpose'],'pass':state['pass_index'],'closed_groups':len(state['groups']),'total_groups':len(groups),'errors':errors}),flush=True)
    for group in groups:
        if str(group['group_index'])in state['groups']:continue
        missing=store.remaining(group)
        if not missing:publish(group);continue
        for index in missing:
            root=Path(attempt_root)/'radix_parts'/('group_%04d'%group['group_index'])/('part_%04d'%index)
            runtime.wait(root);root.mkdir(parents=True,exist_ok=False)
            shard=dict(group,typed_parts=[group['typed_parts'][index]])
            pending[pool.submit(part_pass,(cfg,stage,str(root),shard),index,stage_ref)]=(group,index)
    for future in cf.as_completed(pending):
        group,index=pending[future]
        try:
            store.record(group,index,future.result())
            if not store.remaining(group):publish(group)
        except BaseException as error:errors.append({'group':str(group['group_index']),'part':index,'error':repr(error)})
    if errors:raise ValueError('PPRIME_RADIX_PART_ERRORS:'+repr(errors))