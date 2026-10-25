# Isolated input preparation: ordinary 16 CPU / 32 GiB variant

This review applies only to `vector_audit/prepare_v1.py` on compute-0-20.
It does not change the registered code, chemistry configuration, original
64 GiB request/script, or any scientific-run resource requirement. No execution
or measured-RSS claim is made by this review.

## Code and data boundary

- The input is the already-closed P-prime pilot: 2,000 pairs in 19,385,976 bytes;
  SHA256 `05c1a4909760189b6bfe4b47d5c7b59a3fd5ab13c7d7911e05f687c14f1cbc82`.
  The whole JSONL is read and decoded once. This is a finite metadata input,
  not a scan of the 10.8-million-conformer S-prime corpus.
- `choose_pairs` retains at most four source molecules with 6–80 atoms.
  Original LMDB `read_native` is called serially at most four times. It opens
  shards lazily with readonly/create=False/readahead=False; mmap virtual size
  must not be mistaken for resident RAM. Source payloads are unpickled only
  by the unchanged pinned legacy reader, never newly serialized as pickle.
- A single engine initialization imports torch/Arrow/RDKit and small pinned
  registry/environment/recipe metadata. It hashes pinned files in 8 MiB blocks.
  There are no 16 independent engine processes. The audit membership has at
  most 16 IDs, not the old full record-audit population.
- Each molecule contributes PM7 and existing UFF geometry, with nine views per
  geometry: 36–72 rendered calls. One dense float64 coordinate array per view
  is at most 72*80*3*8 = 138,240 bytes. Several Python-list copies, pair lists
  (at most 3,160 unordered pairs per 80-atom molecule), rendered text and
  parsed metadata add overhead; the number is not a total-RSS estimate.
- A 16-thread ThreadPoolExecutor renders and writes inputs. It never calls
  NATIVE.invoke, subprocess, RDKit embedding, UFF optimization or Slurm.
  Geometry rotation/translation is deterministic arithmetic on existing rows.
  Reader closure and thread joins remain the original registered implementation.
- The 2 GiB configured output cap and 200 GB account reserve remain unchanged.
  No automatic retry, evidence deletion, tolerance change, or QM is introduced.

These finite inputs and small arrays support a conservative ordinary 32 GiB
allocation. The code does not impose a 64 GiB minimum. Python object overhead,
library import size and raw source-payload fields have no analytic hard RSS
bound here; Slurm's 32 GiB limit remains effective. Root should retain actual
sacct MaxRSS (missing means unknown), terminal state and parent
AllocCPUS*ElapsedRaw after execution. An OOM remains a real failed attempt;
it must not trigger an automatic repeat or removal of partial evidence.

## New request, preserving old bytes

Root may derive `dv1_vector_prepare_32g_v1` from the unsubmitted
`control/requests/dv1_vector_prepare_v1.json`. Keep that old request and its
script unchanged. Create a new script with only these substitutions:

1. job name `dv1_vector_prepare_32g_v1`;
2. `#SBATCH --mem=32G`;
3. matching new log and preflight intent names;
4. new output `artifacts/vector_frame_audit/prepared_32g_v1`.

The executable, source/config paths, original prepared manifest SHA, node20,
16 CPUs, two-hour wall limit, frozen chemistry/tolerances and all other argv
remain identical. Generate a new script SHA rather than reusing the old pin.
The new request uses memory_gib=32 and the same kind=analysis, cpus=16,
wall_seconds=7200, estimated_peak_output_bytes=8589934592 and
estimated_total_core_hours=32. Retain the original source_references; append
the original request/script references and this review as derivation evidence.
Only Root supplies the actual APPROVED review and registers the new request.
Use the ordinary all-user declared-memory 85% check and fresh quota check;
there is no memory_basis override and no invocation of the 336 UFF exception.

This review does not authorize an audit QM job. The separate audit QM template
and all formal UFF/P-prime scientific runs retain 16 CPU / 64 GiB and their
original node14–19, review and resource-admission requirements.
