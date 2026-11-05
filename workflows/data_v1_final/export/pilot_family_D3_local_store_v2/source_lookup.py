"""Closed171 source routing: keys only in node-local SQLite, no payload merge.

SOURCE candidate for an isolated copy of the current D3 producer. No submission,
scientific projection, QA, hash replay or release authority is implemented here.
The old parent must be actually terminal before this backend can read its caches.
"""
import collections, concurrent.futures as cf, heapq, hashlib, json, os, pathlib, socket, sqlite3, stat, subprocess, time
from . import contract as C, domain as D, io as I, closed_domain_resume as Closed, store_resume as Resume

SOURCE_COUNT = 171
SOURCE_ROWS = 7128716
PIECES = 65570829
LOOKUP_SQL = 'SELECT PAYLOAD,SOURCE_LOCATOR FROM PIECES WHERE GID=? AND PART=?'
OBSERVATION = {}


def references(plan):
    resume = plan['direct_source_resume']
    source = [resume[k] for k in ('prior_plan_reference', 'prior_terminal_reference', 'closed_groups_reference')]
    return source, [resume['geometry_index_reference']]


def _regular(path):
    path = pathlib.Path(path)
    C.need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)), 'LITERAL_OWN_CLOSED_SOURCE_PATH')
    st = path.stat()
    C.need(stat.S_ISREG(st.st_mode) and st.st_uid == 1278, 'OWN_REGULAR_CLOSED_SOURCE')
    return st


def _wait_space(plan, budget, extra=0):
    resume = plan['direct_source_resume']; path = pathlib.Path(resume['local_directory'])
    while True:
        budget.check(dispatch=False)
        usage = os.statvfs(path); free = usage.f_bavail * usage.f_frsize
        if free >= resume['local_reserve_bytes'] + extra:return free
        # No time/RSS stop, no retry of science. Wait for actual disk recovery.
        time.sleep(60)


def _copy_closed(reference, destination, plan, budget):
    source = pathlib.Path(reference['path']); before = I.identity(source)
    C.need(_regular(source).st_size == reference['bytes'] and not destination.exists(), 'EXACT_CLOSED_SOURCE_AND_FRESH_LOCAL_COPY')
    remaining = reference['bytes']
    with source.open('rb') as incoming, destination.open('xb') as outgoing:
        C.need(I.identity(source) == before, 'CLOSED_SOURCE_FRAME_BEFORE_COPY')
        while True:
            _wait_space(plan, budget, min(remaining, 16 << 20))
            block = incoming.read(16 << 20)
            if not block:break
            outgoing.write(block); remaining -= len(block)
        outgoing.flush(); os.fsync(outgoing.fileno())
    C.need(remaining == 0 and destination.stat().st_size == reference['bytes'] and I.identity(source) == before,
           'SEQUENTIAL_LOCAL_COPY_BYTE_COUNT_AND_STABLE_ORIGIN_FRAME')
    # Producer SHA remains provenance. Do not claim or perform another whole SHA.


def _resume(plan):
    resume = plan['direct_source_resume']; previous = C.meta(resume['prior_plan_reference'])
    terminal = C.meta(resume['prior_terminal_reference'])
    C.need(str(terminal['job_id']) == str(resume['actual_job_id']) == '4525670'
      and terminal['state'] in ('FAILED', 'CANCELLED', 'COMPLETED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL')
      and type(terminal['exit_code']) is str, 'OLD_PARENT_ACTUALLY_TERMINAL_BEFORE_REUSING_CACHES')
    C.need(previous['pilot_acceptance_reference'] == plan['pilot_acceptance_reference']
      and previous['configuration_component_producer_job_id'] == plan['configuration_component_producer_job_id']
      and previous['bounded_export_review_reference'] == resume['prior_bounded_export_review_reference'],
      'SAME_FROZEN55K_CONFIGURATION_AUTHORITY')
    for name in ('source.py', 'projection.py', 'frame_mapping.py', 'payload_io.py'):
        current = C.Q.pin(C.HERE / name)
        matches = [r for r in previous['source_references'] if pathlib.Path(r['path']).name == name
                   and pathlib.Path(r['path']).parent.name == 'pilot_family_D3_lustre_cpu_store_v3']
        C.need(any((r['bytes'], r['sha256']) == (current['bytes'], current['sha256']) for r in matches),
               'UNCHANGED_FOUR_SOURCE_MATH_AND_LOSSLESS_CODEC_FILES')
    log = resume['closed_groups_reference']; raw = pathlib.Path(log['path']).read_bytes()
    C.need(len(raw) == log['bytes'] and hashlib.sha256(raw).hexdigest() == log['sha256'], 'EXACT_SMALL171_CLOSED_LOG')
    groups = [json.loads(line) for line in raw.splitlines() if line.strip()]
    C.need(len(groups) == SOURCE_COUNT and len({r['key'] for r in groups}) == SOURCE_COUNT
      and sum(r['source_rows'] for r in groups) == SOURCE_ROWS and sum(r['pieces'] for r in groups) == PIECES
      and all(r['all_handles_closed'] is True and r['new_QM_UFF_calls'] == 0 for r in groups),
      'ALL_ACTUAL171_CLOSED_GROUPS_NO_NEW_PROJECTION')
    allowed = C.meta(plan['bounded_export_review_reference'])['transitive_closed_output_roots']
    for result in groups:
        D.register(result['reference'], allowed); I.require(result['reference'], content=False)
    return resume, groups


