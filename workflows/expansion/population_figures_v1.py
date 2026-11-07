"""Render accepted current1M/Common counted tables; no molecule or SQLite reads."""
import argparse
import csv
import math
import os
from pathlib import Path
import shutil
import sys
from .alpha_runtime_v1 import common as Q

MODULE = 'workflows.expansion.population_figures_v1'
REVIEW_SHA = '62419f8391a004ba55c2a1e4b8447494fdcfe49001a18c674b1d6bd927869d40'
VERSION = 'alpha-original502-generic3642-recovery-v1'
GROUPS = ('pubchem_1m', 'v1_common')
TOTALS = dict(pubchem_1m=1000000, v1_common=1196122)
FIELDS = ('heavy_atoms', 'molecular_weight_Da', 'rings', 'aromatic_rings', 'isotopic_atoms', 'stereocenters', 'logp', 'tpsa_A2', 'hbd', 'hba', 'rotatable_bonds')
FILES = ('numeric_summary.csv', 'fixed_histograms_and_bin_ecdf.csv', 'complete_categorical_counts.parquet', 'functional_groups.csv', 'scaffold_frequency_spectrum.csv', 'population_summary.json')


def read(ref):
    Q.need(ref['bytes'] <= 2 << 20, 'Small authority metadata only')
    return Q.load(Q.verify(ref))


def authority(ref):
    Q.need(ref['bytes'] == 6683 and ref['sha256'] == REVIEW_SHA, 'Actual current190 Root review required')
    review = read(ref)
    Q.need(review['schema'] == 'ROOT_ALPHA_CURRENT_BASELINE_WITH_COMMON_STATISTICS_ACTUAL_ACCEPTANCE_V1'
        and review['status'] == 'ACCEPTED_CURRENT_1M_AND_COMPLETE_COMMON_POPULATION_STATISTICS'
        and review['reviewer'] == 'root' and review['population_version'] == VERSION
        and review['populations'] == TOTALS, 'Accepted current baseline plus entire Common required')
    parent = review['actual_parent']; account = read(review['actual_accounting_reference'])
    Q.need(parent['JobIDRaw'] == '1885190' and parent['State'] == 'COMPLETED' and parent['ExitCode'] == '0:0'
        and str(parent['UID']) == '1264' and parent['endpoint'] == account['endpoint'] == Q.ENDPOINT
        and parent in account['actual_parents'], 'Actual Alpha terminal parent/accounting binding')
    Q.verify(account['raw_sacct_reference'])
    producer = read(review['producer_receipt_reference'])
    tables = read(review['original_population_tables_receipt_reference'])
    Q.need(producer['actual_parent']['job_id'] == tables['endpoint_execution']['job_id'] == '1885190'
        and producer['actual_parent']['uid'] == tables['endpoint_execution']['uid'] == 1264
        and producer['original_statistics_receipt']['artifacts'] == tables['artifacts'] == review['artifact_references'],
        'Actual wrapper, original counted receipt and Root six-artifact pins must agree')
    refs = {Path(r['path']).name: r for r in review['artifact_references']}
    Q.need(len(refs) == 6 and set(refs) == set(FILES), 'Exactly the six counted population artifacts')
    recipe = read(tables['functional_group_recipe_reference'])
    Q.need(recipe['rdkit'] == '2025.09.5' and len(recipe['definitions']) == 28, 'Frozen original fragment definitions')
    return review, refs, tables['functional_group_recipe_reference'], recipe


def rows(path):
    with Path(path).open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def display_bounds(hist):
    """Same bin-index 0.005/0.995 display rule as original render.figures."""
    edges = [r['right'] for r in hist[:-1]]
    n = sum(r['count'] for r in hist)
    low, high, cumulative = edges[0], edges[-1], 0
    for index, row in enumerate(hist):
        previous = cumulative; cumulative += row['count']
        if previous < .005 * n <= cumulative:
            low = edges[max(0, index - 1)]
        if previous < .995 * n <= cumulative:
            high = edges[min(len(edges) - 1, index)]
    return low, high


