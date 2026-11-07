"""Count complete declared physical populations with bounded, disk-backed state."""
from __future__ import annotations
from bisect import bisect_right
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
import json
import math
import multiprocessing as mp
from pathlib import Path
import sqlite3
from .functional_groups import FUNCTIONS, NUMERIC_FIELDS, enrich_batch, recipe
from .io import GROUPS, RECIPE, batches, canonical, load, need, pointer, population, reference, rows, verify, write_new

RESOURCE_CHECK = lambda: None


def edges_for(field):
    if field == 'nearest_tanimoto':
        return [i / 1000 for i in range(1001)]
    if field == 'molecular_weight_Da':
        return [20 * i for i in range(101)] + [5000, 10000, 100000]
    if field == 'logp':
        return [-20 + i / 4 for i in range(201)] + [50, 100, 1000]
    if field == 'tpsa_A2':
        return [10 * i for i in range(101)] + [2000, 5000, 10000]
    return list(range(101)) + [150, 200, 500, 1000, 10000]


class Moments:
    """Welford population moments and explicit fixed-bin mass, including tails."""
    def __init__(self, field, saved=None):
        self.field, self.edges = field, edges_for(field)
        self.n = 0
        self.mean = self.m2 = 0.0
        self.minimum = self.maximum = None
        self.bins = [0] * (len(self.edges) + 1)
        if saved is not None:
            need(saved['field'] == field and saved['edges'] == self.edges, 'Histogram/statistic recipe changed on resume')
            for name in ('n', 'mean', 'm2', 'minimum', 'maximum', 'bins'):
                setattr(self, name, saved[name])

    def add(self, value):
        need(type(value) in (int, float) and math.isfinite(value), 'Invalid numeric descriptor: ' + self.field)
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)
        self.minimum = value if self.minimum is None else min(value, self.minimum)
        self.maximum = value if self.maximum is None else max(value, self.maximum)
        index = bisect_right(self.edges, value)
        if value == self.edges[-1]:
            index = len(self.edges) - 1
        self.bins[index] += 1

    def result(self):
        need(sum(self.bins) == self.n, 'All finite values must remain in histogram mass')
        return {'field': self.field, 'edges': self.edges, 'n': self.n, 'mean': self.mean, 'm2': self.m2, 'minimum': self.minimum, 'maximum': self.maximum, 'bins': self.bins}

    def summary(self):
        return (self.n, self.mean if self.n else None, math.sqrt(max(0, self.m2 / self.n)) if self.n else None, self.minimum, self.maximum)

    def histogram(self):
        cumulative = 0
        for i, count in enumerate(self.bins):
            cumulative += count
            left = '-inf' if i == 0 else self.edges[i - 1]
            right = 'inf' if i == len(self.edges) else self.edges[i]
            yield (i, left, right, count, cumulative, cumulative / self.n if self.n else None)


def heavy_bin(n):
    for edge in (10, 20, 30, 50, 75, 100):
        if n <= edge:
            return str(edge)
    return 'above_100'


def open_state(path):
    db = sqlite3.connect(path)
    db.executescript('''
      PRAGMA journal_mode=DELETE;
      PRAGMA synchronous=FULL;
      CREATE TABLE IF NOT EXISTS populations(name TEXT PRIMARY KEY,manifest TEXT NOT NULL,expected INTEGER NOT NULL,complete INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS required_members(population TEXT,identity TEXT,PRIMARY KEY(population,identity)) WITHOUT ROWID;
      CREATE TABLE IF NOT EXISTS seen(population TEXT,identity TEXT,heavy_bin TEXT,element_combination TEXT,scaffold TEXT,full_key TEXT NOT NULL,PRIMARY KEY(population,identity)) WITHOUT ROWID;
      CREATE INDEX IF NOT EXISTS seen_full_key ON seen(population,full_key);
      CREATE TABLE IF NOT EXISTS counts(population TEXT,kind TEXT,key TEXT,n INTEGER NOT NULL,PRIMARY KEY(population,kind,key)) WITHOUT ROWID;
      CREATE TABLE IF NOT EXISTS moments(population TEXT,field TEXT,state TEXT NOT NULL,PRIMARY KEY(population,field)) WITHOUT ROWID;
      CREATE TABLE IF NOT EXISTS comparisons(name TEXT PRIMARY KEY,manifest TEXT NOT NULL,query_population TEXT NOT NULL,expected INTEGER NOT NULL,complete INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS nearest(comparison TEXT,identity TEXT,value REAL NOT NULL,PRIMARY KEY(comparison,identity)) WITHOUT ROWID;
    ''')
    return db


