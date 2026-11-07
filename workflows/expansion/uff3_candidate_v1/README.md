# PubChem maximum-three UFF candidate adapter

Implements the user's 2026-11-03 amendment: export at most three actual UFF
conformers per selected R/N molecule, no below-threshold fill and no scientific
retry. Original S-prime sources and the old 10-conformer producer are unchanged.
This is an adapter library; Root supplies Slurm admission, quota/memory guards,
unique work claims, the full 2.5M R/N source population and final family export.
There is no job submitter, hidden training action, PM7, xTB or Pprime call.

## Scientific recipe and prefix stability

The **version fixes thirty internal candidates** (the original 10N for N=3),
independently of the requested export count. These are generation candidates,
not thirty delivered conformers. Use one normal-coordinate ETKDGv3 call with
the original molecule-specific `science.seed_for(newMID, False)` seed and exact
original parameters: one thread, enforced chirality, no pruning, maxIterations
200. The original zero-return random-coordinate fallback is deliberately omitted
because the latest user instruction says no retry. Empty/failed embedding is
retained, with no second call or new seed.

Each embedded candidate gets at most one original native UFF MinimizeTrajectory
call (snapshot1, maxIts2000, energyTol1e-6, forceTol1e-4). Optimizer failure,
nonconvergence, nonfinite geometry and stereo mismatch remain explicit outcomes;
none is resubmitted. Isotopes/specified stereo and graph/atom order checks are
unchanged. Source-defined unresolved stereo retains actual graph D20, no fake
PM7 stereo truth and an explicit geometry-unavailable state.

The canonical generation order is the **original energy-ordered greedy 0.5A
selection phase**, over the entire fixed candidate pool. It does not use the
original below-threshold/farthest-point fill loop. NativeKernel independently
calls the unmodified original selector with the number of actual >=0.5A
survivors and requires identical rows; that count is reached before any fill.
Current export retains only its first min(3, actual survivor count). A shortage
keeps actual coordinates, marks insufficient_conformers, and creates no copy,
fill, extra seed, extra embedding or optimizer retry.

The closed candidate cache preserves all native outcomes and the full canonical
order. It is internal append provenance, separate from delivered geometry count
and storage. **Future explicitly authorized 4+ export reads this same cache**,
validates its source/recipe/content and saved coordinates, copies previous rows
unchanged, then appends the next canonical survivors. It performs no embedding,
optimization or graph-D20 recomputation. No 4+ export is part of current
production. Cache exhaustion means true shortage, not another candidate batch.
Original fixed-random/energy/diversity functions produce three permutations of
the actual exported IDs; canonical generation order separately binds extension.

## D labels and durable records

D20 calls the original twenty no-Kappa graph function objects once per molecule.
D3 uses the same original corrected_base RDKit APIs/parameters on every actual
selected geometry: PMI1/2/3, PBF, volume(grid0.2/box2), LeeRichards/Protor SASA
(probe1.4), including atom SASA. The direct path avoids corrected_base's repeated
HBA graph correction. NativeKernel.compare_original_wire provides an independent
binary64 comparison against original corrected_base on actual coordinates; Root
must run this in the actual compatibility pilot. Property failures preserve the
geometry and explicit null/reasons. No zero-valued missing descriptor is invented.

`store.run_one` creates a new directory, an fsync hash-chain scientific event
journal, deterministic-gzip closed candidate cache, selected packet and manifest.
Native intentions are durable before calls and outcomes before the next call.
An existing/interrupted directory is never reopened or erased. Without a valid
closed cache, interrupted work remains UNKNOWN and is not automatically retried.
For resource-driven draining after completed native returns, usable real rows
are retained; allocation guard behavior belongs to Root's runner. Old output
bytes are never modified for extension.

Current call (inside an admitted CPU worker):

```python
from workflows.expansion.uff3_candidate_v1.store import run_one
manifest = run_one(source_row, fresh_output_directory, checkpoint=resource_guard)
```

The source row binds pubchem_version, CID, full_key, original/canonical isomeric
SMILES, stream and frozen stream rank. Every packet is v2_candidate and
training_eligible=false. Root's family writer must export D20 once/molecule,
D3 and geometry only for packet.conformers, desired_conformers=3, and put the
closed candidate cache in a separate internal provenance inventory.

Pure meaningful tests (no native optimization):

```text
python -B -m unittest workflows.expansion.uff3_candidate_v1.test_v1 -v
```

They check original no-fill parity including the 0.5A boundary; energy-vs-native
order; fixed30/seed; maximum-three; immutable future extension without native or
D20 repeats; true shortage without fill/retry; zero-return single embedding;
exact native parameters; changed cache/source/prefix rejection; durable readback
and explicit interrupted-journal refusal. These prove software semantics, not
real-molecule success rate, numerical compatibility or 2.5M batch completion.