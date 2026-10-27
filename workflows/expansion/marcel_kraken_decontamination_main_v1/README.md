This is a SOURCE-ONLY Main CPU adapter of already completed Kraken4521873.
It does not repeat archive acquisition, primitive decoding, SMILES/MolBlock
normalization, graph interpretation, UFF or QM. The original artifacts stay
unchanged. No executable request or Root approval is supplied by this package.

Actual upstream authority is Main UID1278 endpoint202.38.247.57:22:

- bootstrap4521681 C0,31s/16CPU19,496coresec; its shared account also contains
  Drugs4521682, which is retained separately and is not Kraken cost.
- opcode4521755 C0,32s/16CPU19,512coresec.
- primitive4521767 C0,33s/16CPU19,528coresec; no normalized keys at that stage.
- profile4521859 C0,96s/16CPU19,1536coresec; all1552roots plus1000conformers.
- full4521873 C0,177s/16CPU19,2832coresec; all1552roots/21287conformers and
 22839relationships, zero unknown roots/conformers. All134multi-key roots
 and1201SMILES-vs-MolBlock differences were retained;20086comparisons equal.

The full receipt is
`artifacts/expansion/marcel_kraken_keys_full_v1/receipt.json`;
standard account is `control/accounting/kraken_keys_full_4521873_v1.json`.
All paths are relative to `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025`.
Original source modules `marcel_kraken_primitive_structure_v1` and
`marcel_kraken_keys_main_v1` already provide a nonexecuting13-opcode primitive
reader. No pickle.load/loads/Unpickler/GLOBAL/REDUCE dispatch is introduced.

