# CPU v2 bindings for the bounded size and EA pilots

This directory records source copies and a source-only proof. It contains no new
scientific algorithm, mask rule, test suite, request builder, or Slurm submission.
The old CPU v1 files, templates, successful fixtures and failed MAD0 evidence are
preserved. Root's central v2 runtime and monitor boundary results are independent
evidence; these copies do not claim either pilot has run.

The ten production files are seven files in `size_cpu_v2`, two dependencies in
`normalization_cpu_v2` (`runtime.py`, `reader.py`), and the EA entry in `ea_cpu_v2`.
The latter is necessary: the frozen EA v1 entry imports `checkpoint` and
`checkpoint_iter` statically from CPU v1 support, in addition to loading the
configured support module dynamically. Changing only its JSON pin would leave
the old shared-filesystem heartbeat checks active.

Seven copied files are unchanged. The only four literal source substitutions are
the two directory bindings in `size_shared.py`, the normalization runtime's
stream directory/depth binding, and the EA checkpoint import. All function source
bytes, including size's hard 64 GiB guard, must remain identical. The normalization
directory exposes exactly the two dependencies used by this bounded size pass;
it is not a full final-normalization pipeline and adds no final D4 claim.

`configs/data_v1/labels/ea_cpu_v2.template.json` differs from its CPU v1 template
only at `support_source`, pointing to Root's `streaming_cpu_v2/support.py`.
`size_cpu_v2.template.json` differs only at `scan_adapter`, pointing to Root's
`streaming_cpu_v2/scan_v2.py`. Every other JSON value, including 32/64 GiB memory,
wall time, labels, aggregation, masks and bounded input pins, must be identical.
Separate output paths belong to Root's new command/request; these templates do
not authorize overwriting an existing output directory.

`source_mapping_v2.json` separates the observed child source pins from expected
Root baseline pins. Root baseline files had not been integrated when these copies
were prepared. An equal expected hash is not an observation at a different path.
After integrating the frozen 19 CPU v1 files and these new files, Root runs:

```bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B \
  /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/labels/cpu_variants_v2/verify_bindings_v2.py \
  --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/sb3_size_ea_cpu_bindings_v2.json
```

This pure-stdlib program requires the actual Root repository, reads only small
source/configuration files (each at most 2 MiB), checks both Root physical paths
and bytes, reverses every declared edit to the full original bytes, compares
whole-module ASTs after only the declared path substitutions, and requires every
function's actual bytes and AST to be identical. It also checks exact top-level
JSON differences and reads the actual Root support/scan pins. Git newline drift
fails the proof rather than being silently normalized. Output uses exclusive
creation. Source construction has only been checked by inverse byte comparison;
AST proof and execution remain pending Root.

Root's `prepare_request_v2` creates the fresh commands/requests for the separately
registered `EA_known_seven` (32 GiB) and `size_rho_canonical_512` (64 GiB) scopes.
Pin actual Root bytes of the entry, all its new source dependencies, both new
templates, this mapping/proof, CPU v2 streaming dependencies, central v2 controls
and their original small metadata/source dependencies. Use `PYTHONPATH=Root:deps`.
The size command runs `size_cpu_v2/run_size.py`; the EA command runs
`ea_cpu_v2/bounded_probe.py`. Central launch/intent environment propagation remains
Root's responsibility. Do not reuse an old CPU v1 entry or old request pin merely
because scientific bytes are unchanged. No new tests, science reads, Git, SSH or
Slurm execution were performed during this handoff.
