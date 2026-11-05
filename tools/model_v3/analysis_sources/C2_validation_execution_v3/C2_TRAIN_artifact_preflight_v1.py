"""Real closed TRAIN artifact-only preflight: no geometry reader or evaluation."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--inputs-sha256',required=True)
p.add_argument('--expected-node',required=True);p.add_argument('--output-root',type=Path,required=True);a=p.parse_args()
source=Path('/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/c2_train_artifact_loader_v3_source')
sys.path.insert(0,str(source))
import accepted_train_artifact_v2 as loader
loader.base.support_runtime.cpu_admission(a.expected_node)
inputs=loader.base.support_runtime.bound_json({'path':a.inputs,'sha256':a.inputs_sha256})
loader.require(inputs.get('preflight_only') is True and inputs.get('public_registration') is None,
               'Explicit metadata/TRAIN-array-only pre-publication input required')
before=loader.executed_sources()
protocol=loader.adopted_artifact_protocol(inputs)
sys.path.insert(0,str(Path(inputs['source_repository'])/'current'))
from phychem_mfm.phase1 import v3_coordinate_lookup as core
model=loader.load_accepted_TRAIN_artifact(core,inputs,protocol)
loader.require(before==loader.executed_sources(),'Frozen loader source drifted')
loader.require('phychem_mfm.phase1.v3_coordinate_lookup_source' not in sys.modules,
               'Native geometry reader must never even be imported by this probe')
import numpy as np
loader.require(np.isfinite(model.coefficients).all() and model.fit_receipt['current_job_TRAIN_geometry_reads']==0,
               'Finite closed TRAIN parameters required')
loader.require(not a.output_root.exists(),'Fresh external preflight output required')
a.output_root.mkdir(parents=True)
value=dict(schema='model_v3_C2_real_TRAIN_artifact_preflight_v1',status='PASS_NO_NATIVE_GEOMETRY_NO_EVALUATION',
    inputs={'path':a.inputs,'sha256':a.inputs_sha256},executed_sources=before,
    TRAIN_parameter_estimation_job_id=model.fit_receipt['parameter_estimation_job_id'],
    TRAIN_records=model.fit_receipt['TRAIN_records'],TRAIN_atoms=model.fit_receipt['TRAIN_atoms'],
    active_columns=int(np.count_nonzero(model.train_edge_counts)),full_columns=int(len(model.coefficients)),
    coefficients_finite=True,native_geometry_reader_imported=False,current_job_parameter_estimation_performed=False,
    current_job_TRAIN_geometry_reads=0,current_job_PRETRAIN_VAL_geometry_reads=0,
    diagnostic_registration_mapping=model.fit_receipt['diagnostic_registration_mapping'],
    preflight_is_publication_or_VAL_authorization=False)
with (a.output_root/'PREFLIGHT.json').open('x') as f:json.dump(value,f,indent=2);f.write('\n')
print(json.dumps({k:value[k] for k in ('status','TRAIN_records','TRAIN_atoms','active_columns','full_columns')}))
