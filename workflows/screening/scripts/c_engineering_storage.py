"""C4 sample value serialization, retained population projection and five-file bytes.

Only candidate bytes/analysis Parquet are written; no LMDB or final field format
is chosen. Original Data fields except the expressly revised descriptors remain
in the candidate. Actual new 3D descriptors and registry P values are serialized.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter,defaultdict
import concurrent.futures
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import pickle
import socket
import sys
import tempfile
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
AUDIT=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2')
sys.path[:0]=[str(AUDIT/'deps'),str(AUDIT/'scripts/deps')]
import c_engineering_wire as WIRE
HANDLES={};SOURCES=REGISTRY=ROWS=None

def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1<<20),b''):value.update(block)
    return value.hexdigest()

def save(path,value):
    pending=Path(str(path)+'.pending');pending.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n');pending.replace(path)

def init(sources,registry,rows,barrier):
    global SOURCES,REGISTRY,ROWS
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    import torch,pyarrow as pa
    torch.set_num_threads(1);pa.set_cpu_count(1);pa.set_io_thread_count(1)
    SOURCES,REGISTRY,ROWS=sources,registry,rows
    WIRE.metadata();barrier.wait(timeout=180)

def raw_source(row):
    import lmdb
    sid=int(row['shard_id']);index=int(row['real_index'])
    if sid not in HANDLES:HANDLES[sid]=lmdb.open(SOURCES[sid]['path'],subdir=False,readonly=True,lock=False,create=False,readahead=False,meminit=False,max_readers=512)
    with HANDLES[sid].begin(buffers=False) as tx:payload=tx.get(f'{index:09d}'.encode())
    if payload is None:raise ValueError('SOURCE_RECORD_MISSING')
    if hashlib.sha256(payload).hexdigest()!=row['record_payload_sha256']:raise ValueError('SOURCE_PAYLOAD_SHA_MISMATCH')
    return pickle.loads(payload),payload

def task(item):
    import pyarrow.parquet as pq
    receipt_path,record_ids=item;receipt=json.loads(Path(receipt_path).read_text());ref=receipt['parquet']
    details=defaultdict(dict);issues=[]
    if Path(ref['path']).stat().st_size!=ref['bytes'] or sha(ref['path'])!=ref['sha256']:
        issues.append('NATIVE_SOURCE_PARQUET_BINDING_MISMATCH')
    else:
        for batch in pq.ParquetFile(ref['path']).iter_batches(batch_size=32,columns=['record_id','task','details_json'],use_threads=False):
            for value in batch.to_pylist():details[value['record_id']][value['task']]=json.loads(value['details_json'])
    if details and set(details)!=set(record_ids):raise ValueError('MANIFEST_COUNT_MISMATCH_NATIVE_MOLECULE')
    output=[];groups=[];inventory=None
    for record_id in record_ids:
        row=ROWS[record_id]
        measured={'record_id':record_id,'molecule_id':row['molecule_id'],'size_stratum':row['size_stratum'],
            'molecule_lowest_energy_conformer':row['molecule_lowest_energy_conformer'],
            'heavy_atoms':row['heavy_atoms'],'total_atoms':row['total_atoms'],'worker_pid':os.getpid(),
            'source_payload_bytes':None,'base_Data_pickle4_bytes':None,'base_Data_pickle5_bytes':None,
            'base_Data_zstd3_bytes':None,'all_registry_candidate_pickle5_bytes':None,'all_registry_candidate_zstd3_bytes':None,
            'dedup_derived_candidate_pickle5_bytes':None,'dedup_derived_candidate_zstd3_bytes':None,
            'all_registry_nohessian_pickle5_bytes':None,'all_registry_nohessian_zstd3_bytes':None,
            'hessian_marginal_pickle5_bytes':None,'hessian_marginal_zstd3_bytes':None,
            'derived_nohessian_pickle5_bytes':None,'derived_nohessian_zstd3_bytes':None,
            'derived_hessian_marginal_pickle5_bytes':None,'derived_hessian_marginal_zstd3_bytes':None,
            'nohessian_page_estimate_bytes':None,'hessian_page_marginal_estimate_bytes':None,
            'key_plus_value_zstd3_bytes':None,'per_record_4KiB_rounding_estimate_bytes':None,
            'native_physical_and_QC_registry_values':None,'serialization_seconds':None,'scratch_write_fsync_seconds':None,
            'issues':list(issues)}
        begin=time.monotonic()
        try:
            raw,payload=raw_source(row);measured['source_payload_bytes']=len(payload)
            if inventory is None:
                mapping=raw if isinstance(raw,dict) else raw.to_dict() if hasattr(raw,'to_dict') else vars(raw)
                inventory={key:{'type':type(value).__name__,'shape':list(value.shape) if hasattr(value,'shape') else None}
                    for key,value in mapping.items()}
            candidate,problems=WIRE.corrected_base(raw,row);measured['issues']+=problems
            base4=WIRE.serialized(candidate,4);base5=WIRE.serialized(candidate,5);basez=WIRE.compressed(base5)
            labels,task_groups,problems=WIRE.labels(details.get(record_id,{}),REGISTRY,drop_derived=False)
            derived={'registry_indexed_values':[(index,value) for index,value in labels['registry_indexed_values']
                if not (REGISTRY[index].get('classification')=='physical_label' and REGISTRY[index].get('derived_from'))],
                'task_status_QC':labels['task_status_QC']}
            nohessian={'registry_indexed_values':[(index,value) for index,value in labels['registry_indexed_values']
                if REGISTRY[index].get('task')!='xtb_hessian'],
                'task_status_QC':[value for value in labels['task_status_QC'] if value[0]!='xtb_hessian']}
            candidate_all={'schema_ref':'C4_NATIVE_DATA_REGISTRY_P_V1','data':candidate,'P':labels}
            candidate_dedup={'schema_ref':'C4_NATIVE_DATA_REGISTRY_P_V1','data':candidate,'P':derived}
            all_bytes=WIRE.serialized(candidate_all);all_zstd=WIRE.compressed(all_bytes)
            dedup_bytes=WIRE.serialized(candidate_dedup);dedup_zstd=WIRE.compressed(dedup_bytes)
            nohess_bytes=WIRE.serialized({'schema_ref':'C4_NATIVE_DATA_REGISTRY_P_V1','data':candidate,'P':nohessian})
            nohess_zstd=WIRE.compressed(nohess_bytes)
            derived_nh={'registry_indexed_values':[(index,value) for index,value in derived['registry_indexed_values'] if REGISTRY[index].get('task')!='xtb_hessian'],
                'task_status_QC':[value for value in derived['task_status_QC'] if value[0]!='xtb_hessian']}
            derived_nh_bytes=WIRE.serialized({'schema_ref':'C4_NATIVE_DATA_REGISTRY_P_V1','data':candidate,'P':derived_nh})
            derived_nh_zstd=WIRE.compressed(derived_nh_bytes)
            if not details.get(record_id):
                measured['issues'].append('NATIVE_LABELS_UNAVAILABLE_NO_COMPLETE_LABEL_SIZE_ESTIMATE')
            else:
                measured.update(all_registry_candidate_pickle5_bytes=len(all_bytes),all_registry_candidate_zstd3_bytes=len(all_zstd),
                    dedup_derived_candidate_pickle5_bytes=len(dedup_bytes),dedup_derived_candidate_zstd3_bytes=len(dedup_zstd),
                    all_registry_nohessian_pickle5_bytes=len(nohess_bytes),all_registry_nohessian_zstd3_bytes=len(nohess_zstd),
                    hessian_marginal_pickle5_bytes=len(all_bytes)-len(nohess_bytes),
                    hessian_marginal_zstd3_bytes=len(all_zstd)-len(nohess_zstd),
                    derived_nohessian_pickle5_bytes=len(derived_nh_bytes),derived_nohessian_zstd3_bytes=len(derived_nh_zstd),
                    derived_hessian_marginal_pickle5_bytes=len(dedup_bytes)-len(derived_nh_bytes),
                    derived_hessian_marginal_zstd3_bytes=len(dedup_zstd)-len(derived_nh_zstd),
                    nohessian_page_estimate_bytes=math.ceil((len(nohess_zstd)+32)/4096)*4096,
                    hessian_page_marginal_estimate_bytes=(math.ceil((len(all_zstd)+32)/4096)-math.ceil((len(nohess_zstd)+32)/4096))*4096,
                    key_plus_value_zstd3_bytes=len(all_zstd)+9,
                    per_record_4KiB_rounding_estimate_bytes=math.ceil((len(all_zstd)+32)/4096)*4096,
                    native_physical_and_QC_registry_values=len(labels['registry_indexed_values']))
            measured.update(base_Data_pickle4_bytes=len(base4),base_Data_pickle5_bytes=len(base5),base_Data_zstd3_bytes=len(basez))
            for task_name,values in task_groups.items():
                encoded=WIRE.serialized(values)
                groups.append({'record_id':record_id,'size_stratum':row['size_stratum'],'task':task_name,
                    'registered_values':len(values),'standalone_pickle5_bytes':len(encoded),'standalone_zstd3_bytes':len(WIRE.compressed(encoded))})
            # A deterministic small scratch sample exercises the actual chosen
            # candidate blob write/fsync; all 10k records still serialize/measure.
            if int(hashlib.sha256(record_id.encode()).hexdigest()[:8],16)%157==0:
                fd,name=tempfile.mkstemp(prefix='c4_serial_'+os.environ['SLURM_JOB_ID']+'_',dir='/tmp')
                written=time.monotonic()
                try:
                    with os.fdopen(fd,'wb') as handle:handle.write(all_zstd);handle.flush();os.fsync(handle.fileno())
                    measured['scratch_write_fsync_seconds']=time.monotonic()-written
                    if Path(name).stat().st_size!=len(all_zstd):measured['issues'].append('OWN_SCRATCH_SERIALIZED_BYTE_MISMATCH')
                finally:Path(name).unlink(missing_ok=True)
        except Exception as exc:measured['issues'].append(type(exc).__name__+':'+str(exc))
        measured['serialization_seconds']=time.monotonic()-begin;output.append(measured)
    return {'rows':output,'task_groups':groups,'original_Data_fields_example':inventory,'worker_pid':os.getpid()}

def stratum_summary(metrics,population):
    fields=('source_payload_bytes','base_Data_pickle4_bytes','base_Data_pickle5_bytes','base_Data_zstd3_bytes',
        'all_registry_candidate_pickle5_bytes','all_registry_candidate_zstd3_bytes','dedup_derived_candidate_pickle5_bytes',
        'dedup_derived_candidate_zstd3_bytes','key_plus_value_zstd3_bytes','per_record_4KiB_rounding_estimate_bytes',
        'all_registry_nohessian_pickle5_bytes','all_registry_nohessian_zstd3_bytes',
        'hessian_marginal_pickle5_bytes','hessian_marginal_zstd3_bytes',
        'derived_nohessian_pickle5_bytes','derived_nohessian_zstd3_bytes',
        'derived_hessian_marginal_pickle5_bytes','derived_hessian_marginal_zstd3_bytes',
        'nohessian_page_estimate_bytes','hessian_page_marginal_estimate_bytes')
    result=[]
    for row in population['strata']:
        group=[item for item in metrics if item['size_stratum']==row['size_stratum']]
        entry={'size_stratum':row['size_stratum'],'sample_records':len(group),'population_records':row['records'],
            'population_molecules':row['molecules'],'byte_estimates':{}}
        for field in fields:
            present=[item[field] for item in group if item[field] is not None]
            complete=len(present)==len(group) and bool(group)
            entry['byte_estimates'][field]={'measured_records':len(present),'missing_records':len(group)-len(present),
                'sample_sum_bytes':sum(present),'sample_mean_bytes':sum(present)/len(present) if present else None,
                'population_bytes':sum(present)/len(present)*row['records'] if complete else None}
        result.append(entry)
    totals={field:sum(item['byte_estimates'][field]['population_bytes'] for item in result)
        if all(item['byte_estimates'][field]['population_bytes'] is not None for item in result) else None for field in fields}
    corrected={}
    for suffix in ('pickle5','zstd3','derived_pickle5','derived_zstd3','pages'):
        prefix='derived_' if suffix.startswith('derived_') else ''
        format_=suffix.removeprefix('derived_')
        ordinary_field='nohessian_page_estimate_bytes' if suffix=='pages' else (
            'derived_nohessian_'+format_+'_bytes' if prefix else 'all_registry_nohessian_'+format_+'_bytes')
        marginal_field='hessian_page_marginal_estimate_bytes' if suffix=='pages' else prefix+'hessian_marginal_'+format_+'_bytes'
        full_field='per_record_4KiB_rounding_estimate_bytes' if suffix=='pages' else (
            'dedup_derived_candidate_'+format_+'_bytes' if prefix else 'all_registry_candidate_'+format_+'_bytes')
        full=0.0;complete=True
        for entry in result:
            group=[row for row in metrics if row['size_stratum']==entry['size_stratum']]
            minimum=[row for row in group if row.get('molecule_lowest_energy_conformer') is True]
            marginal=[row[marginal_field] for row in minimum if row[marginal_field] is not None]
            base=entry['byte_estimates'][ordinary_field]['population_bytes']
            if base is None or not minimum or len(marginal)!=len(minimum):complete=False
            else:full+=base+sum(marginal)/len(minimum)*entry['population_molecules']
        totals[full_field]=full if complete else None
        corrected[full_field]={'ordinary_record_bytes_field':ordinary_field,'minimum_molecule_marginal_field':marginal_field}
    totals['key_plus_value_zstd3_bytes']=totals['all_registry_candidate_zstd3_bytes']+population['records']*9 if totals['all_registry_candidate_zstd3_bytes'] is not None else None
    return {'strata':result,'total_estimated_bytes':totals,
        'record_and_minimum_molecule_weighted_fields':corrected,
        'population_scope':'A retained set weights applied to old native stratified sample. Additional relaxed stereo-only conformers have not separately run QM; label-size representativeness is assumed within strata, not measured on those new conformers.'}

def five_files(db,quality,metrics,relaxed=True):
    import pyarrow as pa
    complete=[row for row in metrics if row['all_registry_candidate_zstd3_bytes'] is not None]
    means={}
    for value in {row['heavy_atoms']//5 for row in complete}:
        group=[row for row in complete if row['heavy_atoms']//5==value]
        means[value]=sum(row['all_registry_candidate_zstd3_bytes'] for row in group)/len(group)
    if not means:return {'complete':False,'reason':'No complete candidate size sample'}
    population_max=db.execute('SELECT max(heavy_atoms) FROM read_parquet(?) WHERE retained OR strict_retained',[str(quality)]).fetchone()[0]
    bins=range(0,max(200,int(population_max or 0),max(row['heavy_atoms'] for row in complete))//5+1)
    model=[{'heavy_bin':value,'mean_record_bytes':means.get(value,means[min(means,key=lambda key:abs(key-value))]),
        'observed_sample_bin':value in means} for value in bins]
    db.register('C4_byte_model',pa.Table.from_pylist(model))
    condition='retained' if relaxed else 'strict_retained'
    # Use maximum physical molecule Nheavy, matching A's stable file assignment.
    # Only the byte contribution is restricted to retained conformers.
    query='''WITH maxima AS (SELECT molecule_id,max(heavy_atoms) AS molecule_max_heavy FROM read_parquet(?) GROUP BY molecule_id),
       population AS (SELECT i.molecule_id,m.molecule_max_heavy,i.heavy_atoms FROM read_parquet(?) i JOIN maxima m USING(molecule_id) WHERE '''+condition+''')
       SELECT molecule_max_heavy,count(*) AS records,count(DISTINCT molecule_id) AS molecules,
         sum(b.mean_record_bytes) AS estimated_bytes,count(*) FILTER(WHERE NOT b.observed_sample_bin) AS records_using_nearest_sample_bin
       FROM population p JOIN C4_byte_model b ON floor(p.heavy_atoms/5)=b.heavy_bin GROUP BY molecule_max_heavy ORDER BY molecule_max_heavy'''
    distribution=[dict(zip(('molecule_max_heavy','records','molecules','estimated_bytes','records_using_nearest_sample_bin'),values))
        for values in db.execute(query,[str(quality),str(quality)]).fetchall()]
    total=sum(row['estimated_bytes'] for row in distribution);running=0;cumulative=[]
    for row in distribution:running+=row['estimated_bytes'];cumulative.append((row['molecule_max_heavy'],running))
    boundaries=[]
    for fraction in (.2,.4,.6,.8):
        choices=[(heavy,value) for heavy,value in cumulative if not boundaries or heavy>boundaries[-1]]
        if not choices:break
        boundaries.append(min(choices,key=lambda pair:abs(pair[1]-total*fraction))[0])
    def assign(cuts):
        groups=[{'file':index+1,'records':0,'molecules':0,'estimated_bytes':0,'records_using_nearest_sample_bin':0} for index in range(5)]
        for row in distribution:
            target=sum(row['molecule_max_heavy']>cut for cut in cuts)
            for key in ('records','molecules','estimated_bytes','records_using_nearest_sample_bin'):groups[target][key]+=row[key]
        sizes=[group['estimated_bytes'] for group in groups]
        return {'boundaries_max_molecule_heavy':cuts,'files':groups,'max_to_min_byte_ratio':max(sizes)/min(sizes) if min(sizes)>0 else None}
    return {'complete':len(boundaries)==4,'sample_model':'Mean compressed candidate record bytes by 5-heavy-atom bin; nearest measured bin when absent. No molecular group is split.',
        'population_records':sum(row['records'] for row in distribution),'population_molecules':sum(row['molecules'] for row in distribution),
        'total_estimated_bytes':total,'baseline_20_25_30_40':assign([20,25,30,40]),
        'suggested_byte_balanced':assign(boundaries) if len(boundaries)==4 else None,'molecule_max_heavy_distribution':distribution}

def quota(snapshot):
    raw=json.loads(Path(snapshot).read_text());entry=raw.get('quota',{})
    if entry.get('exit_code',entry.get('rc'))!=0:return None
    for line in entry.get('stdout','').splitlines():
        tokens=line.split()
        if len(tokens)>=4 and tokens[0].startswith('/'):
            try:used,soft,hard=[int(value.rstrip('*')) for value in tokens[1:4]]
            except ValueError:continue
            positive=[value for value in (soft,hard) if value>0]
            return (min(positive)-used)*1024 if positive else None
    return None

def markdown(report):
    def gb(value):return '待测' if value is None else f'{value/1e9:.3f}'
    lines=['候选正式写回 value 格式的样本字节实测；本轮未建立 lmdb_1，最终字段格式尚未决定。','',
        '| 保留集 | 原基础payload GB | D20+指定3D兼容Data GB | 注册表P候选完整 GB | 无损zstd3完整 GB | 4KiB逐记录取整估计 GB |',
        '|---|---:|---:|---:|---:|---:|']
    for key,value in report['populations'].items():
        total=value['total_estimated_bytes']
        lines.append(f"| {key} | {gb(total['source_payload_bytes'])} | {gb(total['base_Data_pickle4_bytes'])} | {gb(total['all_registry_candidate_pickle5_bytes'])} | {gb(total['all_registry_candidate_zstd3_bytes'])} | {gb(total['per_record_4KiB_rounding_estimate_bytes'])} |")
    lines+=['','以上是实际候选 value 字节外推；LMDB Btree、页/碎片实际大小未测，逐记录4KiB取整为保守规划模型，不冒充实测数据库体积。','',
        '| 保留集 | 五文件规则 | 重原子边界 | 最大/最小预测字节比 |', '|---|---|---|---:|']
    for key,value in report['five_files'].items():
        for name in ('baseline_20_25_30_40','suggested_byte_balanced'):
            option=value.get(name)
            if option:lines.append(f"| {key} | {name} | {option['boundaries_max_molecule_heavy']} | {option['max_to_min_byte_ratio']:.3f} |")
    lines+=['','所有物理记录的 molecule maxNheavy 决定文件归属，同分子全部保留构象在一个文件。边界是建议，不改现有数据。','',
        '写回峰值表包括候选 LMDB value/页模型、仍在盘的解析数据、归档和400GB scratch/margin；现有原LMDB已计入账户已用量，不能重复加到新产物预算。明细见 storage_report.json。','',
        f"样本 {report['sample_records']} records、实际worker {len(report['actual_worker_pids'])}，问题记录 {report['records_with_issues']}。D3D采用原PM7坐标，未嵌入或优化。",'',
        'P数值按登记表去重复/共享方法单位元信息，新增可推导字段去除作为独立候选而非擅自删除；浮点仍float64，整型原值，缺失/空/零保持。相关 API 参数依据 [RDKit Descriptors3D](https://www.rdkit.org/docs/source/rdkit.Chem.Descriptors3D.html)、[ComputeMolVolume](https://www.rdkit.org/docs/source/rdkit.Chem.AllChem.html) 和 [rdFreeSASA](https://www.rdkit.org/docs/source/rdkit.Chem.rdFreeSASA.html)。']
    return '\n'.join(lines)+'\n'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workers',type=int,default=16)
    parser.add_argument('--registry',default=str(ROOT/'reports/label_registry.json'))
    parser.add_argument('--population',default=str(ROOT/'a_retained/population_by_stratum.json'))
    parser.add_argument('--quality',default=str(ROOT/'a_retained/relaxed_quality_annotations.parquet'))
    parser.add_argument('--output',default=str(ROOT/'c_engineering/storage'))
    parser.add_argument('--capacity',default=str(ROOT/'reports/resource_snapshot.json'));parser.add_argument('--check',action='store_true');args=parser.parse_args()
    if args.check:
        for path in (Path(__file__),Path(WIRE.__file__)):ast.parse(path.read_text())
        print(json.dumps({'status':'AST_PASS','LMDB_opened':False,'sample_serialized':False}));return 0
    if args.workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<args.workers:raise ValueError('16 effective allocated workers required')
    import pyarrow as pa,pyarrow.parquet as pq,duckdb
    output=Path(args.output).absolute()
    if output.exists() or not output.is_relative_to(ROOT/'c_engineering'):raise ValueError('Fresh own C4 analysis output required')
    output.mkdir(parents=True);start=time.monotonic();schema=WIRE.metadata();registry_bytes=Path(args.registry).read_bytes();registry=json.loads(registry_bytes)
    registry_sha=hashlib.sha256(registry_bytes).hexdigest();(output/'candidate_registry_snapshot.json').write_bytes(registry_bytes)
    entries=registry if isinstance(registry,list) else registry.get('entries',registry.get('labels'))
    if not entries:raise ValueError('Root B6 registry entries required')
    population=json.loads(Path(args.population).read_text());panel=pq.read_table(OLD/'wp4_native_panel/pilot_panel.parquet').to_pylist()
    db=duckdb.connect();db.execute(f'SET threads={args.workers}')
    db.register('C4_sample_keys',pa.table({'record_id':[row['record_id'] for row in panel]}))
    columns={row[0] for row in db.execute('DESCRIBE SELECT * FROM read_parquet(?)',[args.quality]).fetchall()}
    extras=[key for key in ('H01_abs_energy_per_atom','S01','S02_delta_energy_kcal_mol','B01','T01','reidentified_inchikey','member_train','member_full','member_routine') if key in columns]
    selected=db.execute('SELECT q.record_id,'+','.join('q.'+key for key in extras)+' FROM read_parquet(?) q JOIN C4_sample_keys s USING(record_id)',[args.quality]).fetchall()
    rows={row['record_id']:row for row in panel}
    if len(selected)!=len(panel):raise ValueError('MANIFEST_COUNT_MISMATCH_A_C4_SAMPLE')
    for record,*values in selected:rows[record].update(dict(zip(extras,values)))
    receipts=[]
    for path in sorted((OLD/'wp4_native_full_v4').rglob('receipt.json')):
        data=json.loads(path.read_text());ids=[row['record_id'] for row in panel if row['molecule_id']==data['molecule_id']]
        receipts.append((str(path),ids))
    if len(receipts)!=len({row['molecule_id'] for row in panel}) or sum(len(ids) for _,ids in receipts)!=len(panel):raise ValueError('MANIFEST_COUNT_MISMATCH_NATIVE_C4')
    plan=json.loads((AUDIT/'plan.json').read_text());context=multiprocessing.get_context('spawn');barrier=context.Barrier(args.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,initializer=init,
            initargs=(plan['sources'],entries,rows,barrier)) as pool:results=list(pool.map(task,receipts,chunksize=1))
    metrics=[row for result in results for row in result['rows']];groups=[row for result in results for row in result['task_groups']]
    pids=sorted({result['worker_pid'] for result in results})
    if len(metrics)!=len(panel):raise ValueError('MANIFEST_COUNT_MISMATCH_C4_OUTPUT')
    if len(pids)<16:raise ValueError('FEWER_THAN_16_ACTUAL_C4_WORKERS')
    metric_path=output/'sample_serialized_bytes.parquet';pq.write_table(pa.Table.from_pylist(metrics),metric_path,compression='zstd')
    if groups:pq.write_table(pa.Table.from_pylist(groups),output/'P_task_group_bytes.parquet',compression='zstd')
    pop={key:stratum_summary(metrics,population[key]) for key in ('strict','relaxed')}
    five={key:five_files(db,args.quality,metrics,key=='relaxed') for key in ('strict','relaxed')};db.close()
    for key,value in five.items():
        if value.get('population_records')!=population[key]['records'] or value.get('population_molecules')!=population[key]['molecules']:
            raise ValueError('MANIFEST_COUNT_MISMATCH_C4_FIVE_FILES')
    benchmark_path=OLD/'wp4_storage_benchmark/job_4513016/benchmark_summary.json'
    # This old benchmark may have been cleaned after exact metadata close;
    # use retained archive-scope report when the full TEST blobs are gone.
    archive_report_files=sorted((OLD/'wp4_archive_scope_projection').rglob('archive_scope_projection.json'))
    old_benchmark=json.loads(benchmark_path.read_text()) if benchmark_path.is_file() else None
    archive_report=json.loads(archive_report_files[-1].read_text()) if archive_report_files else None
    peaks=[];remaining=quota(args.capacity) if Path(args.capacity).is_file() else None
    native_pop=json.loads((OLD/'wp4_native_panel/pilot_panel_manifest.json').read_text())
    native_strata={row['size_stratum']:row for row in native_pop['strata']}
    for key in ('strict','relaxed'):
        total=pop[key]['total_estimated_bytes'];new_strata={row['size_stratum']:row for row in population[key]['strata']}
        def record_scale(stratum):return new_strata[stratum]['records']/native_strata[stratum]['population_records']
        def molecule_scale(stratum):return new_strata[stratum]['molecules']/native_strata[stratum]['population_molecules']
        parsed=None;parsed_hessian=None
        if old_benchmark:
            old_groups=old_benchmark['storage']['strata']
            fixed=old_benchmark['storage']['estimated_all_labels_recipes_and_manifest_bytes_full_hessian']-sum(
                row['estimated_all_conformer_typed_Parquet_bytes_excluding_hessian']+row['estimated_input_recipe_bytes']+
                row['estimated_source_reference_manifest_bytes']+row['estimated_minimum_hessian_typed_Parquet_bytes'] for row in old_groups)
            parsed=fixed+sum((row['estimated_all_conformer_typed_Parquet_bytes_excluding_hessian']+row['estimated_input_recipe_bytes'])*record_scale(row['size_stratum'])+
                (row['estimated_source_reference_manifest_bytes']+row['estimated_minimum_hessian_typed_Parquet_bytes'])*molecule_scale(row['size_stratum']) for row in old_groups)
            parsed_hessian=sum(row['estimated_minimum_hessian_typed_Parquet_bytes']*molecule_scale(row['size_stratum']) for row in old_groups)
        for size_field in ('all_registry_candidate_pickle5_bytes','all_registry_candidate_zstd3_bytes','per_record_4KiB_rounding_estimate_bytes'):
            raw_plans=archive_report['projection']['estimates'] if archive_report else []
            for scenario in raw_plans:
                if scenario['hessian_molecule_fraction'] not in (0,.1,1):continue
                archive=None
                if archive_report['projection']['complete']:
                    pack={row['size_stratum']:row['archive_pack_factor'] for row in archive_report['projection']['strata']}
                    calibrated=scenario['archive_model']=='EXPECTED_SAME_SIZE_PACK_FACTOR'
                    amount=0.0
                    for component in archive_report['projection']['task_components']:
                        stratum=component['size_stratum'];rw=record_scale(stratum);mw=molecule_scale(stratum)
                        if component['task']=='xtb_hessian':
                            contribution=component['full_minimum_percall_bytes']*mw*scenario['hessian_molecule_fraction']
                        elif scenario['policy']=='ALL_ORDINARY_SUCCESS_MINIMUM_ALL_FAILURES_KEPT' or component['task']=='pm7_B':
                            contribution=component['kept_all_failure_percall_bytes']*rw+component['kept_minimum_success_percall_bytes']*mw
                        else:contribution=component['baseline_percall_bytes']*rw
                        amount+=contribution*(pack[stratum] if calibrated else 1)
                    archive=amount
                ordinary_field={'all_registry_candidate_pickle5_bytes':'all_registry_nohessian_pickle5_bytes',
                    'all_registry_candidate_zstd3_bytes':'all_registry_nohessian_zstd3_bytes',
                    'per_record_4KiB_rounding_estimate_bytes':'nohessian_page_estimate_bytes'}[size_field]
                ordinary=total[ordinary_field];full=total[size_field];fraction=scenario['hessian_molecule_fraction']
                lmdb=ordinary+(full-ordinary)*fraction if ordinary is not None and full is not None else None
                parsed_subset=parsed-parsed_hessian*(1-fraction) if parsed is not None and parsed_hessian is not None else None
                peak=lmdb+parsed_subset+archive+400_000_000_000 if lmdb is not None and archive is not None and parsed_subset is not None else None
                peaks.append({'population':key,'value_format':size_field,'raw_policy':scenario['policy'],'raw_model':scenario['archive_model'],
                    'hessian_fraction':scenario['hessian_molecule_fraction'],'candidate_value_bytes':lmdb,'parsed_data_bytes':parsed_subset,
                    'archive_bytes':archive,'scratch_and_margin_bytes':400_000_000_000,'writeback_peak_forward_bytes':peak,
                    'remaining_account_bytes':remaining,'headroom_bytes':remaining-peak if remaining is not None and peak is not None else None,
                    'scope_limit':'Exact new seven-stratum record/minimum-molecule weights. Archive source is old WITH_POLAR full pilot; fresh C3 NOPOLAR calibration must be considered before choosing final raw retention. No duplicate backups assumed; owned batch atomic overlap included in scratch/margin.'})
    task_estimates=[]
    for population_key in ('strict','relaxed'):
        for stratum in population[population_key]['strata']:
            for name in {item['task'] for item in groups}:
                items=[item for item in groups if item['task']==name and item['size_stratum']==stratum['size_stratum']]
                sample_count=sum(row['size_stratum']==stratum['size_stratum'] for row in metrics)
                population_count=stratum['molecules'] if name=='xtb_hessian' else stratum['records']
                denominator=sum(row['size_stratum']==stratum['size_stratum'] for row in panel if row['molecule_lowest_energy_conformer']) if name=='xtb_hessian' else sample_count
                task_estimates.append({'population':population_key,'size_stratum':stratum['size_stratum'],'task':name,
                    'standalone_pickle5_estimated_bytes':sum(item['standalone_pickle5_bytes'] for item in items)/denominator*population_count if denominator else None,
                    'standalone_zstd3_estimated_bytes':sum(item['standalone_zstd3_bytes'] for item in items)/denominator*population_count if denominator else None,
                    'note':'Standalone group frame overhead counted; group sums do not equal jointly compressed full-record bytes.'})
    report={'status':'C4_CANDIDATE_SAMPLE_STORAGE_ANALYSIS_CLOSED','sample_records':len(metrics),'actual_worker_pids':pids,
        'job_id':os.environ['SLURM_JOB_ID'],'hostname':socket.gethostname(),'wire_schema':schema,'wire_script_sha256':sha(WIRE.__file__),
        'script_sha256':sha(__file__),'registry':{'path':args.registry,'sha256':registry_sha,'candidate_snapshot':str(output/'candidate_registry_snapshot.json'),'entries':entries},
        'population_manifest':{'path':args.population,'sha256':sha(args.population)},'populations':pop,'five_files':five,
        'P_task_group_projections':task_estimates,'writeback_peak_scenarios':peaks,'account_remaining_bytes':remaining,
        'source_Data_fields_examples':[result['original_Data_fields_example'] for result in results if result['original_Data_fields_example'] is not None][:3],
        'records_with_issues':sum(bool(row['issues']) for row in metrics),'issues':[{'record_id':row['record_id'],'issues':row['issues']} for row in metrics if row['issues']],
        'seconds':time.monotonic()-start,'sample_metrics':{'path':str(metric_path),'sha256':sha(metric_path),'bytes':metric_path.stat().st_size},
        'LMDB_options':{'readonly':True,'lock':False,'create':False},'lmdb_1_created':False,'original_data_written':False,
        'temporary_LMDB_created':False,'source_geometry_optimized':False,'formal_wire_schema_chosen':False,
        'archive_compression_large_sample':old_benchmark['storage']['strata'] if old_benchmark else None,
        'archive_note':'Full unique10020-record/1441-molecule closed archive evidence reused, larger than bounded155/32. C3 fresh NOPOLAR archives must be integrated separately, counting unique molecular identities independently of repeated benchmark rounds.'}
    save(output/'storage_report.json',report);(output/'storage_report.md').write_text(markdown(report),encoding='utf-8')
    print(json.dumps({'status':report['status'],'records':len(metrics),'records_with_issues':report['records_with_issues'],'seconds':report['seconds']}));return 0

if __name__=='__main__':raise SystemExit(main())
