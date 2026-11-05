# Composed check runtime v2: complete UUID representation

Prepared for Root CPU tests and actual GPU execution, not yet passed. The
original4521015 startup remains FAILED1/6s, before the48 composed cases or
two old CUDA tests started. No scientific pass/fail observation is inferred
from that admission failure. The original Eq tree, its four frozen sources,
CPU4521006 failure evidence and external seven-variant diagnostic remain
unchanged.

This new independent tree changes only the CLI's GPU identity representation
check and adds this document plus CPU runtime tests. Its mathematical module,
original48-case test, geometry, weights, seeds, transforms, terminal rules,
1e-5/rtol0 threshold and output budget remain byte-identical. It does not adopt
a numerical intervention or relax any model acceptance rule.

## Complete identity comparison

The old `str(prop.uuid)==request['gpu_uuid']` compared representations directly.
For example, Python's real `uuid.UUID` renders without `GPU-`. The exact raw
type/representation observed by a successful new GPU job must still be
reported; the old failure alone does not establish which type it returned.
See the primary [Python3.11 UUID specification](https://docs.python.org/3.11/library/uuid.html).

`canonical_gpu_uuid` accepts only:

- A real `uuid.UUID` value, retaining its exact128 bits.
- An ASCII8-4-4-4-12 hexadecimal string, optionally prefixed `GPU-` (hex/prefix
  case does not alter identity).
- Exactly16 `bytes` or `bytearray` bytes in standard big-endian UUID order.

The canonical value is always `GPU-` plus the complete lowercase hyphenated
UUID. There is no version-bit replacement or little-endian guessing. Integers,
device indices, partial UUIDs,32hex shorthand, whitespace, brace/URN syntax,
MIG identifiers, comma lists, invalid hex/byte lengths and arbitrary objects
that merely implement `str()` are rejected.

The original exact scheduler-CVD-string/request-string equality check remains.
The request still requires a full `GPU-` string, actual single CUDA visibility,
the actual expected Slurm node/job and at least16 requested CPUs. The actual
CUDA UUID canonical value must equal the request's complete canonical UUID.
A different128-bit GPU identity is rejected even if its format is valid. The
NVIDIA physical identifier is still the basis of identity; this is not a
fallback to an ordinal or a weaker resource claim. See
[NVIDIA's GPU UUID documentation](https://docs.nvidia.com/deploy/nvidia-smi/index.html#gpu-uuid).

New outer runtime receipts record `gpu_uuid_observation` with `raw_type`,
`raw_repr`, `canonical` and policy, along with the canonical request UUID.
Malformed/mismatched actual UUID errors include those observations in their
error message so Root's supervisor stderr retains the rejected identity.
The untouched math helper's per-case `runtime.gpu_uuid` remains its original
`str(prop.uuid)` observation; the new outer receipt supplies its strict
canonical identity binding. It does not silently rewrite old metadata.

## CPU tests and fresh requests

The independent runtime file is expected to collect **41 CPU cases**: seven
accepted representation forms, eighteen invalid forms, four mocked same-ID
admissions, four other-ID/wrong-byte-order rejections, six preserved admission
guards, one CUDA-free CPU admission and one source-request/policy check.
Tests use real `uuid.UUID` objects and CPU mocks of CUDA APIs. They never run
models, transfer pinned arrays or prove real CUDA availability/execution.
The original real GPU48-case matrix and two old CUDA tests are still required.

Root can run the new runtime-only tests in its admitted CPU allocation:

```text
PYTHONPATH=current python -B -m pytest -q -p no:cacheprovider current/tests/test_model_v3_composed_runtime_v2.py
```

The new request binds this runtime policy, the entire original source inventory
and the added test/document bytes. Old requests cannot be reused against a new
tree or CLI hash. Source requests and result directories remain fresh and
external. Within this new tree, after Root's CPU verification and source freeze:

```text
python -B tools/model_v3/check_composed_equivariance.py prepare-request --device cuda:0 --expected-node <actual-GPU-node> --gpu-uuid <actual-full-GPU-UUID> --threads 1 --output /external/new_eq_runtime_v2_request.json
python -B tools/model_v3/check_composed_equivariance.py run --request /external/new_eq_runtime_v2_request.json --request-sha256 <machine-returned-rawSHA> --output-root /external/new_eq_runtime_v2_result
```

Root retains the actual GPU UUID lock, outer source/cgroup/process supervision,
quota and85% all-user memory protections. The CLI does not set CUDA visibility
or submit jobs. Successful CPU mocks do not authorize a GPU run or constitute
CUDA acceptance. Every real failed or successful new job is preserved with its
own source/request/runtime receipts, and all existing failed jobs remain intact.
