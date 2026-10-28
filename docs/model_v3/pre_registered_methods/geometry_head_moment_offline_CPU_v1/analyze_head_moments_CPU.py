#!/usr/bin/env python3
"""One saved synthetic two-head local accounting; zero model/head/encoder instances."""
from __future__ import annotations
import argparse,csv,hashlib,io,json,multiprocessing,os,socket,traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import safe_saved_inputs as S

HERE=Path(__file__).absolute().parent
TRANSFORMS=S.TRANSFORMS
CASE_IDS=S.CASE_IDS
PARAM_NAMES=('0.weight','0.bias','2.weight','2.bias')
FIELDS=('p_dipole','p_dipole_magnitude')
CLOSURE=1e-10


def record(kind,port,unit,transform,terms,batch,physical=None):
    np=S.NP
    descriptions={key:S.stats(value) for key,value in terms.items()}
    chosen=tuple(descriptions['D']['argmax'])
    graph=int(batch[chosen[0]]) if kind!='terminal' else chosen[0]
    anchor=dict(row=int(chosen[0]),component=int(chosen[1]),native_graph=graph,
                native_atoms=(3,9,32)[graph],
                signed_terms={key:float(value[chosen]) for key,value in terms.items()})
    for key,description in descriptions.items():
        point=tuple(description['argmax'])
        description['same_component_signed_tuple']={name:float(value[point]) for name,value in terms.items()}
    result=dict(kind=kind,port=port,unit=unit,population='all_clean44' if kind!='terminal' else 'all_three_native_graphs',
                transform=transform,statistics=descriptions,at_D_argmax=anchor)
    if physical is not None:
        point=(physical['argmax']['row'],physical['argmax']['component'])
        result['at_saved_physical_argmax']=dict(row=point[0],component=point[1],
            signed_terms={name:float(value[point]) for name,value in terms.items()},
            saved_maxabs=physical['maxabs'],saved_passed=physical['passed'])
        calculated=descriptions['D']['maxabs']
        S.need(abs(calculated-physical['maxabs'])<=CLOSURE
               and (calculated<=1e-5) is bool(physical['passed']),
               'Captured terminal scalar/physical predicate replay differs')
    return result