def open_domain(plan, accepted, root, budget):
    config, _, _, _ = Closed.reviews(plan, accepted)
    resume, groups = _resume(plan)
    bounded = C.meta(plan['bounded_export_review_reference']); roots = bounded['transitive_closed_output_roots']
    geometry = D.read(accepted['component_references']['geometry_reference'], roots)
    binding = D.register(geometry['cell_binding_reference'], roots)
    geometry_path = str(I.require(binding, content=False))
    if Resume.enabled(plan):
        local = Resume.local_frames(plan)
        index = D.register(resume['geometry_index_reference'], roots); I.require(index, content=False)
        index_path = local/'geometry_index.sqlite'
        db = I.connect(local/'source_routes.sqlite', True)
        Closed.configure_views(db, str(index_path), geometry_path)
        OBSERVATION.update(node=socket.gethostname(),uid=os.getuid(),directory=str(local),
          source_payload_copied=False,source_whole_SHA_repeated=False,existing_routes_reused=True,
          prior_route_producer_job_id=plan['store_write_resume']['actual_job_id'])
        return db,geometry,binding,roots,str(index_path),config['original_series_size_rho_reference'],geometry_path,groups
    local = pathlib.Path(resume['local_directory'])
    C.need(local.is_absolute() and pathlib.Path('/tmp') in local.parents and not local.exists()
      and not any(p.is_symlink() for p in (local, *local.parents)), 'FRESH_LITERAL_NODE_TMP_WORKSPACE')
    local.mkdir(mode=0o700)
    kind = subprocess.run(['findmnt', '-n', '-T', str(local), '-o', 'FSTYPE'], check=True,
                          capture_output=True, text=True).stdout.strip()
    C.need(kind in ('xfs', 'ext4', 'btrfs'), 'ACTUAL_NODE_LOCAL_DISK_NOT_NETWORK_OR_TMPFS')
    C.need(type(resume['local_reserve_bytes']) is int and resume['local_reserve_bytes'] >= 0
      and type(resume['local_working_forecast_bytes']) is int and resume['local_working_forecast_bytes'] > 0,
      'ROOT_ACTUAL_NODE_SCRATCH_FORECAST_NOT_A_FABRICATED_CAPACITY_PASS')
    free = _wait_space(plan, budget, resume['local_working_forecast_bytes'])
    OBSERVATION.update(node=socket.gethostname(), uid=os.getuid(), directory=str(local), filesystem=kind,
      observed_free_bytes=free, reserve_bytes=resume['local_reserve_bytes'],
      working_forecast_bytes=resume['local_working_forecast_bytes'], observed_unix_seconds=time.time(),
      source_payload_copied=False, source_whole_SHA_repeated=False)
    index = D.register(resume['geometry_index_reference'], roots); I.require(index, content=False)
    index_path = local / 'geometry_index.sqlite'; _copy_closed(index, index_path, plan, budget)
    destination = local / 'source_routes.sqlite'
    db = I.connect(destination); db.execute('PRAGMA cache_size=-2097152')
    db.executescript('CREATE TABLE pieces(gid TEXT NOT NULL,part TEXT NOT NULL,source_id INTEGER NOT NULL,PRIMARY KEY(gid,part)) WITHOUT ROWID;'
      'CREATE TABLE source_files(source_id INTEGER PRIMARY KEY,reference TEXT NOT NULL,frame TEXT NOT NULL,pieces INTEGER NOT NULL);')
    Closed.configure_views(db, str(index_path), geometry_path); db.commit()
    return db, geometry, binding, roots, str(index_path), config['original_series_size_rho_reference'], geometry_path, groups


