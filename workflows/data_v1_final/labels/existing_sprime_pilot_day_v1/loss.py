"""User-frozen target-local r674 scale recipe and separate loss eligibility.

This never changes a source/data mask. Source, geometry, quality or statistics
failures remain HOLD; only the expected absent/invalid *scale* is a disabled
target recipe. No whole-pipeline exception is swallowed by this module.
"""
import collections,math,struct
from . import contract as C,io as I,bindings as B,reader as R
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K
COMPONENTS=('xx','xy','yy','xz','yz','zz');WEIGHTS=(1,2,1,2,2,1)

def scale_recipe(value,*,population_reference,statistic_reference,series_key,observed_population_reference):
    if population_reference is None or observed_population_reference!=population_reference or value is None:
        status='LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE';reason='UNBOUND_POPULATION_OR_MISSING_SCALE'
    elif type(value) not in (int,float) or not math.isfinite(value) or value<=0:
        status='LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE'
        reason='NON_NUMERIC_SCALE' if type(value) not in (int,float) else ('NONFINITE_SCALE' if not math.isfinite(value) else ('ZERO_SCALE' if value==0 else 'NEGATIVE_SCALE'))
    else:status='NUMERIC_SCALE_CANDIDATE_BOUND_PENDING_EXTERNAL_ROOT_AND_MODEL';reason=None
    usable=status=='NUMERIC_SCALE_CANDIDATE_BOUND_PENDING_EXTERNAL_ROOT_AND_MODEL'
    return {'status':status,'reason':reason,'candidate_scale':float(value) if usable else None,
        'observed_scale_value':K.binary_json_dumps(value),'statistic_reference':statistic_reference,'series_key':series_key,
        'population_version_reference':population_reference,'observed_population_version_reference':observed_population_reference,
        'loss':'FROBENIUS_RADIAL_HUBER','center':0,'weights':list(WEIGHTS),'normalization_denominator':9,'target_weight':1,'huber_delta':1,
        'one_physical_target':True,'data_and_component_masks_preserved':True,'other_ready_targets_not_blocked_by_missing_scale':True,
        'loss_state':'LOSS_DISABLED_PHYSICAL_POLICY_UNBOUND' if usable else status,
        'physical_policy_signed_for_this_target_condition_source':False,
        'actual_training_loss_enabled':False,'external_actual_C0_Root_seal_and_Model_ACK_pending':True}

def mean_F_report(raw_F_moment,recipe):
    # E[||Q||] and ||E[Q]|| are different. Only an actual raw scalar-F stream
    # may fill the user's numerator; component/winsor means are never aliases.
    mean=raw_F_moment.get('mean_vector')
    raw=None if not raw_F_moment.get('n') or mean is None else mean[0]
    scale=recipe['candidate_scale']
    return {'raw_complete6_TRAIN_F_mean':raw,'raw_F_n':raw_F_moment.get('n',0),
        'mean_F_over_bound_s':None if raw is None or scale is None else raw/scale,
        'status':'DEFINED_RAW_MEAN_F_OVER_BOUND_SCALE' if raw is not None and scale is not None else
            ('RAW_MEAN_F_REPORT_PENDING' if raw is None else 'RAW_MEAN_F_DEFINED_SCALE_UNBOUND_OR_INVALID'),
        'large_raw_mean_F_over_s_gt_10':bool(raw is not None and scale is not None and raw/scale>10),
        'large_mean_action':'REPORT_NEXT_VERSION_ISOTROPIC_CENTERING_EVALUATION_ONLY_NO_CURRENT_CHANGE',
        'winsorized_mean_used_as_raw_mean':False,'norm_of_component_mean_used_as_mean_F':False}

policy=C.user_policy