def scaffold_ranks(spectrum, limit=10000):
    """Recover only frequency ranks; ties share y so key order cannot affect curve."""
    result = []
    for row in sorted(spectrum, key=lambda r: int(r['molecules_per_scaffold']), reverse=True):
        count = min(int(row['number_of_scaffolds']), limit - len(result))
        result.extend([int(row['molecules_per_scaffold'])] * count)
        if len(result) == limit:
            break
    return result


def counted(inputs, recipe):
    summary = Q.load(inputs / 'population_summary.json')
    Q.need(summary['populations'] == TOTALS and summary['histograms_use_unchanged_original_Moments'] is True,
        'Complete accepted population counts and original bins')
    numeric = rows(inputs / FILES[0]); fg = rows(inputs / FILES[3]); spectrum = rows(inputs / FILES[4])
    Q.need(len(numeric) == 22 and {(r['population'], r['field']) for r in numeric} == {(g, f) for g in GROUPS for f in FIELDS}
        and all(int(r['n']) == TOTALS[r['population']] for r in numeric), '11 complete numeric fields per population')
    functions = [d['name'] for d in recipe['definitions']]
    Q.need(len(fg) == 56 and {(r['population'], r['definition']) for r in fg} == {(g, f) for g in GROUPS for f in functions}, '28 fixed functional groups per population')
    for row in fg:
        Q.need(math.isclose(float(row['prevalence']), int(row['molecules_present']) / TOTALS[row['population']], rel_tol=1e-14, abs_tol=1e-15), 'Counted molecular prevalence unchanged')
    histogram = {}
    for r in rows(inputs / FILES[1]):
        row = dict(bin=int(r['bin']), left=float(r['left']), right=float(r['right']), count=int(r['count']), cumulative_count=int(r['cumulative_count']))
        histogram.setdefault((r['population'], r['field']), []).append(row)
    Q.need(set(histogram) == {(g, f) for g in GROUPS for f in FIELDS}, 'No NN or missing descriptor histogram')
    for (g, f), hist in histogram.items():
        hist.sort(key=lambda r: r['bin']); cumulative = 0
        Q.need([r['bin'] for r in hist] == list(range(len(hist))) and hist[0]['left'] == -math.inf and hist[-1]['right'] == math.inf, 'Original contiguous bins and explicit tails')
        for i, r in enumerate(hist):
            cumulative += r['count']
            Q.need(r['count'] >= 0 and cumulative == r['cumulative_count'] and (i == 0 or hist[i-1]['right'] == r['left']), 'Exact fixed-bin adjacency and mass')
        Q.need(cumulative == TOTALS[g], 'Every histogram retains entire population')
    import pyarrow.parquet as pq
    elements = {g: {} for g in GROUPS}; empty = {g: 0 for g in GROUPS}
    for batch in pq.ParquetFile(inputs / FILES[2]).iter_batches(batch_size=8192):
        for r in batch.to_pylist():
            g = r['population']; Q.need(g in GROUPS, 'Only declared counted populations')
            if r['kind'] == 'element_presence': elements[g][int(r['key'])] = int(r['molecules_or_matches'])
            if r['kind'] == 'element_combination' and r['key'] == '': empty[g] += int(r['molecules_or_matches'])
    for g in GROUPS:
        selected = [r for r in spectrum if r['population'] == g]
        Q.need(sum(int(r['molecules']) for r in selected) == TOTALS[g]
            and sum(int(r['number_of_scaffolds']) for r in selected) == summary['scaffold_long_tail'][g]['distinct_scaffolds'], 'Complete counted scaffold spectrum')
        Q.need(all(int(r['molecules']) == int(r['molecules_per_scaffold']) * int(r['number_of_scaffolds']) for r in selected), 'Exact scaffold multiplicities')
    return summary, numeric, fg, histogram, spectrum, elements, empty, functions


