"""Source-schema extraction only; never fit, impute, clip or alter a label."""
from __future__ import annotations
import math
from .common import need,read,VERSION,digest

def extract(registry,mapping,numeric,report,*,numeric_reference,population_reference,heldout_reference):
    need(set(numeric)=={'models','exact_tails','winsorized_component_and_invariant_audit','diagnostic_median_MAD'},
      'EXACT_PRODUCER_CANONICAL_NUMERIC_KEYS')
    body=numeric['winsorized_component_and_invariant_audit']
    need(body['fit_role']=='TRAIN_ONLY' and body['source_labels_modified']is False
      and body['final_Common_D4']is False,'ACTUAL_TRAIN_ONLY_PROVISIONAL_MOMENTS')
    series=body['series'];by={r['key']:(i,r)for i,r in enumerate(series)}
    need(len(by)==len(series),'UNIQUE_ORIGINAL_STATISTICAL_SERIES')
    fields={f['field_key']:f for f in registry['fields']if f['status']=='enabled'}
    need(len(fields)==146,'ALL146_SOURCE_COMPONENT_DEFINITIONS_RETAINED')
    audits={g['physical_group']:g for g in report['groups']}
    out={}
    for t in mapping['physical_targets']:
        fs=[fields[m['field_key']]for m in t['members']];f=fs[0];fid=str(f['field_id'])
        if t['kind']=='symmetric_tensor':key='physical/'+str(f['registry_id'])+'/'+f['task']+'/frobenius_norm'
        elif t['kind']=='vector':
            key=(fid+'/norm' if f['level']=='atom_vector' else 'physical/'+str(f['registry_id'])+'/'+f['task']+'/norm')
        else:key=fid+('/residual'if f['element_reference_eligible']else'/raw')
        need(key in by,'ACTUAL_D4_SERIES_MISSING:'+key);index,s=by[key]
        need(type(s['n'])is int and s['n']>=0 and s['lower_probability']=='0.001'
          and s['upper_probability']=='0.999' and 'mean'in s and 'std_ddof0'in s,'EXACT_ORIGINAL_TYPE7_WINSOR_MOMENT')
        scale=s['std_ddof0'];center=0. if t['kind']in('vector','symmetric_tensor')else s['mean']
        need(scale is None or type(scale)in(int,float),'NO_STRING_OR_IMPUTED_STD')
        if scale is not None:need(math.isfinite(scale)and scale>=0,'MALFORMED_ACTUAL_STD')
        record={'target_id':t['target_id'],'series_key':key,'n':s['n'],'mean':s['mean'],'center':center,
          'std_ddof0':scale,'lower':s['lower'],'upper':s['upper'],'numeric_reference':numeric_reference,
          'statistics_pointer':['winsorized_component_and_invariant_audit','series',index],
          'population_reference':population_reference,'heldout_reference':heldout_reference,
          'registry_id':f['registry_id'],'task':f['task'],'condition':t['condition'],
          'source_fields':[m['field_key']for m in t['members']], 'source_values_or_masks_modified':False}
        if f['element_reference_eligible']:
            need(fid in numeric['models'],'ACTUAL_TRAIN_ELEMENT_MODEL_REQUIRED')
            record['element_reference_model']=numeric['models'][fid]
            record['loss_contract']='RAW_UNIT_PREDICTION_AND_TARGET_USE_SAME_AFFINE_TRANSFORM; SHARED_ELEMENT_OFFSET_CANCELS_IN_ERROR; SCALE_FROM_ACTUAL_RESIDUAL_SERIES'
        if t['kind']=='symmetric_tensor':
            group='physical/'+str(f['registry_id'])+'/'+f['task'];need(group in audits,'ACTUAL_R674_AUDIT_GROUP')
            a=audits[group];recipe=a['loss_recipe_candidate']
            need(recipe['series_key']==key and recipe['statistic_reference']==numeric_reference
              and recipe['population_version_reference']==population_reference,'ACTUAL_R674_SERIES_POPULATION_SOURCE_BINDING')
            record['raw_mean_F_report']=a['raw_mean_F_report'];record['raw_F_moment']=a['raw_F_moment']
        out[t['target_id']]=record
    return {'schema':'ACTUAL_PROVISIONAL_FAST55K_D4_PROJECTION_V1','version':VERSION,
      'fit_role':'TRAIN','source_numeric_reference':numeric_reference,'population_reference':population_reference,
      'heldout_reference':heldout_reference,'targets':out,'source_statistics_recomputed':False,
      'original_statistics_labels_masks_unchanged':True}

def normalizers(registry,projection,projection_reference):
    import torch
    from phychem_mfm.phase1.v3_contract import TrainNormalization,DisabledNormalization
    out={}
    for f in registry.fields:
        if f.group=='S':continue
        r=projection['targets'][f.name];v=r['std_ddof0'];reason=None
        if r['n']==0:reason='EMPTY'
        elif v is None:reason='MISSING'
        elif v==0:reason='ZERO'
        elif not math.isfinite(v):reason='NONFINITE'
        else:
            f32=torch.tensor(float(v),dtype=torch.float32)
            if not bool(torch.isfinite(f32)):reason='NONFINITE'
            elif float(f32)==0:reason='ZERO'
        if reason:
            evidence={'statistics_reference':projection_reference,'statistics_pointer':['targets',f.name],
              'source_numeric_reference':r['numeric_reference'],'original_statistics_pointer':r['statistics_pointer']}
            out[f.name]=DisabledNormalization(f.name,f.name,reason,projection_reference['sha256'],VERSION,evidence)
        else:
            need(type(r['center'])in(int,float)and math.isfinite(r['center'])and v>0,'ACTUAL_READY_AFFINE_D4')
            out[f.name]=TrainNormalization((r['center'],),(v,),projection_reference['sha256'],VERSION)
        out[f.name].validate_for(f)
    return out

def tensor_record(release,field_name):
    """Return the existing Model tensor-normalizer's exact six-item protocol."""
    doc=read(release.evidence['d4_statistics']);r=doc['targets'][field_name]
    need(r['registry_id']==674 and r['series_key']=='physical/674/'+r['task']+'/frobenius_norm',
      'ACTUAL_R674_FROBENIUS_SERIES_NOT_COMPONENT_STD')
    binding=release.projection['D4_bindings'][field_name];target=release.projection['targets'][field_name]
    evidence={'statistics_reference':release.evidence['d4_statistics'],'statistics_pointer':['targets',field_name],
      'source_numeric_reference':r['numeric_reference'],'original_statistics_pointer':r['statistics_pointer'],
      'effective_train_reference':release.evidence['effective_train'],
      'heldout_exclusion_reference':release.evidence['heldout_exclusion'],'joint_policy_reference':release.evidence['joint_contract']}
    return binding,target,r,r['lower'],r['upper'],evidence

def tensor_raw_mean(release,field_name):
    r=read(release.evidence['d4_statistics'])['targets'][field_name];raw=r['raw_mean_F_report']
    # This is the actual raw-F producer record, never norm(meanQ)/winsor mean.
    return {'status':raw['status'],'raw_mean_F':raw['raw_complete6_TRAIN_F_mean'],
      'raw_mean_F_over_s':raw['mean_F_over_bound_s'],'source':release.evidence['d4_statistics'],
      'original_report':raw,'current_centering_changed':False}
