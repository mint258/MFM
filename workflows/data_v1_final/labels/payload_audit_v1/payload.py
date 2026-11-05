"""Read-only payload observations and unchanged inherited mask candidate rules."""
from __future__ import annotations
import collections, math

PAIR_LEAVES={'bond_orders','wiberg_pairs','sigma_pi_entries','mulliken_overlap_population_pairs','enpart_pairs_eV'}
STRUCTURAL={'CELL_DECODE_INVALID','ARRAY_TYPE_INVALID','MOLECULE_VECTOR_SHAPE_INVALID','SHELL_SHAPE_INVALID',
 'FUKUI_SHAPE_INVALID','COMPOUND_SHAPE_INVALID','ONE_CENTER_ATOM_COUNT_INVALID','COMPOUND_ATOM_INDEX_INVALID',
 'PAIR_VALUE_LAYOUT_INVALID','PAIR_INDEX_INVALID','ATOM_VECTOR_SHAPE_INVALID','ATOM_VALUE_SHAPE_INVALID'}

def layout_reviews(value,leaf,atoms,pair_keys):
    """Additional observations only: no new mask rule or invented payload repair."""
    reasons=[]
    if not isinstance(value,list):return reasons
    if leaf in ('enpart_one_center_eV','super_heavy_atom_rows'):
        keys=[x.get('atom_index') if isinstance(x,dict) else None for x in value]
        if any(type(x) is not int or not 0<=x<atoms for x in keys):reasons.append('COMPOUND_OWNED_ATOM_ID_INVALID_REVIEW')
        elif len(set(keys))!=len(keys):reasons.append('COMPOUND_DUPLICATE_ATOM_ID_REVIEW')
        if leaf=='enpart_one_center_eV' and set(keys)!=set(range(atoms)):reasons.append('ONE_CENTER_ATOM_COVERAGE_REVIEW')
    if leaf in PAIR_LEAVES:
        keys=pair_keys(value,leaf)
        if keys is None:return ['SPARSE_PAIR_KEY_LAYOUT_REVIEW']
        for row in value:
            labels=('atom_i','atom_j') if leaf=='sigma_pi_entries' else ('i','j')
            if any(type(row.get(k)) is not int or not 0<=row[k]<atoms for k in labels):
                reasons.append('SPARSE_PAIR_ATOM_ID_RANGE_REVIEW');break
        owned={}
        for key,row in zip(keys,value):
            # Compare stored numeric representation exactly; not a claim of total energy.
            column=('J_K_EE_EN_NN_C_total' if leaf=='enpart_pairs_eV' else
                    'population_e' if leaf=='mulliken_overlap_population_pairs' else 'value')
            v=row.get(column)
            if key in owned:reasons.append('DUPLICATE_PAIR_KEY_SAME_VALUE_REVIEW' if owned[key]==v else 'DUPLICATE_PAIR_KEY_CONFLICT_REVIEW')
            else:owned[key]=v
    return sorted(set(reasons))

def reference_review(item,calibration):
    """Same z/MAD semantics as frozen streaming_v1.scan_v2.add_reference_reviews."""
    entry=calibration.get(str(item['field_id']))
    if entry is None:return None
    center,mad=entry['median'],entry['MAD']
    if center is None or mad is None or not math.isfinite(center) or not math.isfinite(mad):
        item['review_reasons'].append('TRAIN_SCALE_UNDEFINED_REVIEW_ONLY');return None
    eligible=[abs(v-center) for v,keep in zip(item['values_float64'],item['value_mask']) if keep]
    if not eligible:return None
    if mad==0:
        deviation=max(eligible)
        if deviation>0:item['review_reasons'].append('ZERO_MAD_UNEQUAL_VALUE_REVIEW_ONLY')
        return deviation if deviation>0 else 0.0
    score=.6744897501960817*max(eligible)/mad
    if score>20:item['review_reasons'].append('ROBUST_Z_GT20_REVIEW_ONLY')
    return score