def _write_key_fragment(work, plan, budget):
    """Scan every rowid-table row once; materialize only its two key columns."""
    source_id, result, destination, frame = work
    path = pathlib.Path(result['reference']['path']); destination = pathlib.Path(destination)
    source = local = cursor = None; total = 0; batch = []
    started = time.time()
    try:
        C.need(_regular(path).st_size == result['reference']['bytes'] and I.identity(path) == frame,
               'EXACT_CLOSED_SOURCE_FRAME_BEFORE_ROWID_KEY_SCAN')
        C.need(not destination.exists(), 'FRESH_NODE_LOCAL_KEY_FRAGMENT')
        source = I.connect(path, True); source.execute('PRAGMA cache_size=-2048')
        local = I.connect(destination); local.execute('PRAGMA cache_size=-65536')
        local.execute('CREATE TABLE keys(gid TEXT NOT NULL,part TEXT NOT NULL,PRIMARY KEY(gid,part)) WITHOUT ROWID')
        # NOT INDEXED forces the original rowid table scan. No rowid ranges,
        # assumed rowid density, ID parsing, ORDER BY, n, payload or locator.
        cursor = source.execute('SELECT gid,part FROM pieces NOT INDEXED')
        for gid, part in cursor:
            batch.append((gid, part))
            if len(batch) >= 65536:
                _wait_space(plan, budget)
                local.executemany('INSERT INTO keys VALUES(?,?)', batch); local.commit()
                total += len(batch); batch = []
        if batch:
            _wait_space(plan, budget)
            local.executemany('INSERT INTO keys VALUES(?,?)', batch); local.commit(); total += len(batch)
        C.need(total == result['pieces'], 'EXACT_CLOSED_GROUP_ROWID_KEY_COUNT')
        local.commit()
    finally:
        if cursor is not None:cursor.close()
        if local is not None:local.close()
        if source is not None:source.close()
        C.need(I.identity(path) == frame, 'CLOSED_SOURCE_FRAME_STABLE_AFTER_ROWID_KEY_SCAN_CLOSE')
    return dict(source_id=source_id, source_key=result['key'], keys=total,
                path=str(destination), bytes=destination.stat().st_size,
                started_unix_seconds=started, completed_unix_seconds=time.time())


def _prepare_key_fragments(groups, frames, directory, plan, budget):
    """At most16 pending independent SQLite tasks; failures drain, never retry."""
    results = {}; first_error = None; iterator = iter(enumerate(groups)); exhausted = False
    with cf.ThreadPoolExecutor(max_workers=16, thread_name_prefix='closed-source-keys') as pool:
        pending = {}
        def fill():
            nonlocal exhausted
            while first_error is None and not exhausted and len(pending) < 16:
                try:source_id, result = next(iterator)
                except StopIteration:exhausted = True; break
                budget.check()
                destination = directory / (str(source_id).zfill(3) + '.sqlite')
                work = (source_id, result, str(destination), frames[source_id])
                pending[pool.submit(_write_key_fragment, work, plan, budget)] = source_id
        fill()
        while pending:
            ready, _ = cf.wait(pending, timeout=1, return_when=cf.FIRST_COMPLETED)
            budget.check(dispatch=False)
            for future in ready:
                source_id = pending.pop(future)
                try:
                    result = future.result(); results[source_id] = result
                    OBSERVATION['key_fragments_completed'] = len(results)
                    print(json.dumps(dict(phase='CLOSED_SOURCE_LOCAL_KEY_FRAGMENT_COMPLETE',
                      source_id=source_id, source_key=result['source_key'], keys=result['keys'],
                      local_key_bytes=result['bytes'], completed_sources=len(results), source_groups=len(groups),
                      started_unix_seconds=result['started_unix_seconds'],
                      completed_unix_seconds=result['completed_unix_seconds']), sort_keys=True), flush=True)
                except BaseException as error:
                    if first_error is None:first_error = error
            # Once any task reports failure, no new source is dispatched.
            # All already-running tasks finish naturally in this same pool.
            if first_error is None:fill()
        if first_error is not None:raise first_error
    C.need(len(results) == len(groups), 'ALL171_LOCAL_KEY_FRAGMENTS_ACTUALLY_CLOSED')
    return [results[source_id] for source_id in range(len(groups))]


