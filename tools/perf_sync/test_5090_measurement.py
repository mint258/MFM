"""Only new5090 measurement gates and trace I/O; no training/data replay."""
import gzip
import json
from pathlib import Path
import pytest
from statistics_5090 import abba,two_seed_quality
from trace_5090 import events,summarize,export_gzip


def test_abba_uses_mean_rates_and_reports_baseline_drift():
    result=abba([100,112,114,104])
    assert result['speedup']==pytest.approx(113/102)
    assert result['baseline_gap_samples_per_second']==4
    assert result['baseline_noise_fraction']==pytest.approx(4/102)
    assert result['speed_effective']


def test_exact_twice_noise_boundary_is_not_effective():
    assert not abba([98.75,105,105,101.25])['speed_effective']


def test_five_percent_is_required_even_without_drift():
    assert not abba([100,104.99,104.99,100])['speed_effective']
    assert abba([100,105,105,100])['speed_effective']


@pytest.mark.parametrize('rates',([100,110,100],[100,0,110,100],[100,float('inf'),110,100]))
def test_invalid_abba_measurements_are_rejected(rates):
    with pytest.raises(ValueError):abba(rates)


def test_two_seed_noise_bound_includes_both_seeds():
    baseline={0:.4,1:.5}
    assert two_seed_quality(baseline,{0:.51,1:.61},{0:True,1:True})['passed']
    assert not two_seed_quality(baseline,{0:.5101,1:.61},{0:True,1:True})['passed']
    assert not two_seed_quality(baseline,{0:.5,1:.6},{0:True,1:False})['passed']


def test_missing_seed_is_not_silently_accepted():
    with pytest.raises(ValueError):two_seed_quality({0:.4},{0:.4},{0:True})


def test_streaming_trace_parser_preserves_overlap_and_transfer_metrics(tmp_path):
    trace={'traceEvents':[
        dict(ph='X',cat='kernel',name='one',ts=0,dur=6),
        dict(ph='X',cat='kernel',name='two',ts=4,dur=4),
        dict(ph='X',cat='gpu_memcpy',name='Memcpy HtoD',ts=2,dur=1,args={'bytes':128}),
        dict(ph='X',cat='cuda_runtime',name='cudaLaunchKernel',ts=0,dur=2),
        dict(ph='X',cat='cuda_runtime',name='cudaDeviceSynchronize',ts=8,dur=2)]}
    path=tmp_path/'trace.json.gz'
    with gzip.open(path,'wt') as output:json.dump(trace,output)
    assert list(events(path,chunk_size=7))==trace['traceEvents']
    result=summarize(path,10e-6,1)
    assert result['GPU_busy_wall_ratio']==pytest.approx(.8)
    assert result['kernels_per_step']==2
    assert result['H2D_copies_per_step']==1
    assert result['H2D_bytes_per_step']==128
    assert result['synchronizations_per_step']==1


def test_truncated_trace_is_not_accepted(tmp_path):
    path=tmp_path/'incomplete.json.gz'
    with gzip.open(path,'wt') as output:output.write('{"traceEvents":[{"ph":"X"}')
    with pytest.raises(ValueError):list(events(path,chunk_size=5))


def test_real_cpu_profiler_exports_losslessly_without_raw_trace_copy(tmp_path):
    import torch
    with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU],with_stack=True) as profiler:
        x=torch.ones(4,4)
        (x@x).sum()
    destination=export_gzip(profiler,tmp_path/'actual.json.gz',completion_timeout=5)
    with gzip.open(destination,'rt') as source:trace=json.load(source)
    assert any(e.get('name')=='aten::mm' for e in trace['traceEvents'])
    assert not (tmp_path/'actual.json').exists()
    assert not (tmp_path/'actual.json.tmp').exists()


def test_scan_plan_preserves_completed_cell_after_smaller_allocation():
    from statistics_5090 import cpu_scan_plan
    rows=cpu_scan_plan(16,{24})
    assert rows[-1]==dict(cores=24,reuse=True,run=True)
    assert cpu_scan_plan(16)[-1]==dict(cores=24,reuse=False,run=False)


def test_trace_boundary_sync_is_reported_separately(tmp_path):
    path=tmp_path/'boundary.json.gz'
    trace={'traceEvents':[
        dict(ph='X',cat='user_annotation',name='PERF5090_INSTRUMENTATION_SYNC',ts=8,dur=2),
        dict(ph='X',cat='cuda_runtime',name='cudaDeviceSynchronize',ts=8.5,dur=1),
        dict(ph='X',cat='cuda_runtime',name='cudaStreamSynchronize',ts=3,dur=1)]}
    with gzip.open(path,'wt') as f:json.dump(trace,f)
    result=summarize(path,1,1)
    assert result['synchronizations_per_step']==2
    assert result['training_synchronizations_per_step']==1
    assert result['instrumentation_syncs']==1


def test_main_thread_launch_time_includes_runtime_and_driver_apis(tmp_path):
    path=tmp_path/'launch.json.gz'
    trace={'traceEvents':[
        dict(ph='X',cat='cuda_runtime',name='cudaLaunchKernel',ts=1,dur=2,tid=11),
        dict(ph='X',cat='cuda_driver',name='cuLaunchKernel',ts=2,dur=3,tid=22)]}
    with gzip.open(path,'wt') as f:json.dump(trace,f)
    result=summarize(path,1,1,main_tid=11)
    assert result['host_kernel_launch_seconds_per_step']==pytest.approx(2e-6)
    assert result['host_all_threads_kernel_launch_seconds_per_step']==pytest.approx(5e-6)
