"""Adopt qualified A execution changes; capacity remains an independent fact.

No hardware-name capacity estimate, SDK qualification or architecture winner is
created here. Pure metadata predicates are also usable before CUDA import.
"""
from __future__ import annotations

import re
import hashlib
import json
import os
import stat
from pathlib import Path

POLICY = "auto_adopted_A_v1"
FLAGS = ("backbone_checkpointing", "distance_checkpointing", "head_checkpointing")
CONSERVATIVE_FLAGS = dict.fromkeys(FLAGS, True)

# Scientific qualification and the unchanged original speed report, not SDK
# transport status, authorize these choices. Independent JSON evidence refs are
# recorded in configs/model_v3/performance/adopted_A_v3.json.
ADOPTED_A = {
    "5090": {"name": "HeadOff", "flags": dict(zip(FLAGS, (True, True, False))),
        "numeric_GPU_jobs": ("4524722", "4525063"),
        "R1_candidate_over_reference": 1.0693858781321288},
    "4090": {"name": "BackboneOff", "flags": dict(zip(FLAGS, (False, True, True))),
        "numeric_GPU_jobs": ("4525046",),
        "R1_candidate_over_reference": 1.2248576848497117},
}


def adopted_A_for_gpu(gpu_name):
    """Return a fresh qualified choice; a name alone never grants capacity."""
    if type(gpu_name) is not str:
        return None
    keys = [key for key in ADOPTED_A if re.search(r"(?<!\d)" + key + r"(?!\d)", gpu_name)]
    if len(keys) != 1:
        return None
    row = ADOPTED_A[keys[0]]
    return {**row, "flags": dict(row["flags"]), "GPU_family": keys[0]}


def adopted_capacity_records(records, gpu_name):
    """Filter already validated SAME-workload records to a qualified A choice.

    The caller still applies actual UUID/runtime/free-memory compatibility and
    the per-forward shape guard. This does not parse or qualify an A journal.
    """
    choice = adopted_A_for_gpu(gpu_name)
    if choice is None:
        return []
    return [row for row in records if type(row) is dict
        and type(row.get("flags")) is dict and set(row["flags"]) == set(FLAGS)
        and all(type(row["flags"][key]) is bool and row["flags"][key] == choice["flags"][key] for key in FLAGS)
        and type(row.get("peak_bytes")) is int and type(row.get("total_bytes")) is int
        and 0 < row["peak_bytes"] * 100 <= 85 * row["total_bytes"]]


def conservative_selection(reason, *, admission=None):
    """Operational evidence failure is recorded; old recomputation continues."""
    return {"schema": "model_v3_adopted_A_capacity_selection_v1", "policy": POLICY,
        "reason": reason, "resolved_checkpoint_flags": dict(CONSERVATIVE_FLAGS),
        "admission": admission, "capacity_claimed": False,
        "unverified_optimization_adopted": False, "architecture_selected": False}


def _require(ok, reason):
    if not ok:
        raise ValueError(reason)


