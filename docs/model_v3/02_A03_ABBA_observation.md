# A03 5090 single-model A/B/B/A observation

Head-checkpoint-off passed the original20-batch/500-update native numeric gate549. Every timing member starts from seed0 and its own optimizer;2 warmup updates then20 measured updates; no profiler or second resident model.

| Job | Position/role | Window seconds | Base records/s | Native atoms/s | Window Torch allocated bytes |
| --- | --- | ---: | ---: | ---: | ---: |
| 4520576 | 1/reference | 47.337170 | 151.424345 | 9287.585147 | 5364701696 |
| 4520579 | 2/candidate | 64.511433 | 111.112087 | 6815.040022 | 14600138240 |
| 4520580 | 3/candidate | 44.336503 | 161.672650 | 9916.163142 | 14600138240 |
| 4520583 | 4/reference | 46.934826 | 152.722417 | 9367.202159 | 5364701696 |

Pooled reference: 152.070610737 base records/s; candidate: 131.706676698; candidate/reference: 0.866088957x.

Pooling divides summed actual consumed records by summed measured wall time for each role. Inputs, full code/configuration, GPU UUID, seeds and both numeric gates are checked by the existing frozen report tool. All four actual Slurm parents completed0:0.

These are four short observed windows, including input/receipt/monitoring/tracking overhead. The raw variation stays visible; no statistically reliable acceleration or recipe adoption is asserted. Torch counters cover the measured window since reset, not device-global or exact whole-job memory. Cold-start/cleanup remain in the per-member source and actual allocation accounting.

Numeric job549 sampled process-group CPU RSS maximum: 18470543360 bytes over 1043 samples; this is not an exact peak. Independent native SDK verification/archive is recorded separately.
