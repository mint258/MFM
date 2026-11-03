"""Pinned physical sources and bounded streaming, without implicit sampling."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path

GROUPS = ('v1_common', 'pubchem_1m', 'R', 'N')
RECIPE = 'ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5'


def need(test, message):
    if not test:
        raise RuntimeError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def reference(path):
    path = Path(path).absolute()
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    after = path.stat()
    need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'Source changed while hashing: ' + str(path))
    return {'path': str(path), 'bytes': before.st_size, 'sha256': h.hexdigest()}


def verify(ref):
    need(reference(ref['path']) == {k: ref[k] for k in ('path', 'bytes', 'sha256')}, 'Physical reference mismatch: ' + ref['path'])
    return Path(ref['path'])


def write_new(path, value):
    path = Path(path)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(canonical(value) + '\n')
    return reference(path)


def pointer(value, path):
    for component in path.strip('/').split('/'):
        value = value[int(component)] if isinstance(value, list) else value[component.replace('~1', '/').replace('~0', '~')]
    return value


def rows(source, batch_rows=4096):
    """Each file is SHA-verified once; no full-file dataframe/Python list."""
    for artifact in source['artifacts']:
        path = verify(artifact)
        before = path.stat()
        if artifact['format'] == 'parquet':
            import pyarrow.parquet as pq
            def parquet_rows():
                with pq.ParquetFile(path) as parquet:
                    for batch in parquet.iter_batches(batch_size=batch_rows, use_threads=False):
                        yield from batch.to_pylist()
            iterator = parquet_rows()
        elif artifact['format'] == 'jsonl':
            def lines():
                with path.open(encoding='utf-8') as stream:
                    for line in stream:
                        yield json.loads(line)
            iterator = lines()
        else:
            raise RuntimeError('Only explicit Parquet or JSONL sources are supported')
        physical = 0
        for row in iterator:
            physical += 1
            if any(row.get(key) != value for key, value in source.get('equals', {}).items()):
                continue
            maximum = source.get('maximum_stream_rank')
            if maximum is not None and not (1 <= row['stream_rank'] <= maximum):
                continue
            yield row
        if 'rows' in artifact:
            need(physical == artifact['rows'], 'Physical source row count differs: ' + str(path))
        after = path.stat()
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'Physical source changed while streaming')


def batches(iterator, width):
    batch = []
    for row in iterator:
        batch.append(row)
        if len(batch) == width:
            yield batch
            batch = []
    if batch:
        yield batch


def population(path):
    ref = reference(path)
    manifest = load(path)
    need(manifest['schema'] == 'EXPANSION_DISTRIBUTION_POPULATION_V1' and manifest['status'] == 'COMPLETE', 'Complete physical population manifest required')
    need(manifest['population'] in GROUPS and manifest['population_scope'] == 'FULL_DECLARED_POPULATION' and type(manifest['expected_molecules']) is int and manifest['expected_molecules'] > 0, 'No implicit/surrogate population scope')
    authority = load(verify(manifest['authority_reference']))
    actual = pointer(authority, manifest['authority_count_pointer'])
    need(type(actual) is int and actual == manifest['expected_molecules'], 'Declared count differs from actual authoritative population count')
    if manifest['population'] == 'v1_common':
        need(manifest['is_sample'] is False and manifest['population_roles'] == ['TRAIN', 'VAL'] and manifest['authority_kind'] == 'FINAL_FULL_COMMON_MEMBERSHIP', 'Full Common TRAIN/VAL membership is mandatory; a sampled Common is forbidden')
    if manifest['population'] == 'pubchem_1m':
        need(manifest['expected_molecules'] == 1000000 and manifest['is_sample'] is True and manifest['sampling']['uniform'] is True and type(manifest['sampling']['seed']) is int and manifest['sampling']['source_status'] == 'X_SCREENED_INTERNAL_FULLKEY_DEDUPLICATED', 'Exactly one million uniformly selected same-X internally deduplicated PubChem molecules required')
        need(manifest['baseline_pool_phase'] == 'BEFORE_V1_DOWNSTREAM_DECONTAMINATION_AND_NOVELTY', 'PubChem baseline cannot be replaced with the final novelty/decontaminated selection')
        for key in ('raw_chemical_screen_reference', 'internal_deduplicated_pool_reference'):
            verify(manifest[key])
    for key in ('membership', 'features'):
        need(manifest[key]['artifacts'] and manifest[key]['identity_column'], 'Physical identity-bound sources required')
    if manifest['population'] in ('pubchem_1m', 'R', 'N'):
        need(manifest['membership']['identity_column'] == manifest['features']['identity_column'] == 'full_key', 'PubChem and stream membership must use unique full InChIKeys')
    if manifest['population'] in ('R', 'N'):
        need(manifest['stream'] == manifest['population'] and manifest['selection_status'] == 'FINAL_FIRST_BATCH_FROM_RELEASED_DECONTAMINATED_ORDER', 'Actual corresponding first-batch stream selection is required')
    return manifest, ref


def export_cursor(path, header, iterator):
    with Path(path).open('x', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(iterator)
    return reference(path)
