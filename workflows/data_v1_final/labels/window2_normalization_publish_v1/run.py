"""Bind existing statistics to field/target routes; no label/cache scan or fit."""
from __future__ import annotations
import argparse
import copy
import json
import math
import os
from pathlib import Path


def read(reference):
    path=reference['path'] if isinstance(reference,dict) else reference
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def pointer(value,path):
    for key in path.strip('/').split('/') if path.strip('/') else []:
        value=value[key.replace('~1','/').replace('~0','~')]
    return value


def numerical_route(row,series_key,centering):
    result={'series_key':series_key,'center':None,'scale':None,'normalizer_ready':False,
        'clipping_applies_only_to_statistics':True,'training_labels_clipped':False}
    if row is None:return dict(result,status='LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE',reason='SERIES_NOT_COMPUTED')
    result.update(n=row['n'],lower=row.get('lower'),upper=row.get('upper'),
        audit_winsorized_mean=row.get('mean'),scale_statistic='SERIES_STD_DDOF0',centering=centering)
    std=row.get('std_ddof0');mean=row.get('mean')
    if not row['n'] or std is None or not math.isfinite(std) or std<=0 or (centering=='SUBTRACT_SERIES_MEAN' and (mean is None or not math.isfinite(mean))):
        return dict(result,status='LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE',reason=row.get('status','EMPTY_OR_UNDEFINED_SCALE'))
    result.update(status='NORMALIZER_AVAILABLE',center=0.0 if centering=='FIXED_ZERO' else mean,scale=std,normalizer_ready=True)
    return result


def physical_key(target,field):
    if field['level']=='atom_vector':return str(field['field_id'])+'/norm'
    identity=target.get('native_target_identity',{})
    rid=identity.get('registry_id',field['registry_id']);task=identity.get('task',field['task'])
    return 'physical/'+str(rid)+'/'+task+('/frobenius_norm' if target['kind']=='symmetric_tensor' else '/norm')


