"""Original extraction/writer code with private diagnostic membership IO only."""
import heapq
import json
import struct
import types
from . import contract as C
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v2 import source as X, writer as W, io as I
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import reader as R, bindings as B
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K

CTX = None


def initialize(context):
    global CTX
    CTX = context
    X.initialize(context)


def records(cfg, group, fields):
    """Original persisted masks; D5 fit_eligible is deliberately not a mask input."""
    coverage = I.load_data(cfg['coverage_reference'], 8 << 20)
    catalog = I.connect(coverage['parts_catalog']['path'], True)
    domain = I.connect(CTX['domain_database'], True)
    wanted = {r[0] for r in domain.execute('SELECT rid FROM wanted_rids')}
    book = I.load_data(cfg['source_inventory_reference'], 2 << 20)
    byname, byid = {s['path']: s for s in book['files']}, {f['field_id']: f for f in fields}
    expected = sum(row[0] in wanted for row in catalog.execute('SELECT rid FROM selected WHERE job=?',
                                                            (group['source_job_id'],)))
    counts = {task: 0 for task in B.TASKS}
    frame = I.identity(coverage['parts_catalog']['path'])
    try:
        for ref in group['label_files']:
            source = byname[ref['path']]
            C.need(source['source_job_id'] == group['source_job_id'], 'EXACT_ORIGINAL_SOURCE_GROUP')
            windows = {}
            for lo, hi, task, rawref, parent in catalog.execute(
                    "SELECT lo,hi,task,ref,parent FROM parts WHERE file=? AND kind='task' ORDER BY lo,task", (source['file_id'],)):
                part = json.loads(rawref)
                I.B.register_part(part, json.loads(parent))
                windows.setdefault((lo, hi), []).append(part)
            for (lo, hi), parts in windows.items():
                streams = [R.one_part(part, source['file_id'], lo, hi) for part in parts]
                heap = []
                try:
                    for index, stream in enumerate(streams):
                        row = next(stream, None)
                        if row is not None:
                            heapq.heappush(heap, (row['physical_row'], index, row))
                    last = -1
                    while heap:
                        physical, index, row = heapq.heappop(heap)
                        C.need(physical > last, 'ORIGINAL_PHYSICAL_SOURCE_ORDER_NO_DUPLICATE')
                        last = physical
                        if row['record_id'] in wanted:
                            saved = catalog.execute('SELECT owner FROM selected WHERE ordinal=? AND rid=?',
                                (row['record_ordinal'], row['record_id'])).fetchone()
                            C.need(saved is not None, 'ACTUAL_FROZEN_SELECTED_CANONICAL_OWNER')
                            owner = json.loads(saved[0])
                            C.need(K.owner_signature(owner) == row['owner_sha256'] and owner['new_role'] == 'TRAIN' and
                                   B.ROLES[owner['new_role']] == row['role_code'] and owner['job_id'] == group['source_job_id'],
                                   'ORIGINAL_TRAIN_OWNER_BITS_NOT_RELABELLED_AS_SOURCE_ROLE')
                            base = catalog.execute('SELECT numbers,owner_sha,usable FROM base WHERE ordinal=?',
                                (row['record_ordinal'],)).fetchone()
                            C.need(base is not None and base['owner_sha'] == row['owner_sha256'] and base['usable'] == 1,
                                   'ACTUAL_NATIVE_ATOM_ORDER_NO_UNKNOWN_GEOMETRY')
                            numbers = [struct.unpack_from('<q', base['numbers'], k)[0] for k in range(0, len(base['numbers']), 8)]
                            entries = K.unpack_entries(row, byid)
                            compact = K.binary_json_loads(row['compact_mask_json'])
                            C.need(B.compact.encode(row['record_ordinal'], row['task_code'], entries) == compact,
                                   'ORIGINAL_SCIENTIFIC_SOURCE_NEW_REVIEW_MASKS_NO_D5_FIT_MASK_SUBSTITUTION')
                            entries.sort(key=lambda entry: entry['field_id'])
                            task = next(t for t, code in B.TASKS.items() if code == row['task_code'])
                            counts[task] += 1
                            yield owner, numbers, entries, row, source
                        following = next(streams[index], None)
                        if following is not None:
                            heapq.heappush(heap, (following['physical_row'], index, following))
                finally:
                    for stream in streams:
                        stream.close()
        C.need(all(count == expected for count in counts.values()), 'ALL14_ORIGINAL_TASKS_FOR_EACH_REAL_HELD_NATIVE_RID')
    finally:
        domain.close()
        catalog.close()
        C.need(I.identity(coverage['parts_catalog']['path']) == frame, 'CLOSED_FAST55K_TYPED_CATALOG_FRAME_UNCHANGED')


def one(work):
    # Entire original projection body is retained. Only its reader IO binding
    # is private; no old module/global/source or scientific function is patched.
    namespace = dict(X.one.__globals__)
    namespace.update(R=types.SimpleNamespace(records=records), CTX=X.CTX)
    function = types.FunctionType(X.one.__code__, namespace, X.one.__name__, X.one.__defaults__, X.one.__closure__)
    function.__kwdefaults__ = X.one.__kwdefaults__
    return function(work)


def metadata(db, geometry):
    value = W.metadata(db, geometry)
    row = db.execute('SELECT selected FROM geometries WHERE gid=?', (geometry['geometry_id'],)).fetchone()
    C.need(value['effective_role'] == 'TRAIN' and row is not None and row['selected'] == 1,
           'ONLY_TRUE_SEEN_TRAIN_MOLECULE_HELD_DIAGNOSTIC_MEMBERS')
    value.update(sample_role=C.ROLE, diagnostic_role=C.ROLE, diagnostic_only=True,
                 training_excluded=True, train_eligible=False, source_scientific_mask_unchanged=True,
                 diagnostic_exclusion_not_a_scientific_invalidity=True, store_namespace=C.STORE_NAMESPACE)
    return value


def write(*args):
    namespace = dict(W.write.__globals__)
    namespace['metadata'] = metadata
    function = types.FunctionType(W.write.__code__, namespace, W.write.__name__, W.write.__defaults__, W.write.__closure__)
    function.__kwdefaults__ = W.write.__kwdefaults__
    return function(*args)
