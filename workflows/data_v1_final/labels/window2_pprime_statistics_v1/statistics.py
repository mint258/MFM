"""Cached P-prime F64 entries into the unchanged normalization kernel."""
import collections,types
from pathlib import Path
from ..window2_normalization_v1 import io as I,statistics as Original
from ..normalization_compact_runtime_v3 import codec as K


def observations(cfg,group,fields,**unused):
    import pyarrow as pa,pyarrow.parquet as pq
    runtime=cfg.get('_temporary_guard')
    byid={f['field_id']:f for f in fields};means=collections.defaultdict(lambda:[0,0.]);counts=collections.Counter()
    for reference in group['typed_parts']:
        pf=pq.ParquetFile(I.require(reference),pre_buffer=False)
        try:
            for batch in pf.iter_batches(batch_size=32,use_threads=False):
                if runtime and not cfg.get('_histogram_write_proxy_active',False):runtime.wait(cfg['_current_group_output'])
                for row in batch.to_pylist():
                    owner={'record_id':row['record_id'],'molecule_id':row['molecule_id'],'fit_eligible':row['fit_eligible'],'geometry_source':'uff_sprime'}
                    entries=K.unpack_entries(row,byid)
                    for e in entries:e['field']=byid[e['field_id']]
                    if cfg['statistics_purpose']=='normalization_moments'and owner['fit_eligible']:
                        for e in entries:
                            values=[v for v,keep in zip(e['values_float64'],e['value_mask'])if keep]
                            if values:
                                c=means[(owner['molecule_id'],e['field_id'])];c[0]+=len(values);c[1]+=sum(values)
                    counts[row['calc_type']]+=1
                    yield owner,row['atomic_numbers'],entries
        finally:pf.close()
    if cfg['statistics_purpose']=='normalization_moments':
        path=Path(cfg['_current_group_output'])/'molecule_field_means.parquet'
        schema=pa.schema([('molecule_id',pa.string()),('field_id',pa.uint16()),('n',pa.uint64()),('sum',pa.float64()),('mean',pa.float64())])
        writer=pq.ParquetWriter(path,schema,compression='zstd')
        try:
            rows=[]
            for (mid,fid),(n,total)in sorted(means.items()):
                rows.append({'molecule_id':mid,'field_id':fid,'n':n,'sum':total,'mean':total/n})
                if len(rows)>=8192:writer.write_table(pa.Table.from_pylist(rows,schema=schema));rows=[]
            if rows:writer.write_table(pa.Table.from_pylist(rows,schema=schema))
        finally:writer.close()


def group_pass(work):
    cfg,stage,root,group=work
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    from . import temporary as Temp
    runtime=Temp.activate(cfg['_temporary_runtime'],admit=False);runtime.wait(root)
    cfg=dict(cfg,_current_group_output=str(Path(root)/('group_%04d'%group['group_index'])),_temporary_guard=runtime,_histogram_write_proxy_active=False)
    state={'cfg':cfg,'stage':stage,'root':Path(root),'fields':I.load_data(cfg['field_map_reference'])}
    # Same full mathematical worker bytecode and original TSQR/Radix/moment
    # objects; only the source generator and process-local work state differ.
    original=Original._group_pass;overrides={}
    from . import histogram_io as H
    if H.enabled(cfg,cfg['statistics_purpose']):
        state['root'],overrides=H.bindings(runtime,root);cfg['_histogram_write_proxy_active']=True
    fn=types.FunctionType(original.__code__,dict(original.__globals__,observations=observations,WORK=state,**overrides),original.__name__,original.__defaults__,original.__closure__)
    fn.__kwdefaults__=original.__kwdefaults__
    return fn((group,False))
