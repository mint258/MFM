# Read-only D wide-descriptor consumer

`WideDescriptorStore` consumes `D_WIDE_DESCRIPTOR_STORE_V1`. The manifest's
`libraries` maps `L1` or `L2` to the following metadata:

```json
{
  "values": "/absolute/raw_float64.npy",
  "status": "/absolute/status_uint8.npy",
  "rows": "/absolute/rows.jsonl",
  "ordered_fields": ["field0", "filtered_field", "field2"],
  "enabled_columns": [0, 2],
  "normalization": [
    {"field_name": "field0", "mean": 1.0, "std_ddof0": 2.0},
    null,
    {"field_name": "field2", "center": 3.0, "scale": 4.0}
  ],
  "fit_role": "TRAIN",
  "producer_alignment_checked": true,
  "reception_acceptance": "pending"
}
```

Both arrays have raw shape `(N, F)`. Status 0 is missing, 1 is observed valid,
and 2 is numeric nonfinite/overflow. Each JSONL row contains `molecule_id`,
`molecule_index`, `split`, `role`, and `smiles`; row order corresponds to array
order. IDs and `(split, molecule_index)` keys must be unique within the library.
`enabled_columns` freezes output order; `normalization` has exactly F entries,
with disabled entries allowed to be null. Parameters have either `mean` and
`std_ddof0`, or `center` and `scale`. An optional `field_name` must agree with
the ordered field at that raw column. Scales of zero are explicit errors, never
replaced with epsilon.

At open, identity and field metadata and array header shape/dtypes are checked
once. The arrays use `np.load(..., mmap_mode="r", allow_pickle=False)`. No hashes,
numeric corpus reread, parameter fitting, or scientific acceptance is performed.

```python
store = WideDescriptorStore(
    manifest_path, "L1", expected_fields=frozen_enabled_field_names,
    normalization_overrides=original_D20_parameters_by_field_name,
)
batch = store.get_batch(
    "TRAIN", molecule_indices, expected_ids=source_ids, expected_role="TRAIN"
)
```

The caller supplies the original 11-07 D20 parameters for overlapping enabled
fields. Neither this mapping nor any normalization is fitted here. `get_batch`
resolves exact source keys and preserves the requested order. `raw_values`,
`status`, and `observed_valid` remain distinct; true zero is valid, missingness
is not imputed, and numeric-event status remains available. `values` contains
standardized values only where observed-valid, and NaN elsewhere. The loader
does not perform ±6 loss clipping or modify source arrays. Batch arrays are
copies and can be safely consumed without modifying the read-only store.

Before statistics are published, explicit `require_normalization=False` permits
raw-only access using `get_batch(..., standardized=False)`. Standardized access
still raises an error. Opening a producer manifest never changes its
`reception_acceptance`: the real 64-sample frozen-encoder per-head overfit test
remains the separate D reception acceptance. SASA stays on the original loader;
this consumer never remaps atom IDs or supplies atomic labels.
