"""Standalone scientific figures and counted CSV/JSON/Parquet report artifacts."""
from __future__ import annotations
import json
from pathlib import Path
from .aggregate import Moments, completion, load_moments
from .functional_groups import FUNCTIONS, NUMERIC_FIELDS
from .io import GROUPS, canonical, export_cursor, load, reference, verify, write_new


def export_all_counts(db, path, groups=GROUPS):
    import pyarrow as pa
    import pyarrow.parquet as pq
    schema = pa.schema([('population', pa.string()), ('kind', pa.string()), ('key', pa.string()), ('molecules_or_matches', pa.int64())])
    cursor = db.execute('SELECT population,kind,key,n FROM counts ORDER BY population,kind,key')
    with pq.ParquetWriter(path, schema, compression='zstd') as writer:
        while True:
            rows = cursor.fetchmany(4096)
            if not rows:
                break
            selected = [dict(zip(schema.names, row)) for row in rows if row[0] in groups]
            if selected:
                writer.write_table(pa.Table.from_pylist(selected, schema=schema))
    return reference(path)


def long_tail(db, population_name, total):
    unique, singleton = db.execute("SELECT count(*),coalesce(sum(n=1),0) FROM counts WHERE population=? AND kind='scaffold'", (population_name,)).fetchone()
    crossing, cumulative = {}, 0
    for rank, (n,) in enumerate(db.execute("SELECT n FROM counts WHERE population=? AND kind='scaffold' ORDER BY n DESC,key", (population_name,)), 1):
        cumulative += n
        for fraction in (.5, .9, .99):
            if fraction not in crossing and cumulative >= fraction * total:
                crossing[fraction] = rank
    return {'distinct_scaffolds': unique, 'singleton_scaffolds': singleton, 'singleton_scaffold_fraction': singleton / unique, 'molecules_in_singleton_scaffolds': singleton, 'scaffolds_for_50pct_molecules': crossing[.5], 'scaffolds_for_90pct_molecules': crossing[.9], 'scaffolds_for_99pct_molecules': crossing[.99], 'acyclic_empty_scaffold_molecules': (db.execute("SELECT n FROM counts WHERE population=? AND kind='scaffold' AND key=''", (population_name,)).fetchone() or (0,))[0]}


