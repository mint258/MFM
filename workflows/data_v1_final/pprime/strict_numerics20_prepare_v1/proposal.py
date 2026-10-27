"""Concrete NEW20 proposal arithmetic, no scientific bodies or approvals."""
from . import contract as C

def proposal():
    q=C.Q
    maximum=C.PREP_CAP+C.EXEC_PARENT_CAP+(C.MAX_CALLS-16)*C.CLOSED_CALL_CAP+16*C.UNRESOLVED_CALL_CAP
    q.need(C.MAX_CALLS==1200 and maximum<C.WHOLE_CAP,'EXACT1200_AND32GIB_MANAGED_ROLE_MATH')
    return {'schema':'PPRIME_NEW20_ALL12_STRICT_NUMERICS_QA_PROPOSAL_V1','status':'PROPOSED_NO_NEW_QM_AUTHORIZATION',
        'new_unique_MIDs':20,'UFF_geometries_per_MID':1,'task_names':list(C.TASKS),'arms':list(C.ARMS),'maximum_new_QM_calls':1200,
        'selection':C.PARAMETERS,'protocol':'reuse frozen strict_numerics15 proposed JSON; only original3 fields differ',
        'parameters_changed_tasks':['pm7_B','xtb_singlepoint','xtb_perturbed_gradient'],'other9_tasks_unchanged':True,
        'P90':'proper coordinate-axis signed permutation; never shuffle atom order','original_four_vector_gates_unchanged':True,
        'other_fields':'original WP5 parser/status/physical gates; unverified basis/tensor/axes remain UNKNOWN',
        'execution_resources_proposed':{'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','maximum_wall_seconds':86400,
            'per_call_timeout_seconds':900,'maximum_native_workers':16,'automatic_retry':False,
            'prepare_cap_bytes':C.PREP_CAP,'execution_cap_bytes':C.EXEC_CAP,'combined_shared_cap_bytes':C.WHOLE_CAP,
            'closed_managed_call_role_cap_bytes':C.CLOSED_CALL_CAP,'unclosed_or_UNKNOWN_private_partition_bytes':C.UNRESOLVED_CALL_CAP,
            'execution_parent_partition_bytes':C.EXEC_PARENT_CAP,'managed_upper_bound_bytes':maximum,
            'managed_bound_requires_verified_closed_roles_or_STOP_at_uncompacted_UNKNOWN':True,
            'frozen_RLIMIT_FSIZE_bytes':134217728,'RLIMIT_FSIZE_is_not_total_scratch_limit':True,
            'scratch_total_observation_separate_and_unimplemented_in_prepare':True,'quota_reserve_bytes':200000000000,
            'expiry_or_resource_pressure':'STOP_NEW_DISPATCH_NATURAL_DRAIN_NO_FORCED_SIGNALS'},
        'source_state':{'read_only_input_prepare_entry_present':True,'prepare_original_protocol_initialize_allowed':True,
            'prepare_candidate_initialize_or_invoke_allowed':False,'execution_entrypoint_present':False,
            'new_exact_USER_AUTHORIZED20_decision_required_before_execution':True},
        'prepared20_reference':None,'user_decision_reference':None,'new_QM_calls_performed':0,'original15FAIL_preserved':True,
        'scientific_PASS':False,'production_or_2000_or_full_release':'HOLD','cause_of_old_direction_effect':'UNKNOWN'}