def audit(plan,cfg,groups,geometry,population_reference,numeric,root):
    """One additional selected compact pass, zero extra raw-source scans."""
    import pyarrow as pa,pyarrow.parquet as pq,sqlite3
    policy(plan['user_D1_design_policy_reference'],plan['user_D1_decision_reference']);fields=I.load_data(plan['field_map_reference'],2<<20)
    catalog,all_physical=B.inventory({'fields':fields,'plan':{'element_basis':plan['element_basis']}})
    physical=[p for p in all_physical if any(f['registry_id']==674 and f['field_id']in p['field_ids'] for f in fields)]
    C.need(len(catalog)<65536,'ORIGINAL_RHO_UINT16_SERIES_CATALOG_BOUND')
    rho_catalog=[r for r in catalog if r['view'] in ('raw','TRAIN_element_reference_residual','norm','frobenius_norm','atom_vector_norm')]
    series_ids={r['key']:r['field_id'] for r in rho_catalog}
    schema=pa.schema([('field_id',pa.uint16()),('value',pa.float64()),('heavy_atoms',pa.uint16()),('n',pa.uint64())])
    buffers=[];histograms=[];histroot=root/'rho_histograms';histroot.mkdir();sequence=0
    def flush():
        nonlocal sequence
        if not buffers:return
        aggregated=collections.Counter(buffers);sequence+=1
        ref=I.write_parquet(histroot/('part_%06d.parquet'%sequence),
            ({'field_id':fid,'value':value,'heavy_atoms':heavy,'n':n} for (fid,value,heavy),n in sorted(aggregated.items())),schema)
        histograms.append(ref);buffers.clear()
    C.need(all(p['components']==list(COMPONENTS) for p in physical),'ORIGINAL_R674_COMPLETE_SIX_SOURCE_COMPONENT_ORDER')
    bykey={p['key']:p for p in physical};states=collections.defaultdict(list);counts=collections.defaultdict(collections.Counter);bias={k:collections.defaultdict(collections.Counter) for k in bykey}
    role_counts={key:collections.defaultdict(collections.Counter) for key in bykey}
    structure_status={key:collections.Counter() for key in bykey};structure_unknown=collections.Counter()
    features={r['molecule_id']:r for r in pq.read_table(I.require(geometry['bias_features_reference'])).to_pylist()}
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import sqlite_ro,identity
    binding_path=I.require(geometry['cell_binding_reference']);binding_frame=identity(binding_path);bindings=sqlite_ro(binding_path)
    try:
        for group in groups:
            moments={k:B.JointMoments(1) for k in bykey}
            for owner,numbers,entries,row,source in R.records(cfg,group,fields):
                fit=owner['new_role']=='TRAIN' and owner['fit_eligible'];byid={e['field_id']:e for e in entries};values={}
                if fit:
                    values,_=B.views(entries,numbers,all_physical,numeric['models']);heavy=sum(z>1 for z in numbers)
                    C.need(0<=heavy<65536,'ORIGINAL_RHO_HEAVY_COUNT_TYPE')
                    for key,actual_values in values.items():
                        if key not in series_ids:continue
                        for value in actual_values:buffers.append((series_ids[key],float(value),heavy))
                        if len(buffers)>=65536:flush()
                for key,p in bykey.items():
                    if not set(p['field_ids'])<=set(byid):continue
                    selected=[byid[fid] for fid in p['field_ids']];complete=all(len(e['values_float64'])==1 and e['value_mask']==[True] for e in selected)
                    bound=bindings.execute('SELECT geometry_sha,unknown,source,physical_row FROM bindings WHERE rid=? AND task=?',(owner['record_id'],selected[0]['field']['task'])).fetchone()
                    same_geometry=bound is not None and bound[1]==0
                    if bound is not None:
                        C.need(__import__('json').loads(bound[2])==C.reference(source) and bound[3]==row['physical_row'],
                            'R674_TYPED_VALUES_AND_DOUBLE_HASH_GEOMETRY_FROM_EXACT_SAME_SOURCE_CELL_NOT_ONLY_RECORD_TASK')
                    C.need(not complete or same_geometry,'R674_COMPLETE6_ACTUAL_GEOMETRY_UNBOUND_IS_SOURCE_HOLD_NOT_SCALE_FALLBACK')
                    scope=role_counts[key][owner['new_role']];scope['applicable_records']+=1;scope['complete6']+=complete
                    scope['incomplete6']+=not complete;scope['complete6_same_actual_geometry']+=complete and same_geometry
                    scope['fit_eligible_after_D5_anti_join']+=fit
                    if not fit:continue
                    counts[key]['records']+=1;counts[key]['complete6']+=complete;counts[key]['complete6_same_actual_geometry']+=complete and same_geometry
                    if complete:
                        F=values[key+'/frobenius_norm'];C.need(len(F)==1,'ONE_ORIGINAL_RAW_FROBENIUS_SCALAR_PER_COMPLETE6')
                        moments[key].add([[F[0]]])
                    feature=features[owner['molecule_id']];labels=['Z='+str(z) for z in feature['elements_atomic_numbers']]
                    structure_status[key][str(feature['scaffold_status'])]+=1;structure_unknown[key]+=feature['generic_scaffold']is None
                    labels += [name+'='+str(feature[name]) for name in ('heavy_atoms','rotatable_bonds','rings','generic_scaffold')]
                    for label in labels:bias[key][label]['records']+=1;bias[key][label]['excluded_incomplete6']+=not complete
            for key in bykey:states[key].append(moments[key].state())
        flush()
    finally:
        bindings.close();C.need(identity(binding_path)==binding_frame,'ACTUAL_INPUT_GEOMETRY_BINDING_DATABASE_FRAME_UNCHANGED')
    # The original weighted-rank implementation receives the original view
    # values. This is descriptive per-series rho, not a new non-scalar target
    # aggregation or a final size-dependent training-policy decision.
    import duckdb
    from .originals import objects
    _,reducer,_,_,_=objects();db=duckdb.connect();db.execute('SET threads=1');rho={}
    try:
        for row in rho_catalog:
            C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_RHO_PENDING')
            rho[row['key']]=reducer.rho_external(db,[r['path'] for r in histograms],row['field_id'])
    finally:db.close()
    rho_ref=I.save(root/'original_series_weighted_size_rho.json',{'schema':'PROVISIONAL_TRAIN_ORIGINAL_SERIES_SIZE_RHO_V1',
        'catalog':rho_catalog,'series':rho,'histogram_references':histograms,'fit_population_reference':population_reference,
        'original_function':'streaming_v1.reduce.rho_external','threshold_abs_rho':.95,'undefined_kept_explicit':True,
        'final_target_size_classification_or_normalizer_released':False})
    rows=[];series={r['key']:r for r in numeric['winsorized_component_and_invariant_audit']['series']}
    for key in sorted(bykey):
        scale_series=key+'/frobenius_norm';observed=series.get(scale_series);value=None if observed is None else observed['std_ddof0']
        recipe=scale_recipe(value,population_reference=population_reference,statistic_reference=plan['resolved_numeric_reference'],
            series_key=scale_series,observed_population_reference=population_reference if observed is not None else None)
        raw=B.combine_joint(states[key]);n=counts[key]['records'];bad=n-counts[key]['complete6']
        rows.append({'physical_group':key,'counts':dict(counts[key]),'excluded_incomplete6_fraction':None if not n else bad/n,
            'fit_count_scope':'PROVISIONAL_COMPLETE_OLD_SPRIME_EFFECTIVE_TRAIN_ANTI_ACTUAL_D5_HELDOUT_BASE_AND_CHILDREN',
            'actual_applicable_scope_by_original_role':{role:dict(c,retained_fraction=None if not c['applicable_records'] else c['complete6_same_actual_geometry']/c['applicable_records'],
                excluded_fraction=None if not c['applicable_records'] else c['incomplete6']/c['applicable_records']) for role,c in role_counts[key].items()},
            'exclusion_over_10_percent':bool(n and bad/n>.1),'exclusion_over_20_percent':bool(n and bad/n>.2),
            'structure_status_counts':dict(structure_status[key]),'structure_UNKNOWN_records':structure_unknown[key],
            'structure_known_fraction':None if not n else (n-structure_unknown[key])/n,
            'raw_mean_F_report':mean_F_report(raw,recipe),'raw_F_moment':raw,
            'winsorized_F_mean_separate':None if observed is None else observed['mean'],
            'raw_component_mean_vector_separate':numeric['winsorized_component_and_invariant_audit']['raw_complete_physical_joint_audit'].get(key),
            'element_and_structure_bias':{label:dict(count,excluded_fraction=None if not count['records']else count['excluded_incomplete6']/count['records']) for label,count in sorted(bias[key].items())},
            'loss_recipe_candidate':recipe,'new_data_mask_from_loss_ineligibility':False})
    return I.save(root/'r674_loss_eligibility_and_raw_mean_F.json',{'schema':'PROVISIONAL_R674_USER_POLICY_LOSS_ELIGIBILITY_V1',
        'user_decision_reference':plan['user_D1_decision_reference'],'user_design_policy_reference':plan['user_D1_design_policy_reference'],
        'population_version_reference':population_reference,'groups':rows,'original_series_size_rho_reference':rho_ref,
        'raw_F_is_per_sample_norm_not_norm_of_mean_or_winsor_mean':True,'source_and_original_masks_unchanged':True,'full_training_release':False})
