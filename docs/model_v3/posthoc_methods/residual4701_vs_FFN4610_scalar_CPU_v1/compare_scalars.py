"""Paired closed JSON scalars only. No tensor/NPZ/model/SDK/data payload access."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import threading

P=Path('/share/home/zixiao/descriptor_analysis')
O=P/'runs/model_v3_20261025';N=P/'runs/model_v3_20261026';HERE=Path(__file__).absolute().parent
FIELDS=('PD/p_extensive','PD/p_intensive','PD/d_intensive','PD/d_binary','PD/d_atom','PD/p_pair',
    'PD/p_gradient','PD/p_dipole','PD/p_dipole_magnitude','S/noise','S/coordinate','S/element_logits','S/clean_bond_logits')
TRANSFORMS=('general_rotation','translation_only','other_rotation_and_translation')
SPECS=list(itertools.product(('C1-0','C1-a','C1-b'),('two','three'),
    ('H1_fixed','H1_learned','H2_fixed','H3_fixed'),(20261026,20261027)))
IDS=[f'{c}__{v}__{h}__seed{s}' for c,v,h,s in SPECS]
IDENTITY=('case','case_id','domain','encoder_forward_shapes','fixture_geometry_sha256','fixture_native_atoms',
    'original_physical_geometry_sha256','original_view_identity_sha256','registry_sha256')
POLICY=('TF32_cudnn','TF32_matmul','autocast_enabled','default_dtype','deterministic_algorithms',
    'device','float32_matmul_precision','gpu_uuid','torch')


def require(ok,message):
    if not ok:raise ValueError(message)


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def unique(items):
    result={}
    for key,value in items:
        require(key not in result,'Duplicate JSON key');result[key]=value
    return result


class Metadata:
    def __init__(self):self.refs={};self.lock=threading.Lock()
    def raw(self,path,expected=None):
        path=Path(path).absolute()
        require(path.is_relative_to(P) and path==path.resolve(strict=True)
            and path.suffix in ('.json','.py','.md'),'Only owned physical project JSON/source metadata permitted')
        before=path.stat()
        require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid()
            and before.st_nlink==1 and before.st_size<=1<<20,'Bounded owned metadata file required')
        raw=path.read_bytes();after=path.stat()
        require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Metadata changed while reading')
        ref=dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if expected is not None:
            require(type(expected) is dict and set(expected)=={'path','bytes','sha256'}
                and ref==expected,'Exact selected metadata rawref differs')
        with self.lock:
            require(str(path) not in self.refs or self.refs[str(path)]==ref,'Selected input changed')
            self.refs[str(path)]=ref
            require(sum(row['bytes'] for row in self.refs.values())<=32<<20,'Selected metadata input cap32MiB exceeded')
        return raw,ref
    def load(self,ref):
        raw,_=self.raw(ref['path'],ref)
        require(Path(ref['path']).suffix=='.json','JSON metadata only')
        return json.loads(raw,object_pairs_hook=unique,
            parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON literal')))


def cohort(reader,pins,label):
    refs=pins['inputs'][label];closure=reader.load(refs['closure']);result=reader.load(refs['result'])
    job='4524610' if label=='FFN4610' else '4524701'
    key='result' if label=='FFN4610' else 'RESULT'
    require(closure['job_id']==job and closure[key]==refs['result'] and closure['scientific_adoption'] is False,
        'Original Root negative closure/job/RESULT binding differs')
    require(result['status']=='PHYSICAL_CRITERION_FAIL' and result['failure'] is None
        and result['source_before_after_equal'] is True and result['scientific_adoption'] is False
        and result['ordinary_all_arithmetic_FP32_encoder_forwards']==192
        and result['full_FP64_encoder_forwards']==0,'Original complete negative FP32 cohort required')
    require(result['counts']==closure['counts'] and result['counts']['tests']==48
        and result['counts']['errors']==result['counts']['skipped']==0 and result['counts']['failures']>0,
        'Complete48 original negative counts required')
    rows=result['cases'];require(type(rows) is list and [row['case_id'] for row in rows]==IDS,
        'Exact ordered unique complete48 case/seed population required')
    return rows,result,closure


def gate_rows(measured):
    require(measured['schema']=='model_v3_composed_equivariance_v1_case'
        and measured['complete_terminal_count']==13 and type(measured['actual_native_data_reads']) is int
        and measured['actual_native_data_reads']==0
        and measured['trained_or_selected_model'] is False and measured['fixture_native_atoms']==[3,9,32]
        and measured['domain']['domain_pass'] is True,'Original synthetic complete13-field domain required')
    moves=measured['measurements'];require([row['transform']['name'] for row in moves]==list(TRANSFORMS),
        'Exact original three transforms required')
    for move in moves:
        require([row['field'] for row in move['fields']]==list(FIELDS)
            and move['vector_edges_unchanged'] is True
            and move['original_vector_edges']==move['transformed_vector_edges'],'Original full fields/edge population differs')
        for row in move['fields']:
            require(row['absolute_tolerance']==1e-5 and row['relative_tolerance']==0.0
                and row['finite'] is True and finite(row['maxabs']) and row['maxabs']>=0
                and type(row['passed']) is bool and type(row['count']) is int and row['count']>0
                and type(row['components']) is int and row['components']>0,'Original finite absolute1e-5/rtol0 gate required')
            if row['nonzero_required']:
                require(row['actual_nonzero_rows']>0 and row['reference_nonzero_rows']>0
                    and row['actual_max_row_norm']>row['nonzero_norm_floor']
                    and row['reference_max_row_norm']>row['nonzero_norm_floor'],'Original nonzero terminal guard failed')
            require(row['passed']==(row['maxabs']<=1e-5),'Recorded scalar gate verdict differs')
        require(move['passed']==all(row['passed'] for row in move['fields'])
            and finite(move['H0_maxabs_diagnostic_not_raw_unit_terminal'])
            and move['H0_maxabs_diagnostic_not_raw_unit_terminal']>=0,'Recorded transform/H0 scalar invalid')
    require(measured['passed']==all(move['passed'] for move in moves),'Recorded case verdict differs')
    return moves


def paired(reader,old_row,new_row):
    old=reader.load(old_row['case_json']);new=reader.load(new_row['case_json'])
    a,b=old['measured'],new['measured'];case_id=old_row['case_id']
    require(a['case_id']==b['case_id']==new_row['case_id']==case_id
        and all(a[key]==b[key] for key in IDENTITY),'Paired case/fixture/registry/view/domain identity differs')
    index=IDS.index(case_id);c,v,h,s=SPECS[index]
    require(a['case']==dict(distance_bias=c,views=v,head_policy=h,weight_seed=s)
        and a['encoder_forward_shapes']==[[44*(2 if v=='two' else 3),512]]*4,'Actual6x512/full-view forward shape differs')
    ca,cb=deepcopy(a['encoder_configuration']),deepcopy(b['encoder_configuration'])
    require(ca['backbone_config'].pop('residual_accumulation_mode','legacy')=='legacy'
        and cb['backbone_config'].pop('residual_accumulation_mode')=='two_sum_three_term_fp32_v1'
        and ca==cb and ca['backbone_config']['layers']==6 and ca['backbone_config']['dim']==512,
        'Only the declared residual accumulation configuration may differ')
    require(all(a['runtime'][key]==b['runtime'][key] for key in POLICY)
        and a['runtime']['autocast_enabled'] is False and a['runtime']['TF32_matmul'] is False,
        'Paired original FP32 runtime policy differs')
    require(old['original_fixture_source_sha256']==new['original_fixture_source_sha256'],
        'Original fixture implementation differs')
    for value in (old,new):
        weights=value['measured']['weight_summary'];construction=value['construction']
        require(re.fullmatch('[0-9a-f]{64}',weights['all_named_parameter_sha256'])
            and weights['all_named_parameter_sha256']==construction['actual_parameter_sha256']
                ==construction['original_parameter_sha256'],'Complete original1492 parameter identity differs')
    require(a['weight_summary']['all_named_parameter_sha256']==b['weight_summary']['all_named_parameter_sha256']
        and a['weight_summary']['parameters']==b['weight_summary']['parameters']
        and a['weight_summary']['state_selection']==b['weight_summary']['state_selection'],
        'Paired complete parameter identity/count/seed policy differs')
    require(old_row['actual_terminal_output_artifact']['arrays']==new_row['actual_terminal_output_artifact']['arrays']
        and len(old_row['actual_terminal_output_artifact']['arrays'])==52,'Original52 terminal metadata headers differ')
    am,bm=gate_rows(a),gate_rows(b);observations=[];h0=[]
    require(old_row['passed']==a['passed'] and new_row['passed']==b['passed'],'RESULT/case verdict differs')
    for x,y in zip(am,bm):
        require(x['transform']==y['transform'] and x['view_proof']==y['view_proof']
            and x['original_vector_edges']==y['original_vector_edges'],'Actual transforms/noise/view/edge controls differ')
        name=x['transform']['name'];h0.append(dict(transform=name,
            FFN4610=x['H0_maxabs_diagnostic_not_raw_unit_terminal'],residual4701=y['H0_maxabs_diagnostic_not_raw_unit_terminal']))
        for left,right in zip(x['fields'],y['fields']):
            require(all(left[key]==right[key] for key in ('field','law','unit','count','components',
                'nonzero_required','nonzero_norm_floor','absolute_tolerance','relative_tolerance')),
                'Original paired field/unit/population/gate differs')
            observations.append(dict(case_id=case_id,transform=name,field=left['field'],unit=left['unit'],
                count=left['count'],components=left['components'],FFN4610=dict(maxabs=left['maxabs'],passed=left['passed'],argmax=left['argmax']),
                residual4701=dict(maxabs=right['maxabs'],passed=right['passed'],argmax=right['argmax'])))
    return dict(case_id=case_id,FFN4610_passed=a['passed'],residual4701_passed=b['passed'],H0_diagnostics=h0),observations


def summary(rows,key=None):
    output={}
    for field in FIELDS:
        for transform in ((None,) if key is None else TRANSFORMS):
            selected=[row for row in rows if row['field']==field and (transform is None or row['transform']==transform)]
            require(len(selected)==(144 if transform is None else 48) and len({row['unit'] for row in selected})==1,
                'Complete same-unit scalar cohort required')
            item=dict(field=field,transform=transform,unit=selected[0]['unit'],observations=len(selected))
            for label in ('FFN4610','residual4701'):
                maximum=max(row[label]['maxabs'] for row in selected)
                representative=next(row for row in selected if row[label]['maxabs']==maximum)
                item[label]=dict(failed=sum(not row[label]['passed'] for row in selected),maxabs=maximum,
                    maximum_tie_count=sum(row[label]['maxabs']==maximum for row in selected),
                    first_canonical_representative=dict(case_id=representative['case_id'],transform=representative['transform'],
                        argmax=representative[label]['argmax']))
            output[field if transform is None else field+'|'+transform]=item
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-pins',type=Path,required=True);parser.add_argument('--source-pins-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True,help='Fresh JSON path beneath the existing supervised O/N output root');args=parser.parse_args()
    require(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID','').isdigit()
        and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16 and os.environ.get('CUDA_VISIBLE_DEVICES')==''
        and socket.gethostname().split('.')[0] in ['compute-0-'+str(i) for i in (2,*range(8,20))],
        'Owned CPU-only16CPU allocation required; Root supplies original supervisor')
    reader=Metadata();raw,pin_ref=reader.raw(args.source_pins)
    require(pin_ref['sha256']==args.source_pins_sha256,'Actual source-pins rawSHA required')
    pins=json.loads(raw,object_pairs_hook=unique)
    require(pins['schema']=='model_v3_residual4701_vs_FFN4610_scalar_source_pins_v1','Exact source-only manifest required')
    for ref in pins['files']:reader.raw(ref['path'],ref)
    require(any(ref['path']==str(Path(__file__).absolute()) for ref in pins['files']),'Actual consumer source must be bound')
    context=reader.load(pins['context_reference'])
    require(context['new_job']=='4524610' and context['new_root_closure']==pins['inputs']['FFN4610']['closure'],
        'Existing FFN/geometry context binds another original FFN closure')
    old,old_result,old_closure=cohort(reader,pins,'FFN4610')
    new,new_result,new_closure=cohort(reader,pins,'residual4701')
    with ThreadPoolExecutor(max_workers=16) as pool:
        pairs=list(pool.map(lambda pair:paired(reader,*pair),zip(old,new)))
    cases=[row[0] for row in pairs];rows=[obs for row in pairs for obs in row[1]]
    require(len(cases)==48 and len(rows)==1872,'No incomplete/screened comparison allowed')
    transition=lambda a,b:('P' if a else 'F')+'_to_'+('P' if b else 'F')
    case_changes=Counter(transition(row['FFN4610_passed'],row['residual4701_passed']) for row in cases)
    gate_changes=Counter(transition(row['FFN4610']['passed'],row['residual4701']['passed']) for row in rows)
    cohort_counts={}
    for label,result,closure in (('FFN4610',old_result,old_closure),('residual4701',new_result,new_closure)):
        failures=sum(not row[label+'_passed'] for row in cases)
        require(failures==result['counts']['failures']==closure['failed'] and 48-failures==closure['passed'],
            'Closed Root/producer and actual paired case counts differ')
        cohort_counts[label]=dict(cases=48,passed=48-failures,failed=failures,
            field_transform_observations=1872,failed_observations=sum(not row[label]['passed'] for row in rows))
    h0={t:{label:max(value[label] for row in cases for value in row['H0_diagnostics'] if value['transform']==t)
        for label in ('FFN4610','residual4701')} for t in TRANSFORMS}
    before=list(reader.refs.values())
    for ref in before:reader.raw(ref['path'],ref)
    output=args.output.absolute()
    require(output.suffix=='.json' and (output.is_relative_to(O) or output.is_relative_to(N))
        and output==output.resolve(strict=False) and not output.exists(),
        'Fresh physical model-owned O/N JSON output required')
    output.parent.mkdir(mode=0o700,exist_ok=True)
    require(output.parent.stat().st_uid==os.getuid(),'Owned existing supervisor output root required')
    payload=dict(schema='model_v3_residual4701_vs_FFN4610_scalar_comparison_v1',
        status='COMPLETE_PAIRED_METADATA_ANALYSIS_NOT_SCIENTIFIC_ADOPTION',cohort_counts=cohort_counts,
        case_transitions={k:case_changes[k] for k in ('P_to_P','P_to_F','F_to_P','F_to_F')},
        field_transform_transitions={k:gate_changes[k] for k in ('P_to_P','P_to_F','F_to_P','F_to_F')},
        fields=summary(rows),fields_by_transform=summary(rows,'transform'),case_rows=cases,
        paired_scalar_rows=rows,H0_diagnostic_maxima_by_transform=h0,all48_identity_checks_passed=True,
        selected_inputs_before_after_equal=True,selected_input_rawrefs=before,
        selected_unique_input_bytes=sum(r['bytes'] for r in before),
        input_cap_bytes=32<<20,NPZ_CP_SDK_data_or_weight_payload_opened_or_hashed=False,
        both_original_physical_gates_failed=True,scientific_adoption=False,universal_improvement_claimed=False,
        limits='Maxima are separate summaries, never same-component differences; H0 is diagnostic, not terminal units or causal attribution.')
    encoded=(json.dumps(payload,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    require(len(encoded)<=4<<20,'Scalar output cap4MiB exceeded')
    with output.open('xb') as stream:stream.write(encoded);stream.flush();os.fsync(stream.fileno())
    print(json.dumps(dict(status=payload['status'],output=str(output),cases=48,scalar_pairs=1872,
        selected_unique_input_bytes=payload['selected_unique_input_bytes'])))
    return 0


if __name__=='__main__':raise SystemExit(main())
