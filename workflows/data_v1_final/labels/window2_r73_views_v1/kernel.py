"""User-approved F64 pure sigma/sigma and pi/pi atom-pair training targets.

Original ordered r73 records, directions, onsite rows and duplicates are retained.
Derived IDs146/147 extend only the normalization-view map, never the registry.
"""
import copy,math
DERIVED_IDS={'sigma':146,'pi':147}
USER_DEFINITION='USER_APPROVED_20261105_PURE_SIGMA_SIGMA_PI_PI_BLOCKS'


def symmetry(name):
    if not isinstance(name,str):return None
    if name.endswith('-SIGMA'):return'sigma'
    if name.endswith('-PI'):return'pi'
    return None


def derived_fields(fields):
    source=[f for f in fields if f.get('registry_id')==73 and f['field_id']<146]
    if len(source)!=1:raise ValueError('ONE_ORIGINAL_R73_FIELD_REQUIRED')
    original=source[0];out=[]
    for name,fid in DERIVED_IDS.items():
        field=copy.deepcopy(original);field.update(field_id=fid,field_key=original['field_key']+'.'+name,
            source_field_id=original['field_id'],source_field_key=original['field_key'],component=name+'_pair_sum',
            element_reference_eligible=False,normalization_view_only=True,registry_unchanged=True,
            derived_target_definition=USER_DEFINITION,pair_order='directed original atom-pair first occurrence; onsite and repeated entries retained in sum')
        out.append(field)
    return out


def derive_entries(raw_records,original_entry,*,field_map=None):
    """Return sigma and pi standard entries from one raw original r73 CELL.

    Numeric sums use F64, in original K order, exactly like the B2 bincount
    accumulation. An absent pure block has value None and false masks, never0.
    Invalid selected terms make that block invalid; mixed/delta terms do not.
    """
    if not isinstance(raw_records,list):raise ValueError('ORIGINAL_R73_RECORD_LIST_REQUIRED')
    n=len(raw_records)
    if n!=len(original_entry['values_float64'])or n!=len(original_entry['value_mask'])or n!=len(original_entry['source_value_mask']):
        raise ValueError('R73_K_VALUES_AND_MASKS_ALIGNMENT')
    pairs=[];position={};blocks={name:[]for name in DERIVED_IDS}
    for k,row in enumerate(raw_records):
        if not isinstance(row,dict)or type(row.get('atom_i'))is not int or type(row.get('atom_j'))is not int:
            raise ValueError('EXPLICIT_ORIGINAL_R73_PAIR_INDICES_REQUIRED')
        pair=(row['atom_i'],row['atom_j'])
        if pair not in position:
            position[pair]=len(pairs);pairs.append(pair)
            for name in blocks:blocks[name].append([])
        left,right=symmetry(row.get('basis_i')),symmetry(row.get('basis_j'))
        if left is not None and left==right:blocks[left][position[pair]].append(k)
        observed=original_entry['values_float64'][k];raw=row.get('value')
        if isinstance(raw,(int,float))and math.isfinite(raw)and observed is not None and math.isfinite(observed):
            if not math.isclose(float(raw),observed,rel_tol=0.,abs_tol=0.):raise ValueError('R73_RAW_K_AND_EVALUATED_VALUE_ALIGNMENT')
    definitions=derived_fields([original_entry['field']])if field_map is None else field_map
    result=[]
    for field in definitions:
        name=next(name for name,fid in DERIVED_IDS.items()if fid==field['field_id']);values=[];source_mask=[];value_mask=[]
        for ids in blocks[name]:
            numeric=bool(ids)and all(original_entry['values_float64'][k]is not None and math.isfinite(original_entry['values_float64'][k])for k in ids)
            # Deterministic F64 left-fold, retaining duplicate terms and K order.
            value=0.
            if numeric:
                for k in ids:value+=original_entry['values_float64'][k]
            values.append(value if numeric else None)
            source_mask.append(bool(numeric and all(original_entry['source_value_mask'][k]for k in ids)))
            value_mask.append(bool(numeric and all(original_entry['value_mask'][k]for k in ids)))
        result.append({'field':field,'field_id':field['field_id'],'field_key':field['field_key'],'source_path':field['source_path'],
            'values_float64':values,'source_value_mask':source_mask,'value_mask':value_mask,'atom_indices':None,
            'pair_indices':[list(pair)for pair in pairs],
            'source_reasons':list(original_entry['source_reasons']),'new_reasons':list(original_entry['new_reasons']),
            'review_reasons':list(original_entry['review_reasons'])})
    return result