def figures(out, data, check):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({'svg.fonttype': 'none', 'svg.hashsalt': 'pubchem-population-v1', 'font.family': 'DejaVu Sans'})
    summary, numeric, fg, histogram, spectrum, elements, empty, functions = data
    colors = dict(pubchem_1m='#2468a2', v1_common='#2f8b62')
    labels = dict(pubchem_1m='Current PubChem baseline (1,000,000)', v1_common='Complete v1 Common (1,196,122)')
    artifacts = []; limits = {}
    def save(fig, name):
        fig.tight_layout()
        for extension in ('svg', 'pdf', 'png'):
            check(); path = out / (name + '.' + extension)
            fig.savefig(path, dpi=180, bbox_inches='tight')
            if extension == 'svg':
                path.read_text(encoding='utf-8')
                Q.need(path.stat().st_size < 2000000, 'Each UTF-8 SVG must fit Git figure limit')
            artifacts.append(Q.reference(path))
        plt.close(fig)
    fig, axes = plt.subplots(4, 3, figsize=(13, 13))
    for axis, field in zip(axes.flat, FIELDS):
        bounds = []
        for g in GROUPS:
            h = histogram[(g, field)]
            axis.stairs([r['count'] / TOTALS[g] for r in h[1:-1]], [h[1]['left']] + [r['right'] for r in h[1:-1]], baseline=None, color=colors[g], label=labels[g], linewidth=1.25)
            bounds.append(display_bounds(h))
        low, high = min(b[0] for b in bounds), max(b[1] for b in bounds)
        high = high if high > low else low + 1
        axis.set_xlim(low, high); limits[field] = [low, high]
        axis.set_title(field); axis.set_ylabel('Fraction per original fixed bin'); axis.grid(alpha=.2)
    axes.flat[-1].axis('off'); axes.flat[0].legend(frameon=False, fontsize=7)
    save(fig, 'descriptor_distributions')
    fig, axis = plt.subplots(figsize=(15, 4))
    matrix = [[float(next(r['prevalence'] for r in fg if r['population'] == g and r['definition'] == f)) for f in functions] for g in GROUPS]
    plot = axis.imshow(matrix, aspect='auto', vmin=0, vmax=1, cmap='Blues')
    axis.set_yticks(range(2), [labels[g] for g in GROUPS])
    axis.set_xticks(range(28), [f.removeprefix('fr_') for f in functions], rotation=70, ha='right')
    fig.colorbar(plot, ax=axis, label='Molecular prevalence (overlapping definitions)')
    save(fig, 'functional_group_prevalence')
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    atomic_numbers = sorted(set().union(*(set(e) for e in elements.values())))
    for index, g in enumerate(GROUPS):
        axes[0].bar([i + (index - .5) * .36 for i in range(len(atomic_numbers))], [elements[g].get(z, 0) / TOTALS[g] for z in atomic_numbers], width=.36, color=colors[g], label=labels[g])
        ranked = scaffold_ranks([r for r in spectrum if r['population'] == g])
        axes[1].loglog(range(1, len(ranked) + 1), ranked, color=colors[g], label=labels[g])
    axes[0].set_xticks(range(len(atomic_numbers)), list(map(str, atomic_numbers)), rotation=90)
    axes[0].set(xlabel='Atomic number', ylabel='Fraction of molecules containing element')
    axes[1].set(xlabel='Generic Murcko scaffold rank (first 10,000)', ylabel='Molecules per scaffold')
    for axis in axes: axis.legend(frameon=False, fontsize=7); axis.grid(alpha=.2)
    save(fig, 'elements_and_scaffold_long_tail')
    return artifacts, limits