def tables(db, out, baseline_only=False):
    populations, comparisons = completion(db, baseline_only=baseline_only)
    groups = tuple(populations)
    totals = {name: value[0] for name, value in populations.items()}
    numeric, histogram = [], []
    state = {}
    for group, field, raw in db.execute('SELECT population,field,state FROM moments ORDER BY population,field'):
        if group not in populations and not (group.startswith('NN:') and group[3:] in comparisons):
            continue
        value = Moments(field, json.loads(raw))
        state[(group, field)] = value
        numeric.append((group, field, *value.summary()))
        histogram.extend((group, field, *row) for row in value.histogram())
    refs = []
    refs.append(export_cursor(out / 'numeric_summary.csv', ['population_or_comparison', 'field', 'n', 'mean', 'population_std', 'min', 'max'], numeric))
    refs.append(export_cursor(out / 'fixed_histograms_and_bin_ecdf.csv', ['population_or_comparison', 'field', 'bin', 'left', 'right', 'count', 'cumulative_count', 'bin_ecdf'], histogram))
    refs.append(export_all_counts(db, out / 'complete_categorical_counts.parquet', groups))
    refs.append(export_cursor(out / 'scaffold_frequency_spectrum.csv', ['population', 'molecules_per_scaffold', 'number_of_scaffolds', 'molecules'], (row for row in db.execute("SELECT population,n,count(*),n*count(*) FROM counts WHERE kind='scaffold' GROUP BY population,n ORDER BY population,n") if row[0] in groups)))
    refs.append(export_cursor(out / 'top1000_scaffolds_each.csv', ['population', 'rank', 'scaffold', 'molecules'], ((group, rank, key, n) for group in groups for rank, (key, n) in enumerate(db.execute("SELECT key,n FROM counts WHERE population=? AND kind='scaffold' ORDER BY n DESC,key LIMIT 1000", (group,)), 1))))
    fg = []
    for group in groups:
        counts = {(kind, key): n for kind, key, n in db.execute("SELECT kind,key,n FROM counts WHERE population=? AND kind IN ('functional_prevalence','functional_matches')", (group,))}
        for function in FUNCTIONS:
            prevalent, matches = counts.get(('functional_prevalence', function), 0), counts.get(('functional_matches', function), 0)
            fg.append((group, function, prevalent, matches, prevalent / totals[group], matches / totals[group]))
    refs.append(export_cursor(out / 'functional_groups.csv', ['population', 'definition', 'molecules_present', 'total_unique_matches', 'prevalence', 'mean_matches'], fg))
    category_rows = []
    for kind in ('heavy_bin', 'element_combination', 'element_presence', 'ring_system', 'scaffold'):
        query = '''SELECT p.key,p.n,coalesce(v.n,0) FROM counts p
                   LEFT JOIN counts v ON v.population='v1_common' AND v.kind=p.kind AND v.key=p.key
                   WHERE p.population='pubchem_1m' AND p.kind=? ORDER BY p.n DESC,p.key'''
        # Full category coverage rows stream directly to disk, never all in RAM.
        def coverage_rows():
            for key, pubchem, common in db.execute(query, (kind,)):
                p, v = pubchem / totals['pubchem_1m'], common / totals['v1_common']
                yield (key, pubchem, common, p, v, p / v if v else '', int(common == 0), int(common == 0 or p >= 2 * v))
        refs.append(export_cursor(out / ('coverage_' + kind + '.csv'), ['key', 'pubchem_molecules', 'v1_molecules', 'pubchem_frequency', 'v1_frequency', 'pubchem_over_v1_frequency', 'absent_in_v1', 'descriptive_at_least_2x_underrepresentation'], coverage_rows()))
    strata = db.execute('''SELECT s.heavy_bin,s.element_combination,count(*),avg(n.value),
           avg(n.value<0.4),avg(n.value<0.6),avg(n.value<0.8)
           FROM seen s JOIN nearest n ON n.identity=s.identity AND n.comparison='pubchem_to_v1'
           WHERE s.population='pubchem_1m' GROUP BY s.heavy_bin,s.element_combination ORDER BY s.heavy_bin,s.element_combination''')
    refs.append(export_cursor(out / 'exact_nearest_v1_by_size_element_stratum.csv', ['heavy_bin', 'element_combination', 'queries', 'mean_exact_similarity', 'fraction_below_0.4', 'fraction_below_0.6', 'fraction_below_0.8'], strata))
    gain = db.execute("SELECT count(*),avg(a.value-b.value),sum(a.value>b.value),min(a.value-b.value),max(a.value-b.value) FROM nearest b JOIN nearest a USING(identity) WHERE b.comparison='pubchem_to_v1' AND a.comparison='pubchem_to_augmented'").fetchone()
    identity_matches = {}
    for comparison, binding in comparisons.items():
        manifest = load(verify(json.loads(binding[3])))
        reference_groups = manifest['reference_populations']
        placeholders = ','.join('?' for unused in reference_groups)
        query = '''SELECT count(*) FROM nearest n JOIN seen q ON q.population=? AND q.identity=n.identity
          WHERE n.comparison=? AND EXISTS(SELECT 1 FROM seen r WHERE r.full_key=q.full_key AND r.population IN (''' + placeholders + '))'
        exact = db.execute(query, (binding[0], comparison, *reference_groups)).fetchone()[0]
        identical_fp = db.execute('SELECT count(*) FROM nearest WHERE comparison=? AND value=1.0', (comparison,)).fetchone()[0]
        identity_matches[comparison] = {'exact_full_identity_matches_in_reference': exact, 'tanimoto_equal_one_including_distinct_identity_fingerprint_matches': identical_fp, 'identity_matches_retained_in_all_statistics': True}
    long_tails = {group: long_tail(db, group, totals[group]) for group in groups}
    summary = {'schema': 'EXPANSION_DISTRIBUTION_COUNTED_SUMMARY_V1', 'status': 'ALL_REQUIRED_NUMERICAL_POPULATIONS_AND_EXACT_COVERAGE_COMPLETE', 'populations': totals, 'numeric': [{'population_or_comparison': row[0], 'field': row[1], 'n': row[2], 'mean': row[3], 'population_std': row[4], 'min': row[5], 'max': row[6]} for row in numeric], 'scaffold_long_tail': long_tails, 'coverage_gain': dict(zip(('same_queries', 'mean_similarity_gain', 'queries_with_strictly_improved_coverage', 'minimum_similarity_gain', 'maximum_similarity_gain'), gain)), 'comparison_manifests': {name: json.loads(value[3]) for name, value in comparisons.items()}, 'population_manifests': {name: json.loads(raw) for name, raw in db.execute('SELECT name,manifest FROM populations')}, 'functional_group_definitions_overlap': True, 'bin_ecdf_is_fixed_bin_not_an_unbinned_curve': True, 'underrepresentation_frequency_ratio_2_is_descriptive_only_not_selection': True}
    summary['identity_match_counts'] = identity_matches
    if baseline_only:
        summary['coverage_gain'] = None
        summary['status'] = 'FULL_COMMON_AND_ONE_MILLION_PUBCHEM_BASELINE_COMPLETE'
        summary['R_N_conformer_generation_required_for_this_baseline'] = False
    summary['pubchem_baseline_pool_phase'] = 'SAME_X_INTERNAL_DEDUP_BEFORE_V1_DOWNSTREAM_DECONTAMINATION_AND_NOVELTY'
    refs.append(write_new(out / 'summary.json', summary))
    return summary, state, fg, refs


