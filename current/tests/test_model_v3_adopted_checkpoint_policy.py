"""CPU policy/configuration checks only, never fabricated GPU acceptance."""
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
from pathlib import Path
import hashlib
import json
import sys

import pytest

from phychem_mfm.model.v3_adopted_checkpoint_policy import (
    ADOPTED_A, CONSERVATIVE_FLAGS, POLICY, adopted_A_for_gpu, adopted_capacity_records)
from phychem_mfm.model.v3_performance import PerformanceOptions
from phychem_mfm.model import v3_checkpoint_policy as A
from phychem_mfm.model import v3_training_capacity as T


def test_only_actual_qualified_positive_A_choices_are_adopted():
    assert adopted_A_for_gpu('NVIDIA GeForce RTX 3090') is None
    assert adopted_A_for_gpu('unknown') is None
    assert adopted_A_for_gpu('4090 5090') is None
    assert adopted_A_for_gpu('NVIDIA GeForce RTX 5090')['flags']['head_checkpointing'] is False
    assert adopted_A_for_gpu('NVIDIA GeForce RTX 4090')['flags']['backbone_checkpointing'] is False
    assert all(row['R1_candidate_over_reference'] > 1 for row in ADOPTED_A.values())
    first=adopted_A_for_gpu('5090');first['flags']['head_checkpointing']=True
    assert adopted_A_for_gpu('5090')['flags']['head_checkpointing'] is False


@pytest.mark.parametrize('change', ['over85','wrong_flag','bool_peak','unknown_total','all_off','wrong_card'])
def test_capacity_is_not_inferred_from_card_name_or_wrong_checkpoint_profile(change):
    row={'flags':deepcopy(ADOPTED_A['5090']['flags']),'peak_bytes':85,'total_bytes':100}
    assert adopted_capacity_records([row],'5090') == [row]  # Pure boundary predicate, not hardware evidence.
    name='5090'
    if change=='over85':row['peak_bytes']=86
    elif change=='wrong_flag':row['flags']['distance_checkpointing']=False
    elif change=='bool_peak':row['peak_bytes']=True
    elif change=='unknown_total':row['total_bytes']=None
    elif change=='all_off':row['flags']=dict.fromkeys(CONSERVATIVE_FLAGS,False)
    else:name='3090'
    assert adopted_capacity_records([row],name) == []


def test_existing_A_consumer_missing_profile_keeps_original_checkpoint_path_without_CUDA(monkeypatch):
    monkeypatch.setattr(A,'implementation_sources',lambda:{})
    monkeypatch.setattr(A,'current_cuda_capacity',lambda:pytest.fail('No capacity evidence must not query CUDA'))
    resolved,spec,guard,receipt=A.prepare_execution({'backbone':{}},PerformanceOptions(),
        {'checkpoint_policy':POLICY})
    assert guard is None and all(asdict(resolved)[key] is True for key in CONSERVATIVE_FLAGS)
    assert receipt['selection']['reason']=='NO_MATCHED_CAPACITY_KEEP_OLD_CHECKPOINTS'
    assert receipt['selection']['architecture_selected'] is False
    assert A.PerformanceExecution().semantic()['checkpoint_policy']=='manual'
    with pytest.raises(ValueError,match='profile'):
        A.PerformanceExecution(checkpoint_policy='auto_closed_profile_v1')


def actual_R1_metadata_case(tmp_path):
    """Byte-copied closed config/summary, not a fabricated CUDA/C0 fixture."""
    from phychem_mfm.model.v3_adopted_checkpoint_policy import configuration_workload
    fixture=Path(__file__).parent/'fixtures/model_v3/adopted_R1_4090'
    members=[];config=None
    def ref(path):
        raw=path.read_bytes()
        return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    for position in (2,3):
        child=fixture/('member_'+str(position))/'child'
        config=json.loads((child/'configuration.json').read_bytes());summary=json.loads((child/'summary.json').read_bytes())
        assert 'performance_execution' not in config
        assert config['data_version']['original_shard_snapshot']['mtime_ns']==1791880208985935300
        members.append({'position':position,'actual_job_id':config['job_id'],'run_id':summary['tracking_run_id'],
            'GPU_uuid':config['gpu_uuid'],'configuration':ref(child/'configuration.json'),'summary':ref(child/'summary.json')})
    table=tmp_path/'adopted.json';table.write_text(json.dumps({'schema':'model_v3_qualified_A_execution_adoption_v1',
        'adopted_cases':[{'GPU_family':'4090','name':'BackboneOff','A_execution_adopted':True,
            'original_R1_candidate_over_reference':1.2248576848497117,'candidate_members':members}]}))
    environment={'uuid':config['gpu_uuid'],'name':config['gpu_name'],'total_bytes':config['gpu']['total_bytes'],
        'free_bytes':config['gpu']['free_bytes'],'torch_total_bytes':config['gpu_total_bytes'],
        'torch_version':config['torch_version'],'cuda_version':config['cuda_version'],'cudnn_version':config['cudnn_version'],
        'driver_version':config['gpu']['driver_version'],
        'runtime_controls':{k:v for k,v in config['deterministic_controls']['actual'].items() if k!='deterministic_debug_mode'}}
    execution={'checkpoint_policy':POLICY,'capacity_profile':ref(table),'workload_sha256':configuration_workload(config)}
    argv=[str(A.ROOT/'tools/model_v3/single_a_benchmark.py'),'--role','candidate','--abba-position','2',
        '--input','native_s','--seed','0','--workers','8','--max-padded-cost','8000000','--deterministic-controls']
    return config,environment,execution,argv