def build_dataset(name,fields,statistics,models,schema,policy,policy_reference,physical_rules=None):
    bykey={field['field_key']:field for field in fields};series={row['key']:row for row in statistics['series']}
    catalog={}
    for row in statistics['series']:
        item=catalog.setdefault(row['source_field_key'],{'source_field_id':row['source_field_id'],'series':{}})
        # row.field_id is a radix series ID, never the original registry field ID.
        item['series'][row['key']]={key:row.get(key) for key in ('field_id','source_field_id','view','element_atomic_number','axis','n','lower','upper','mean','std_ddof0','status')}
    descriptors={f['field_key']:f for f in [*schema['fields'],*schema.get('derived_training_fields',[])]}
    targets={}
    for tid,layout in schema['target_layout'].items():
        target=layout['mapping_target'];keys=[m['field_key'] for m in target.get('members',[])]
        flags=[descriptors.get(key,{}).get('loss_enabled') for key in keys]
        source_enabled=False if any(flag is False for flag in flags) else (True if flags and all(flag is True for flag in flags) else 'UNKNOWN_PRESERVED')
        route={'target_id':tid,'dataset':name,'kind':target.get('kind',layout.get('kind')),
            'condition':target.get('condition'),'members':keys,'normalizer_ready':False,
            'source_loss_policy':{key:{k:descriptors.get(key,{}).get(k) for k in ('loss_enabled','loss_status','physical_policy_status')} for key in keys},
            'existing_loss_policy_must_still_apply':True,'original_loss_enabled':source_enabled}
        if layout.get('array_name')=='r73_ordered' or target.get('wire_kind')=='SOURCE_ORDERED_RECORDS_V1':
            # Original K-entry statistics are retained for diagnosis only.
            # Approved pair-sum training routes bind their own146/147 series.
            route.update(status='RAW_CONTAINER_STATISTICS_ONLY',normalizer_ready=False,
                raw_series_keys=[str(bykey[key]['field_id'])+'/raw' for key in keys if key in bykey],
                derived_training_target_ids=[value['target_id'] for value in schema.get('derived_r73_pair_targets',{}).values()])
            targets[tid]=route;continue
        if not keys or any(key not in bykey for key in keys):
            targets[tid]=dict(route,status='NOT_IN_THIS_STATISTICS_DATASET');continue
        selected=[bykey[key] for key in keys];field=selected[0]
        if route['kind'] in ('vector','symmetric_tensor'):
            candidate=physical_key(target,field);route['available_invariant_series_key']=candidate
            binding=(physical_rules or {}).get(tid)
            if binding:
                recipe=binding['recipe'];source=binding['policy_reference'];location=binding['json_pointer']
            elif route['kind']=='symmetric_tensor' and all(f['registry_id']==674 for f in selected):
                recipe=policy['r674']['normalization'];source=policy_reference;location='/r674/normalization'
            else:
                targets[tid]=dict(route,status='FIXED_ZERO_SINGLE_SCALE_POLICY_PENDING',policy_reference=policy_reference,
                    reason='No frozen per-target vector scale recipe was supplied; available norm statistics do not choose a policy');continue
            if recipe.get('centering')!='FIXED_ZERO' or recipe.get('scale')!='SERIES_STD_DDOF0' or recipe.get('per_head_single_scale') is not True:
                targets[tid]=dict(route,status='FROZEN_PHYSICAL_RECIPE_NOT_SUPPORTED_BY_EXISTING_SERIES',policy_reference=source,json_pointer=location);continue
            key=recipe.get('series_key',recipe.get('series_key_template',candidate))
            key=key.replace('<registry_id>',str(field['registry_id'])).replace('<task>',field['task']).replace('<field_id>',str(field['field_id']))
            route.update(numerical_route(series.get(key),key,'FIXED_ZERO'),per_head_single_scale=True,
                policy_reference=source,json_pointer=location,raw_invariant_mean_status='RAW_MEAN_F_REPORT_PENDING')
        elif route['kind']=='scalar' and len(selected)==1:
            energy=field['element_reference_eligible'];key=str(field['field_id'])+('/residual' if energy else '/raw')
            route.update(numerical_route(series.get(key),key,'SUBTRACT_SERIES_MEAN'),per_head_single_scale=False)
            if energy:
                model=models.get(str(field['field_id']))
                if not model or not isinstance(model.get('coefficients'),list) or len(model['coefficients'])!=len(model.get('basis',[])) or model.get('intercept') is None:
                    route.update(status='LOSS_DISABLED_ELEMENT_REFERENCE_UNBOUND',normalizer_ready=False)
                else:
                    route['element_reference']=copy.deepcopy(model)
                    route['coefficients_by_atomic_number']={str(z):b for z,b in zip(model['basis'],model['coefficients'])}
                    route['element_reference_transform']='residual = y - (intercept + fsum(count(Z)*coefficient[Z])); normalized = (residual-center)/scale'
        else:
            route.update(status='NO_FROZEN_SCALAR_ROUTE_FOR_THIS_CONTAINER')
        # Having a numerical scale never enables a disabled physical exposure.
        targets[tid]=route
    return {'status':'BOUND_TO_INDEPENDENT_PRODUCER_STATISTICS','field_series':catalog,'targets':targets}


def dataset_input(path,name):
    manifest=read(path)
    expected='PM7_P_D_TRAIN_STATISTICS_COMPLETE' if name=='P_D' else 'PPRIME_INDEPENDENT_TRAIN_STATISTICS_COMPLETE'
    if manifest['status']!=expected:raise ValueError('PRODUCER_STATISTICS_NOT_CLOSED:'+name)
    references=manifest['statistics'];numeric=read(references['winsorized_statistics_reference'])
    models=read(references['element_models_reference'])
    fields_ref=manifest['inputs']['field_map_reference'] if name=='P_D' else read(manifest['source_projection'])['field_map_reference']
    return read(fields_ref),numeric,models,{'manifest':str(Path(path).absolute()),'statistics':references['winsorized_statistics_reference'],
        'element_models':references['element_models_reference'],'fields':fields_ref}


