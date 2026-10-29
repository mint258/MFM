"""Explicit model-side D6 consumption contract; never defines a data release schema."""
from __future__ import annotations

from .v3_contract import canonical_hash, require
from .v3_decision_evidence import bound_bytes, digest

MODE = 'authoritative_full_train'
SCOPE = 'full_convergence'
SCHEMA = 'model_v3_full_TRAIN_consumption_v1'
FULL_MILESTONES = (1_000_000, 2_000_000, 4_000_000, 8_000_000,
                   16_000_000, 32_000_000, 64_000_000)


def validate_full_contract(configuration, *, verify_release=True):
    """A reviewed adapter verifies the opaque owner release, not a FULL role string.

    This projection is a MODEL consumer API. It does not certify unknown D6
    manifests or invent the data owner's physical release/label schema.
    """
    require(configuration.get('engineering_only') is False
            and configuration.get('experiment_scope') == 'FULL_TRAIN_CONVERGENCE_PROPOSAL',
            'Full TRAIN convergence is an explicit scientific scope, never synthetic acceptance')
    c = configuration.get('full_train_contract')
    require(type(c) is dict and set(c) == {'schema', 'role', 'population_scope', 'molecule_count',
            'membership_sha256', 'release_evidence', 'geometry_source', 'conformations'},
            'Complete versioned full TRAIN consumer projection required')
    require(c['schema'] == SCHEMA and c['role'] == 'TRAIN'
            and c['population_scope'] == 'entire_frozen_v1_TRAIN'
            and type(c['molecule_count']) is int and c['molecule_count'] > 0,
            'Full data means the entire frozen TRAIN population, never a source FULL role or prefix')
    digest(c['membership_sha256'])
    require(c['geometry_source'] == 'PM7' and c['conformations'] == 'all_authorized',
            'D6 convergence uses PM7 and all authorized conformations')
    release = c['release_evidence']
    require(type(release) is dict and {'path','sha256'} <= set(release), 'Actual frozen D6 release evidence required')
    digest(release['sha256'])
    if verify_release:
        bound_bytes(release)  # Metadata evidence only; never native targets.
    p = configuration['proxy_contract']
    require(type(p['sample_budget']) is int and p['sample_budget'] == FULL_MILESTONES[-1]
            and all(type(x) is int for x in p['milestones'])
            and set(FULL_MILESTONES) <= set(p['milestones'])
            and set(FULL_MILESTONES) <= set(p['sample_plan']['panel_samples'])
            and set(FULL_MILESTONES) <= set(p['sample_plan']['validation_samples']),
            'Full convergence needs the 64M cap and all seven actual-draw panel/validation milestones')
    require(p['sampler']['geometry_source'] == 'PM7'
            and p['sampler']['selection'] == {'mode':'all','k':None},
            'Full convergence cannot silently select a conformer subset')
    require(p['groups'] in (['S'], ['P']), 'Full convergence compares separate S and P curves')
    require('long_run_policy' in configuration,
            'Full convergence needs an explicit finite durable-storage policy and fresh Root reservation')
    validate_full_resources(configuration)
    return c


def verify_full_inputs(inputs, configuration):
    c = validate_full_contract(configuration)
    require(inputs.index.role == 'TRAIN' and len(inputs.index) == c['molecule_count']
            and inputs.index.content_sha256 == c['membership_sha256'],
            'Actual entire TRAIN membership/count differs from D6 projection')
    require(inputs.full_train_contract == c
            and inputs.authority_receipt.get('full_TRAIN_consumption_contract_sha256') == canonical_hash(c),
            'Reviewed final-D6 adapter did not bind this full population projection')
    validate_full_resources(configuration)
    return c


def validate_full_resources(configuration):
    """Finite common profile bound plus existing fresh per-segment quota admission.

    Reservation/lease refs remain in request.storage, outside recipe identity.
    This preflight never reserves, expands caps, deletes or resets history.
    """
    r=configuration.get('full_resource_contract')
    require(type(r) is dict and set(r) == {'schema','profile_evidence','checkpoint_upper_bytes',
        'retained_checkpoint_limit','atomic_inflight_checkpoints','noncheckpoint_upper_bytes','durable_upper_bytes'},
        'Independent finite full-D6 resource/storage declaration required')
    require(r['schema'] == 'model_v3_full_TRAIN_resource_declaration_v1','Unknown full-data storage declaration')
    for key in ('checkpoint_upper_bytes','retained_checkpoint_limit','atomic_inflight_checkpoints',
                'noncheckpoint_upper_bytes','durable_upper_bytes'):
        require(type(r[key]) is int and r[key] > 0,'Positive finite explicit full-data capacity required: '+key)
    bound_bytes(r['profile_evidence'])
    plan=configuration['proxy_contract']['sample_plan']
    # Count all recovery/final/milestone/failed-attempt checkpoints under one cap.
    require(r['retained_checkpoint_limit'] == plan['max_total_checkpoints']
        and r['retained_checkpoint_limit'] >= len(FULL_MILESTONES), 'Retained global checkpoint cap differs')
    required=r['checkpoint_upper_bytes']*(r['retained_checkpoint_limit']+r['atomic_inflight_checkpoints'])+r['noncheckpoint_upper_bytes']
    require(r['durable_upper_bytes'] >= required,'Insufficient full-data durable budget for retained/atomic checkpoints and all other output')
    # Actual measured profile, source/config compatibility and fresh quota are
    # additionally revalidated by the unchanged v3_long_run_storage path.
    return required