def load_moments(db, population_name, fields=NUMERIC_FIELDS):
    saved = {field: json.loads(raw) for field, raw in db.execute('SELECT field,state FROM moments WHERE population=?', (population_name,))}
    return {field: Moments(field, saved.get(field)) for field in fields}


def prepare_members(db, manifest, manifest_ref):
    name, expected = manifest['population'], manifest['expected_molecules']
    old = db.execute('SELECT manifest,expected FROM populations WHERE name=?', (name,)).fetchone()
    binding = canonical(manifest_ref)
    need(old is None or old == (binding, expected), 'Population manifest or authoritative size changed on resume')
    db.execute('INSERT OR IGNORE INTO populations(name,manifest,expected) VALUES(?,?,?)', (name, binding, expected))
    db.execute('CREATE TEMP TABLE member_pass(identity TEXT PRIMARY KEY) WITHOUT ROWID')
    count = 0
    for row in rows(manifest['membership']):
        identity = str(row[manifest['membership']['identity_column']])
        need(identity and identity != 'None', 'Authoritative molecular member identity required')
        db.execute('INSERT INTO member_pass VALUES(?)', (identity,))
        count += 1
    need(count == expected, 'Actual full membership cardinality differs from authoritative count')
    extra = db.execute('SELECT count(*) FROM required_members r LEFT JOIN member_pass p USING(identity) WHERE r.population=? AND p.identity IS NULL', (name,)).fetchone()[0]
    need(extra == 0, 'Historical membership contains a member absent from current immutable source')
    db.execute('INSERT OR IGNORE INTO required_members SELECT ?,identity FROM member_pass', (name,))
    db.execute('DROP TABLE member_pass')
    db.commit()


def ingest_enriched(db, name, identity_column, enriched, state):
    categorical = Counter()
    with db:
        for row in enriched:
            identity = str(row[identity_column])
            composition = json.loads(row['non_h_composition']) if isinstance(row['non_h_composition'], str) else row['non_h_composition']
            need(type(composition) is list and all(len(pair) == 2 and type(pair[0]) is int and 2 <= pair[0] <= 118 and type(pair[1]) is int and pair[1] > 0 for pair in composition), 'Exact non-H composition required; H-only candidates retain the empty vector')
            need([p[0] for p in composition] == sorted(set(p[0] for p in composition)) == row['elements'], 'Element/composition definitions differ')
            need(sum(p[1] for p in composition) == row['heavy_atoms'] and row['element_combination'] == ','.join(str(p[0]) for p in composition), 'Size/element-combination fields differ')
            hbin = heavy_bin(row['heavy_atoms'])
            db.execute('INSERT INTO seen VALUES(?,?,?,?,?,?)', (name, identity, hbin, row['element_combination'], row['generic_murcko'], row['full_key']))
            for field, moment in state.items():
                moment.add(row[field])
            categorical[('heavy_bin', hbin)] += 1
            categorical[('element_combination', row['element_combination'])] += 1
            categorical[('scaffold', row['generic_murcko'])] += 1
            for ring in sorted(set(row['generic_ring_systems'])):
                categorical[('ring_system', ring)] += 1
            for element, atoms in composition:
                categorical[('element_presence', str(element))] += 1
                categorical[('element_atoms', str(element))] += atoms
            need(set(row['functional_groups']) == set(FUNCTIONS), 'Fixed functional group recipe required for every population')
            for function, count in row['functional_groups'].items():
                need(type(count) is int and count >= 0, 'Nonnegative integer fragment count required')
                categorical[('functional_prevalence', function)] += int(count > 0)
                categorical[('functional_matches', function)] += count
        db.executemany('INSERT INTO counts VALUES(?,?,?,?) ON CONFLICT(population,kind,key) DO UPDATE SET n=n+excluded.n', [(name, kind, key, n) for (kind, key), n in categorical.items()])
        db.executemany('INSERT OR REPLACE INTO moments VALUES(?,?,?)', [(name, field, canonical(moment.result())) for field, moment in state.items()])