def report(out, review_ref, refs, recipe_ref, data, limits):
    summary, numeric, fg, histogram, spectrum, elements, empty, functions = data
    lines = ['# v1 and PubChem distribution: completed population structure statistics', '',
        'Purpose: compare the current fixed pre-decontamination PubChem sample with the complete v1 Common TRAIN/VAL population. This is the completed structure-statistics portion of the eventual v1_distribution.md; Task 2.1 is not yet complete.', '',
        'The accepted statistics parent is Alpha 1885190 (COMPLETED, 0:0; 6,209 seconds; 16 CPUs). Common counts were reused byte-exact from accepted parent 1885178; zero Common feature rows were recomputed. The corrected baseline uses population version `' + VERSION + '`: seed 20261025, hash domain `PubChem-baseline-uniform`, minimum-CID full-key deduplication before v1/downstream exclusion. It replaces 31 old sample identities with 31 new identities; representative CIDs of retained identities did not change.', '',
        '| Population | Molecules | Distinct scaffolds | Singleton scaffolds | Acyclic / empty scaffold molecules |', '|---|---:|---:|---:|---:|']
    for g in GROUPS:
        t = summary['scaffold_long_tail'][g]
        lines.append('| %s | %s | %s | %s | %s |' % (g, f'{TOTALS[g]:,}', f"{t['distinct_scaffolds']:,}", f"{t['singleton_scaffolds']:,}", f"{t['acyclic_empty_scaffold_molecules']:,}"))
    lines += ['', '## Figures and method', '', '![Eleven descriptor distributions](descriptor_distributions.svg)', '',
        '![Twenty-eight overlapping functional group definitions, two populations](functional_group_prevalence.svg)', '',
        '![Element prevalence and scaffold rank](elements_and_scaffold_long_tail.svg)', '',
        'The 22 original numeric summaries use population Welford moments. All eleven descriptor panels plot the original fixed-bin probability masses as steps spanning each unchanged bin, without rebinning, smoothing, or density normalization. The common display bounds are the minimum lower and maximum upper original bin edges containing each population\'s 0.5th and 99.5th percentile. Underflow, overflow and every clipped tail remain in [the complete histogram CSV](counted_inputs/fixed_histograms_and_bin_ecdf.csv); these are binned summaries, not exact unbinned quantiles.', '',
        'The functional group matrix uses the original RDKit 2025.09.5 recipe (28 definitions, unique matches); overlapping definitions are not mutually exclusive. The six counted inputs are read directly. No molecule, fingerprint, geometry, or database is opened and no chemistry is recomputed. Element prevalence counts molecules containing an element, divided by each full population count. Scaffold frequencies are recovered exactly from the counted frequency spectrum; tied frequencies are identical irrespective of key order. Rank plots display only the first 10,000; [the full spectrum](counted_inputs/scaffold_frequency_spectrum.csv) and [all categories](counted_inputs/complete_categorical_counts.parquet) are retained.', '',
        '## Observations, anomalies and limits', '',
        'Current PubChem has 221,134 distinct generic scaffolds versus 185,507 in Common. This descriptive comparison is affected by population size and population composition; it is not a diversity or coverage significance test. Acyclic molecules share the empty scaffold category; it is retained rather than treated as a missing value. Functional group prevalence does not sum to one. Original outliers, explicit histogram tails and empty non-hydrogen compositions are retained; rendering introduces no screening or masking.', '',
        'Empty non-hydrogen composition counted molecules: ' + ', '.join(g + '=' + str(empty[g]) for g in GROUPS) + '.', '',
        '**Pending:** the complete one-million-query exact-nearest calculation, before/after exact coverage, 10-million R/N ordering and the first 2.5-million-molecule expansion batch are not certified by this report. No nearest-neighbour figure or empty placeholder is emitted. Conformer/D-label production, quality application and training release are separate work. This renderer does not change source selection, statistical definitions, scientific masks or acceptance thresholds.', '',
        '## Exact counted input bindings', '',
        '| File | Bytes | SHA-256 |', '|---|---:|---|']
    for name in FILES:
        r = refs[name]; lines.append('| [%s](counted_inputs/%s) | %s | `%s` |' % (name, name, r['bytes'], r['sha256']))
    lines += ['', 'Root statistics review: `' + review_ref['path'] + '`; SHA-256 `' + review_ref['sha256'] + '`.', '',
        'Original functional group recipe: `' + recipe_ref['path'] + '`; SHA-256 `' + recipe_ref['sha256'] + '`. The actual rendering receipt records the copied recipe, renderer/source/runtime pins, all image hashes and numerical display bounds. PNG/PDF and UTF-8 vector SVG are emitted; each SVG is smaller than 2 MB. Native plot inspection and this rendering parent\'s terminal accounting are recorded separately by Root.', '']
    path = out / 'v1_distribution_population_only.md'; path.write_text('\n'.join(lines), encoding='utf-8')
    return Q.reference(path)