def case_worker(task):
    records=[];decodes=0;replays=[];closure_max=0.;reference_calls=0
    try:
        np,torch=S.runtime()
        import moment_reference as M
        if not hasattr(S,'INLINE_CONTROLS'):S.INLINE_CONTROLS=M.inline_controls()
        row,spec=task['row'],task['spec'];case=S.bound(row['case_json'])
        measured,holder,construction=case['original_measurement'],case['passive_capture'],case['construction']
        identity=row['case_id']
        S.need(case['schema']=='model_v3_geometry_head_moment_passive_case_v1'
             and case['case_id']==measured['case_id']==identity and measured['case']==spec
             and case['error'] is None and case['scientific_adoption'] is False
             and case['no_local_module_replays'] is True and case['no_F64_model_or_local_reference_calls'] is True
             and measured['complete_terminal_count']==13 and measured['domain']['domain_pass'] is True
             and measured['fixture_native_atoms']==[3,9,32],
             'Actual complete case/fixture scope differs')
        S.need(construction['original_parameter_sha256']==construction['actual_parameter_sha256']
               ==measured['weight_summary']['all_named_parameter_sha256']
               and construction['geometry_mode']=='residual_expansion_fp32_v1'
               and construction['attention_projection_mode']=='blocked_k64_compensated_fp32_v1'
               and construction['attention_aggregation_mode']=='centered_fp32_v1'
               and construction['FP64_core_or_encoder'] is False,'Original parameter/mode controls differ')
        S.need(holder['state_unchanged'] is True and holder['state_before']==holder['state_after']
             and holder['synthetic_weight_seed']==spec['weight_seed'] and holder['errors']==[]
             and holder['forward_calls']==holder['full_forward_returns']==holder['observed_encoder_returns']==4
             and [c['role'] for c in holder['calls']]==[0,1,2,3],'Four successful passive roles/state required')
        control=case['terminal_control']
        S.need(control['passed'] is True and len(control['arrays'])==52
             and all(v['bitwise_equal'] is True for v in control['arrays'])
             and control['baseline_passed']==control['fresh_passed']==measured['passed'],
             'Actual all52 external4579 terminal bitwise/pass controls required')
        roles=[]
        for call in holder['calls']:
            loaded=S.load_role(call,call['artifact']['file'],Path(row['case_json']['path']).parent)
            roles.append(loaded);decodes+=1
        base=roles[0][0];base_meta=roles[0][1]['head_ports']
        for a,pop,_,_ in roles:
            S.need(pop['head_ports']['parameter_bindings']==base_meta['parameter_bindings'],
                   'All roles must bind the same actual role0 synthetic parameters')
        for a,_,_,_ in roles:
            for field in FIELDS:replays.append(M.local_replay(a,field))
        W={field:M.weights(base,field) for field in FIELDS}
        Qrefs={}
        for field in FIELDS:
            Qrefs[field]=[]
            for a,_,_,_ in roles:
                Qrefs[field].append(M.readout(a['head__H0'],W[field]));reference_calls+=1
        S.need([m['transform']['name'] for m in measured['measurements']]==list(TRANSFORMS),
               'Exact three original transforms required')
        for index,(moved,pop,_,_) in enumerate(roles[1:]):
            document=measured['measurements'][index]['transform']
            S.need(document['row_vector_rule']=='x @ R + t','Original row-vector convention required')
            R=torch.tensor(document['rotation_float64'],dtype=torch.float64)
            t=torch.tensor(document['translation_A'],dtype=torch.float64)
            S.need(R.shape==(3,3) and t.shape==(3,) and bool(torch.isfinite(R).all()) and bool(torch.isfinite(t).all()),
                   'Exact finite original transform required')
            # Same original standalone CPU push/cast control, no new coordinates enter any model.
            for key in S.BASE_KEYS-{'pos'}:
                S.need(base[key].tobytes()==moved[key].tobytes(),'Original discrete/native view mapping changed')
            full_pushed=(torch.from_numpy(base['pos']).double()@R+t).float().numpy()
            S.need(full_pushed.tobytes()==moved['pos'].tobytes(),
                   'Actual full88/132 position float32 cast provenance differs')
            pushed=torch.from_numpy(base['head__pos']).double()@R+t
            S.need(pushed.float().numpy().tobytes()==moved['head__pos'].tobytes(),
                   'Actual clean44 position cast provenance differs')
            coordinate={'D':moved['head__pos'].astype(np.float64)-pushed.numpy()}
            records.append(record('coordinate','actual_input_cast','Angstrom',document['name'],
                                  coordinate,base['head__batch']))
            original_fields={f['field']:f for f in measured['measurements'][index]['fields']}
            S.need(len(original_fields)==13 and all(f['absolute_tolerance']==1e-5 and f['relative_tolerance']==0
                   for f in original_fields.values()),'Original13-field absolute1e-5/rtol0 unchanged')
            for field in FIELDS:
                terms,qterms,error=M.terminal_terms(base,moved,field,R,(Qrefs[field][0],Qrefs[field][index+1]))
                closure_max=max(closure_max,error)
                records.append(record('terminal','PD/'+field,'synthetic_charge*Angstrom',document['name'],
                    terms,base['head__batch'],original_fields['PD/'+field]))
                records.append(record('charge',field+'/charges','synthetic_charge',document['name'],
                    qterms,base['head__batch']))
        return dict(case_id=identity,case=spec,error=None,records=records,array_decodes=decodes,
            exact_CPU_local_replays=replays,
            local_replay_ports_exact=all(v['all_actual_CPU_local_ports_bitwise_equal'] for v in replays),closure_max=closure_max,
            controls=S.INLINE_CONTROLS,small_MLP_reference_calls=reference_calls,
            new_model_head_encoder_instances=0,new_model_head_encoder_forwards=0)
    except Exception as exc:
        return dict(case_id=task['row']['case_id'],case=task['spec'],
            error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()),
            records=records,array_decodes=decodes,exact_CPU_local_replays=replays,local_replay_ports_exact=False,
            no_partial_case_attribution=True,small_MLP_reference_calls=reference_calls)


