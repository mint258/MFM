# Population-only figures from accepted current1M and complete Common counts

Source-only implementation: `workflows.expansion.population_figures_v1`.
No figures or native test success are claimed by this source commit. Root owns
actual deployment, CPU admission, native source fixtures, render/visual QA and
terminal-accounting review. The original statistics_cache_bc4669c ten files are
untouched; no scientific calculation, chemistry enrichment, SQLite open or
original molecule-feature read occurs here.

The only counted inputs are the six exact artifacts in the actual190 Root review:
`B/current_baseline_Common_statistics_1885190_root_actual_v1.json`, 6683 bytes,
SHA256 `62419f8391a004ba55c2a1e4b8447494fdcfe49001a18c674b1d6bd927869d40`.
The wrapper/Root/original receipt artifact lists must agree. Total counted body
bytes are 4,838,956. They are copied without changing bytes into `counted_inputs`
so complete tails, categories and full scaffold spectra remain available alongside
the report. The separately pinned original functional-group recipe is copied too.
The reference review, producer receipt, original tables receipt and accounting
are small metadata; the closed database path present in the review is never used.

The plot rule follows original `distribution_report_v1/render.py`
SHA256 `c788b25b698c4f86c6fbdc011b707665eb37868382a9af85c6f5dd0142740737`:
finite-bin midpoint/probability-mass lines and combined per-population .005/.995
bin-edge limits, including its boundary convention. No histogram rebinning or
smoothing. Functional groups retain the original recipe order, original .0–1.0
prevalence scale and overlapping definitions. Elements use molecule-presence
counts. The scaffold top10,000 frequency ranks are reconstructed from the full
counted spectrum (tied counts give identical plotted y), not recomputed chemistry.

## Admitted CLI and plan

Using Root's actual clean cwd, absolute Python-I guarded entry and source pins:

```text
PY -I -B ABS_GUARDED_ENTRY workflows.expansion.test_population_figures_v1 -v
PY -I -B ABS_GUARDED_ENTRY workflows.expansion.population_figures_v1 --plan ABS_BOUND_PLAN --startup-proof ABS_STARTUP
```

A minimal template extends the actual current Alpha reports resource template
(no new generic builder is necessary):

- `schema: PUBCHEM_POPULATION_ONLY_FIGURES_PLAN_V1`
- `scope_key: current_baseline_Common_population_figures_v1`
- `statistics_actual_review_reference`: actual190 triple above
- `reviewed_storage_budget_reference`: actual Root V2 triple
- `endpoint: 218.192.171.238:22`, `uid: 1264`
- existing real `runtime_profile_reference`, `quota_snapshot`, `quota_authority`,
  `code_references`, bound `execution_argv` and node-launcher startup bindings
- `workers: 16` (actual admitted allocation; rendering is sequential),
  `software_rss_budget_bytes` e.g. 8 GiB and actual reviewed node reserve
- aggregate `output_scope_root: /gfshome/alpha/pubchem_expansion_20261103/reports`
- fresh private `output_directory` under that scope; retries preserve old output
  and use a fresh stage directory (no SQLite resume or scientific retry)
- current V2 reports `output_cap_bytes: 5000000000`,
  `other_future_reserved_bytes: 1264483236352`,
  `minimum_free_bytes: 200000000000`, all checked against actual review

Native source tests cover original edge-quantile behaviour including retained
underflow/overflow, and exact spectrum→top10k recovery including boundary ties.
They do not run chemistry. Main static repository checker is separate from native
tests; do not label AST/source checking as actual figure QA.

Dependencies are this module + `alpha_runtime_v1` (common/profile/guard/quota and
its existing dependencies), Matplotlib and PyArrow. No `distribution_report_v1`
namespace, RDKit, legacy Main1278 or original scientific source imports are needed.
Matplotlib uses Agg, UTF-8 SVG text, fixed salt and DejaVu Sans; PNG/PDF/SVG hashes
and software versions are recorded. Each SVG must be <2,000,000 bytes. Output is
nine images plus `v1_distribution_population_only.md`, counted inputs, recipe and
receipt, ordinarily well below 100MB (not a new storage cap or stopping policy).

The report explicitly does not claim complete Task2.1, one-million exact NN,
before/after coverage, ten-million R/N queues, 2.5-million generation or training.
No empty NN placeholder figure is created. The receipt is pending actual plot QA
and Root terminal acceptance, not self-certification of a complete release.