def figures(db, out, state, fg, groups=GROUPS):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    colors = dict(zip(groups, ('#2468a2', '#2f8b62', '#c47615', '#98506e')))
    refs = []

    def save(figure, name):
        figure.tight_layout()
        for extension in ('pdf', 'png'):
            path = out / (name + '.' + extension)
            figure.savefig(path, dpi=180, bbox_inches='tight')
            refs.append(reference(path))
        plt.close(figure)

    fig, axes = plt.subplots(4, 3, figsize=(13, 13))
    for axis, field in zip(axes.flat, NUMERIC_FIELDS):
        display_limits = []
        for group in groups:
            value = state[(group, field)]
            # All finite-bin mass is plotted; explicit under/overflow remain in CSV.
            x = [(a + b) / 2 for a, b in zip(value.edges[:-1], value.edges[1:])]
            y = [n / value.n for n in value.bins[1:-1]]
            axis.plot(x, y, label=group, color=colors[group], linewidth=1.25)
            cumulative = 0
            low, high = value.edges[0], value.edges[-1]
            for index, count in enumerate(value.bins):
                previous = cumulative
                cumulative += count
                if previous < .005 * value.n <= cumulative:
                    low = value.edges[max(0, index - 1)]
                if previous < .995 * value.n <= cumulative:
                    high = value.edges[min(len(value.edges) - 1, index)]
            display_limits.append((low, high))
        lower = min(pair[0] for pair in display_limits)
        upper = max(pair[1] for pair in display_limits)
        axis.set_xlim(lower, upper if upper > lower else lower + 1)
        axis.set_title(field)
        axis.set_ylabel('Fraction per fixed bin')
        axis.grid(alpha=.2)
    for axis in list(axes.flat)[len(NUMERIC_FIELDS):]:
        axis.axis('off')
    axes.flat[0].legend(frameon=False, fontsize=8)
    save(fig, 'descriptor_distributions')

    fig, axis = plt.subplots(figsize=(6.8, 4.5))
    for name, label, color in (('pubchem_to_v1', 'v1 Common', '#2468a2'), ('pubchem_to_augmented', 'v1 Common + R + N', '#b55538')):
        if ('NN:' + name, 'nearest_tanimoto') not in state:
            continue
        value = state[('NN:' + name, 'nearest_tanimoto')]
        cdf = np.cumsum(value.bins[1:-1]) / value.n
        axis.step(value.edges[1:], cdf, where='post', color=color, label=label)
    axis.set(xlim=(0, 1), ylim=(0, 1), xlabel='Exact nearest ECFP4 Tanimoto', ylabel='Fixed-bin empirical cumulative fraction')
    axis.legend(frameon=False)
    axis.grid(alpha=.2)
    save(fig, 'exact_nearest_coverage_before_after' if 'R' in groups else 'exact_nearest_coverage_baseline')

    matrix = np.array([[next(row[4] for row in fg if row[0] == group and row[1] == function) for function in FUNCTIONS] for group in groups])
    fig, axis = plt.subplots(figsize=(15, 4))
    plot = axis.imshow(matrix, aspect='auto', vmin=0, vmax=1, cmap='Blues')
    axis.set_yticks(range(len(groups)), groups)
    axis.set_xticks(range(len(FUNCTIONS)), [name.removeprefix('fr_') for name in FUNCTIONS], rotation=70, ha='right')
    fig.colorbar(plot, ax=axis, label='Molecular prevalence')
    save(fig, 'functional_group_prevalence')

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    elements = sorted({int(key) for key, in db.execute("SELECT DISTINCT key FROM counts WHERE kind='element_presence'")})
    for index, group in enumerate(groups):
        total = state[(group, 'heavy_atoms')].n
        present = {int(key): n / total for key, n in db.execute("SELECT key,n FROM counts WHERE population=? AND kind='element_presence'", (group,))}
        axes[0].bar(np.arange(len(elements)) + (index - 1.5) * .18, [present.get(z, 0) for z in elements], width=.18, color=colors[group], label=group)
        frequencies = [n for n, in db.execute("SELECT n FROM counts WHERE population=? AND kind='scaffold' ORDER BY n DESC,key LIMIT 10000", (group,))]
        axes[1].loglog(range(1, len(frequencies) + 1), frequencies, color=colors[group], label=group)
    axes[0].set_xticks(np.arange(len(elements)), [str(z) for z in elements])
    axes[0].set(xlabel='Atomic number', ylabel='Fraction of molecules containing element')
    axes[1].set(xlabel='Generic Murcko scaffold frequency rank (first 10,000)', ylabel='Molecules per scaffold')
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].legend(frameon=False, fontsize=8)
    save(fig, 'elements_and_scaffold_long_tail')
    return refs


