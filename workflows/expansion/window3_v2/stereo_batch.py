"""Metadata selection and source-status schema evolution for the stereo supplement.

Reads original source_status as the new population input, never numerical D20,
D3 or geometry. Original Parquet remains immutable. D20 references are reused.
"""
import argparse
import collections
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import uuid

from .capacity import protect
from .kernel import molecule_id
from .producer import read, save
from .stereo import defaults, FIELDS

OLD_STATE = 'STEREO_REFERENCE_UNAVAILABLE_NO_PM7'
EXPECTED = 1285342


def status_tables(files, workers, with_reference=False):
    """Bounded metadata-only prefetch, preserving the original manifest order."""
    import pyarrow.parquet as pq
    references = iter(r for r in files if Path(r['path']).name == 'source_status.parquet')
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = collections.deque()
        def submit():
            ref = next(references, None)
            if ref is not None:
                pending.append((ref,pool.submit(pq.read_table, ref['path'], use_threads=False)))
                return True
            return False
        for _ in range(workers * 2):
            if not submit(): break
        while pending:
            ref,future = pending.popleft()
            table = future.result()
            submit()
            yield (ref,table) if with_reference else table


def preparation_failure(row):
    """Only these v3 paths returned before any embedding/UFF invocation."""
    return (row['state'] == OLD_STATE or
        (row['state'] == 'SOURCE_INTEGRITY_HOLD' and row.get('error') ==
         'IntegrityError: POTENTIAL_DOUBLE_WITHOUT_STEREO_REFERENCES'))


def prepare_repair(config):
    import pyarrow.parquet as pq
    protect(config)
    root=Path(config['output']);root.mkdir(parents=True,exist_ok=True)
    ready=root/'prepared.json'
    if ready.exists():return read(ready)
    folder=root/('prepare_'+uuid.uuid4().hex);folder.mkdir()
    files=read(Path(config['base_output'])/'manifest.json')
    summary=read(Path(config['base_output'])/'summary.json')
    registered={r['path'] for r in files}
    parts=[]; selected=total=part_rows=0; stream=None
    superseded_cip,superseded_ez=collections.Counter(),collections.Counter()
    for ref,table in status_tables(files,config.get('metadata_readers',4),with_reference=True):
        protect(config)
        chosen=[]
        for row in table.to_pylist():
            total+=1
            if not preparation_failure(row):continue
            if row['actual_conformers'] != 0:
                raise ValueError('PREPARATION_REPAIR_WOULD_RECOMPUTE_EXISTING_GEOMETRY')
            chosen.append(row['molecule_id'])
            if stream is None or part_rows>=20000:
                if stream is not None:
                    stream.close();parts[-1].update(size=Path(parts[-1]['path']).stat().st_size,rows=part_rows)
                path=folder/('stereo_source_%04d.jsonl'%len(parts))
                stream=path.open('x');part_rows=0;parts.append(dict(path=str(path)))
            stream.write(json.dumps(source_from_status(row),allow_nan=False)+'\n')
            part_rows+=1;selected+=1
        if chosen:
            # R/S and E/Z are producer metadata, not D20/D3 or coordinate reads.
            timing=str(Path(ref['path']).with_name('timings.parquet'))
            if timing not in registered:raise ValueError('PREPARATION_TIMING_METADATA_MISSING')
            chosen=set(chosen)
            for row in pq.read_table(timing,columns=['molecule_id','assigned_CIP_counts_json','assigned_EZ_counts_json']).to_pylist():
                if row['molecule_id'] in chosen:
                    superseded_cip.update(json.loads(row['assigned_CIP_counts_json']))
                    superseded_ez.update(json.loads(row['assigned_EZ_counts_json']))
    if stream is not None:
        stream.close();parts[-1].update(size=Path(parts[-1]['path']).stat().st_size,rows=part_rows)
    if total!=summary['counts']['molecules']:
        raise ValueError('CLOSED_BASE_SHARD_METADATA_COUNT_DIFFERS')
    result=dict(stereo_source_parts=parts,stereo_molecules=selected,base_output=config['base_output'],
        original_scope_rows=total,superseded_CIP=dict(superseded_cip),superseded_EZ=dict(superseded_ez),
        policy='ONLY_KNOWN_ZERO_EMBEDDING_UFF_PREPARATION_FAILURES; no existing conformer or native failure replay')
    protect(config);save(ready,result)
    print(json.dumps(result),flush=True)
    return result


