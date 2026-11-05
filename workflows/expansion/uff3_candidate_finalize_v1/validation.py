"""Exact saved-packet/family fingerprints; pure stdlib, no scientific recalculation."""
import hashlib
import struct
from ..alpha_runtime_v1.common import need
from ..uff3_candidate_v1 import core as C

D3_NAMES=('PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2','SASA_atom_A2')


def numeric_hash(value):
    """F64 bits, list boundaries and NULL distinguish -0, shape and missingness."""
    h=hashlib.sha256()
    def add(v):
        if v is None:h.update(b'N')
        elif isinstance(v,(list,tuple)):
            h.update(b'L'+struct.pack('<Q',len(v)))
            for x in v:add(x)
        else:h.update(b'D'+struct.pack('<d',float(v)))
    add(value);return h.hexdigest()


def status_hash(row):
    names=('state','actual_conformers','desired_conformers','insufficient_conformers',
           'generation_count_unknown','cache_complete','orders','generation_order','error')
    return C.sha(C.canonical({k:row[k]for k in names}))


def packet(source,cache,p,manifest,events):
    C.validate_cache(cache,source)
    copy=dict(p);digest=copy.pop('packet_content_sha256')
    need(C.sha(C.canonical(copy))==digest,'Closed packet content hash')
    need(p['schema']=='PUBCHEM_UFF3_SELECTED_PACKET_V1'and p['source']==source
        and p['molecule_id']==C.molecule_id(source)and p['recipe_sha256']==C.recipe_sha()
        and p['candidate_cache_sha256']==cache['cache_content_sha256']
        and p['seed']==C.seed_for(C.molecule_id(source))
        and p['atomic_numbers']==cache['atomic_numbers']
        and C.canonical(p['D20'])==C.canonical(cache['D20'])
        and p['dataset_version']=='v2_candidate'and p['training_eligible']is False
        and p['requested_conformers']==3 and p['no_fill']is True and p['no_retry']is True
        and p['new_QM_calls']==0 and manifest['export_limit']==3,
        'Same immutable source/cache/once recipe, current max3 nofill/no-retry packet')
    rows=p['conformers'];n=len(rows);ids=list(range(n))
    need(n<=3 and p['actual_conformers']==n and manifest['actual_conformers']==n
        and [r['conformer_id']for r in rows]==ids and p['generation_order']==ids
        and set(p['orders'])=={'fixed_random','energy','diversity'}
        and all(sorted(p['orders'][name])==ids for name in p['orders']),
        'Actual0..3 and three complete permutations, without dropping sparse sources')
    canonical=cache['canonical_candidates']
    need(len(rows)==min(3,len(canonical)),'Exact saved no-fill canonical prefix, no replacement/fill')
    conformers=[]
    for i,row in enumerate(rows):
        need(row['candidate_id']==canonical[i]['candidate_id']
            and row['geometry_sha256']==canonical[i]['geometry_sha256']
            ==C.geometry_sha(p['atomic_numbers'],row['coordinates'])
            and numeric_hash(row['energy'])==numeric_hash(canonical[i]['energy'])
            and set(row['D3'])==set(D3_NAMES),'Saved coordinate/energy bits, native ID and original seven D3 fields')
        atoms=row['D3']['SASA_atom_A2']
        need(atoms is None or len(atoms)==len(p['atomic_numbers']),'Actual atomSASA length, including explicit source hydrogen atoms')
        conformers.append({'record_id':p['molecule_id']+':uff:'+str(i),'conformer_id':i,
            'D3_hash':numeric_hash([row['D3'][name]for name in D3_NAMES]),
            'geometry_sha256':row['geometry_sha256'],'energy_hash':numeric_hash(row['energy']),
            'native_candidate_id':row['candidate_id'],'atom_order_sha256':p['atom_order_sha256']})
    phases=[e.get('phase')for e in events]
    if not manifest['closed_cache_reused_without_UFF']:
        optimizers=[e['candidate_id']for e in events if e.get('phase')=='optimizer_intent']
        need(phases.count('molecule_intent')==1 and phases.count('graph_return')<=1
            and phases.count('embedding_intent')==cache['embedding_calls']<=1
            and len(optimizers)==len(set(optimizers))==cache['optimizer_calls']<=30,
            'Durable current-pool once intents, no scientific retry/replacement candidates')
    else:
        need(phases.count('closed_cache_adopted_without_native_calls')==1
            and not any(x in phases for x in('embedding_intent','optimizer_intent','molecule_intent')),
            'Explicit cache adoption must have no repeated prepare/embed/optimization')
    descriptors=[e['conformer_id']for e in events if e.get('phase')=='descriptor_intent']
    need(descriptors==ids and phases.count('packet_closed')==1
        and any(e.get('phase')=='packet_closed'and C.canonical(e['packet'])==C.canonical(p)for e in events),
        'Actual current three descriptor intents and closed immutable packet')
    value=p['D20']
    d20_state=('PRESENT_VALID'if all(value['valid_mask'])else'PRESENT_WITH_FAILED_COMPONENTS')if value else'UNAVAILABLE_FAILED_OR_UNKNOWN_NO_REPLAY'
    status=dict(state=p['state'],actual_conformers=n,desired_conformers=3,
        insufficient_conformers=p['insufficient_conformers'],generation_count_unknown=False,
        cache_complete=p['cache_complete'],orders=p['orders'],generation_order=p['generation_order'],error=cache.get('error'))
    return {'D20_state':d20_state,'D20_hash':numeric_hash(value['values']if value else[None]*20),
        'D20_names':value['names']if value else None,'D20_valid_mask':value['valid_mask']if value else[False]*20,
        'actual_conformers':n,'delivered_conformers':n,'status_hash':status_hash(status),
        'conformers':conformers,'state':p['state'],'D20_native_call_count_replayed_or_inferred':False,
        'embedding_calls_recorded':cache['embedding_calls'],'optimizer_calls_recorded':cache['optimizer_calls'],
        'cache_available':True,'cache_complete':cache['complete'],'saved_canonical_candidates':len(canonical),
        'recorded_successful_saved_native_candidates':len(cache['valid_candidates']),
        'saved_cache_supports_at_least_four_total':len(canonical)>=4}


def interrupted(source,manifest):
    need(manifest['schema']=='PUBCHEM_UFF3_INTERRUPTED_MOLECULE_V1'
        and manifest['source']==source and manifest['source_identity_sha256']==C.source_identity(source)
        and manifest['state']=='INTERRUPTED_NO_AUTOMATIC_SCIENCE_RETRY',
        'Retain actual interrupted source; no fabricated completed zero-conformer packet')
    status=dict(state=manifest['state'],actual_conformers=None,desired_conformers=3,
        insufficient_conformers=True,generation_count_unknown=True,cache_complete=False,
        orders={'fixed_random':[],'energy':[],'diversity':[]},generation_order=[],
        error='Interrupted original outputs retained; no scientific retry')
    return {'D20_state':'UNKNOWN_INTERRUPTED_NO_REPLAY','D20_hash':numeric_hash([None]*20),
        'D20_names':None,'D20_valid_mask':[False]*20,'actual_conformers':None,'delivered_conformers':0,
        'status_hash':status_hash(status),'conformers':[],'state':manifest['state'],
        'D20_native_call_count_replayed_or_inferred':False,'embedding_calls_recorded':None,'optimizer_calls_recorded':None,
        'cache_available':False,'cache_complete':None,'saved_canonical_candidates':None,
        'recorded_successful_saved_native_candidates':None,
        'saved_cache_supports_at_least_four_total':None}