def ingest_population(db, manifest_path, workers=16, batch_size=1024):
    manifest, manifest_ref = population(manifest_path)
    name = manifest['population']
    prepare_members(db, manifest, manifest_ref)
    state = load_moments(db, name)
    db.execute('CREATE TEMP TABLE feature_pass(identity TEXT PRIMARY KEY) WITHOUT ROWID')
    identity_column = manifest['features']['identity_column']
    source_count = 0
    reused = 0

    def pending_rows():
        nonlocal source_count, reused
        for row in rows(manifest['features']):
            RESOURCE_CHECK()
            identity = str(row[identity_column])
            db.execute('INSERT INTO feature_pass VALUES(?)', (identity,))
            need(db.execute('SELECT 1 FROM required_members WHERE population=? AND identity=?', (name, identity)).fetchone() is not None, 'Feature row outside the exact required population')
            source_count += 1
            if db.execute('SELECT 1 FROM seen WHERE population=? AND identity=?', (name, identity)).fetchone():
                reused += 1
            else:
                yield row

    waiting = deque()
    with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context('spawn')) as pool:
        for batch in batches(pending_rows(), batch_size):
            task = (batch, identity_column, manifest.get('allow_additive_descriptor_completion', False))
            waiting.append((pool.submit(enrich_batch, task), [str(r[identity_column]) for r in batch]))
            if len(waiting) >= 2 * workers:
                future, identities = waiting.popleft()
                enriched = future.result()
                need([str(r[identity_column]) for r in enriched] == identities, 'Descriptor enrichment changed membership/order')
                ingest_enriched(db, name, identity_column, enriched, state)
        while waiting:
            future, identities = waiting.popleft()
            enriched = future.result()
            need([str(r[identity_column]) for r in enriched] == identities, 'Descriptor enrichment changed membership/order')
            ingest_enriched(db, name, identity_column, enriched, state)
    need(source_count == manifest['expected_molecules'], 'All physical feature rows must be counted, without silent omissions')
    missing = db.execute('SELECT count(*) FROM required_members r LEFT JOIN seen s USING(population,identity) WHERE r.population=? AND s.identity IS NULL', (name,)).fetchone()[0]
    observed = db.execute('SELECT count(*) FROM seen WHERE population=?', (name,)).fetchone()[0]
    need(missing == 0 and observed == source_count and all(moment.n == observed for moment in state.values()), 'Complete exact population membership and every numeric denominator required')
    db.execute('UPDATE populations SET complete=1 WHERE name=?', (name,))
    db.execute('DROP TABLE feature_pass')
    db.commit()
    return {'population': name, 'molecules': observed, 'reused_rows': reused, 'manifest_reference': manifest_ref, 'exact_required_member_antijoin_missing': missing}


def validate_nearest(manifest_path, population_refs):
    manifest = load(manifest_path)
    need(manifest['schema'] == 'EXPANSION_EXACT_NEAREST_DISTRIBUTION_V1' and manifest['status'] == 'COMPLETE' and manifest['nearest_similarity_exact'] is True and manifest['fingerprint_recipe'] == RECIPE, 'A complete exact-nearest producer is required, not a sampled/approximate substitute')
    need(manifest['query_population'] in population_refs and manifest['query_population_manifest_reference'] == population_refs[manifest['query_population']], 'Exact-nearest query population differs')
    need(manifest['reference_populations'] and manifest['reference_population_manifest_references'] == [population_refs[name] for name in manifest['reference_populations']], 'Exact-nearest reference populations differ')
    producer = load(verify(manifest['producer_evidence_reference']))
    need(producer['status'] == 'COMPLETE' and producer['nearest_similarity_exact'] is True and producer['queries'] == manifest['expected_queries'], 'Actual full exact-nearest producer evidence required')
    need(producer['query_population_manifest_reference'] == manifest['query_population_manifest_reference'] and producer['reference_population_manifest_references'] == manifest['reference_population_manifest_references'], 'Exact-nearest producer must bind actual complete query/reference populations')
    return manifest, reference(manifest_path)