def _canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _metadata(ref, warnings):
    """Read only bounded owned JSON. Raw SHA/size differences are reports."""
    _require(type(ref) is dict and set(ref)=={'path','bytes','sha256'}, 'Explicit R1 metadata reference required')
    path=Path(ref['path']);before=path.lstat()
    _require(path.is_absolute() and path.resolve()==path and stat.S_ISREG(before.st_mode)
        and before.st_uid==os.getuid() and before.st_nlink==1 and 0<before.st_size<=2<<20
        and path.suffix=='.json' and not {'wandb','stage'} & set(path.parts)
        and not any(word in path.name for word in ('journal','steps','checkpoint','gate')),
        'Owned small config/summary/adoption JSON only; no payloads')
    raw=path.read_bytes();after=path.lstat()
    _require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Metadata changed during read')
    actual={'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    if actual != ref:
        warnings.append({'kind':'METADATA_RAW_BINDING_DIFFERENCE_REPORT_ONLY','expected':ref,'actual':actual})
    return json.loads(raw,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite metadata')))


def configuration_workload(config):
    """Exact mature workload_identity projection, excluding source manifests."""
    return _canonical({'model':config['model'],'seed':config['seed'],'input':config['input'],
        'snapshot':config['original_shard_snapshot_prejob_sha256'],
        'reference_configuration_sha256':config['reference_configuration']['sha256'],
        'a4_configuration_sha256':config['a4_configuration']['sha256'],
        'loss_policy':config['loss_policy'],'loss_weights':config['loss_weights'],'supervision':config['supervision']})


def fresh_A22_scope(argv, root):
    """Only the existing fresh original-S single member, never generic training."""
    if not argv:
        return False
    entry=Path(argv[0]);entry=entry if entry.is_absolute() else Path.cwd()/entry
    if entry.resolve()!=Path(root)/'tools/model_v3/single_a_benchmark.py':
        return False
    def value(name, default=None):
        hits=[i for i,x in enumerate(argv) if x==name]
        if len(hits)>1 or any(x.startswith(name+'=') for x in argv):
            return None
        return default if not hits else argv[hits[0]+1] if hits[0]+1<len(argv) else None
    forbidden={'--smoke','--resume','--atom-bucket-width','--exact-atom-sort'}
    return (not any(x==key or x.startswith(key+'=') for x in argv for key in forbidden) and '--deterministic-controls' in argv
        and value('--input','native_s')=='native_s' and value('--seed','0')=='0'
        and value('--workers','8')=='8' and value('--max-padded-cost','8000000')=='8000000'
        and value('--role')=='candidate' and value('--abba-position') in ('2','3'))


def load_R1_capacity(table_ref, *, model, workload_sha256, options, configured_cost, resident_models, gpu_uuid=None):
    """Consume already closed ordinary R1 metadata; no old profile/API/source gate.

    Its capacity covers ONLY the same fresh original-S22 population. The caller
    must check fresh_A22_scope and actual CUDA/card/free-space independently.
    """
    _require(resident_models==1 and configured_cost==8000000,'Original R1 single residency/cost only')
    warnings=[];table=_metadata(table_ref,warnings)
    _require(table['schema']=='model_v3_qualified_A_execution_adoption_v1','Known closed A adoption table required')
    records=[]
    for case in table['adopted_cases']:
        choice=ADOPTED_A.get(case['GPU_family'])
        if choice is None or case['name']!=choice['name'] or case['A_execution_adopted'] is not True:
            continue
        if gpu_uuid is not None and not any(member.get('GPU_uuid')==gpu_uuid for member in case['candidate_members']):
            continue
        _require(case['original_R1_candidate_over_reference']>1 and len(case['candidate_members'])==2,
            'Original positive two-candidate R1 facts required')
        row=None;peak=0;matched=True;jobs=set();positions=[]
        for member in case['candidate_members']:
            config=_metadata(member['configuration'],warnings);summary=_metadata(member['summary'],warnings)
            sampler=config['data_version']['sampler'];actual=config['deterministic_controls']['actual']
            _require(config['role']==summary['role']=='candidate' and summary['status']=='STANDALONE_TIMING_COMPLETED'
                and config['abba_position']==summary['abba_position']==member['position']
                and config['job_id']==member['actual_job_id'] and summary['tracking_run_id']==member['run_id']
                and config['code_sha']==summary['code_sha']=='7ffe8a5557590b1481f4ca74073007f070dc6a50'
                and config['warmup_updates']==summary['warmup_updates']==2
                and config['measured_updates']==summary['measured_updates']==20
                and summary['foreign_gpu_risk_observed'] is False and config['smoke'] is summary['smoke'] is False,
                'Actual ordinary completed original R1 2+20 facts required')
            jobs.add(config['job_id']);positions.append(config['abba_position'])
            _require(config['effective_options']=={**options,**choice['flags']}
                and config['input']=='native_s' and type(config['seed']) is int and config['seed']==0
                and sampler['max_padded_cost']==8000000 and sampler['max_molecules']==512
                and sampler['max_native_atoms']==65536 and sampler['padded_cost_multiplier']==3
                and config['data_version']['loader']['num_workers']==8
                and 'performance_execution' not in config,'Exact qualified ordinary S execution facts required')
            if config['model']!=model or configuration_workload(config)!=workload_sha256:
                matched=False
            for key in ('peak_allocated_bytes','peak_reserved_bytes'):
                _require(type(summary[key]) is int and summary[key]>0,'Actual finite positive original R1 peak required')
                peak=max(peak,summary[key])
            environment={'gpu_uuid':config['gpu_uuid'],'gpu_name':config['gpu_name'],
                'total_bytes':config['gpu']['total_bytes'],'torch_total_bytes':config['gpu_total_bytes'],
                'torch_version':config['torch_version'],'cuda_version':config['cuda_version'],
                'cudnn_version':config['cudnn_version'],'driver_version':config['gpu']['driver_version'],
                'runtime_controls':{k:v for k,v in actual.items() if k!='deterministic_debug_mode'},
                'flags':dict(choice['flags']),'input_receipts_sha256':summary['input_receipts_sha256']}
            _require(row is None or environment==row,'Both original candidate members must share card/runtime/population')
            row=environment
        _require(len(jobs)==2 and positions==[2,3],'Two distinct actual original candidate positions2/3 required')
        if matched:
            _require(0<peak*100<=85*min(row['total_bytes'],row['torch_total_bytes']),
                'Original measured R1 capacity must stay within85% of actual physical capacity')
            row.update(peak_bytes=peak,source={'adoption_table':table_ref,'R1_case':case},
                scope='ONLY_FRESH_ORIGINAL_S_2WARM_20MEASURED_NOT_GENERIC_SHAPE_CAPACITY')
            records.append(row)
    return records,warnings


class FreshR1WindowGuard:
    """Keep the original source window finite, then confirm its actual input IDs."""
    def __init__(self, record):
        self.record=self.observation=record;self.calls=0

    def check(self, data, counts):
        _require(data.x.device.type=='cuda' and self.calls<22 and len(counts)%3==0
            and 0<len(counts)<=3*512 and sum(counts)<=3*65536
            and len(counts)*max(counts)**2<=8000000
            and all(counts[i]==counts[i+1]==counts[i+2] for i in range(0,len(counts),3)),
            'Only this fresh original three-view S22 window; no larger or generic batch capacity')
        self.calls+=1

    def confirm_measured_inputs(self, receipts):
        actual=_canonical(receipts)
        return {'scope':'ONLY_FRESH_ORIGINAL_S_2WARM_20MEASURED_NOT_GENERIC_SHAPE_CAPACITY',
            'forward_calls':self.calls,'measured_input_receipts':len(receipts),
            'expected_input_receipts_sha256':self.record['input_receipts_sha256'],
            'actual_input_receipts_sha256':actual,
            'same_measured_input_population':self.calls==22 and len(receipts)==20 and actual==self.record['input_receipts_sha256'],
            'observation_only_existing_A_math_PASS_preserved':True,
            'generic_shape_or_long_training_capacity_claimed':False}
