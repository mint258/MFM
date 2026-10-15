"""Lossless typed WP4 storage prototype; read closed pilot outputs, never QM/LMDB.

Every original scientific value, status and QC is preserved, including missing
keys, null, empty containers, integer/float types and float64 signed zero.
Prototype files are TEST artifacts. No original result or archive is modified.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
import concurrent.futures
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import re
import socket
import struct
import sys
import time

ROOT = Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
DEPS = Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps')
CLOSED = {'COMPLETE_WITH_RECORDED_OUTCOMES', 'COMPLETE_WITH_RECORDED_OUTCOME'}
SHARED_FIELDS = ('argv', 'arguments', 'keywords', 'software_version_lines', 'job_id')
ROW_DETAIL = {key:key for key in (
    'record_id', 'molecule_id', 'conformer_id', 'split', 'size_stratum', 'natoms',
    'heavy_atoms', 'task', 'family', 'status', 'failure_code', 'failure_reason',
    'elapsed_seconds', 'qm_child_cpu_seconds', 'raw_total_bytes', 'aux_bytes',
    'Q01_gradient_norm_kcal_mol_A', 'Q02_delta_HOF_kcal_mol', 'qc_codes')}
ROW_DETAIL['source_payload_sha256'] = 'payload_sha256'
ROW_KEYS = tuple(sorted(ROW_DETAIL))
SPECS = SHARED = BASE_SCHEMA = OUTPUT = SOURCES = None


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def object_sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_json(path, value):
    path = Path(path)
    pending = path.with_name(path.name + '.pending')
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    pending.replace(path)


def modules():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ModuleNotFoundError:
        sys.path.insert(0, str(DEPS))
        import pyarrow as pa
        import pyarrow.parquet as pq
    return pa, pq


def init_worker(barrier, specs=None, shared=None, schema_bytes=None, output=None, sources=None):
    global SPECS, SHARED, BASE_SCHEMA, OUTPUT, SOURCES
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    pa, _ = modules()
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    SPECS, SHARED, OUTPUT, SOURCES = specs, shared, Path(output) if output else None, sources
    BASE_SCHEMA = pa.ipc.read_schema(pa.BufferReader(schema_bytes)) if schema_bytes else None
    # This initializes all requested processes; actual work PIDs are separately checked.
    barrier.wait(timeout=180)


def infer(value):
    if value is None: return {'k':'null'}
    if type(value) is bool: return {'k':'bool'}
    if type(value) is int:
        if not -(1 << 63) <= value < (1 << 63):
            raise ValueError('Integer outside int64; do not coerce or count compression as successful')
        return {'k':'int'}
    if type(value) is float:
        if not math.isfinite(value): raise ValueError('Nonfinite scientific float')
        return {'k':'float'}
    if type(value) is str: return {'k':'string'}
    if type(value) is list:
        child = {'k':'null'}
        for item in value: child = merge(child, infer(item))
        return {'k':'list', 'item':child}
    if type(value) is dict:
        if any(type(key) is not str for key in value): raise ValueError('Non-string JSON key')
        return {'k':'dict', 'fields':{key:infer(item) for key,item in value.items()}}
    raise TypeError('Unsupported parsed value type: ' + type(value).__name__)


def merge(left, right):
    if left['k'] == 'null': return right
    if right['k'] == 'null': return left
    if left['k'] == right['k'] and left['k'] != 'union':
        kind = left['k']
        if kind == 'dict':
            fields = dict(left['fields'])
            for key, value in right['fields'].items():
                fields[key] = merge(fields.get(key, {'k':'null'}), value)
            return {'k':'dict', 'fields':fields}
        if kind == 'list': return {'k':'list', 'item':merge(left['item'], right['item'])}
        return left
    variants = dict(left['variants']) if left['k'] == 'union' else {left['k']:left}
    other = right['variants'] if right['k'] == 'union' else {right['k']:right}
    for key,value in other.items(): variants[key] = merge(variants[key], value) if key in variants else value
    return {'k':'union', 'variants':variants}


def value_kind(value):
    return {bool:'bool', int:'int', float:'float', str:'string', list:'list', dict:'dict'}[type(value)]


def bitmap(keys, present):
    bits = bytearray((len(keys)+7)//8)
    for index,key in enumerate(keys):
        if key in present: bits[index//8] |= 1 << (index % 8)
    return bytes(bits)


def present_keys(keys, bits):
    if len(bits) != (len(keys)+7)//8: raise ValueError('Presence bitmap length differs')
    return [key for index,key in enumerate(keys) if bits[index//8] & (1 << (index % 8))]


def arrow_type(spec, pa):
    kind = spec['k']
    if kind in {'null','bool','int','float','string'}:
        return {'null':pa.null(), 'bool':pa.bool_(), 'int':pa.int64(), 'float':pa.float64(), 'string':pa.string()}[kind]
    if kind == 'list': return pa.list_(arrow_type(spec['item'], pa))
    if kind == 'dict':
        fields = [(key, arrow_type(spec['fields'][key], pa)) for key in sorted(spec['fields'])]
        if not fields: fields = [('_empty', pa.bool_())]
        return pa.struct([('present', pa.binary()), ('data', pa.struct(fields))])
    if kind == 'union':
        return pa.struct([('kind',pa.string())] + [(key,arrow_type(value,pa)) for key,value in sorted(spec['variants'].items())])
    raise ValueError(kind)


def encode(value, spec):
    if value is None: return None
    kind = spec['k']
    if kind == 'dict':
        keys = sorted(spec['fields'])
        if not isinstance(value, dict) or set(value)-set(keys): raise ValueError('Frozen dictionary schema differs')
        data = {key:encode(value.get(key), spec['fields'][key]) for key in keys} if keys else {'_empty':True}
        return {'present':bitmap(keys,value), 'data':data}
    if kind == 'list': return [encode(item,spec['item']) for item in value]
    if kind == 'union':
        selected = value_kind(value)
        if selected not in spec['variants']: raise ValueError('Frozen variant schema differs')
        return {'kind':selected, selected:encode(value,spec['variants'][selected])}
    if kind != value_kind(value): raise ValueError('Frozen scalar schema differs: '+kind)
    return value


def decode(value, spec):
    if value is None: return None
    kind = spec['k']
    if kind == 'dict':
        keys = sorted(spec['fields'])
        return {key:decode(value['data'][key],spec['fields'][key]) for key in present_keys(keys,value['present'])}
    if kind == 'list': return [decode(item,spec['item']) for item in value]
    if kind == 'union':
        selected = value['kind']
        return decode(value[selected],spec['variants'][selected])
    return value


def exact(original, restored, counts=None, path='$'):
    """Visit every leaf; compare original JSON type and float64 bit pattern."""
    if type(original) is not type(restored): raise ValueError('Roundtrip type differs at '+path)
    if counts is not None: counts[type(original).__name__] += 1
    if isinstance(original, dict):
        if original.keys() != restored.keys(): raise ValueError('Roundtrip keys differ at '+path)
        if counts is not None and not original: counts['empty_dict'] += 1
        for key in original: exact(original[key],restored[key],counts,path+'.'+key)
    elif isinstance(original, list):
        if len(original) != len(restored): raise ValueError('Roundtrip length differs at '+path)
        if counts is not None and not original: counts['empty_list'] += 1
        for index,(left,right) in enumerate(zip(original,restored)): exact(left,right,counts,path+'['+str(index)+']')
    elif type(original) is float:
        if struct.pack('>d',original) != struct.pack('>d',restored): raise ValueError('Roundtrip float64 bits differ at '+path)
        if counts is not None and original == 0:
            counts['float_negative_zero' if math.copysign(1,original)<0 else 'float_positive_zero'] += 1
    elif original != restored: raise ValueError('Roundtrip scalar differs at '+path)
    elif counts is not None and type(original) is int and original == 0: counts['int_zero'] += 1


def split_detail(row, detail):
    removed = {key for key in ROW_KEYS if key in detail}
    for key in removed:
        value = row.get(ROW_DETAIL[key]) if key != 'qc_codes' else detail[key]
        exact(detail[key], value, path='detail.'+key)
    shared = {key:detail[key] for key in SHARED_FIELDS if key in detail}
    remainder = {key:value for key,value in detail.items() if key not in removed and key not in SHARED_FIELDS and key != 'values'}
    return removed, shared, remainder


def load_closed(source):
    _, pq = modules()
    receipt = read_json(source['receipt_path'])
    if sha(source['receipt_path']) != source['receipt_sha256']: raise ValueError('Receipt changed')
    if receipt.get('status') not in CLOSED: raise ValueError('Source receipt is not closed')
    reference = receipt['parquet']
    if Path(reference['path']).stat().st_size != reference['bytes'] or sha(reference['path']) != reference['sha256']:
        raise ValueError('Source Parquet binding differs')
    rows = pq.read_table(reference['path'], use_threads=False).to_pylist()
    if len(rows) != receipt['requested_outcomes']: raise ValueError('Closed outcome count differs')
    slots = [(row['record_id'],row['task']) for row in rows]
    if len(set(slots)) != len(slots): raise ValueError('Duplicate final source outcome')
    return receipt, rows


def discover(source):
    receipt, rows = load_closed(source)
    values, operations, shared = {}, {}, {}
    records, tasks, strata = set(), Counter(), set()
    for row in rows:
        detail = json.loads(row['details_json'])
        removed, common, run = split_detail(row,detail)
        task = row['task']
        values[task] = merge(values.get(task,{'k':'null'}),infer(detail.get('values')))
        operations[task] = merge(operations.get(task,{'k':'null'}),infer(run))
        common_id = object_sha(common)
        shared[common_id] = common
        records.add(row['record_id']); tasks[task] += 1; strata.add(row['size_stratum'])
    if len(strata) != 1 or None in strata: raise ValueError('Molecule has mixed or absent size stratum')
    if len(records) != receipt['records']: raise ValueError('Receipt record count differs')
    return {'source_id':source['source_id'],'molecule_id':receipt['molecule_id'],'records':sorted(records),
        'minimum_record_id':receipt.get('minimum_original_energy_record_id'),'size_stratum':next(iter(strata)),
        'tasks':dict(tasks),'value_specs':values,'operation_specs':operations,'shared':shared,
        'worker_pid':os.getpid()}


def task_schema(task):
    pa,_ = modules()
    extra = [('qc_codes',pa.list_(pa.string())),('source_result_ref',pa.int64()),
        ('source_details_sha256',pa.binary(32)),('detail_row_present',pa.binary()),
        ('shared_provenance_ref',pa.binary(32)),('scientific_values_present',pa.bool_()),
        ('scientific_values',arrow_type(SPECS[task]['values'],pa)),
        ('run_detail',arrow_type(SPECS[task]['run_detail'],pa))]
    return pa.schema(list(BASE_SCHEMA)+[pa.field(name,type_) for name,type_ in extra],metadata={
        b'scope':b'TEST_LOSSLESS_STORAGE_PROTOTYPE_NO_LMDB',b'task':task.encode(),
        b'typed_schema_sha256':object_sha(SPECS[task]).encode()})


def physical_breakdown(path, rowgroup_strata):
    """Exact additive file bytes, attributing footer/schema overhead by data bytes."""
    _, pq = modules()
    meta = pq.ParquetFile(path).metadata
    if meta.num_row_groups != len(rowgroup_strata): raise ValueError('Row-group accounting differs')
    data, rows = Counter(), Counter()
    for index,key in enumerate(rowgroup_strata):
        group = meta.row_group(index)
        data[key] += sum(group.column(column).total_compressed_size for column in range(group.num_columns))
        rows[key] += group.num_rows
    size = Path(path).stat().st_size
    compressed = sum(data.values()); overhead = size-compressed
    if overhead < 0: raise ValueError('Physical Parquet column chunks exceed file size')
    denominator = compressed or sum(rows.values())
    allocated = {key:data[key]+overhead*(data[key] if compressed else rows[key])/denominator for key in rows}
    return {'bytes':size,'column_chunk_bytes':compressed,'footer_and_header_bytes':overhead,
        'allocated_bytes_by_stratum':allocated,'rows_by_stratum':dict(rows),
        'attribution':'Stratum-homogeneous row groups; physical footer/header bytes allocated by compressed column-chunk bytes.'}


def convert_chunk(item):
    pa,pq = modules()
    shard, selected, row_group_size, max_bytes = item
    started = time.monotonic(); directory = OUTPUT/'TEST_parquet'/('worker_'+str(shard).zfill(2))
    directory.mkdir(parents=True)
    writers, paths, buffers, buffer_strata, group_strata = {}, {}, defaultdict(list), {}, defaultdict(list)
    stats, archive_calls, units = Counter(), [], []
    schema_map = {task:task_schema(task) for task in SPECS}

    def flush(task):
        if not buffers[task]: return
        if task not in writers:
            path = directory/(task+'.parquet')
            paths[task] = path
            writers[task] = pq.ParquetWriter(path,schema_map[task],compression='zstd',compression_level=3,use_dictionary=True)
        table = pa.Table.from_pylist(buffers[task],schema=schema_map[task])
        writers[task].write_table(table,row_group_size=len(buffers[task]))
        group_strata[task].append(buffer_strata[task])
        buffers[task].clear()
        if sum(path.stat().st_size for path in paths.values()) > max_bytes:
            raise RuntimeError('Owned TEST per-worker output cap exceeded')

    try:
        for source in sorted(selected,key=lambda value:(value['size_stratum'],value['source_id'])):
            receipt, rows = load_closed(source)
            percall = 0; launched_outcomes = 0
            for row in rows:
                detail = json.loads(row['details_json']); task = row['task']; key = row['size_stratum']
                if buffers[task] and buffer_strata[task] != key: flush(task)
                removed, common, run = split_detail(row,detail)
                shared_id = object_sha(common)
                if shared_id not in SHARED: raise ValueError('Shared provenance differs after discovery')
                typed = {field.name:row[field.name] for field in BASE_SCHEMA}
                typed.update(qc_codes=detail.get('qc_codes'),source_result_ref=source['source_id'],
                    source_details_sha256=hashlib.sha256(row['details_json'].encode()).digest(),
                    detail_row_present=bitmap(ROW_KEYS,removed),shared_provenance_ref=bytes.fromhex(shared_id),
                    scientific_values_present='values' in detail,
                    scientific_values=encode(detail.get('values'),SPECS[task]['values']),
                    run_detail=encode(run,SPECS[task]['run_detail']))
                buffers[task].append(typed); buffer_strata[task] = key
                if len(buffers[task]) >= row_group_size: flush(task)
                archive = detail.get('archive')
                launched = bool(detail.get('argv')) and not row['status'].startswith(('SKIPPED_','Q03_SOURCE','NOT_STARTED_'))
                launched_outcomes += launched
                amount = archive.get('per_call_compressed_bytes',row.get('archive_bytes')) if archive else None
                if amount is not None:
                    if type(amount) is not int or amount < 0: raise ValueError('Invalid per-call compressed bytes')
                    percall += amount
                archive_calls.append({'size_stratum':key,'task':task,'record_id':row['record_id'],
                    'minimum':row['record_id']==receipt.get('minimum_original_energy_record_id'),
                    'status':row['status'],'launched':launched,'percall_bytes':amount,
                    'archive_present':archive is not None,'aux_archived':detail.get('aux_archived'),
                    'archived_file_names':[entry.get('name') for entry in detail.get('archived_files',[])]})
            archive = receipt.get('archive')
            if archive and Path(archive['path']).stat().st_size != archive['bytes']: raise ValueError('Closed archive size differs')
            units.append({'source_id':source['source_id'],'size_stratum':source['size_stratum'],
                'molecules':1,'records':receipt['records'],'slots':len(rows),'source_parquet_bytes':receipt['parquet']['bytes'],
                'closed_archive_bytes':archive['bytes'] if archive else (0 if launched_outcomes==0 else None),
                'percall_archive_bytes':percall,'launched_outcomes':launched_outcomes,
                'total_qm_attempts':receipt.get('total_qm_attempts'),
                'minimum_record_id':receipt.get('minimum_original_energy_record_id')})
        for task in list(buffers): flush(task)
    finally:
        for writer in writers.values(): writer.close()

    files = []
    # Re-read the original closed source, and recursively compare every scalar,
    # list item, dictionary key, QC and operational value with the written file.
    # At most one source molecule is cached per task; no AO arrays or LMDB read.
    for task,path in sorted(paths.items()):
        cached_id, originals = None, None
        for batch in pq.ParquetFile(path).iter_batches(batch_size=64,use_threads=False):
            for restored in batch.to_pylist():
                source_id = restored['source_result_ref']
                if source_id != cached_id:
                    _,source_rows = load_closed(SOURCES[source_id])
                    originals = {(row['record_id'],row['task']):row for row in source_rows}
                    cached_id = source_id
                original = originals[(restored['record_id'],restored['task'])]
                expected_detail = json.loads(original['details_json'])
                recovered = decode(restored['run_detail'],SPECS[task]['run_detail'])
                recovered.update(SHARED[restored['shared_provenance_ref'].hex()])
                for key in present_keys(ROW_KEYS,restored['detail_row_present']): recovered[key] = restored[ROW_DETAIL[key]]
                if restored['scientific_values_present']:
                    recovered['values'] = decode(restored['scientific_values'],SPECS[task]['values'])
                for field in BASE_SCHEMA: exact(original[field.name],restored[field.name],path='row.'+field.name)
                exact(expected_detail.get('values'),recovered.get('values'),stats,path='scientific_values')
                exact(expected_detail,recovered,path='full_detail')
                if restored['source_details_sha256'] != hashlib.sha256(original['details_json'].encode()).digest():
                    raise ValueError('Original details SHA reference differs')
                stats['rows_pass'] += 1
                stats['QC_cases_pass'] += 1
        info = physical_breakdown(path,group_strata[task])
        files.append({'path':str(path),'task':task,'sha256':sha(path),**info})
    if sum(file['bytes'] for file in files) > max_bytes: raise RuntimeError('Owned TEST output cap exceeded after close')
    return {'status':'ROUNDTRIP_PASS','shard':shard,'worker_pid':os.getpid(),'seconds':time.monotonic()-started,
        'roundtrip':dict(stats),'files':files,'units':units,'archive_calls':archive_calls}


def write_recipes(panel, output):
    pa,pq = modules()
    candidates = ('record_id','molecule_id','conformer_id','split','source_path','shard_id',
        'real_index','source_record_index','record_payload_sha256','sample_key','energy_raw',
        'size_stratum','retained_conformer_count','molecule_lowest_energy_conformer')
    columns = [key for key in candidates if key in panel.column_names]
    required = {'record_id','molecule_id','record_payload_sha256','size_stratum','molecule_lowest_energy_conformer'}
    if not required <= set(columns): raise ValueError('Panel lacks input reconstruction identity')
    if 'source_path' not in columns or not {'real_index','source_record_index'} & set(columns):
        raise ValueError('Panel lacks exact source location/index for reconstruction recipe')
    schema = pa.schema([panel.schema.field(key) for key in columns])
    rows = panel.select(columns).to_pylist(); group_strata = []
    path = output/'TEST_input_recipes.parquet'
    with pq.ParquetWriter(path,schema,compression='zstd',compression_level=3) as writer:
        for key in sorted({row['size_stratum'] for row in rows}):
            group = [row for row in rows if row['size_stratum']==key]
            writer.write_table(pa.Table.from_pylist(group,schema=schema),row_group_size=len(group))
            group_strata.append(key)
    expected = {row['record_id']:row for row in rows}
    for recovered in pq.read_table(path).to_pylist(): exact(expected[recovered['record_id']],recovered,path='input_recipe')
    return {'path':str(path),'sha256':sha(path),'columns':columns,'roundtrip_rows_pass':len(rows),
        **physical_breakdown(path,group_strata)}


def quota(snapshot):
    raw = read_json(snapshot); entry = raw.get('quota',{})
    if entry.get('exit_code',entry.get('rc')) != 0: return {'remaining_bytes':None,'reason':'Quota query unavailable'}
    for line in entry.get('stdout','').splitlines():
        tokens = line.split()
        if len(tokens) < 4 or not tokens[0].startswith('/'): continue
        try: used,soft,hard = [int(item.rstrip('*')) for item in tokens[1:4]]
        except ValueError: continue
        limits = [value for value in (soft,hard) if value>0]
        remaining = (min(limits)-used)*1024 if limits else None
        return {'snapshot':str(snapshot),'sha256':sha(snapshot),'time_UTC':raw.get('time_UTC'),
            'used_KiB':used,'soft_KiB':soft,'hard_KiB':hard,'remaining_bytes':remaining,
            'budget_bytes':min(2_000_000_000_000,remaining) if remaining is not None else None}
    return {'remaining_bytes':None,'reason':'Quota line could not be parsed'}


def storage_report(manifest, chunks, source_refs, prototype_manifest, recipe, shared_constant_bytes, quota_info):
    weights = {row['size_stratum']:row for row in manifest['strata']}
    files = [file for chunk in chunks for file in chunk['files']]
    units = [unit for chunk in chunks for unit in chunk['units']]
    calls = [call for chunk in chunks for call in chunk['archive_calls']]
    groups = []
    for key,weight in weights.items():
        group = [unit for unit in units if unit['size_stratum']==key]
        selected_calls = [call for call in calls if call['size_stratum']==key]
        old = sum(unit['source_parquet_bytes'] for unit in group)
        typed = sum(file['allocated_bytes_by_stratum'].get(key,0) for file in files)
        recipe_bytes = recipe['allocated_bytes_by_stratum'].get(key,0)
        hess_bytes = sum(file['allocated_bytes_by_stratum'].get(key,0) for file in files if file['task']=='xtb_hessian')
        archives = sum(unit['closed_archive_bytes'] or 0 for unit in group)
        percall = sum(unit['percall_archive_bytes'] for unit in group)
        missing = [call for call in selected_calls if call['launched'] and call['percall_bytes'] is None]
        calibration_complete = all(unit['closed_archive_bytes'] is not None for unit in group) and not missing
        pack = archives/percall if percall and calibration_complete else None
        rw, mw = weight['record_population_weight'], weight['molecule_population_weight']
        reference_bytes = sum(len(canonical(source_refs[unit['source_id']]).encode())+2 for unit in group)
        reference_estimate = reference_bytes*mw
        baseline_nonhess = sum((call['percall_bytes'] or 0) for call in selected_calls if call['task']!='xtb_hessian')*rw
        hessian = sum((call['percall_bytes'] or 0) for call in selected_calls if call['task']=='xtb_hessian')*mw
        b_success = [call for call in selected_calls if call['task']=='pm7_B' and call['status']=='SUCCESS']
        b_minimum = [call for call in b_success if call['minimum']]
        b_failure = [call for call in selected_calls if call['task']=='pm7_B' and call['status']!='SUCCESS']
        removed_all_success = sum((call['percall_bytes'] or 0) for call in b_success)*rw
        kept_minimum_success = sum((call['percall_bytes'] or 0) for call in b_minimum)*mw
        kept_failed = sum((call['percall_bytes'] or 0) for call in b_failure)*rw
        kept_nonhess = baseline_nonhess-removed_all_success+kept_minimum_success
        all_minima_known = all(unit['minimum_record_id'] is not None for unit in group)
        nonmin_success_out_missing = sum('input.out' not in call['archived_file_names'] for call in b_minimum)
        complete = calibration_complete and all_minima_known and not nonmin_success_out_missing
        groups.append({'size_stratum':key,'sample_molecules':len(group),'sample_records':sum(unit['records'] for unit in group),
            'population_records':weight['population_records'],'population_molecules':weight['population_molecules'],
            'record_population_weight':rw,'molecule_population_weight':mw,
            'observed_old_json_Parquet_bytes':old,'observed_TEST_typed_Parquet_bytes':typed,
            'observed_ratio_typed_to_old':typed/old if old else None,
            'observed_closed_archive_bytes':archives,'observed_percall_compressed_bytes':percall,
            'archive_pack_factor':pack,'archive_complete':complete,'missing_archive_measurements':len(missing),
            'missing_success_minimum_full_out':nonmin_success_out_missing,
            'historical_attempts_beyond_final_slots':sum(unit['total_qm_attempts']-unit['launched_outcomes'] for unit in group)
                if all(unit['total_qm_attempts'] is not None for unit in group) else None,
            'estimated_all_conformer_typed_Parquet_bytes_excluding_hessian':(typed-hess_bytes)*rw,
            'estimated_minimum_hessian_typed_Parquet_bytes':hess_bytes*mw,
            'estimated_input_recipe_bytes':recipe_bytes*rw,
            'estimated_source_reference_manifest_bytes':reference_estimate,
            'estimated_B_failed_kept_percall_bytes':kept_failed if complete else None,
            'estimated_B_success_minimum_kept_percall_bytes':kept_minimum_success if complete else None,
            'sample_B_success':len(b_success),'sample_B_success_minimum':len(b_minimum),'sample_B_nonSUCCESS':len(b_failure),
            'expected_baseline_archive_bytes_excluding_hessian':baseline_nonhess*pack if complete else None,
            'expected_policy_archive_bytes_excluding_hessian':kept_nonhess*pack if complete else None,
            'conservative_policy_percall_compressed_bytes_excluding_hessian':kept_nonhess if complete else None,
            'expected_saved_archive_bytes':(removed_all_success-kept_minimum_success)*pack if complete else None,
            'conservative_model_saved_percall_bytes':removed_all_success-kept_minimum_success if complete else None,
            'expected_hessian_full_minimum_archive_bytes':hessian*pack if complete else None,
            'conservative_hessian_full_minimum_percall_bytes':hessian if complete else None})
    complete = all(group['archive_complete'] for group in groups)
    base_typed = sum(group['estimated_all_conformer_typed_Parquet_bytes_excluding_hessian'] for group in groups)
    hess_typed = sum(group['estimated_minimum_hessian_typed_Parquet_bytes'] for group in groups)
    recipe_estimate = sum(group['estimated_input_recipe_bytes'] for group in groups)
    references = sum(group['estimated_source_reference_manifest_bytes'] for group in groups)
    label_total = base_typed+hess_typed+recipe_estimate+references+shared_constant_bytes
    expected_raw = sum(group['expected_policy_archive_bytes_excluding_hessian'] for group in groups) if complete else None
    conservative_raw = sum(group['conservative_policy_percall_compressed_bytes_excluding_hessian'] for group in groups) if complete else None
    expected_hess = sum(group['expected_hessian_full_minimum_archive_bytes'] for group in groups) if complete else None
    conservative_hess = sum(group['conservative_hessian_full_minimum_percall_bytes'] for group in groups) if complete else None
    budget = quota_info.get('budget_bytes')
    plans = []
    for fraction in (0,.001,.01,.05,.1,1):
        parsed = base_typed+hess_typed*fraction+recipe_estimate+references+shared_constant_bytes
        for name, raw, hessian in (('EXPECTED_SAME_PACK_FACTOR',expected_raw,expected_hess),
                                  ('CONSERVATIVE_SUM_OF_PER_CALL_COMPRESSED_BYTES',conservative_raw,conservative_hess)):
            archive = raw+hessian*fraction if complete else None
            total = parsed+archive+1_000_000_000_000 if archive is not None else None
            plans.append({'model':name,'hessian_molecule_fraction':fraction,'parsed_labels_and_provenance_bytes':parsed,
                'archive_bytes':archive,'lmdb_reservation_bytes':600_000_000_000,
                'scratch_and_margin_reservation_bytes':400_000_000_000,'total_forward_bytes':total,
                'actual_remaining_account_budget_bytes':budget,'headroom_bytes':budget-total if total is not None and budget is not None else None,
                'fits_account_budget':total<=budget if total is not None and budget is not None else None,
                'fits_200GB_parsed_label_budget':parsed<=200_000_000_000,
                'fits_800GB_archive_budget':archive<=800_000_000_000 if archive is not None else None})
    return {'scope':'ALL_NATIVE_SCIENTIFIC_LABELS_RETAINED_ALL_CONFORMERS',
        'strata':groups,'prototype_files':files,'observed_typed_Parquet_bytes':sum(file['bytes'] for file in files),
        'observed_source_Parquet_bytes':sum(unit['source_parquet_bytes'] for unit in units),
        'observed_prototype_manifest_bytes':prototype_manifest.stat().st_size,
        'estimated_all_labels_recipes_and_manifest_bytes_full_hessian':label_total,
        'estimated_expected_saved_archive_bytes':sum(group['expected_saved_archive_bytes'] for group in groups) if complete else None,
        'estimated_expected_baseline_archive_bytes_excluding_hessian':sum(group['expected_baseline_archive_bytes_excluding_hessian'] for group in groups) if complete else None,
        'expected_archive_estimate_complete':complete,'budget_plans':plans,
        'raw_policy':'Keep all scientific values and QC for every native task. Keep every unsuccessful B full existing output; keep successful original-minimum B full existing output; other successful B need only parsed values and exact input reconstruction recipe. C/D/xTB retention unchanged.',
        'minimum_success_B_policy_is_conservative':'Entire existing minimum-success B per-call archive, including available stdout/AUX, is retained in the estimate. This covers the requested full .out and avoids inventing isolated .out compressed sizes.',
        'calibration_limit':'Expected archive volumes apply the original per-stratum closed/per-call pack factor. Filtering B changes cross-call compression; this is an expectation, not measured repacking. Separate direct per-call sums remove dependence on that factor, but are a conservative planning model, not a mathematical bound on arbitrary future compression/framing.',
        'historical_attempts':'Any historical attempt bytes in the closed archive are included in the pack factor. Their allocation to retained tasks is not directly observed.',
        'Parquet_estimation':'Non-hessian task shards and input recipes use record weights; minimum-only Hessian task shards and per-molecule source references use molecule weights. File overhead is included. Fixed shared schema/config/provenance manifest is counted once.',
        'units':'All GB/TB decimal; estimates are projections of the formal seven-stratum whole-molecule panel.'}


def markdown(summary):
    report = summary.get('storage')
    if report is None:
        return '存储规整基准未通过，不能报告成功压缩或全量存储投影。\n\n'+canonical(summary.get('issues',[]))+'\n'
    def gb(value): return '待测' if value is None else f'{value/1e9:.3f}'
    lines = ['全部原生科学标签保留；typed TEST Parquet 及完整科学值往返检查已通过。', '',
        f"正式 pilot：{summary['records']:,} records / {summary['molecules']:,} molecules / {summary['slots']:,} outcomes；有效转换 worker {len(summary['actual_conversion_worker_pids'])}。", '',
        f"pilot 原 JSON Parquet {gb(report['observed_source_Parquet_bytes'])} GB → typed TEST {gb(report['observed_typed_Parquet_bytes'])} GB。含全部最低能 Hessian、输入重建 recipe 和 provenance 的全量解析存储估计 {gb(report['estimated_all_labels_recipes_and_manifest_bytes_full_hessian'])} GB。", '',
        f"成功 B 仅保留原最低能构象完整输出、失败 B 全保留，预计归档节省 {gb(report['estimated_expected_saved_archive_bytes'])} GB。未改变任何原始归档。", '',
        'GB/TB 使用十进制；600 GB LMDB 与 400 GB scratch/margin 是预留。', '',
        '| Hessian 分子比例 | 归档模型 | 解析+来源 GB | 归档 GB | 含预留总 TB | 配额余量 GB | 满足配额 |',
        '|---|---|---:|---:|---:|---:|---|']
    for plan in report['budget_plans']:
        label = '原 pack factor 期望' if plan['model'].startswith('EXPECTED') else 'per-call 相加保守估计'
        lines.append(f"| {plan['hessian_molecule_fraction']:.3g} | {label} | {gb(plan['parsed_labels_and_provenance_bytes'])} | {gb(plan['archive_bytes'])} | {'待测' if plan['total_forward_bytes'] is None else format(plan['total_forward_bytes']/1e12,'.3f')} | {gb(plan['headroom_bytes'])} | {plan['fits_account_budget']} |")
    lines += ['', '| 大小层 | 原 pilot Parquet GB | typed pilot GB | 比率 | pack factor | 期望省归档 GB |',
        '|---|---:|---:|---:|---:|---:|']
    for group in report['strata']:
        lines.append(f"| {group['size_stratum']} | {gb(group['observed_old_json_Parquet_bytes'])} | {gb(group['observed_TEST_typed_Parquet_bytes'])} | {group['observed_ratio_typed_to_old']:.4f} | {'待测' if group['archive_pack_factor'] is None else format(group['archive_pack_factor'],'.4f')} | {gb(group['expected_saved_archive_bytes'])} |")
    lines += ['', '科学检查逐叶比较 float64 原始位模式及整数类型/值；缺键、null、空列表、真实零、原生 POLAR 不对称和全部 QC 保持。完整 detail 也已重建比较，原结果 Parquet SHA 与每行 details SHA 可追溯。', '',
        '归档仅为估算：选择后 pack factor 可能改变，因此同时列出直接 per-call 压缩字节相加的保守规划值。最低能成功 B 按 molecule 权重；全构象失败 B、C/D、非 Hessian xTB 按 record 权重。', '',
        '详细分层、字段 schema、每分片 SHA、来源引用、逐项检查计数及缺失见 benchmark_summary.json 和 prototype_manifest.json。']
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panel-manifest',default=str(ROOT/'wp4_native_panel/pilot_panel_manifest.json'))
    parser.add_argument('--native-root',action='append',default=None)
    parser.add_argument('--capacity',default=str(ROOT/'reports/wp5_capacity_snapshot.json'))
    parser.add_argument('--output',required=False)
    parser.add_argument('--workers',type=int,default=16)
    parser.add_argument('--row-group-size',type=int,default=512)
    parser.add_argument('--max-output-bytes',type=int,default=4_000_000_000)
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    if args.check:
        ast.parse(Path(__file__).read_text())
        print(json.dumps({'status':'AST_PASS','data_read':False,'QM_started':False,'LMDB_opened_or_written':False}))
        return 0
    if args.workers < 16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0')) < args.workers:
        raise RuntimeError('Slurm allocation and at least 16 actual workers required')
    if args.row_group_size < 1: raise ValueError('Positive row group size required')
    if not args.output: raise ValueError('New TEST --output directory required')
    output = Path(args.output).absolute()
    if not output.is_relative_to(ROOT) or output == ROOT or output.exists():
        raise ValueError('Use a new independent TEST directory under this phase root')
    roots = [Path(path).absolute() for path in (args.native_root or [ROOT/'wp4_native_full_v4'])]
    if any(output.is_relative_to(path) or path.is_relative_to(output) for path in roots):
        raise ValueError('TEST output must be disjoint from original pilot input')
    pa,pq = modules(); pa.set_cpu_count(args.workers); pa.set_io_thread_count(min(8,args.workers))
    started = time.monotonic(); manifest_path = Path(args.panel_manifest)
    manifest = read_json(manifest_path)
    if manifest.get('target_records',0) < 10000 or not manifest.get('all_retained_conformers_of_each_selected_molecule') or manifest.get('status') != 'READY_FOR_NATIVE_WP4':
        raise ValueError('Formal genuine whole-molecule WP4 panel required; bounded/synthetic cannot extrapolate')
    panel_path = Path(manifest['output']); panel_sha = sha(panel_path); manifest_sha = sha(manifest_path)
    panel = pq.read_table(panel_path); panel_rows = panel.to_pylist()
    record_map = {row['record_id']:row for row in panel_rows}
    if len(record_map) != len(panel_rows) or len(panel_rows) != manifest['actual_records']: raise ValueError('Panel identity/count differs')
    molecules = defaultdict(list)
    for row in panel_rows: molecules[row['molecule_id']].append(row)
    if len(molecules) != manifest['molecules']: raise ValueError('Panel molecule count differs')
    metadata_refs, sources = [], []
    for root in roots:
        metadatas = sorted(root.rglob('metadata.json'))
        for path in metadatas:
            data = read_json(path); binding = data.get('input_and_implementation_binding',{})
            if binding.get('panel_sha256') != panel_sha or binding.get('panel_manifest_sha256') != manifest_sha:
                raise ValueError('Native panel SHA binding differs: '+str(path))
            metadata_refs.append({'path':str(path),'sha256':sha(path),'data':data})
        for path in sorted(root.rglob('receipt.json')):
            receipt = read_json(path)
            if receipt.get('status') not in CLOSED: raise ValueError('Partial source found: '+str(path))
            sources.append({'source_id':len(sources),'receipt_path':str(path),'receipt_sha256':sha(path),
                'parquet':receipt['parquet'],'archive':receipt.get('archive'),'molecule_id':receipt['molecule_id'],
                'minimum_original_energy_record_id':receipt.get('minimum_original_energy_record_id'),
                'input_identity_sha256':receipt['input_identity_sha256']})
    if not metadata_refs or len(sources) != len(molecules) or len({source['molecule_id'] for source in sources}) != len(sources):
        raise ValueError('Exactly one closed receipt per formal molecule required')
    output.mkdir(); (output/'TEST_parquet').mkdir()
    summary = {'status':'RUNNING','scope':'TEST_LOSSLESS_STORAGE_BENCHMARK_NOT_FORMAL_DATASET',
        'job_id':os.environ.get('SLURM_JOB_ID'),'hostname':socket.gethostname(),'python_logical_entry':sys.executable,
        'script':str(Path(__file__).absolute()),'script_sha256':sha(__file__),'requested_workers':args.workers,
        'output_limit_bytes':args.max_output_bytes,'QM_started':False,'LMDB_opened_or_written':False,
        'original_results_modified':False,'original_raw_modified_or_deleted':False,'issues':[]}
    save_json(output/'benchmark_summary.json',summary)
    context = multiprocessing.get_context('spawn')
    barrier = context.Barrier(args.workers)
    print(json.dumps({'stage':'DISCOVER_FIXED_TYPED_SCHEMAS','closed_molecules':len(sources),'workers':args.workers}),flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,
            initializer=init_worker,initargs=(barrier,)) as pool:
        discovered = list(pool.map(discover,sources,chunksize=1))
    effective_discovery = sorted({entry['worker_pid'] for entry in discovered})
    if len(effective_discovery) < 16: raise RuntimeError('Fewer than 16 actual scientific discovery workers')
    specs, shared = {}, {}
    for entry in discovered:
        expected = molecules[entry['molecule_id']]
        if set(entry['records']) != {row['record_id'] for row in expected}: raise ValueError('Closed molecule differs from formal panel')
        minima = [row['record_id'] for row in expected if row['molecule_lowest_energy_conformer']]
        if len(minima) != 1 or entry['minimum_record_id'] != minima[0]: raise ValueError('Original energy minimum binding differs')
        for task,count in entry['tasks'].items():
            if count != (1 if task=='xtb_hessian' else len(expected)): raise ValueError('Requested task outcome count differs')
            specs.setdefault(task,{'values':{'k':'null'},'run_detail':{'k':'null'}})
            specs[task]['values'] = merge(specs[task]['values'],entry['value_specs'][task])
            specs[task]['run_detail'] = merge(specs[task]['run_detail'],entry['operation_specs'][task])
        for key,value in entry['shared'].items():
            if key in shared: exact(shared[key],value,path='shared provenance')
            shared[key] = value
        source = sources[entry['source_id']]
        source.update(size_stratum=entry['size_stratum'],record_ids=entry['records'],task_counts=entry['tasks'])
    expected_tasks = {task['name'] for task in metadata_refs[0]['data']['config']['tasks']} | {'xtb_hessian'}
    if set(specs) != expected_tasks or any(set(entry['tasks']) != expected_tasks for entry in discovered):
        raise ValueError('Native task slot set differs')
    base_schema = pq.read_schema(sources[0]['parquet']['path'])
    base_schema = pa.schema([field for field in base_schema if field.name!='details_json'])
    recipe = write_recipes(panel,output)
    reconstruct = {
        'source':'TEST_input_recipes.parquet source_path plus real_index/source_record_index; original LMDB is not opened by this benchmark.',
        'payload_check':'Require recorded record_payload_sha256 before reading fields; native x encodes atomic_number-1, pos Angstrom, unchanged atom order.',
        'geometry_check':'run_detail native_coordinates_sha256/atom_order_sha256 bind original geometry; retain both hashes. Native coords are never optimized.',
        'mopac_input':'Exact per-task keywords from shared provenance; native .mop title=record_id; coordinates formatted .12f with optimizer flags 1; header Stored native PM7 coordinates; single point, no optimization. 1SCF and THREADS=1 are part of recorded keywords.',
        'xtb_input':'Task args/xcontrol/executable/environment are in native metadata/config; input.xyz native coordinate .12f formatting. Perturbation task retains positions_A, elements, perturb_seed and sigma in scientific values.',
        'reconstruction_is_not_rerun_authorization':True}
    prototype = {'scope':'TEST_FIXED_TYPED_NATIVE_LABEL_STORAGE_PROTOTYPE','panel':{'path':str(panel_path),'sha256':panel_sha},
        'formal_manifest':{'path':str(manifest_path),'sha256':manifest_sha,'data':manifest},
        'task_schemas':specs,'row_detail_mapping':ROW_DETAIL,'row_detail_bitmap_keys':ROW_KEYS,
        'shared_provenance_by_sha256':shared,'native_metadata':metadata_refs,
        'source_results':sources,'input_recipe':recipe,'input_reconstruction_recipe':reconstruct,
        'types':'Float64 unchanged; int64 unchanged; fields with both int and float use tagged typed structs rather than float coercion. Dict presence bitmaps retain absent vs null; lists retain empty vs null. No scientific JSON column.',
        'roundtrip_status':'PENDING'}
    proto_path = output/'prototype_manifest.json'
    save_json(proto_path,prototype)
    # Fixed schemas/config/provenance counted once; per-molecule original-result
    # references separately use the formal molecule population weight.
    fixed = {key:value for key,value in prototype.items() if key not in {'source_results','input_recipe'}}
    fixed['formal_manifest'] = prototype['formal_manifest']
    shared_constant_bytes = len(json.dumps(fixed,indent=2,ensure_ascii=False,allow_nan=False).encode())
    ordered = sorted(sources,key=lambda value:(value['size_stratum'],value['parquet']['bytes']),reverse=True)
    selections, loads = [[] for _ in range(args.workers)], [0]*args.workers
    for source in ordered:
        target = min(range(args.workers),key=lambda index:loads[index])
        selections[target].append(source); loads[target] += source['parquet']['bytes']
    barrier = context.Barrier(args.workers)
    arguments = [(index,selection,args.row_group_size,args.max_output_bytes//args.workers) for index,selection in enumerate(selections)]
    print(json.dumps({'stage':'WRITE_AND_EXACT_ROUNDTRIP','tasks':len(specs),'shards':args.workers,
        'maximum_Parquet_files':len(specs)*args.workers,'source_Parquet_bytes':sum(loads)}),flush=True)
    chunks = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,
            initializer=init_worker,initargs=(barrier,specs,shared,base_schema.serialize().to_pybytes(),str(output),sources)) as pool:
        pending = {pool.submit(convert_chunk,item):item[0] for item in arguments}
        for future in concurrent.futures.as_completed(pending):
            shard = pending[future]
            try:
                result = future.result(); chunks.append(result)
                save_json(output/('worker_'+str(shard).zfill(2)+'_receipt.json'),{key:value for key,value in result.items() if key!='archive_calls'})
                print(json.dumps({'stage':'SHARD_ROUNDTRIP_PASS','shard':shard,'worker_pid':result['worker_pid'],
                    'rows':result['roundtrip']['rows_pass'],'seconds':result['seconds']}),flush=True)
            except Exception as exc:
                summary['issues'].append({'shard':shard,'error':type(exc).__name__+': '+str(exc),'counts_as_successful_compression':False})
    summary.update(actual_discovery_worker_pids=effective_discovery,
        actual_conversion_worker_pids=sorted({chunk['worker_pid'] for chunk in chunks}),
        records=len(panel_rows),molecules=len(molecules),slots=sum(sum(entry['tasks'].values()) for entry in discovered))
    if len(summary['actual_conversion_worker_pids']) < 16:
        summary['issues'].append({'error':'Fewer than 16 actual conversion/validation workers','counts_as_successful_compression':False})
    checks = Counter()
    for chunk in chunks: checks.update(chunk['roundtrip'])
    summary['roundtrip'] = dict(checks)
    if checks['rows_pass'] != summary['slots']: summary['issues'].append({'error':'Not every original outcome passed exact roundtrip'})
    if summary['issues']:
        summary['status'] = 'FAILED_NO_VALID_FULL_COMPRESSION_ESTIMATE'; summary['storage'] = None
    else:
        prototype['roundtrip_status'] = 'ALL_SCIENTIFIC_AND_FULL_DETAIL_LEAVES_EXACT_PASS'
        prototype['roundtrip'] = dict(checks)
        prototype['output_files'] = [{key:file[key] for key in ('path','task','sha256','bytes')} for chunk in chunks for file in chunk['files']]
        save_json(proto_path,prototype)
        quota_info = quota(args.capacity) if Path(args.capacity).is_file() else {'remaining_bytes':None,'reason':'Capacity snapshot absent'}
        summary['quota'] = quota_info
        summary['storage'] = storage_report(manifest,chunks,sources,proto_path,recipe,shared_constant_bytes,quota_info)
        summary['status'] = 'TEST_LOSSLESS_STORAGE_BENCHMARK_COMPLETE'
    summary['seconds'] = time.monotonic()-started
    summary['own_output_bytes'] = sum(path.stat().st_size for path in output.rglob('*') if path.is_file())
    if summary['own_output_bytes'] > args.max_output_bytes:
        summary['issues'].append({'error':'Total TEST output cap exceeded; no originals modified'})
        summary['status'] = 'FAILED_NO_VALID_FULL_COMPRESSION_ESTIMATE'; summary['storage'] = None
    save_json(output/'benchmark_summary.json',summary)
    (output/'storage_benchmark.md').write_text(markdown(summary),encoding='utf-8')
    print(json.dumps({'status':summary['status'],'output':str(output),'seconds':summary['seconds'],
        'roundtrip_rows':checks['rows_pass'],'issues':summary['issues']}),flush=True)
    return 0 if not summary['issues'] else 1


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    raise SystemExit(main())
