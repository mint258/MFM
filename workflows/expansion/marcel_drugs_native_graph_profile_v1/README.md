# Drugs native graph bounded profile

Source only; not run, submitted or approved by this package. This is an independent
profile, leaving the frozen Drugs9 source and its active/full job untouched.

The fixed author loader at commit dae6b3b824b68d1362ed3b9fa23b34a45fa5366c
uses `with Chem.SDMolSupplier(raw_file, removeHs=False)` then literal ID, `_Name`
and smiles properties before graph conversion. Primary source:
https://raw.githubusercontent.com/SXKDZ/MARCEL/dae6b3b824b68d1362ed3b9fa23b34a45fa5366c/benchmarks/data/drugs.py

This new graph seam uses the same SDMolSupplier constructor on each independent
byte-identical single-record temporary SDF. It does not call MolFromMolBlock,
pass alternate sanitize/strictParsing flags, repair a graph, remove hydrogens,
neutralize, canonicalize a tautomer, edit coordinates, or strip isotope/stereo.
The constructor keeps its author/default sanitization and strict parsing behavior.
Native MolToInchiKey is followed by the original frozen `full_keys` and `wp5_key`
function objects. MolFromSmiles is used only by synthetic fixtures; production
source-SMILES keys are reused from actual1818 and never recomputed here.

## Fixed population and sample

All558002 SDF records and75099 CSV names remain the source context. Physical
ordinals, original IDs (including leading zeros), title/name, every selected
literal property variant, record bytes/SHA, all conformers and the290 distinct
SMILES byte name groups are preserved. No source split or X filter is applied.

The exact Python3.11.14 sampler is
`random.Random(20261027).sample(range(558002),10000)`. The first1000 entries in
that draw-order list are the native graph profile, not the first1000 completed
rows or smallest ordinals. This is uniform sampling without replacement. The
entire10000 set must exactly match actual1818's durable source/result journal.

The four data bodies are derived from actual1818/1750/bootstrap receipts:
the original259283872-byte ZIP, original666-byte bootstrap inventory,1750's
401229188-byte source journal, and1818's21838201-byte key journal. They stay
DATA even when small, with producer triples only on login. No current1858 output,
active old SQLite or invented future full/profile pin is read.

## Actual CPU read and write order

Fresh existing Main central v2 admission is mandatory: analysis, true pilot,
16CPU, no requested memory/exclusive/GPU,7200 seconds, whole2GiB output. The node
must be in the current resource authority's analysis allowlist; Root can choose19.
All new and reused imports are source-pinned. Python3.11.14 and RDKit2025.09.5
are exact. Three synthetic tests must all pass before any of the four DATA bodies.
They exercise raw grammar/binding, author reader/explicit H and mismatch union,
and sampler/cached-source boundaries with no original data or QM/UFF/network.

After those tests each DATA body is whole-SHA/fstat checked. The original archive
preflight/directory and member readers verify complete ZIP CRC, decoded SHA and
EOF. The original P.NameCSV and exact P.sdf_rows/P.sdf_record function objects
reconstruct every row and compare it for complete equality to1750's source row.
The only new parser seam retains bytes already returned by readline until the
original SDF callback; it does not redefine record boundaries or parse fields.
The10k cached keys bind all source fields and every original SMILES variant,
including ordinal/ID/name/raw record SHA. No source-SMILES key is recalculated.

Each selected original record is first appended with O_APPEND and fsync to one
new raw blob. Its offset/bytes/SHA segment and cached source identity are written
durably to the result journal before worker dispatch. The final blob whole triple
is produced only after actual bytes have closed; no future size/SHA is assumed.
Workers verify the segment against the original record, use their own single
record file in /tmp, and remove only that temporary directory on return. At most
16*16MiB node-local SDF bytes are covered by the original258MiB dispatch/drain
reserve, with an additional actual1GiB node-local free requirement. One shared
blob avoids1000 persistent small files and pathological repeated tree-stat cost.

The original Drugs Budget/Writer objects are directly reused, including actual
parent/children RSS, MemAvailable, physical free, cap and natural-drain checks;
the fresh central proof supplies the independent account-quota admission.
16 workers/32 pending rows are bounded, with16GiB algorithm RSS soft cap and
4GiB/15% MemAvailable minimum. No Slurm memory request is implied. There are no
new signals or automatic retries. Results become durable before native-key SQL
or name unions. A new job-owned relationship index reuses the original relation
logic; every original row was already durable in the verified1750 producer log.

## Unknowns and conservative unions

Parser None/errors, missing or differing literal fields and invalid graph keys
remain explicit unknowns. A readable SDF is not called unavailable merely because
native graph keys were previously unexamined. This job does not claim a native
composition fallback from source-SMILES or edit a failed raw graph.

Every selected graph key is retained separately from every1818 source-SMILES
variant key. Per-record source/graph mismatches and unknown comparisons are
reported independently. The name export unions all observed source-profile keys
(10000 conformers) and all observed native keys (1000 conformers), across every
conformer of that name; it never chooses a representative. All75099 CSV names
remain, and each unselected native graph is explicitly NOT_YET_EXAMINED. This is
partial key coverage with complete physical relationship context, not558002
accepted native graphs. No assay field is explicitly selected/exported; RDKit
internally consumes the full SDF record as required by the author's reader.

## Root metadata CLI

The Root request has schema `ROOT_REQUESTED_MARCEL_DRUGS_NATIVE_GRAPH_PROFILE_V1`,
status `REQUESTED_FOR_REVIEW`, requested_by `root`, and real triples:

- accepted_source_key_profile_receipt_reference: actual1818 profile receipt.
- accepted_source_key_profile_accounting_reference: actual1818 C0/raw accounting.
- Current resource_authority_reference and cost_decision_reference.
- Fresh output_directory under Main artifacts.

```
python -B -m workflows.expansion.marcel_drugs_native_graph_profile_v1.materialize draft --request ACTUAL_REQUEST --output FRESH_CONTROL
```

The helper reads small metadata/source only, derives actual four DATA locators,
and emits plan and pending independent Root review. Root must separately review
the exact template, copy it, change only status to APPROVED_FOR_EXACT_STAGE and
reviewer to root, then:

```
python -B -m workflows.expansion.marcel_drugs_native_graph_profile_v1.materialize finalize --draft ACTUAL_DRAFT --root-review INDEPENDENT_ROOT_REVIEW
```

The ordinary central stage_spec uses the existing queue; no new queue is added.
Runtime is `PY -B -m workflows.expansion.marcel_drugs_native_graph_profile_v1.run
--plan PLAN --startup-proof PROOF`. No helper submits or runs computation.

C0 denotes complete bounded observations with unknowns retained, not scientific
acceptance. Actual terminal costs including failures/startup are appended by Root
afterward. Full native graph implementation is deliberately absent: it requires
this actual profile/accounting/cost-and-unknown review plus actual1858 C0 and its
full source-key journal in a separate later Root review. No pool, global
decontamination, training, full generation, QM or UFF is released.