def test_real_ordinary_R1_metadata_actually_selects_off_without_old_full_source_or_execution_gate(tmp_path,monkeypatch):
    config,environment,execution,argv=actual_R1_metadata_case(tmp_path)
    # Explicitly CPU metadata selection. No CUDA availability or real resource
    # admission is claimed by this synthetic CURRENT environment argument.
    monkeypatch.setattr(sys,'argv',argv)
    monkeypatch.setattr(A,'current_cuda_capacity',lambda:environment)
    monkeypatch.setattr(A,'implementation_sources',lambda:pytest.fail('Old mandatory source gate is not the adoption route'))
    monkeypatch.setattr(A,'load_closed_observation',lambda *a:pytest.fail('Ordinary R1 has no performance_execution field'))
    execution['capacity_profile']['sha256']='0'*64  # SHA transport mismatch must report, not block established facts.
    resolved,_,guard,receipt=A.prepare_execution(config['model'],PerformanceOptions(),execution)
    assert resolved.backbone_checkpointing is False and resolved.distance_checkpointing is True and resolved.head_checkpointing is True
    assert guard is not None and receipt['selection']['metadata_warnings']
    assert receipt['selection']['reason']=='QUALIFIED_A_WITH_MATCHED_MEASURED_CAPACITY'
    assert receipt['selection']['scope'].startswith('ONLY_FRESH_ORIGINAL_S')
    monkeypatch.setattr(sys,'argv',[*argv,'--smoke'])
    resolved,_,guard,_=A.prepare_execution(config['model'],PerformanceOptions(),execution)
    assert guard is None and resolved.backbone_checkpointing is True


def test_R1_operational_metadata_missing_falls_back_but_physical_refusal_is_not_caught(tmp_path,monkeypatch):
    config,environment,execution,argv=actual_R1_metadata_case(tmp_path)
    monkeypatch.setattr(sys,'argv',argv);monkeypatch.setattr(A,'current_cuda_capacity',lambda:environment)
    execution['capacity_profile']['path']=str(tmp_path/'missing.json')
    resolved,_,guard,receipt=A.prepare_execution(config['model'],PerformanceOptions(),execution)
    assert guard is None and resolved.backbone_checkpointing is True
    assert receipt['selection']['reason']=='CAPACITY_EVIDENCE_UNAVAILABLE_KEEP_OLD_CHECKPOINTS'
    def physical():raise MemoryError('CPU fixture of physical guard refusal')
    monkeypatch.setattr(A,'current_cuda_capacity',physical)
    with pytest.raises(MemoryError,match='physical'):
        A.prepare_execution(config['model'],PerformanceOptions(),execution)


def test_receipt_difference_is_a_report_and_does_not_erase_existing_math_PASS():
    from phychem_mfm.model.v3_adopted_checkpoint_policy import FreshR1WindowGuard
    guard=FreshR1WindowGuard({'input_receipts_sha256':'0'*64});guard.calls=22
    observed=guard.confirm_measured_inputs(['actual_metadata_fixture']*20)
    assert observed['same_measured_input_population'] is False
    assert observed['observation_only_existing_A_math_PASS_preserved'] is True
    assert observed['generic_shape_or_long_training_capacity_claimed'] is False


def test_new_training_policy_missing_evidence_builds_real_CPU_encoder_with_original_flags():
    from phychem_mfm.phase1.v3_training_execution import build_training_encoder
    from test_model_v3_training_execution import configuration, workload, policy
    cfg=configuration();spec=policy();spec['checkpoint_policy']=POLICY
    spec['options']['backbone_checkpointing']=None
    built=build_training_encoder(cfg,execution=spec,workload_binding=workload(cfg))
    assert next(built.encoder.parameters()).device.type=='cpu'
    assert all(asdict(built.resolved_options)[key] is True for key in CONSERVATIVE_FLAGS)
    assert built.observer.capacity_selection['capacity_claimed'] is False


def test_training_metadata_failure_keeps_old_path_and_old_strict_policy_stays_strict(monkeypatch):
    options=PerformanceOptions();spec=SimpleNamespace(checkpoint_policy=POLICY)
    admission={'schema':'model_v3_training_execution_admission_v1','capacity_profile':{'fixture':'CPU_only'}}
    def stale(_):raise ValueError('CPU metadata fixture')
    monkeypatch.setattr(T,'read_bound',stale)
    result,guard,frame=T.resolve_training_capacity(spec,{}, {},options,{},admission)
    assert guard is None and result.head_checkpointing is True and frame['capacity_claimed'] is False
    spec.checkpoint_policy='auto_closed_training_profile_v1'
    with pytest.raises(ValueError,match='CPU metadata'):
        T.resolve_training_capacity(spec,{}, {},options,{},admission)