def pm7_closed_checkpoint_input(path):
    """Consume committed full-TRAIN parameter stages, not an invented C0 manifest."""
    state=read(path);cfg=state.get('inputs',{});results=state.get('results',{});eligibility=state.get('eligibility',{})
    def need(value,reason):
        if not value:raise ValueError('PM7_CLOSED_CHECKPOINT:'+reason)
    need(cfg.get('mode')=='full','FULL_INPUT_REQUIRED')
    # At index3 all three parameter purposes have closed; the diagnostic purpose
    # is still pending/running. Index4 belongs to the original post-C0 mode.
    need(type(state.get('purpose_index')) is int and state['purpose_index']==3,'THREE_PARAMETER_PURPOSES_CLOSED_DIAGNOSTICS_PENDING_REQUIRED')
    required=('element_models_reference','exact_tail_reference','winsorized_statistics_reference')
    for key in required:
        need(isinstance(results.get(key),dict) and isinstance(results[key].get('path'),str) and bool(results[key]['path']),'CLOSED_REFERENCE_REQUIRED:'+key)
    for key in ('coverage_reference','common_reference','d5_reference','field_map_reference','input_release_reference'):
        need(isinstance(cfg.get(key),dict) and bool(cfg[key].get('path')),'FULL_INPUT_REFERENCE_REQUIRED:'+key)
    need(cfg['input_release_reference']==cfg['common_reference'],'FINAL_COMMON_INPUT_RELEASE_REQUIRED')
    need(eligibility.get('Common_TRAIN_only') is True and eligibility.get('D5_excludes_base_and_all_14_source_tasks') is True,'COMMON_TRAIN_ANTI_D5_ELIGIBILITY_REQUIRED')
    need(type(cfg.get('source_records')) is int and cfg['source_records']>0 and eligibility.get('source_records')==cfg['source_records'] and eligibility.get('fit_records',0)>0,'FULL_SOURCE_ELIGIBILITY_CLOSURE_REQUIRED')
    eligibility_ref=eligibility.get('eligibility_reference')
    need(isinstance(eligibility_ref,dict) and bool(eligibility_ref.get('path')),'ELIGIBILITY_REFERENCE_REQUIRED')
    need(not results.get('diagnostic_median_MAD_reference'),'DIAGNOSTICS_ALREADY_CLOSED_USE_POST_C0_MODE')
    tail=read(results['exact_tail_reference'])
    for key,expected in (('coverage_reference',cfg['coverage_reference']),('field_map_reference',cfg['field_map_reference']),
        ('input_release_reference',cfg['input_release_reference']),('eligibility_reference',eligibility_ref),
        ('element_models_reference',results['element_models_reference'])):
        need(tail.get(key)==expected,'CLOSED_TAIL_SOURCE_BINDING:'+key)
    numeric=read(results['winsorized_statistics_reference'])
    need(numeric.get('fit_role')=='TRAIN_ONLY' and numeric.get('source_labels_modified') is False,'TRAIN_MOMENTS_CLOSURE_REQUIRED')
    models=read(results['element_models_reference']);fields_ref=cfg['field_map_reference']
    closed_keys=(*required,'mask_overrides_reference','validity_mask_counts_reference','r73_derived_reference','molecule_field_means_reference')
    references={'source_kind':'PM7_CLOSED_PARAMETER_CHECKPOINT','checkpoint':str(Path(path).absolute()),
        'statistics':copy.deepcopy(results['winsorized_statistics_reference']),'element_models':copy.deepcopy(results['element_models_reference']),
        'exact_tail':copy.deepcopy(results['exact_tail_reference']),'fields':copy.deepcopy(fields_ref),
        'eligibility_reference':copy.deepcopy(eligibility_ref),'eligibility':copy.deepcopy(eligibility),
        'inputs':copy.deepcopy(cfg),'closed_training_stage_references':{key:copy.deepcopy(results[key]) for key in closed_keys if key in results},
        'completed_parameter_purposes':['element_reference','normalization_quantiles','normalization_moments'],
        'diagnostic_progress':{'purpose_index':state['purpose_index'],'pass_index':state.get('pass_index'),'active_stage_reference':copy.deepcopy(state.get('active_stage'))},
        'publication_state':{'status':'NORMALIZATION_PARAMETERS_READY_D4_PENDING_MAD','D4_complete':False,
            'PM7_parent_C0_not_claimed':True,'PM7_parent_C0_claimed':False,'PM7_diagnostic_status':'PENDING_MAD','PM7_diagnostics_continue':True}}
    return read(fields_ref),numeric,models,references