Official source: [author dataset README at fixed commit](https://github.com/SXKDZ/MARCEL/blob/dae6b3b824b68d1362ed3b9fa23b34a45fa5366c/datasets/Kraken/README.md)
and [loader](https://github.com/SXKDZ/MARCEL/blob/dae6b3b824b68d1362ed3b9fa23b34a45fa5366c/benchmarks/data/kraken.py).
The official Drive fileID is1QrV651Re7s6UF7Lg4KC9PM5QQUMPU7wd. Fixed Git
commit is a code locator, not a Drive revision. The observed archive is
13339592bytes SHA2565152df55775da397e39d98c9e856f371d098e87fc55fea329147afc16b6b0fcc;
original member is94805786bytes. No current Drive version/MD5 is invented.

The remaining interface gap was that the frozen decontamination manifest still
had Kraken PENDING and `identities:null`, while the full union schema cannot
be fed directly to `decontamination.identity_keys`. This adapter fills that
gap only. It is specific to actual4521873; it is not a generic replacement for
the independently shaped TDC, MoleculeNet or Drugs source adapters.

Root request schema is `ROOT_REQUESTED_KRAKEN_DECONTAMINATION_PROJECTION_V1`,
status `REQUESTED_FOR_REVIEW`, `requested_by:"root"`. Required fields:
`accepted_full_receipt_reference`, `accepted_full_accounting_reference`,
`decontamination_policy_reference` (frozen configs/data_v1/decontamination_sources.json),
`resource_authority_reference`, `cost_decision_reference`, `wall_seconds`
(whole minute600..1800), fresh `output_directory` under artifacts.
All references are actual small triples. The only3 DATA references are
inherited from4521873: selected_source_key_results.jsonl232046820bytes,
all_native_source_relationships.jsonl19880250bytes and
all_native_root_conservative_key_unions.jsonl11649179bytes. Login helpers
do not open/hash these DATA files or infer new source SHA values.

Root metadata CLI (Main login, no science):

```
PY -B -m workflows.expansion.marcel_kraken_decontamination_main_v1.materialize draft --request ACTUAL_REQUEST --output FRESH_CONTROL
PY -B -m workflows.expansion.marcel_kraken_decontamination_main_v1.materialize finalize --draft FRESH_CONTROL/draft_receipt.json --root-review INDEPENDENT_ROOT_REVIEW
```

Root independently copies/reviews the template and sets only status to
`APPROVED_FOR_EXACT_STAGE` and reviewer to `root`. The standard centralv2
helper consumes stage_spec.json with analysis/pilotfalse/16CPU/no_mem;
actual node19 or another explicitly allowed analysis node is chosen there.
There is no hard13 provider. A fresh central proof, exact primary/full argv,
all new/original source pins, explicit real parent chain,512MiB writer cap
and current account reserve of200GB are required. This cap is a ceiling,
not a forecast. Direct frozen Drugs Budget/Writer objects retain original
RSS/MemAvailable/finitewall/stop-new behavior, no signals or auto retry.
The initial quota is central's actual account observation; runtime statvfs
is explicitly reported as filesystem capacity, not a refreshed user quota.

Actual allocation argv is exactly:

```
PY -B -m workflows.expansion.marcel_kraken_decontamination_main_v1.run --plan ACTUAL_PLAN --startup-proof FRESH_STARTUP_PROOF
```

Three new meaningful Main-only methods run before any DATA. They cover all
key variants/native ID zeros and Unicode, unknown preservation/parent and
ordinal conflicts, >2MiB DATA locators vs bounded small metadata/bad triples,
and actual synthetic same-fd SHA/EOF/file reopen/original-consumer readback.
They have not been executed by this source-only author. No mock UID/path
alias makes this group portable to Alpha. The original scientific fixture
and C0 evidence remain separate and are not re-labelled as these3 tests.

All3 old files are current whole-SHA checked in1MiB chunks, parsed with an
8MiB line bound from the same fd, then verified at second SHA/EOF/fstat.
Context, dispatch and result rows are joined by native assignment locators,
not by guessed names/line numbers or ordinal pairing of asynchronous results.
Every source must have exactly one original dispatch and result. Original
relationship and comparison function objects rebuild the full per-root
union, which must exactly equal the original union DATA. No chemistry runs.
Private new SQLite joins are retained inside the new output only.

Outputs:

- identities.jsonl:1552rows with exactly source_id/role/subdataset/inchikeys/
  non_h_composition. All observed full keys per native root are retained.
  `role:"all"` is existing consumer all-source scope, not a fabricated
  native train/test split; native role is unknown and recorded as null.
- all_native_identity_provenance.jsonl:22839native source/result relationships,
  original ID tokens, assignment ordinals, version, unknown/error states,
  key variants and exact old DATA byte offsets/lengths/SHA locators. Each
  source_record_id explicitly includes original archive/native assignment;
  duplicate native text names cannot merge separate assignments.
- all_root_union_projection_evidence.jsonl:1552whole original unions and
  binding to new identity bytes.134multi-key roots and1201differences stay.
- coverage.json: original all-source consumer coverage schema plus explicit
  complete-native relationship/mismatch/unknown/readback evidence.

Every new identity is reopened through the unchanged original identity_keys
object; both other new streams also receive whole-SHA/EOF/row readback.
Any missing/duplicate/conflicting row, unknown, failed resource observation,
partial result or failed parent remains evidence, never READY or an exclusion.
No old output/once/registry is overwritten and no source task is retried.

After actual adapter C0, Root captures standard accounting/raw and runs:

```
PY -B -m workflows.expansion.marcel_kraken_decontamination_main_v1.materialize acceptance-draft --receipt ACTUAL_RECEIPT --accounting ACTUAL_STANDARD_C0 --output FRESH_ACCEPTANCE
PY -B -m workflows.expansion.marcel_kraken_decontamination_main_v1.materialize acceptance-finalize --draft FRESH_ACCEPTANCE/acceptance_draft.json --root-review NEW_INDEPENDENT_ACCEPTANCE
```

Only then may `kraken_READY_source_candidate.json` exist. Root still merges
that standalone source entry into an independently reviewed full manifest;
the adapter does not mutate the existing manifest or release the whole pool.
`full_keys`/WP5 policy, raw archive version/provenance and all other datasets
remain separately controlled. Historical docs claiming bootstrap pending
should gain a new current-state addendum; original historical snapshots and
their hashes must remain intact.