def raw_parent(value,job):
    S.need(type(job) is str and job.isdigit() and value['argv']==['sacct','-X','-n','-P','-j',job,
        '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
        and type(value['returncode']) is int and value['returncode']==0 and value['stderr']=='',
        'Actual owned parent raw accounting command required')
    rows=[r.split('|') for r in value['stdout'].splitlines() if r.strip()]
    S.need(len(rows)==1 and len(rows[0])==7 and rows[0][:4]==[job,'zixiao','COMPLETED','0:0']
           and rows[0][4].isdigit() and int(rows[0][4])>0 and rows[0][5:] == ['16','compute-0-21'],
           'Actual GPU trace parent must be completed0:0 with16CPU/node21')


def selected_cap(leaf):
    return S.ROLE_CAP if leaf['path'].endswith('.npz') else (16<<20 if leaf['path'].endswith('.xml') else S.META_CAP)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--inputs-sha256',required=True)
    parser.add_argument('--source-pins-sha256',required=True);parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--expected-node',choices=['compute-0-'+str(i) for i in (2,*range(8,20))],required=True)
    args=parser.parse_args()
    S.need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID','').isdigit()
           and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==16
           and os.environ.get('CUDA_VISIBLE_DEVICES')==''
           and socket.gethostname().split('.')[0]==args.expected_node,'Actual owned16CPU CPU-only allocation required')
    pinsref,inputsref=S.rawref(HERE/'source_pins.json'),S.rawref(args.inputs)
    S.need(pinsref['sha256']==args.source_pins_sha256 and inputsref['sha256']==args.inputs_sha256,
           'Exact Root-bound CPU source/actual inputs required')
    pins,inputs=S.bound(pinsref),S.bound(inputsref)
    S.need(pins['schema']=='model_v3_geometry_head_moment_CPU_source_v1'
           and pins['status']=='ROOT_BOUND_ACTUAL_GPU_INPUTS_NO_CPU_EXECUTION' and pins['inputs']==inputsref
           and inputs['schema']=='model_v3_geometry_head_moment_CPU_inputs_v1'
           and inputs['status']=='ACTUAL_C0_GPU_CAPTURE_BOUND_FOR_CPU_DIAGNOSTIC'
           and inputs['input_cap_bytes']==512<<20 and inputs['output_cap_bytes']==128<<20
           and inputs['diagnostic_closure_absolute_bound']==CLOSURE,'Fixed narrow saved-input diagnostic required')
    dependencies=S.bound(inputs['dependencies'])
    # Actual4595 certificate now exists; this is its read schema, not an invented future projection.
    closure=S.bound(inputs['GPU_Root_closure'])
    result,complete=S.bound(inputs['GPU_result']),S.bound(inputs['GPU_complete'])
    supervisor=S.bound(inputs['GPU_supervisor']);accounting=closure['actual_sacct']
    job=result['job_id'];raw_parent(accounting,job)
    S.need(closure['schema']=='model_v3_Root_geometry_head_moment_passive_GPU_closure_v1'
           and closure['status']=='ACTUAL_C0_FULL48_HEAD_MOMENT_PASSIVE_TRACE_ALL2496_TERMINALS_BITWISE_EQUAL_SOURCE_RESOURCE_CLOSED'
           and closure['job_id']==job=='4524595' and closure['result']==inputs['GPU_result']
           and closure['supervisor']==inputs['GPU_supervisor']
           and closure['sources_before']==inputs['GPU_sources_before']
           and closure['sources_after']==inputs['GPU_sources_after']
           and closure['baseline_negative_Root_closure']==inputs['baseline4579_Root_closure']
           and closure['FP32_full_forwards']==192 and closure['FP64_model_or_local_replays']==0
           and closure['stage_observations']==1728 and closure['geometry_observations']==512
           and closure['projection_port_observations']==2304 and closure['terminal_bitwise_controls']==2496
           and closure['head_observations']==384 and closure['magnitude_norm_observations']==192
           and closure['parameter_subset_bytes']==12632448
           and closure['contains_seeded_synthetic_qMLP_weights'] is True
           and closure['physical_passed']==15 and closure['physical_failed']==33
           and closure['whole_private_original_limits_unchanged'] is True
           and closure['all_NVML_used_memory_known'] is True
           and closure['scientific_adoption'] is False and closure['formal_physics_gate_satisfied'] is False,
           'Actual owned4595 full transparent capture/source/resource certificate required')
    S.need(complete==dict(result=inputs['GPU_result'])
           and supervisor['job_id']==job and supervisor['status']=='COMPLETED'
           and supervisor['exit_code']==0 and supervisor['first_failure'] is None
           and supervisor['remaining_recorded_processes_before_retirement']==[]
           and supervisor['private_storage_cleanup_errors']==[],
           'Actual committed complete-result/clean original GPU supervision required')
    S.need(result['schema']=='model_v3_geometry_head_moment_passive_result_v1'
           and result['status']=='PASSIVE_TRACE_COMPLETE_PENDING_ACTUAL_OUTER_C0'
           and result['failures']==[] and result['ordinary_original_FP32_encoder_forwards']==192
           and result['original_full_model_returns']==192 and result['node_stage_observations']==1728
           and result['geometry_observations']==512 and result['actual_geometry_helper_calls']==512
           and result['actual_projection_helper_calls']==2304 and result['head_observations']==384
           and result['magnitude_norm_observations']==192 and result['full_FP64_encoder_forwards']==0
           and result['local_module_replays']==0 and result['source_before_after_equal'] is True
           and result['physical_passed']==15 and result['physical_failed']==33
           and result['baseline_terminal_job']=='4524579' and result['contains_parameter_weights'] is True
           and result['parameter_subset_bytes']==48*263176,
           'Actual complete passive4579 bit-comparable GPU capture required, not a pending/source-only record')
    negative=S.bound(inputs['baseline4579_Root_closure'])
    S.need(negative['schema']=='model_v3_Root_complete48_geometry_FP32_scientific_failure_closure_v1'
           and negative['job_id']=='4524579' and negative['formal_FP32_gate_satisfied'] is False
           and negative['all_sources_before_after_current_equal'] is True
           and negative['private_cleanup_and_recorded_processes_closed'] is True
           and negative['counts']==dict(tests=48,failures=33,errors=0,skipped=0),
           'Original complete geometry scientific failure must remain15/33')
    before,after=S.bound(inputs['GPU_sources_before']),S.bound(inputs['GPU_sources_after'])
    S.need(before==after and inputs['GPU_sources_before']['sha256']==inputs['GPU_sources_after']['sha256'],
           'Actual GPU source snapshots differ')
    source_refs=[]
    for path,value in before.items():
        S.need(type(value) is dict and set(value)=={'path','bytes','sha256'} and path==value['path'],
               'Complete original actual GPU source rawref map required')
        source_refs.append(value)
    frozen=S.bound(inputs['GPU_source_freeze'])
    S.need(frozen['schema']=='model_v3_geometry_head_moment_passive_source_freeze_v1'
           and frozen['authored_count']==10 and len(frozen['files'])==10
           and all(before.get(x['path'])==x for x in frozen['files']),
           'Exact frozen ten-leaf capture implementation must be in the actual before/after map')
    S.need([r['case_id'] for r in result['cases']]==list(CASE_IDS),'Exact canonical full48 required')
    required=('dependencies','GPU_Root_closure','GPU_result','GPU_complete','GPU_supervisor',
              'GPU_sources_before','GPU_sources_after','GPU_source_freeze',
              'baseline4579_Root_closure')
    leaves=[pinsref,inputsref]+pins['files']+dependencies['files']+inputs['metadata_refs']+source_refs
    leaves.extend(inputs[key] for key in required)
    # Parse bounded case metadata before any numerical import/decode, so all true role refs enter the512MiB total.
    S.need([r['case_id'] for r in closure['cases']]==list(CASE_IDS),'Actual Root full48 membership differs')
    tasks=[]
    for authority,row,spec in zip(closure['cases'],result['cases'],S.SPEC_TUPLES):
        case=S.bound(row['case_json']);holder=case['passive_capture'];control=case['terminal_control']
        S.need(authority['case_json']==row['case_json']
               and authority['role_archives']==[c['artifact']['file'] for c in holder['calls']],
               'Actual Root closed48case/192role raw references differ')
        S.need(row['transparency_passed'] is True and row['captured_roles']==4
               and row['forward_calls']==row['observed_encoder_returns']==4
               and row['head_observations']==8 and row['magnitude_norm_observations']==4
               and row['parameter_subset_bytes']==263176 and len(holder['calls'])==4
               and control['passed'] is True and len(control['arrays'])==52
               and all(c['bitwise_equal'] is True for c in control['arrays']),
               'All48/192 original forwards and2496 external4579 controls required')
        leaves.append(row['case_json'])
        leaves.extend(call['artifact']['file'] for call in holder['calls'])
        tasks.append(dict(row=row,spec=dict(zip(('distance_bias','views','head_policy','weight_seed'),spec))))
    selected,total=S.stat_inputs(leaves)  # Counts source,control,sourcefreeze,XML and payload exactly once by physical inode.
    for leaf in selected.values():
        if not leaf['path'].endswith('.npz'):
            S.need(S.rawref(leaf['path'],selected_cap(leaf))==leaf,'Source/control drift before numerical runtime')
    S.need(not args.output_root.exists() and not args.output_root.is_symlink(),'Fresh bounded child output required')
    args.output_root.mkdir();output=S.Outputs(args.output_root)
    # No Torch/NumPy/project numerical runtime imported in parent before fork.
    with ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('fork')) as pool:
        cases=list(pool.map(case_worker,tasks))
    errors=[dict(case_id=c['case_id'],error=c['error']) for c in cases if c['error'] is not None]
    decodes=sum(c['array_decodes'] for c in cases);records=sum(len(c['records']) for c in cases)
    reference_count=sum(c['small_MLP_reference_calls'] for c in cases)
    failed_dipole_observations=sum(r['at_saved_physical_argmax']['saved_passed'] is False
        for c in cases for r in c['records'] if r['kind']=='terminal')
    algebra_complete=not errors and len(cases)==48 and decodes==192 and records==720 and reference_count==384 and failed_dipole_observations==51
    replay_holds=[dict(case_id=c['case_id'],field=v['field'],controls=v['controls'])
                  for c in cases for v in c['exact_CPU_local_replays'] if not v['all_actual_CPU_local_ports_bitwise_equal']]
    complete_ok=algebra_complete and not replay_holds
    refs=[output.json('case_%02d.json'%i,c) for i,c in enumerate(cases)]
    groups=S.aggregate(cases)
    stream=io.StringIO(newline='');columns=('case_id','kind','port','unit','population','transform','record_json')
    writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
    for case in cases:
        for row in case['records']:
            writer.writerow(dict(case_id=case['case_id'],**{k:row[k] for k in columns[1:6]},
                                 record_json=json.dumps(row,sort_keys=True)))
    csvref=output.write('all_same_component_records.csv',stream.getvalue().encode())
    after_errors=[]
    for leaf in selected.values():
        try:S.need(S.rawref(leaf['path'],selected_cap(leaf))==leaf,'Selected input changed during CPU analysis')
        except Exception as exc:after_errors.append(dict(path=leaf['path'],type=type(exc).__name__,message=str(exc)))
    complete_ok=complete_ok and not after_errors
    summary=dict(schema='model_v3_geometry_head_moment_CPU_result_v1',
        status='COMPLETE_PENDING_ACTUAL_CPU_OUTER_C0' if complete_ok else 'HOLD_NO_ATTRIBUTION',
        job_id=os.environ['SLURM_JOB_ID'],node=socket.gethostname(),GPU_source_job=job,
        GPU_Root_closure=inputs['GPU_Root_closure'],GPU_Root_closure_scope='Actual4595 read certificate schema plus producer/complete/supervisor/rawC0/source/all48 controls verified; no future certificate guessed',
        source_pins=pinsref,inputs=inputsref,cases=refs,errors=errors,input_after_errors=after_errors,
        all_selected_sources_and_payloads_after_match=not after_errors,
        selected_unique_input_bytes=total,input_cap_bytes=512<<20,output_cap_bytes=128<<20,
        decoded_role_archives=decodes,records=records,small_MLP_reference_calls=reference_count,aggregate_groups=groups,CSV=csvref,figures=[],
        all48_saved_operand_algebra_complete=algebra_complete,CPU_GPU_local_replay_holds=replay_holds,
        algebra_scope_if_replay_HOLD='Retained same-component accounting of saved GPU operands, not CPU/GPU arithmetic attribution',
        groups_admissible_for_local_diagnostic_only=complete_ok,
        groups_saved_GPU_operand_algebra_valid=algebra_complete and not after_errors,
        groups_CPU_GPU_arithmetic_replay_valid=complete_ok,
        fixed_head_observations=288,charge_comparisons=288,coordinate_cast_comparisons=144,
        exact_CPU_local_head_paths_replayed=sum(len(c['exact_CPU_local_replays']) for c in cases),
        closure_absolute_bound=CLOSURE,physical_absolute_tolerance_unchanged=1e-5,
        weighted_RMS='sqrt(sum component sumsq / sum component count), units/populations/cohorts kept separate',
        reference_scope='Small actual-state affine/SiLU/affine and local moment real-formula CPU64, including algorithm/backend contrast',
        contains_seeded_synthetic_parameter_input=True,raw_parameter_values_exported=False,
        new_full_model_head_encoder_instances=0,new_full_model_head_encoder_forwards=0,
        historical_H64_quantization_or_whole_F64_head_experiments=0,
        baseline4579_physical_counts=dict(passed=15,failed=33),
        diagnosed_original_dipole_failures=failed_dipole_observations,baseline_expected_dipole_failures=51,
        other_five_extensive_failures_explained=False,
        original_centered21_27_and_all_failures_unchanged=True,
        no_universal_precision_floor_or_necessary_API_dtype_change=True,
        no_whole_model_causal_ranking=True,scientific_adoption=False,output_bytes_before_summary=output.total)
    final=output.json('RESULT.json',summary)
    if complete_ok:output.json('COMPLETE.json',dict(result=final))
    print(json.dumps(dict(status=summary['status'],cases=len(cases),decoded=decodes,records=records,
                         errors=len(errors),selected_bytes=total,output_bytes=output.total),sort_keys=True))
    return 0 if complete_ok else 1


if __name__=='__main__':raise SystemExit(main())