def ingest_nearest(db, manifest_path, population_refs):
    manifest, manifest_ref = validate_nearest(manifest_path, population_refs)
    name, query = manifest['comparison'], manifest['query_population']
    expected = db.execute('SELECT expected FROM populations WHERE name=? AND complete=1', (query,)).fetchone()
    need(expected is not None and expected[0] == manifest['expected_queries'], 'Full query population must be present in statistics')
    binding = canonical(manifest_ref)
    previous = db.execute('SELECT manifest,query_population,expected FROM comparisons WHERE name=?', (name,)).fetchone()
    need(previous is None or previous == (binding, query, expected[0]), 'Nearest comparison changed on resume')
    db.execute('INSERT OR IGNORE INTO comparisons(name,manifest,query_population,expected) VALUES(?,?,?,?)', (name, binding, query, expected[0]))
    db.execute('CREATE TEMP TABLE nearest_pass(identity TEXT PRIMARY KEY) WITHOUT ROWID')
    state = Moments('nearest_tanimoto')
    buffer = []
    for row in rows(manifest['results']):
        RESOURCE_CHECK()
        identity = str(row[manifest['results']['identity_column']])
        value = row[manifest['value_column']]
        need(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1, 'Exact Tanimoto must be finite in [0,1]')
        db.execute('INSERT INTO nearest_pass VALUES(?)', (identity,))
        need(db.execute('SELECT 1 FROM required_members WHERE population=? AND identity=?', (query, identity)).fetchone(), 'Nearest result outside exact query membership')
        old = db.execute('SELECT value FROM nearest WHERE comparison=? AND identity=?', (name, identity)).fetchone()
        need(old is None or old[0] == value, 'Immutable exact-nearest value changed on resume')
        buffer.append((name, identity, value))
        state.add(value)
        if len(buffer) >= 4096:
            db.executemany('INSERT OR IGNORE INTO nearest VALUES(?,?,?)', buffer)
            db.commit()
            buffer = []
    db.executemany('INSERT OR IGNORE INTO nearest VALUES(?,?,?)', buffer)
    missing = db.execute('SELECT count(*) FROM required_members r LEFT JOIN nearest n ON n.comparison=? AND n.identity=r.identity WHERE r.population=? AND n.identity IS NULL', (name, query)).fetchone()[0]
    count = db.execute('SELECT count(*) FROM nearest WHERE comparison=?', (name,)).fetchone()[0]
    need(missing == 0 and count == state.n == expected[0], 'Every exact-nearest query result must be present exactly once')
    db.execute('INSERT OR REPLACE INTO moments VALUES(?,?,?)', ('NN:' + name, state.field, canonical(state.result())))
    db.execute('UPDATE comparisons SET complete=1 WHERE name=?', (name,))
    db.execute('DROP TABLE nearest_pass')
    db.commit()
    return {'comparison': name, 'queries': count, 'manifest_reference': manifest_ref, 'missing_results': missing}


def completion(db, baseline_only=False):
    all_populations = {name: (expected, complete) for name, expected, complete in db.execute('SELECT name,expected,complete FROM populations')}
    required = ('v1_common', 'pubchem_1m') if baseline_only else GROUPS
    need(set(required) <= set(all_populations) and all(all_populations[name][1] == 1 for name in required), 'Complete Common/PubChem baseline required' if baseline_only else 'All four exact full populations must complete before the report')
    populations = {name: all_populations[name] for name in required}
    need(populations['pubchem_1m'][0] == 1000000, 'Declared PubChem baseline size must be exactly1M')
    if not baseline_only:
        need(populations['R'][0] == populations['N'][0] == 1250000, 'Declared first-batch/sample sizes must match task2.1/2.5')
        overlap = db.execute("SELECT count(*) FROM seen r JOIN seen n ON n.identity=r.identity AND n.population='N' WHERE r.population='R'").fetchone()[0]
        need(overlap == 0, 'Random and novelty streams must contain disjoint full identities')
    all_comparisons = {name: (query, expected, complete, load_manifest) for name, query, expected, complete, load_manifest in db.execute('SELECT name,query_population,expected,complete,manifest FROM comparisons')}
    required_comparisons = [('pubchem_to_v1', ['v1_common'])]
    if not baseline_only:
        required_comparisons.append(('pubchem_to_augmented', ['v1_common', 'R', 'N']))
    comparisons = {}
    for name, references in required_comparisons:
        need(name in all_comparisons, 'Complete same-query exact before/after coverage is mandatory: ' + name)
        comparisons[name] = all_comparisons[name]
        need(name in comparisons and comparisons[name][:3] == ('pubchem_1m', 1000000, 1), 'Complete same-query exact before/after coverage is mandatory: ' + name)
        manifest = load(verify(json.loads(comparisons[name][3])))
        need(manifest['reference_populations'] == references, 'Incorrect reference scope for coverage comparison')
    if not baseline_only:
        violation = db.execute("SELECT count(*) FROM nearest b JOIN nearest a USING(identity) WHERE b.comparison='pubchem_to_v1' AND a.comparison='pubchem_to_augmented' AND a.value<b.value").fetchone()[0]
        need(violation == 0, 'Exact coverage cannot decrease when reference molecules are added')
    return populations, comparisons
