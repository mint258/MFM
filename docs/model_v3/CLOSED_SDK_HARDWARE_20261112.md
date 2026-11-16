# Closed SDK hardware reports

Report-only existing native W&B statistics. No scientific selection or timing comparison is made.

| Bundle | Job | SDK role | Native stats records | gpu.0.powerWatts mean (W) | gpu.0.gpu mean (%) | gpu.0.memoryAllocatedBytes max (GiB) | gpu.0.temp max (C) |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| C1_v2_v3_closed | 4529715 | training / evaluation host | 60 | 96.914 | 11.467 | 0.696 | 38.000 |
| C1_v2_v3_closed | 4529716 | training / evaluation host | 28 | 116.109 | 14.786 | 1.286 | 53.000 |
| C1_v2_v3_closed | 4529717 | training / evaluation host | 28 | 120.636 | 13.500 | 1.286 | 55.000 |
| C1_v2_v3_closed | 4529718 | training / evaluation host | 28 | 116.269 | 14.571 | 1.286 | 54.000 |
| C1_v2_v3_closed | 4529719 | training / evaluation host | 28 | 121.713 | 13.429 | 1.286 | 56.000 |
| C1_v2_v3_closed | 4529720 | training / evaluation host | 28 | 115.634 | 13.429 | 1.286 | 54.000 |
| C1_v2_v3_closed | 4529721 | training / evaluation host | 28 | 121.676 | 14.571 | 1.286 | 56.000 |
| T0_S_v3_closed | 4529723 | training / evaluation host | 248 | 178.873 | 22.008 | 2.506 | 68.000 |
| T0_S_v3_closed | 4529739 | training / evaluation host | 34 | 116.794 | 9.353 | 1.616 | 61.000 |
| T0_S_v3_closed | 4529724 | training / evaluation host | 248 | 185.217 | 22.694 | 2.649 | 69.000 |
| T0_S_v3_closed | 4529740 | training / evaluation host | 34 | 130.452 | 12.235 | 1.620 | 64.000 |
| T0_P_v3_closed | 4529730 | training / evaluation host | 356 | 217.327 | 32.292 | 3.034 | 72.000 |
| T0_P_v3_closed | 4529746 | training / evaluation host | 16 | 113.795 | 9.250 | 1.260 | 57.000 |
| T0_P_v3_closed | 4529731 | training / evaluation host | 356 | 227.080 | 33.860 | 3.291 | 72.000 |
| T0_P_v3_closed | 4529747 | training / evaluation host | 16 | 119.806 | 7.625 | 1.260 | 58.000 |
| cancelled_seed1_partial_v3_closed | 4529691 | training / evaluation host | 1398 | 243.285 | 74.604 | 1.263 | 62.000 |
| cancelled_seed1_partial_v3_closed | 4529691 | legacy diagnostic host | 702 | unavailable | unavailable | unavailable | unavailable |
| cancelled_seed1_partial_v3_closed | 4529704 | training / evaluation host | 1032 | 247.101 | 75.209 | 1.263 | 62.000 |
| cancelled_seed1_partial_v3_closed | 4529704 | legacy diagnostic host | 521 | unavailable | unavailable | unavailable | unavailable |
| cancelled_seed1_partial_v3_closed | 4529711 | training / evaluation host | 308 | 260.415 | 76.636 | 1.263 | 62.000 |
| cancelled_seed1_partial_v3_closed | 4529711 | legacy diagnostic host | 155 | unavailable | unavailable | unavailable | unavailable |

| T1_A0_A1_S_training_closed | 4529725 | training host | 2008 | 297.308 | 69.792 | 20.932 | 79.000 |
| T1_A0_A1_S_training_closed | 4529726 | training host | 2012 | 295.756 | 67.616 | 23.493 | 78.000 |

| T1_A0_A1_S_evaluation_closed | 4529741 | evaluation host | 38 | 102.434 | 9.158 | 1.286 | 55.000 |
| T1_A0_A1_S_evaluation_closed | 4529742 | evaluation host | 54 | 111.448 | 9.333 | 1.286 | 56.000 |

The complete native-key summaries, including CPU, memory, disk and network fields, are in [the complete JSON summaries](../../results/model_v3_wandb/closed_sdk_hardware_20261112.json). Raw timestamped JSONL and original .wandb files are in each complete SDK archive.

Device-side GPU statistics describe the whole device. They differ from the own-process torch allocator peak in training histories and can include other compute contexts. Earlier node5 sharing observations remain recorded in RESOURCE_STATUS.md.

Legacy diagnostic SDK StatsRecords describe the recorder host; customized remote training-node observations remain in the original HistoryRecords and system_metrics.jsonl. This table does not relabel recorder-host metrics as training-device measurements.

Native metric names and units are preserved in JSON; only the displayed maximum byte count is converted to GiB. Missing metrics remain unavailable. No additional bootstrap, analysis or SDK replay was performed.
