# Immutable preparation-method snapshots, 2026-10-27

These files preserve the actual standalone metadata/runtime sources used by the
model line. They are analysis/execution snapshots, not imported production code.
Original absolute server inputs and raw-byte pins are retained in each manifest.
See docs/model_v3/reports/training_preparation_20261027_v1/PROGRESS.md for actual
job states, test counts, failures, publication identity and limitations.

- wandb_selective_sync50_v3 and closure_v1: fixed50 online replay/readback.
- numeric_full_regression_v1_source: one16CPU/four-pytest complete regression.
- numeric_composed_GPU_v2_source: original48 matrix, actual10PASS38FAIL.
- native_S_long_operational_v4: original-science runtime retry and same-host seal.
- native_S_long_segment_sdk_audit_v2: prepared28-test closed-segment auditor;
  no actual audit of the currently running segment is claimed.
- Root_metadata: actual accounting, strict full-suite/failed-matrix closure and
  online-index publication. The exact script relocation in CPU verification
  is explicit; original submission receipts and plan remain unchanged.

The production model does not enable the failed numerical candidate. Its
independent scientific preregistration is public5cdb2772/local4068623, same Git
treeb2b53cde. Only two metadata JSON files have explicit Git LF/raw CRLF identities;
code/test/config bytes remain strict. No weights, SDK bodies, datasets or keys
are contained here. Prepared source status is not a test/execution certificate.