def report(out, summary):
    lines = ['# PubChem expansion: distribution and exact coverage', '', 'This report covers the complete declared v1 Common TRAIN/VAL population, the fixed-seed same-X internally deduplicated PubChem sample of one million molecules before v1/downstream decontamination and novelty selection, and both complete first-batch streams. All physical input rows are counted and checked against their exact authoritative molecular membership. No sampled Common is substituted.', '', '| Population | Molecules | Distinct generic Murcko scaffolds | Singleton scaffolds |', '|---|---:|---:|---:|']
    for group in GROUPS:
        tail = summary['scaffold_long_tail'][group]
        lines.append('| %s | %s | %s | %s |' % (group, f"{summary['populations'][group]:,}", f"{tail['distinct_scaffolds']:,}", f"{tail['singleton_scaffolds']:,}"))
    lines += ['', '## Rules and reproducibility', '', 'All source/selection/producer manifests and physical hashes are listed in summary.json and receipt.json. Functional groups use the fixed RDKit2025.09.5 fragment definitions in functional_group_recipe.json, with unique substructure matches. These definitions overlap. Existing screening descriptors and decisions are unchanged; missing descriptive Common fields may be added only by the pinned v1 compatibility dispatcher with full-identity and existing-field checks.', '', 'Numeric summaries use streaming Welford population moments. Every finite value enters a fixed bin, including explicit underflow/overflow. Descriptor figures display the combined 0.5th-to-99.5th-percentile bin range to make the main distributions legible; all tail counts remain in CSV. Curves labelled bin ECDF use 0.001-wide Tanimoto bins and are not presented as unbinned empirical curves. Complete scaffold/ring/element/combination counts are preserved in Parquet; CSV tables provide summaries, frequency spectra, and descriptive coverage ratios.', '', '## Distribution and underrepresented regions', '', '![Descriptor distributions](descriptor_distributions.png)', '', '![Elements and scaffold long tail](elements_and_scaffold_long_tail.png)', '', '![Functional groups](functional_group_prevalence.png)', '', 'coverage_scaffold.csv, coverage_ring_system.csv, coverage_element_combination.csv and coverage_heavy_bin.csv report exact molecular frequencies in the PubChem sample and v1 Common. Absent categories and a prespecified PubChem/v1 frequency ratio of at least two are descriptive reporting flags, not molecule-selection rules. exact_nearest_v1_by_size_element_stratum.csv also reports exact nearest-neighbour similarities by size and element combination.', '', '## Exact coverage before and after expansion', '', 'Both comparisons use exactly the same one million query identities. The augmented reference is the union of complete v1 Common, R and N populations. Approximate nearest neighbours, partial references and query samples are rejected.', '', '![Exact nearest coverage](exact_nearest_coverage_before_after.png)', '']
    gain = summary['coverage_gain']
    lines += ['Mean exact nearest-similarity gain: %.8g. Strictly improved queries: %s / %s. Minimum gain: %.8g.' % (gain['mean_similarity_gain'], f"{gain['queries_with_strictly_improved_coverage']:,}", f"{gain['same_queries']:,}", gain['minimum_similarity_gain']), '', 'Exact full-identity/self matches remain in these query distributions and are counted separately from Tanimoto=1 fingerprint matches in summary.json. No unasked identity exclusion changes the reference sample.', '', '## Limitations', '', 'This component reports molecular structure distributions and coverage. It does not by itself establish conformer/D-label completion, production parent accounting, or a training release. Complete batch-level scientific delivery is certified separately. Figure rank curves display the first 10,000 scaffold ranks; full counted spectra and categorical tables remain available. No missing input or incomplete exact-nearest computation is described as completed.', '']
    path = out / 'v1_distribution.md'
    path.write_text('\n'.join(lines), encoding='utf-8')
    return reference(path)