def source_from_status(row):
    source = dict(pubchem_version=row['pubchem_version'], cid=row['pubchem_cid'],
                  full_key=row['full_key'], wp5_key=row['wp5_key'],
                  source_smiles=row['source_smiles'], isomeric_smiles=row['isomeric_smiles'],
                  stream=row['stream'], stream_rank=row['stream_rank'],
                  source_row_sha256=row.get('source_row_sha256'))
    if molecule_id(source) != row['molecule_id']:
        raise ValueError('ORIGINAL_STATUS_IDENTITY_DIFFERS')
    return source


def prepare(config):
    import pyarrow.parquet as pq
    protect(config)
    base = Path(config['output'])
    base.mkdir(parents=True, exist_ok=True)
    ready = base / 'prepared.json'
    if ready.exists():
        return read(ready)
    root = base / ('prepare_' + uuid.uuid4().hex)
    root.mkdir()
    connection = sqlite3.connect(':memory:')
    connection.execute('PRAGMA temp_store=MEMORY')
    connection.execute('CREATE TABLE original(mid TEXT PRIMARY KEY, ordinal INTEGER UNIQUE, row_json TEXT NOT NULL)')
    files = read(config['original_manifest'])
    parts, rows, eligible, positive, conformers = [], 0, 0, 0, 0
    counts = collections.Counter()
    source_file, part_rows = None, 0
    status_schema = None
    try:
        for table in status_tables(files, config.get('metadata_readers', 1)):
            protect(config)
            if status_schema is None:
                status_schema = table.schema.remove_metadata()
                (root / 'original_status.arrow_schema').write_bytes(status_schema.serialize().to_pybytes())
            for row in table.to_pylist():
                rows += 1
                connection.execute('INSERT INTO original VALUES(?,?,?)',
                    (row['molecule_id'], rows, json.dumps(row, allow_nan=False)))
                actual = row['actual_conformers'] or 0
                positive += int(actual > 0)
                conformers += actual
                counts[row['state']] += 1
                if row['state'] != OLD_STATE:
                    continue
                if actual:
                    raise ValueError('STEREO_SUPPLEMENT_WOULD_RECOMPUTE_OLD_GEOMETRY')
                if source_file is None or part_rows >= 20000:
                    if source_file is not None:
                        source_file.close()
                        parts[-1].update(size=Path(parts[-1]['path']).stat().st_size, rows=part_rows)
                    protect(config)
                    path = root / ('stereo_source_%04d.jsonl' % len(parts))
                    source_file, part_rows = path.open('x'), 0
                    parts.append({'path': str(path)})
                source_file.write(json.dumps(source_from_status(row), allow_nan=False) + '\n')
                part_rows += 1
                eligible += 1
            connection.commit()
            if rows % 25000 < len(table):
                print(json.dumps(dict(prepared_original_rows=rows, stereo_molecules=eligible)), flush=True)
        protect(config)
        target = sqlite3.connect(root / 'original_status.sqlite')
        try:
            connection.backup(target)
        finally:
            target.close()
    finally:
        if source_file is not None:
            source_file.close()
            parts[-1].update(size=Path(parts[-1]['path']).stat().st_size, rows=part_rows)
        connection.close()
    if rows != 2500000 or eligible != EXPECTED:
        raise ValueError('FROZEN_STEREO_POPULATION_DIFFERS')
    result = dict(stereo_source_parts=parts, original_status_index=str(root / 'original_status.sqlite'),
        original_status_schema=str(root / 'original_status.arrow_schema'),
        original_manifest=config['original_manifest'], original_rows=rows,
        original_states=dict(counts), original_molecules_with_3D=positive,
        original_conformers=conformers, stereo_molecules=eligible,
        decontamination='EXISTING_FULL_OR_WP5_UNION_IS_STEREO_INSENSITIVE_NO_NEW_LOOKUP',
        D20='REUSE_ORIGINAL_MANIFEST_REFERENCES_NO_RECOMPUTATION_OR_NUMERIC_READ')
    protect(config)
    save(ready, result)
    print(json.dumps(result), flush=True)
    return result


