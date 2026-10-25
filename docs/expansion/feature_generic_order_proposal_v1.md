# Isolated generic-ring order candidate, not an applied repair

Actual diagnostic4520484 completed on compute-0-17 with no memory denial.
Its three original CIDs7/52/53 reproduced the frozen screen.py failure at
line70: sanitation of a cut ring fragment, before genericization. They fail
at fragment2/34/34 respectively. All original chemical X01-X05 are false.
The failed fragments have the same9 atoms/10 bonds, four N atoms, all atoms
aromatic, zero formal charges and zero explicit H counts. Identity, Murcko,
fingerprint and all ten independently observed original-molecule fields pass.
This is observed feature-chain failure, not evidence for a new X exclusion.

The exact official [RDKit2025.09.5 source](https://github.com/rdkit/rdkit/blob/Release_2025_09_5/rdkit/Chem/Scaffolds/MurckoScaffold.py)
(Git blob8b456b1d3ae6fcdce6b1e0e13239ff382af9efe9) copies its input, changes
non-H atoms to carbon, clears aromatic/isotope/charge/stereo state, resets H
settings, makes bonds single/nonaromatic and then removes H. Thus doing that
conversion before sanitizing the generic result has source support. These
generic-copy transformations already belong to the old feature definition;
they do not alter the source molecule, original isotope policy or identity.

Loss of a heteroaromatic N's external substituent during bond cutting is
consistent with the observed state, but “missing H” is not yet proven as the
unique cause: the old trace lacks NoImplicit/implicit-H details. The new
evaluation records original versus cut atom degree, explicit H, NoImplicit
and cached implicit H, plus removed external bonds. Cached H reads are labeled
as cached, not freshly inferred valence. It compares fresh independent copies
because a failed SanitizeMol may have mutated its own input.

## Small candidate implementation

`features_generic_candidate_v1.py` changes only the generic-ring block. It
keeps the exact frozen chemical_flags/rdkit_modules/wp5_key function objects.
The source-only proof requires unchanged screen.py bytes and compares complete
old/candidate feature ASTs after replacing only the known ring-block slice.
All remaining expressions and output fields must be structurally identical.

The candidate deletes the same non-ring bonds in the same descending order,
uses the same unsanitized connected fragments and no-bond skip rule, then
calls MakeScaffoldGeneric before SanitizeMol on that generic result. It does
not catch errors and turn them into chemical exclusions. Fragment comparison
checks exact retained heavy-atom adjacency, all-carbon/nonaromatic atoms and
single bonds. Old successful fragments and candidate fragments retain their
canonical generic SMILES for comparison. Multiplicity is retained.

The helper also records the installed Murcko source file/hash and its Git blob
comparison to the official tag. A different installed byte hash remains an
explicit fact for review; it is not silently labeled an upstream match.

`test_feature_candidate_v1.py` contains four unexecuted checks: source/X-boundary
proof; six old-pass synthetic cases covering no rings, ordinary aromatic,
already-H-bearing aromatic N, bridged rings, linked-ring multiplicity and an
isotope-bearing source; two original X rejections that must never call the new
ring helper; and the three exact observed cases plus minimal N-methylpyrrole.
These are evaluation fixtures, not additions to the candidate pool.

## Field-level evidence and the required next10000 replay

For old-pass molecules every field, including generic_ring_systems, must be
exactly equal. Identity, source/isomeric SMILES, isotope count, composition,
Murcko, all original-molecule descriptors and fingerprint receive no tolerance
or alternate normalization. A changed old-pass field stops acceptance and is
kept for review. The candidate descriptor operates on copies; its original
molecule is not retyped or re-sanitized as a repair.

For these three old failures there is no old complete output. The evaluator
compares every directly observed original trace field to the candidate,
including full key, WP5 key, composition, Murcko, fingerprint and ten original
molecule fields. Isotope count was not directly observed in the old trace;
the report says so and relies on the unchanged source expression plus the
separate old-pass isotope fixture. This is not a fabricated observed value.

`candidate_feature_eval_v1.py` consumes only the pinned small diagnostic trace,
receipt and completed monitor closure. The central preparer's inherited raw
metadata reference may remain declared, but that body is never opened; no other
data reference is accepted. It is
hard-limited to7/52/53 and records repair_applied=false/pool_modified=false.
Candidate failures or observed non-ring field drift fail after retaining all
comparison artifacts. Passing three cases does not resolve all753 failures.
The NOT_READY plan template has no runtime/code pins and grants no full replay.

Only after this evaluation may a separately reviewed new functional variant
replay all original10000 input ordinals side by side with frozen screen.py.
It must first reproduce old427's8198 per-CID feature successes and8197 unique
full keys, retaining the duplicate alias;8197 unique rows cannot stand in for
all8198 successful inputs. Every old753 feature failure must be accounted for
as recovered or still unresolved, and every original chemical rejection must
stay identical. The three diagnosed cases alone do not prove a common cause
for all753. Any new failure or old-pass drift remains explicit. All old427
artifacts/database remain unchanged, and the new output stays unreleased.
Chemical rules remain the exact frozen function; no heavy-atom cap, isotope
change, new decontamination acceptance, UFF or training permission is added.

## Checkpoint performance: use the new transport, not a weaker checkpoint

The194.98-second old diagnostic includes full raw hash/I/O, checkpoints and
case work. It is not a measured pure per-checkpoint benchmark. Root's later
MAD pilot demonstrated heartbeat-stale failure despite all-ALLOW monitoring;
the new central runtime_v2/launch_v2 moves live heartbeat/STOP/samples to
node-local/tmp with boot-monotonic timing. Sampling remains1s, age limit5s,
75-percent own RSS and85-percent memory envelope, with natural child drain.
Complete stable-SHA export to global evidence is required after monitor close;
export failure fails the parent. Local plus global guard output remains32MiB.

Therefore no rate limiter, cache window, reduced checkpoint frequency or
identity limit variant is introduced here. Frozen central/v1 sources remain
unchanged. The proposed evaluator imports runtime_v2 and explicitly binds both
v1 and v2 runtime/launcher sources. Actual76-source pin execution remains held
until Root reviews/tests the local transport and cost. The old NOT_READY
second-stage identity drafts remain frozen and are not a decontamination PASS.

Pending metadata-only entry, for Root on the source-checking node:

```bash
PYTHONPATH=REVIEWED_REPO /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.expansion.features_generic_candidate_v1 --verify-source-only
```

Pending small tests, only in a Root-authorized allocation:

```bash
PYTHONPATH=REVIEWED_REPO:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m unittest workflows.expansion.test_feature_candidate_v1 -v
```

After Root reviews a new READY plan and new monitored CPU request, the entry is
`python -B -m workflows.expansion.candidate_feature_eval_v1 --plan NEW_PLAN --root-submit-intent NEW_INTENT`.
None of these metadata checks, tests, candidate science, Git or submissions
was executed during preparation.