def _source_keys(db, source_id, expected, counts):
    # This connection is to a node-local, already-closed key-only file.
    cursor = db.execute('SELECT gid,part FROM keys ORDER BY gid,part')
    try:
        for gid, part in cursor:
            counts[source_id] += 1
            yield gid, part, source_id
        C.need(counts[source_id] == expected, 'EXACT_LOCAL_FRAGMENT_KEY_COUNT')
    finally:cursor.close()


def build_routes(db, groups, expected_groups, plan, root, budget):
    if Resume.enabled(plan):
        expected={hashlib.sha256(json.dumps(g,sort_keys=True,separators=(',',':')).encode()).hexdigest() for g in expected_groups}
        C.need({r['key'] for r in groups}==expected,'CLOSED171_KEYS_MATCH_SAME_FROZEN_LOGICAL_GROUP_PLAN')
        rows=db.execute('SELECT source_id,reference,frame,pieces FROM source_files ORDER BY source_id').fetchall()
        C.need(len(rows)==SOURCE_COUNT,'ORIGINAL_CLOSED171_SOURCE_ROUTE_CATALOG')
        for source_id,(row,result) in enumerate(zip(rows,groups)):
            C.need(row['source_id']==source_id and json.loads(row['reference'])==result['reference']
              and row['pieces']==result['pieces'] and I.identity(result['reference']['path'])==json.loads(row['frame']),
              'EXACT_CLOSED_ROUTE_SOURCE_CATALOG_AND_STABLE_ORIGINAL_FILES')
        local=Resume.local_frames(plan)
        OBSERVATION.update(source_groups=len(rows),pieces=PIECES,
          key_count_authority='ORIGINAL_CLOSED_ROUTE_BUILD_BEFORE_PRIOR_STORE_WRITES',
          key_preparation_performed_in_this_parent=False,
          source_routes_path=str(local/'source_routes.sqlite'),source_routes_bytes=(local/'source_routes.sqlite').stat().st_size,
          geometry_index_path=str(local/'geometry_index.sqlite'),geometry_index_bytes=(local/'geometry_index.sqlite').stat().st_size,
          original_closed_groups_reference=plan['direct_source_resume']['closed_groups_reference'],
          original_source_files_preserved=True,original_source_payloads_copied=False,new_QM_UFF_calls=0)
        return
    OBSERVATION.update(prepare_started_unix_seconds=time.time(), key_fragments_completed=0,
      key_scan_workers=16, key_scan_policy='ALL_ROWID_TABLE_ROWS_NOT_INDEXED_KEY_COLUMNS_ONLY')
    expected = {hashlib.sha256(json.dumps(g, sort_keys=True, separators=(',', ':')).encode()).hexdigest() for g in expected_groups}
    C.need({r['key'] for r in groups} == expected, 'CLOSED171_KEYS_MATCH_SAME_FROZEN_LOGICAL_GROUP_PLAN')
    local = pathlib.Path(plan['direct_source_resume']['local_directory'])
    directory = local / 'source_key_fragments'; directory.mkdir(mode=0o700)
    frames = []
    for source_id, result in enumerate(groups):
        reference = result['reference']; path = pathlib.Path(reference['path']); _regular(path)
        frame = I.identity(path); frames.append(frame)
        db.execute('INSERT INTO source_files VALUES(?,?,?,?)',
                   (source_id, json.dumps(reference, sort_keys=True), json.dumps(frame), result['pieces']))
    db.commit()
    fragments = _prepare_key_fragments(groups, frames, directory, plan, budget)
    OBSERVATION.update(key_fragment_scan_completed_unix_seconds=time.time(),
      key_fragment_total_bytes=sum(result['bytes'] for result in fragments),
      local_key_merge_started_unix_seconds=time.time())
    sources = []; counts = collections.Counter(); streams = []; total = 0
    try:
        for source_id, result in enumerate(fragments):
            path = pathlib.Path(result['path']); frame = I.identity(path)
            source = I.connect(path, True); source.execute('PRAGMA cache_size=-2048')
            sources.append((source, path, frame))
            streams.append(_source_keys(source, source_id, result['keys'], counts))
        previous = None; batch = []
        for gid, part, source_id in heapq.merge(*streams):
            key = (gid, part)
            C.need(key != previous, 'NO_DUPLICATE_GID_PART_OWNERSHIP_ACROSS_CLOSED_SOURCES')
            previous = key; batch.append((gid, part, source_id))
            if len(batch) >= 65536:
                _wait_space(plan, budget); db.executemany('INSERT INTO pieces VALUES(?,?,?)', batch); db.commit()
                total += len(batch); batch = []
        if batch:
            _wait_space(plan, budget); db.executemany('INSERT INTO pieces VALUES(?,?,?)', batch); db.commit(); total += len(batch)
        C.need(total == PIECES, 'ALL171_SOURCE_KEYS_INDEXED_WITHOUT_COPYING_PAYLOADS')
        db.commit()
    finally:
        for stream in streams:stream.close()
        changed = []
        for source, path, frame in sources:
            source.close()
            if I.identity(path) != frame:changed.append(str(path))
        C.need(not changed, 'CLOSED_LOCAL_KEY_FILES_STABLE_DURING_FINAL_MERGE')
    # All key readers/cursors are closed before removing any local fragment.
    # Original171 source files are never deleted or modified here.
    for result in fragments:os.unlink(result['path'])
    directory.rmdir()
    OBSERVATION.update(source_groups=len(groups), pieces=total,
      source_routes_path=str(local / 'source_routes.sqlite'), source_routes_bytes=(local / 'source_routes.sqlite').stat().st_size,
      geometry_index_path=str(local / 'geometry_index.sqlite'), geometry_index_bytes=(local / 'geometry_index.sqlite').stat().st_size,
      original_closed_groups_reference=plan['direct_source_resume']['closed_groups_reference'],
      original_source_files_preserved=True, original_source_payloads_copied=False, new_QM_UFF_calls=0,
      local_key_fragments_retired_after_all_readers_closed=True, prepare_completed_unix_seconds=time.time())