def finalize(config):
    import pyarrow as pa
    import pyarrow.parquet as pq
    protect(config)
    prepared = read(config['prepared'])
    root = Path(config['delivery'])
    root.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(':memory:')
    connection.execute('PRAGMA temp_store=MEMORY')
    connection.execute('CREATE TABLE result(mid TEXT PRIMARY KEY, row_json TEXT NOT NULL)')
    new_files, summaries = [], []
    total = 0
    for folder in config['producer_outputs']:
        folder = Path(folder)
        summaries.append(read(folder / 'summary.json'))
        for ref in read(folder / 'manifest.json'):
            if Path(ref['path']).name == 'source_status.parquet':
                protect(config)
                for row in pq.read_table(ref['path']).to_pylist():
                    connection.execute('INSERT INTO result VALUES(?,?)',
                                       (row['molecule_id'], json.dumps(row, allow_nan=False)))
                    total += 1
                connection.commit()
            else:
                new_files.append(ref)
    if total != EXPECTED:
        raise ValueError('STEREO_RESULT_POPULATION_DIFFERS')
    repair_total=0
    superseded_cip,superseded_ez=collections.Counter(),collections.Counter()
    for repair in config.get('preparation_repairs',[]):
        plan=read(repair['prepared'])
        superseded_cip.update(plan['superseded_CIP']);superseded_ez.update(plan['superseded_EZ'])
        if not repair.get('output'):
            if plan['stereo_molecules']!=0:raise ValueError('NONEMPTY_PREPARATION_REPAIR_MISSING')
            continue
        folder=Path(repair['output']);summaries.append(read(folder/'summary.json'))
        repaired=0
        for ref in read(folder/'manifest.json'):
            if Path(ref['path']).name!='source_status.parquet':
                new_files.append(ref);continue
            protect(config)
            for row in pq.read_table(ref['path']).to_pylist():
                previous=connection.execute('SELECT row_json FROM result WHERE mid=?',(row['molecule_id'],)).fetchone()
                if not previous:raise ValueError('PREPARATION_REPAIR_OUTSIDE_BASE_SCOPE')
                previous=json.loads(previous[0])
                if (not preparation_failure(previous) or previous['actual_conformers']!=0
                        or previous.get('_preparation_repaired')):
                    raise ValueError('PREPARATION_REPAIR_WOULD_REPEAT_NATIVE_WORK')
                row['_preparation_repaired']=True
                connection.execute('UPDATE result SET row_json=? WHERE mid=?',
                                   (json.dumps(row,allow_nan=False),row['molecule_id']))
                repaired+=1
            connection.commit()
        if repaired!=plan['stereo_molecules']:raise ValueError('PREPARATION_REPAIR_POPULATION_DIFFERS')
        repair_total+=repaired
    connection.execute('ATTACH DATABASE ? AS old', (prepared['original_status_index'],))
    schema = pa.ipc.read_schema(pa.BufferReader(Path(prepared['original_status_schema']).read_bytes()))
    schema = pa.schema(list(schema) + [('stereo_assigned',pa.bool_()),
        ('assigned_isomeric_smiles',pa.large_string()), ('n_assigned_tetrahedral',pa.int64()),
        ('n_assigned_double_bond',pa.int64()), ('stereo_draw_index',pa.int64()),
        ('stereo_state',pa.string()), ('stereo_error',pa.large_string()),
        ('stereo_actual_conformers',pa.int64()), ('stereo_job_id',pa.int64()),
        ('effective_state',pa.string()), ('effective_actual_conformers',pa.int64()),
        ('stereo_preparation_repaired',pa.bool_()),('effective_orders_json',pa.large_string()),
        ('effective_generation_order_json',pa.large_string()),('effective_generation_count_unknown',pa.bool_()),
        ('effective_cache_complete',pa.bool_()),('effective_insufficient_conformers',pa.bool_())])
    source_refs, buffer, effective, positives = [], [], collections.Counter(), 0
    conformer_counts,zero_states=collections.Counter(),collections.Counter()
    redrawn_final=collections.Counter()
    members = (root / 'molecules_with_3D.jsonl').open('x')
    def flush():
        protect(config)
        folder = root / ('status_%05d' % len(source_refs))
        folder.mkdir()
        path = folder / 'source_status.parquet'
        pq.write_table(pa.Table.from_pylist(buffer, schema=schema), path, compression='zstd')
        source_refs.append(dict(path=str(path), size=path.stat().st_size, rows=len(buffer)))
        buffer.clear()
    try:
        for original_json, assigned_json in connection.execute(
            'SELECT o.row_json,r.row_json FROM old.original o LEFT JOIN result r ON r.mid=o.mid ORDER BY o.ordinal'):
            row = json.loads(original_json)
            row.update({k: defaults()[k] for k in FIELDS})
            row['stereo_preparation_repaired']=False
            state, actual = row['state'], row['actual_conformers']
            current=row
            if assigned_json is not None:
                assigned = json.loads(assigned_json)
                current=assigned
                if row['state'] != OLD_STATE:
                    raise ValueError('STEREO_RESULT_OUTSIDE_ORIGINAL_SCOPE')
                row.update({k: assigned[k] for k in FIELDS})
                state, actual = assigned['state'], assigned['actual_conformers']
                row.update(stereo_state=state, stereo_actual_conformers=actual,
                           stereo_error=assigned['error'], stereo_job_id=assigned['job_id'],
                           stereo_preparation_repaired=assigned.get('_preparation_repaired',False))
            elif row['state'] == OLD_STATE:
                raise ValueError('STEREO_RESULT_MISSING')
            row.update(effective_state=state, effective_actual_conformers=actual)
            row.update(effective_orders_json=current.get('orders_json'),
                effective_generation_order_json=current.get('generation_order_json'),
                effective_generation_count_unknown=current.get('generation_count_unknown',actual is None),
                effective_cache_complete=current.get('cache_complete',False),
                effective_insufficient_conformers=actual is None or actual<3)
            effective[state] += 1
            if assigned_json is not None and (row['stereo_draw_index'] or 0)>0:
                redrawn_final['molecules']+=1
                if actual is None: redrawn_final['unknown']+=1
                elif actual==0: redrawn_final['zero']+=1
            conformer_counts['unknown' if actual is None else str(actual)]+=1
            if (actual or 0) > 0:
                positives += 1
                members.write(json.dumps({k: row[k] for k in
                    ('molecule_id','pubchem_cid','full_key','stream','stream_rank')}) + '\n')
            else:zero_states[state]+=1
            buffer.append(row)
            if len(buffer) >= 10000:
                flush()
        if buffer:
            flush()
    finally:
        members.close()
        connection.close()
    old_files = read(prepared['original_manifest'])
    # Preserve completed all-graph NN; only source_status receives schema evolution.
    files = [r for r in old_files if Path(r['path']).name != 'source_status.parquet'] + new_files + source_refs
    save(root / 'manifest.json', files)
    cip,ez=collections.Counter(),collections.Counter()
    redraws=0
    for item in summaries:
        stats=item.get('stereo',{})
        cip.update(stats.get('CIP',{}));ez.update(stats.get('EZ',{}))
        redraws+=stats.get('redrawn_molecules',0)
    cip.subtract(superseded_cip);ez.subtract(superseded_ez)
    if any(v<0 for v in list(cip.values())+list(ez.values())):raise ValueError('STEREO_COUNTER_SUPERSESSION_DIFFERS')
    summary = dict(original_manifest=prepared['original_manifest'], prepared=config['prepared'],
        producer_summaries=summaries, effective_states=dict(effective), molecules_with_3D=positives,
        original_molecules_with_3D=prepared['original_molecules_with_3D'],
        original_conformers=prepared['original_conformers'],
        final_conformers=prepared['original_conformers'] + sum(s['counts']['conformers'] for s in summaries),
        source_status_original_fields_preserved=True, D20_recomputed=0,
        original_historical_files_preserved=True, member_path=str(root / 'molecules_with_3D.jsonl'),
        stereo_unique_molecules=EXPECTED,preparation_repairs=repair_total,processing_events=EXPECTED+repair_total,
        assigned_CIP_counts=dict(cip),assigned_EZ_counts=dict(ez),
        redrawn_molecules=redrawn_final['molecules'],redrawn_processing_events=redraws,
        redrawn_final_zero_conformers=redrawn_final['zero'],
        redrawn_unknown_conformer_count=redrawn_final['unknown'])
    summary.update(effective_conformer_counts=dict(conformer_counts),zero_geometry_states=dict(zero_states))
    save(root / 'batch_summary.json', summary)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare','prepare-repair','finalize'))
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    {'prepare':prepare,'prepare-repair':prepare_repair,'finalize':finalize}[args.mode](read(args.config))