def evaluate(row,family,fields,common,masks,pair_keys,calibration):
    """Decode each raw CELL once, retain all264 declarations, assess146 enabled."""
    atoms=row['total_atoms'];decoded={};errors={};raw=collections.Counter();structural=[]
    if family not in ('D20','D3'):
        for cell in row.get('values') or []:
            if not isinstance(cell,dict) or type(cell.get('registry_id')) is not int:
                structural.append({'registry_id':None,'reason':'NULL_OR_UNIDENTIFIED_CELL_REVIEW'});continue
            rid=cell['registry_id'];raw['kind:'+str(cell.get('kind'))]+=1
            if rid in decoded:
                errors[rid]='CELL_DECODE_INVALID:DUPLICATE_REGISTRY_CELL'
                structural.append({'registry_id':rid,'reason':'DUPLICATE_REGISTRY_CELL_REVIEW'});continue
            try:
                decoded[rid]=common.decode_cell(cell)
                if cell.get('kind') in (5,6,7):raw['array_actual_length_valid']+=1
                if cell.get('kind') in (8,10):raw['json_payload_decoded']+=1
            except (ValueError,TypeError,KeyError,OverflowError) as exc:
                raw['raw_registry_cell_decode_failures']+=1
                decoded[rid]=common.MISSING;errors[rid]='CELL_DECODE_INVALID:'+str(exc)
                structural.append({'registry_id':rid,'reason':'CELL_ACTUAL_PAYLOAD_DECODE_INVALID'})
    observations=[];items=[];layout_by_rid={};score_by_id={}
    if family in ('D20','D3'):
        values_by_key={f['field_key']:(vals,idx,reason) for f,vals,idx,reason in common.task_components(row,family,fields)}
    else:values_by_key={}
    for field in fields:
        rid=field['registry_id'];leaf=field['source_path'].rsplit('.',1)[-1]
        if family in ('D20','D3'):values,indices,reason=values_by_key[field['field_key']]
        else:
            value=decoded.get(rid,common.MISSING);reason=errors.get(rid)
            if rid in (row.get('numeric_issues') or []):reason='SOURCE_NUMERIC_ISSUE'
            values,indices,layout=common.component_values(field,value,atoms);reason=reason or layout
            if rid not in layout_by_rid:
                layout_by_rid[rid]=layout_reviews(value,leaf,atoms,pair_keys) if value is not common.MISSING else []
                structural.extend({'registry_id':rid,'reason':r} for r in layout_by_rid[rid])
        numeric=[v for v in values if common.numeric(v)]
        observations.append({'field_key':field['field_key'],'declaration':field['status'],'records':1,
          'reason':reason,'numeric_leaves':len(numeric),'nonnumeric_or_nonfinite_leaves':len(values)-len(numeric),
          'zero_leaves':sum(v==0 for v in numeric),'layout_accepted':reason is None,
          'payload_structural_failure':bool(reason and reason.split(':',1)[0] in STRUCTURAL)})
        if field['status']!='enabled':continue
        source_valid,source_mask,mask,source_reason,new_reason,review=masks.source_value_mask(field,row,values,reason)
        item={'field_id':field['field_id'],'field_key':field['field_key'],'source_path':field['source_path'],
          'values_float64':[float(v) if type(v) in (int,float) else None for v in values],
          'source_value_mask':source_mask,'value_mask':mask,'source_reasons':source_reason,'new_reasons':new_reason,
          'review_reasons':review,'atom_indices':indices}
        items.append(item)
    # Native graph rows do not have calc_type; the inherited helper expects one.
    context=dict(row,calc_type=row.get('calc_type',family))
    try:masks.add_cross_field_checks(items,context)
    except (ValueError,TypeError,KeyError,OverflowError):
        for item in items:item.setdefault('structural_review',[]).append('CROSSFIELD_SOURCE_PRECISION_UNPARSEABLE_REVIEW')
    for item in items:score_by_id[item['field_id']]=reference_review(item,calibration)
    return items,observations,structural,dict(raw),score_by_id

def worst_preview(item,owner,reason,score,limit=32):
    values=item['values_float64']
    return {'field_id':item['field_id'],'field_key':item['field_key'],'molecule_id':owner['molecule_id'],
      'record_ordinal':owner['record_ordinal'],'record_id':owner['record_id'],'role':owner['new_role'],
      'reason':reason,'score':score,'raw_value_preview':[v if v is None or math.isfinite(v) else repr(v) for v in values[:limit]],
      'raw_value_preview_truncated':len(values)>limit,'source_reasons':item['source_reasons'],
      'new_reasons':item['new_reasons'],'review_reasons':item['review_reasons']}

def quality_stop_fields(stats,denominator,fraction=.01):
    return sorted(key for key,s in stats.items() if denominator and
       (s.get('newly_masked_records',0)/denominator>fraction or s.get('new_payload_structural_invalid_records',0)/denominator>fraction))