def pm7_input(args):
    checkpoint=getattr(args,'pm7_closed_checkpoint',None)
    return pm7_closed_checkpoint_input(checkpoint) if checkpoint else dataset_input(args.pm7,'P_D')

def publish(args):
    from workflows.data_v1_final.export.v31_stream_v1.derived_pair import augment_schema
    from workflows.data_v1_final.export.v31_stream_v1.disk_guard import Guard
    schema=read(args.schema)
    if not schema.get('derived_training_fields') and any(t['array_name']=='r73_ordered' for t in schema['target_layout'].values()):augment_schema(schema)
    policy=read(args.physical_policy);policy_reference={'path':str(Path(args.physical_policy).absolute())}
    rules={}
    if args.physical_routes:
        for tid,binding in read(args.physical_routes)['targets'].items():
            # Routing document contains only pointers into existing formal policies.
            rules[tid]=dict(binding,recipe=pointer(read(binding['policy_reference']),binding['json_pointer']))
    result={'schema':'WINDOW2_D4_MODEL_NORMALIZATION_ROUTES_V1','status':'METADATA_ROUTES_WITH_EXPLICIT_TARGET_LOCAL_READINESS',
        'lookup_key':['dataset','target_id'],'scalar_policy':'Root2026-11-06: existing TRAIN mean/std; no invented epsilon/RMS/scale fallback',
        'physical_policy_reference':policy_reference,'datasets':{},'source_references':{},
        'numeric_statistics_refitted':False,'label_or_Parquet_scanned':False,'source_values_or_masks_modified':False,
        'componentwise_statistics_are_not_a_vector_training_route':True,'Pprime_falls_back_to_PM7':False}
    for name,path in (('P_D',args.pm7 or getattr(args,'pm7_closed_checkpoint',None)),('Pprime',args.pprime)):
        if path:
            fields,numeric,models,references=pm7_input(args) if name=='P_D' else dataset_input(path,name)
            result['datasets'][name]=build_dataset(name,fields,numeric,models,schema,policy,policy_reference,rules)
            result['source_references'][name]=references
            if name=='P_D':result.update(references.get('publication_state',{}))
        else:result['datasets'][name]={'status':'PENDING_REAL_INDEPENDENT_PRODUCER_C0','field_series':{},'targets':{}}
    guard=Guard(read(args.disk_plan));out=Path(args.output)
    raw=(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode('utf-8')
    guard.wait(out,bytes_needed=len(raw)+65536,inodes_needed=4);out.mkdir(parents=True,exist_ok=False)
    path=out/'routes.json';partial=out/'routes.writing'
    with partial.open('xb') as stream:
        for offset in range(0,len(raw),1<<20):
            chunk=raw[offset:offset+(1<<20)];guard.wait(partial,len(chunk),1);stream.write(chunk)
    os.replace(partial,path)
    manifest={'schema':'WINDOW2_D4_ROUTES_DELIVERY_V1','files':[{'path':str(path.absolute()),'bytes':path.stat().st_size,
        'records':sum(len(v['targets']) for v in result['datasets'].values()),'record_unit':'dataset-target route'}]}
    body=(json.dumps(manifest,indent=2)+'\n').encode('utf-8');guard.wait(out,len(body),1)
    with (out/'manifest.json').open('xb') as stream:stream.write(body)
    return manifest


def argument_parser():
    parser=argparse.ArgumentParser(description=__doc__)
    pm7=parser.add_mutually_exclusive_group(required=True)
    pm7.add_argument('--pm7',help='original producer-complete PM7 manifest (default publication mode)')
    pm7.add_argument('--pm7-closed-checkpoint',help='committed full-TRAIN parameter checkpoint; complete D4 remains pending MAD')
    for key in ('schema','physical-policy','disk-plan','output'):parser.add_argument('--'+key,required=True)
    parser.add_argument('--pprime');parser.add_argument('--physical-routes')
    return parser


def main():
    args=argument_parser().parse_args();print(json.dumps(publish(args)),flush=True)


if __name__=='__main__':main()