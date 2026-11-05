# Build the model-side selected TRAIN store

The panel uses existing frozen downstream sources, independently of the new
pretraining D1–D6 label line. No complete historical packed store was found in
the three known launch roots. Their failed partial payloads are not inputs.
This new route creates a separate native store, complete only for the sealed
selected TRAIN population. All artifacts stay outside Git and the data-line
directories; original labels, units, splits, atom identities and saved geometry
are retained.

The source catalog is `configs/model_v3/existing_downstream_sources_v1.json`,
SHA256 `838553159d34ab00a157c66e01cdd60d3265713041ac12567503033c27a81b4e`.
The frozen panel is `configs/dev_panel_v1.json`, SHA256
`110658491fbb77b0e647c5636d9cd894a389dd7e8c0f401847273c4f7c127132`.
Both are checked against their supplied hashes. Source receipts and decoder
hashes are explicit in the catalog and the source audit; no path is inferred
from the old failed binary. A checksum over opaque source bytes is a version
check, not numeric/annotation target decoding or evaluation.

## Root CPU execution

Use the established root-owned development-server Slurm wrapper and logical
Python entry. Each phase requests at least 16 CPUs and 64 GiB, with a one-hour
hard wall, no GPU, `CUDA_VISIBLE_DEVICES` empty and OMP/MKL/OpenBLAS threads 1.
The internal bounds are 16 workers, 48 GiB peak RSS and 2 GiB output. The writer
keeps at most 32 futures pending, consumes results in fixed native source order,
and preserves incomplete outputs. The supervisor still enforces the aggregate
process wall/RAM limits. No school-server job or training is started here.

First commit/review the exact source and publish the panel/rules. The
`--code-sha` must be the actual committed executing revision;
`--preregistration-sha` must identify the published panel/rules that exist at
that revision, not merely the earlier stage-0 tree. The commands below are to
be launched by Root in its owned CPU allocation, not on a login node.

```bash
python -B tools/model_v3/prepare_selected_training_store.py \
  --sources-sha256 838553159d34ab00a157c66e01cdd60d3265713041ac12567503033c27a81b4e \
  --panel-sha256 110658491fbb77b0e647c5636d9cd894a389dd7e8c0f401847273c4f7c127132 \
  --code-sha ACTUAL_EXECUTING_40_CHARACTER_COMMIT \
  --preregistration-sha PUBLISHED_PANEL_40_CHARACTER_COMMIT \
  --output-root /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/selection_NEW
```

Preparation verifies original target-free membership/role receipts and closed
geometry metadata, including the Expansion TRAIN full-InChIKey/member-row join.
It applies the existing overlap purge, chemical groups, caps and fixed split
before any target decoder. It saves the original source contracts and a new
`selection_request.json`; its raw SHA is printed in `preparation_result.json`.
No labels or old downstream scores are inspected. Any metadata/source drift
is an error.

After reviewing that immutable native selection, use its exact printed SHA:

```bash
python -B tools/model_v3/materialize_selected_training_store.py \
  --selection-request /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/selection_NEW/selection_request.json \
  --request-sha256 EXACT_PRINTED_SELECTION_REQUEST_SHA256 \
  --output-root /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/selected_store_NEW
```

The second phase reloads and reconstructs the metadata-only selection and
verifies exact equality before source target access. Every numeric/annotation
decoder checks `(dataset, native index, selected role)` against the sealed
allowlist first. Each selected member is decoded once; unrelated or outer
roles are unavailable. The official Expansion held-out source file is never
used by the graph decoder. QM CSV framing may traverse opaque byte fields for
all source rows, but excluded target tokens never reach numeric conversion.
CYP raw-frame/structure indexing does not invoke annotation parsing; only an
allowlisted native member reaches the unchanged PRIMARY_SOM decoder.

The exact reused transport is `observed_scalar`, `som_payload` and
`record_bytes` from the pinned original helpers. The new code does not call
their all-role `run`, historical probe CLI or full-evaluation entry point.
Original known/unknown NaN masks, native task order, source atom IDs and literal
F64-to-F32 geometry cast are retained. Saved geometry and full chemical keys
are consumed, not regenerated. Malformed labels fail without becoming unknown
supervision.

The new selected-population contract is checked twice against the existing
`GroupedTrainingView`: before labels exist and after writing the selective
reader sidecar. The exact selected native IDs/roles must replay unchanged.
For Expansion, the current 5,326 official TRAIN records fit the fixed caps;
all original official TRAIN metadata remains, so its balanced five-way split
cannot be recomputed on a silently reduced population. A source for which
this condition fails is refused rather than reassigning its members.

## Closing artifacts and evaluation

`native_store/records.bin` is a new P1DS1 file. Its new record index and source
proofs bind each packed frame back to its original member-row/geometry/source
receipts; no historical packed-frame hash is invented. A pending sidecar is
validated with the already tested `TrainOnlyPackedStore`. Original source
files, selected XYZs, all implementation files and the selection request are
then rechecked. Only afterward are the complete selected-store manifest and
final `training_store.json` published. A failed close leaves the partial/
PENDING files and no final consumable sidecar.

The manifest says `closure_scope=complete_for_selected_TRAIN` and
`historical_full_store_claimed=false`. The sidecar's `source_complete=true`
refers to this new closed selected-TRAIN source. Its native record hashes come
from the newly closed index; the original failed whole-source export is not
promoted. `materialization_result.json` prints the final sidecar path/SHA,
data-version source binding, actual worker count and elapsed time. This is a
data preparation result, not a model score, training run or GPU benchmark.

Pass that final sidecar as `training_store` to the existing
`prepare_dev_evaluation.py` workflow. Build its target-free packing request,
bind its actual plan hashes, then execute the real B3/matching-random panel in
one owned GPU allocation. B3 remains a 384-dimensional descriptive reference.
The nine tasks, 18 cells, separate readout means and uncertainty are unchanged;
the measured one-GPU-hour target still needs that real evaluation.

## Verification status

The prior source at 464b96eff38a7b73b2dab5b7fd68bfd7b1146e58 passed all
2,076 tests in actual Slurm 4520363, no skips. Real B3 checkpoint-byte SHA,
safe load and paired synthetic H0 `[5,384]` passed actual 4520360. These are
separate from the new selected-TRAIN preparation implementation above.
The selected-store regression bundle actually passed 15/15 in 4520372,
source hashes unchanged. Metadata preparation 4520379 completed C0/25s,
target records decoded 0; native selections are CYP 1,803 / ExpansionRx 5,326 /
QM9 10,473. Its 27,382,324-byte request raw SHA is
`ed8b4682ece4f11bf6645ab266000a1f7d26f0a071730c61f3bd1a487b243da1`.
The semantic decoding boundary is independently reviewed in
`TRAIN_TARGET_ACCESS_AUDIT.md`; source remains frozen. Actual materialization
and real panel scores/GPU performance are still pending, not implied by the
metadata run. The published panel/rules preregistration commit is
`39cf4929299cd227a3c361183a4b26c8b1405900`; record the actual executing code
commit separately.