def report_baseline(out, summary):
    lines = ['# v1 Common and PubChem baseline distribution', '', 'Task2.1 baseline: complete v1 Common TRAIN/VAL and the fixed-seed random one million molecules from the same-X screened, internally full-InChIKey-deduplicated PubChem pool. The PubChem sample is taken BEFORE v1/downstream decontamination or novelty selection. No R/N conformer-generation readiness is required for this graph-only baseline.', '', '| Population | Molecules | Distinct generic Murcko scaffolds |', '|---|---:|---:|']
    for group in ('v1_common', 'pubchem_1m'):
        lines.append('| %s | %s | %s |' % (group, f"{summary['populations'][group]:,}", f"{summary['scaffold_long_tail'][group]['distinct_scaffolds']:,}"))
    lines += ['', '![Structure descriptor distributions](descriptor_distributions.png)', '', '![Elements and scaffold long tail](elements_and_scaffold_long_tail.png)', '', '![Fixed functional group definitions](functional_group_prevalence.png)', '', '![Exact nearest-v1 coverage baseline](exact_nearest_coverage_baseline.png)', '', 'Every physical source row is counted and checked against independently pinned complete membership. Exact nearest-v1 results cover the SAME one million PubChem query identities. Exact full-identity/self matches are retained; summary.json reports them separately from Tanimoto=1 fingerprint matches. The exact NN source, complete reference population, source hashes, seed and baseline pool phase remain pinned.', '', 'Numeric summaries use Welford population moments. Histogram CSV retains all finite-bin and under/overflow mass; displayed descriptor panels use the combined0.5th-to-99.5th-percentile bin range. Tanimoto curves are explicitly fixed-bin ECDFs (0.001 bins), not unbinned empirical curves. Functional-group SMARTS/count uniqueness/version/source hashes are recorded in functional_group_recipe.json and used unchanged in all eventual cohorts.', '', 'Complete categorical counts, scaffold frequency spectra, long-tail summaries, functional-group counts and descriptive size/element/scaffold/ring coverage ratios are provided as CSV/JSON/Parquet. Absent-v1 and PubChem/v1 frequency ratio>=2 are descriptive annotations only, never selection rules. Existing molecular screening decisions and original descriptors remain unchanged.', '', 'This baseline report does not claim R/N generation, D-label completion, augmented-reference coverage, batch1 release or training. The separate complete-batch report adds R/N distributions and exact before/after coverage once their graph populations are available.', '']
    path=out/'v1_distribution.md'
    path.write_text('\n'.join(lines),encoding='utf-8')
    return reference(path)