def run(plan_path, startup_proof):
    from .alpha_runtime_v1.profile import admit
    from .alpha_runtime_v1.guard import Guard
    plan = Q.load(plan_path); proof = Q.load(startup_proof); actual = admit(plan, minimum_workers=16)
    request = proof['request']
    Q.need(plan['schema'] == 'PUBCHEM_POPULATION_ONLY_FIGURES_PLAN_V1'
        and plan['scope_key'] == request['scope_key'] == 'current_baseline_Common_population_figures_v1'
        and request['producer_plan_reference'] == Q.reference(plan_path) and request['execution_argv'] == plan['execution_argv']
        and sys.argv[-4:] == ['--plan', str(plan_path), '--startup-proof', str(startup_proof)]
        and request['execution_argv'][-4:] == sys.argv[-4:]
        and str(proof['job_id']) == actual['job_id'] and proof['uid'] == os.getuid() == 1264
        and proof['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        and Q.reference(__file__) in request['source_references'], 'Actual pinned Alpha rendering plan/boot/entry')
    budget = read(plan['reviewed_storage_budget_reference'])
    Q.need(budget['schema'] == 'ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2' and budget['reviewer'] == 'root'
        and budget['scope_total_caps_bytes']['reports'] == plan['output_cap_bytes']
        and budget['other_future_reserved_bytes_for_each_scope']['reports'] == plan['other_future_reserved_bytes']
        and budget['minimum_free_after_all_future_bytes'] == plan['minimum_free_bytes'], 'Reviewed aggregate reports cap and all-future floor')
    guard = Guard(plan)
    try:
        review, refs, recipe_ref, recipe = authority(plan['statistics_actual_review_reference'])
        out = Path(plan['output_directory']); out.mkdir(parents=True, exist_ok=False)
        inputs = out / 'counted_inputs'; inputs.mkdir()
        copied = []
        for name in FILES:
            guard.check(); source = Q.verify(refs[name]); target = inputs / name
            shutil.copyfile(source, target); r = Q.reference(target)
            Q.need((r['bytes'], r['sha256']) == (refs[name]['bytes'], refs[name]['sha256']), 'Counted input copy exactly preserved')
            copied.append(r)
        recipe_copy = out / 'functional_group_recipe.json'; shutil.copyfile(Q.verify(recipe_ref), recipe_copy)
        replica = Q.reference(recipe_copy)
        Q.need((replica['bytes'], replica['sha256']) == (recipe_ref['bytes'], recipe_ref['sha256']), 'Copied original fragment recipe unchanged')
        data = counted(inputs, recipe)
        Q.need(data[0]['scaffold_long_tail'] == review['scaffold_long_tail'], 'Original summary equals actual Root scaffold review')
        artifacts, limits = figures(out, data, guard.check)
        artifacts.append(report(out, plan['statistics_actual_review_reference'], refs, recipe_ref, data, limits))
        guard.sample(); guard.check()
        import matplotlib, pyarrow
        return Q.write(out / 'receipt.json', dict(schema='PUBCHEM_POPULATION_ONLY_FIGURES_RECEIPT_V1',
            status='FIGURES_AND_POPULATION_REPORT_WRITTEN_PENDING_NATIVE_QA_AND_ROOT_ACTUAL_C0_REVIEW',
            statistics_actual_review_reference=plan['statistics_actual_review_reference'], input_artifact_references=list(refs.values()),
            copied_counted_inputs=copied, functional_group_recipe_reference=recipe_ref, copied_recipe_reference=Q.reference(recipe_copy),
            original_statistics_receipt_reference=review['original_population_tables_receipt_reference'],
            actual_parent=actual, plan_reference=Q.reference(plan_path), startup_proof_reference=Q.reference(startup_proof),
            source_reference=Q.reference(__file__), artifacts=artifacts, display_bounds=limits,
            software_versions=dict(matplotlib=matplotlib.__version__, pyarrow=pyarrow.__version__),
            populations=TOTALS, population_version=VERSION, fixed_bins_rebinned=False, chemistry_rows_recomputed=0,
            database_opened=False, full_1M_exact_nearest_or_coverage_complete=False, batch2_5M_complete=False,
            task2_1_complete=False, scaffold_rank_display_limit=10000, runtime=guard.receipt()))
    finally:
        guard.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--startup-proof', required=True, type=Path)
    args = parser.parse_args(); run(args.plan, args.startup_proof)


if __name__ == '__main__':
    main()
