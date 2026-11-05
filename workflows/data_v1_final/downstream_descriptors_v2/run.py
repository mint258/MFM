"""Low-priority target-free RDKit2D + complete-geometry GFN2 descriptors, v2."""
from __future__ import annotations
import argparse
import collections
import concurrent.futures as cf
import json
import multiprocessing as mp
import os
from pathlib import Path
from . import worker
from .geometry import GEOMETRY_RECIPE, QM7_GRAPH_PROVENANCE


def selected_members(path,start=0,stop=None,shard_index=0,shards=1):
    if shards<1 or not 0<=shard_index<shards or start<0 or (stop is not None and stop<start):
        raise ValueError('INVALID_SOURCE_RECORD_SLICE')
    with Path(path).open(encoding='utf-8') as stream:
        for ordinal,line in enumerate(stream):
            if stop is not None and ordinal>=stop:break
            if ordinal<start or ordinal%shards!=shard_index:continue
            original=json.loads(line)
            # This whitelist deliberately drops label masks/annotations/targets.
            row={key:original.get(key) for key in ('dataset','member_uid','sample_id','fold','source_frame','geometry_artifact_ref')}
            if row['dataset'] not in ('qm7','qm9','cyp_isoform','az_exactsom','expansionrx'):
                raise ValueError('UNDECLARED_DATASET_IN_SOURCE_MEMBERSHIP')
            yield ordinal,row


def save(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def run(config,output,workers,start,stop,shard_index,shards,batch_size):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from rdkit import rdBase
    names=[name for name,_ in worker.descriptor_functions()]
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    binding={'config':config,'start_record':start,'stop_record':stop,'shard_index':shard_index,'shards':shards,
        'rdkit_version':rdBase.rdkitVersion,'rdkit_descriptor_names':names,'batch_size':batch_size}
    checkpoint=out/'checkpoint.json'
    if checkpoint.exists():
        state=json.loads(checkpoint.read_text(encoding='utf-8'))
        if state['binding']!=binding:raise ValueError('RESUME_SOURCE_SLICE_OR_DESCRIPTOR_SCHEMA_CHANGED')
    else:state={'binding':binding,'parts':[],'completed_source_ordinals':[],'status_counts':{}}
    if (out/'manifest.json').exists():
        print(json.dumps({'status':'ALREADY_COMPLETE','manifest':str(out/'manifest.json')}),flush=True)
        return
    completed=set(state['completed_source_ordinals']);items=selected_members(config['members'],start,stop,shard_index,shards)
    pending=[];count=sum(part['rows'] for part in state['parts'])
    counts=collections.Counter(state['status_counts'])
    integer_fields={'source_ordinal','charge','unpaired_electrons','xtb_scf_iterations','geometry_seed','geometry_mmff_status'}
    integer_lists={'native_atomic_numbers','source_atom_ids','xtb_atomic_numbers','xtb_source_atom_ids'}
    string_fields={'dataset','member_uid','sample_id','source_fold','rdkit_status','xtb_status','xtb_raw_json',
        'xtb_features_json','native_scratch','error','geometry_reason','geometry_policy','geometry_recipe_json','graph_provenance'}
    schema=pa.schema([(name,pa.int64()) for name in sorted(integer_fields)]+
        [(name,pa.list_(pa.int32())) for name in sorted(integer_lists)]+
        [(name,pa.string()) for name in sorted(string_fields)]+
        [('rdkit_values',pa.list_(pa.float64())),('rdkit_mask',pa.list_(pa.bool_())),('xtb_converged',pa.bool_())])
    def write_rows(rows):
        nonlocal count
        path=out/('part-%06d-%d.parquet'%(len(state['parts']),os.getpid()))
        table=pa.Table.from_pylist(rows,schema=schema)
        pq.write_table(table,path,compression='zstd',row_group_size=1024)
        state['parts'].append({'path':str(path),'bytes':path.stat().st_size,'rows':len(rows)})
        state['completed_source_ordinals'].extend(row['source_ordinal'] for row in rows)
        for row in rows:
            counts['rdkit:'+row['rdkit_status']]+=1;counts['xtb:'+row['xtb_status']]+=1
            counts['geometry:'+str(row['geometry_policy'])]+=1
        state['status_counts']=dict(counts)
        temporary=out/'checkpoint.next.json';temporary.write_text(json.dumps(state),encoding='utf-8');os.replace(temporary,checkpoint)
        count+=len(rows);print(json.dumps({'stage':'B6','closed_rows':count,'latest_source_ordinal':rows[-1]['source_ordinal']}),flush=True)
    with cf.ProcessPoolExecutor(max_workers=workers,mp_context=mp.get_context('spawn'),initializer=worker.initialize,initargs=(config,names)) as pool:
        for item in items:
            if item[0] in completed:continue
            pending.append(item)
            if len(pending)>=batch_size:
                write_rows(list(pool.map(worker.one,pending,chunksize=4)));pending=[]
        if pending:write_rows(list(pool.map(worker.one,pending,chunksize=4)))
    manifest={'schema':'DATA_V1_DOWNSTREAM_BASELINE_DESCRIPTORS_V2','status':'SOURCE_SLICE_COMPLETE_WITH_EXPLICIT_MISSING',
        'files':state['parts'],'rows':count,'source_slice':{key:binding[key] for key in ('start_record','stop_record','shard_index','shards')},
        'rdkit_version':rdBase.rdkitVersion,'rdkit_descriptor_names':names,'rdkit_2D_graph_policy':'RemoveHs on a source graph copy; native geometry/atom IDs untouched',
        'xtb_method':'same installed GFN2-xTB singlepoint; source/perceived graph charge and closed-shell spin; complete original or baseline-only H-completed geometry; no QM optimization',
        'xtb_native_timeout_seconds':config.get('native_singlepoint_timeout_seconds',900),
        'status_counts':dict(counts),'normalization_or_model_selection_performed':False,
        'target_or_annotation_values_decoded':False,'new_geometry_generated':'Only baseline-only missing H/full-geometry work copies; count in geometry statuses',
        'baseline_geometry_recipe':GEOMETRY_RECIPE,'qm7_graph_provenance':QM7_GRAPH_PROVENANCE,'integrity_hashes_computed':False,
        'native_scratch_retained':config['scratch'],'missing_feature_representation':'RDKit float NaN and explicit mask; xTB null with reason'}
    save(out/'manifest.json',manifest)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--workers',type=int,default=16);parser.add_argument('--start-record',type=int,default=0)
    parser.add_argument('--stop-record',type=int);parser.add_argument('--shard-index',type=int,default=0)
    parser.add_argument('--shards',type=int,default=1);parser.add_argument('--batch-size',type=int,default=1024)
    args=parser.parse_args();config=json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    run(config,args.output,args.workers,args.start_record,args.stop_record,args.shard_index,args.shards,args.batch_size)


if __name__=='__main__':main()