# Explicit numeric validation entry

Do not run this directory as a substitute for Root's resource/UUID/source guard.
The only scientific adapter selects `compensated_fp32_v1` at the existing encoder
builder and V3HeadBank constructor. It imports the raw-SHA-bound original fixture
module into this tree's single phychem_mfm namespace. All seed, nontrivial
parameter assignments, 32-atom geometry, view/mask/noise and transform code stay
in that immutable module. It restores the original symbols in finally.

After Root public registration and source freeze, the actual child command is:

```
PYTHONPATH=/share/home/zixiao/descriptor_analysis/MFM_model_v3_numeric_stability_v1/current MODEL_V3_NUMERIC_TEST_DEVICE=cuda:0 MODEL_V3_NUMERIC_TEST_MODE=compensated_fp32_v1 MODEL_V3_NUMERIC_TEST_THREADS=1 python -B -m pytest -q /share/home/zixiao/descriptor_analysis/MFM_model_v3_numeric_stability_v1/validation/model_v3_numeric_stability_v1/test_candidate_matrix.py --basetemp=<fresh-owned-child>/cases --junitxml=<fresh-owned-child>/matrix.xml
```

Use device=cpu only on a CPU node. There are exactly 48 parameterized cases,
192 full actual encoder forwards and 1872 declared transformed-terminal field
observations. No early-stop option is supplied. Keep pytest's whole failure log
and every case JSON/NPZ. A nonzero exit is not a successful scientific result.
`MODEL_V3_NUMERIC_TEST_MODE=legacy` is a separate explicitly labelled control;
it does not silently switch on candidate arithmetic. Its expected current
physics failures are preserved.

The CPU unit entry is current/tests/test_model_v3_numeric_stability.py. Root
records actual collection count, machine source snapshots and parent Slurm
closure. This file contains no submission, runtime admission or claims of tests
already passed. Existing whole 2GiB output/private and 28GiB RSS bounds apply.
