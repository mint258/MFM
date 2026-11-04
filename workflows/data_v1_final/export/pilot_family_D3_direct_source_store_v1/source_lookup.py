"""Closed171 source routing: keys only in node-local SQLite, no payload merge.

SOURCE candidate for an isolated copy of the current D3 producer. No submission,
scientific projection, QA, hash replay or release authority is implemented here.
The old parent must be actually terminal before this backend can read its caches.
"""
import collections, heapq, hashlib, json, os, pathlib, socket, sqlite3, stat, subprocess, time
from . import contract as C, domain as D, io as I, closed_domain_resume as Closed

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


def _source_keys(db, source_id, expected, counts):
    # Original source.py creates PRIMARY KEY(gid,part). Explicitly use its
    # covering index: do not fetch n, payload or locator/overflow BLOB pages.
    names = []
    for index in db.execute('PRAGMA index_list(pieces)'):
        if index['unique']:
            name = index['name']; quoted = '"' + name.replace('"', '""') + '"'
            if [r['name'] for r in db.execute('PRAGMA index_info(' + quoted + ')')] == ['gid', 'part']:
                names.append(quoted)
    C.need(len(names) == 1, 'ORIGINAL_SOURCE_GID_PART_COVERING_PRIMARY_KEY')
    cursor = db.execute('SELECT gid,part FROM pieces INDEXED BY ' + names[0] + ' ORDER BY gid,part')
    try:
        for gid, part in cursor:
            counts[source_id] += 1
            yield gid, part, source_id
        C.need(counts[source_id] == expected, 'EXACT_CLOSED_GROUP_KEY_COUNT')
    finally:cursor.close()


def build_routes(db, groups, expected_groups, plan, root, budget):
    expected = {hashlib.sha256(json.dumps(g, sort_keys=True, separators=(',', ':')).encode()).hexdigest() for g in expected_groups}
    C.need({r['key'] for r in groups} == expected, 'CLOSED171_KEYS_MATCH_SAME_FROZEN_LOGICAL_GROUP_PLAN')
    sources = []; counts = collections.Counter(); streams = []
    try:
        for source_id, result in enumerate(groups):
            reference = result['reference']; path = pathlib.Path(reference['path']); _regular(path)
            frame = I.identity(path); source = I.connect(path, True)
            source.execute('PRAGMA cache_size=-2048')
            sources.append((source, path, frame))
            db.execute('INSERT INTO source_files VALUES(?,?,?,?)',
                       (source_id, json.dumps(reference, sort_keys=True), json.dumps(frame), result['pieces']))
            streams.append(_source_keys(source, source_id, result['pieces'], counts))
        db.commit(); previous = None; batch = []; total = 0
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
    finally:
        for stream in streams:stream.close()
        for source, path, frame in sources:
            source.close(); C.need(I.identity(path) == frame, 'CLOSED_SOURCE_FRAME_STABLE_DURING_KEY_INDEX_BUILD')
    db.commit()
    local = pathlib.Path(plan['direct_source_resume']['local_directory'])
    OBSERVATION.update(source_groups=len(groups), pieces=total,
      source_routes_path=str(local / 'source_routes.sqlite'), source_routes_bytes=(local / 'source_routes.sqlite').stat().st_size,
      geometry_index_path=str(local / 'geometry_index.sqlite'), geometry_index_bytes=(local / 'geometry_index.sqlite').stat().st_size,
      original_closed_groups_reference=plan['direct_source_resume']['closed_groups_reference'],
      original_source_files_preserved=True, original_source_payloads_copied=False, new_QM_UFF_calls=0)


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