class RoutingConnection:
    """One indexed route + original closed source PK lookup; never query171 DBs."""
    def __init__(self, connection, max_open=8):
        self.connection = connection; self.max_open = max_open; self.sources = collections.OrderedDict()
    def __getattr__(self, name):return getattr(self.connection, name)
    def _drop(self, value):
        source, path, frame = value; source.close()
        C.need(I.identity(path) == frame, 'READONLY_CLOSED_SOURCE_FRAME_STABLE_DURING_WRITER')
    def _source(self, source_id):
        if source_id in self.sources:
            value = self.sources.pop(source_id); self.sources[source_id] = value; return value[0]
        row = self.connection.execute('SELECT reference,frame FROM source_files WHERE source_id=?', (source_id,)).fetchone()
        C.need(row is not None, 'EXACT_SOURCE_ID_ROUTE_EXISTS')
        reference, frame = json.loads(row['reference']), json.loads(row['frame']); path = pathlib.Path(reference['path'])
        C.need(I.identity(path) == frame and _regular(path).st_size == reference['bytes'], 'ORIGINAL_CLOSED_SOURCE_STILL_PRESENT')
        source = I.connect(path, True); source.execute('PRAGMA cache_size=-4096')
        self.sources[source_id] = (source, path, frame)
        if len(self.sources) > self.max_open:self._drop(self.sources.popitem(last=False)[1])
        return source
    def execute(self, sql, parameters=()):
        if ' '.join(sql.split()).upper() == LOOKUP_SQL:
            row = self.connection.execute('SELECT source_id FROM pieces WHERE gid=? AND part=?', parameters).fetchone()
            if row is None:return self.connection.execute('SELECT NULL AS payload,NULL AS source_locator WHERE 0')
            return self._source(row['source_id']).execute(sql, parameters)
        return self.connection.execute(sql, parameters)
    def close(self):
        try:
            while self.sources:self._drop(self.sources.popitem(last=False)[1])
        finally:self.connection.close()