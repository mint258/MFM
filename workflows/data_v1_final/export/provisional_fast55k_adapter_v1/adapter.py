"""Actual provisional verifier/typed reader hook; never fabricate final lineage."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict
import csv,io,json,os,sys
from pathlib import Path

# The Model hook loader uses spec_from_file_location, not a package import.
DATA_REPO=Path(__file__).absolute().parents[4]
if str(DATA_REPO)not in sys.path:sys.path.insert(0,str(DATA_REPO))
if not __package__:__package__='workflows.data_v1_final.export.provisional_fast55k_adapter_v1'
from workflows.data_v1_final.export.provisional_fast55k_adapter_v1.common import (
    need,read,reference,write,digest,VERSION,FAMILY,EVIDENCE,binding_for,compute_context)

def verify_provisional_documents(request,documents,references):
    """Small metadata lineage, independently checked by the patched Model seam."""
    _,b=binding_for(request);p=read(b['D3_export_reference']);d4=read(b['D4_delivery_reference'])
    need(request['mode']=='authoritative_pilot'and request['scope']=='pilot_smoke','PROVISIONAL_NEVER_FULL_OR_PROXY_AUTHORITY')
    need(set(references)==set(EVIDENCE)and documents['release']==p
      and references['release']==b['D3_export_reference'],'EXACT_PROVISIONAL_EVIDENCE_SET')
    need(p['schema']=='DATA_V1_PILOT_D3_FORMAL_EXPORT_DELIVERY_V1'and p['version']==VERSION
      and p['status']=='DELIVERED_PROVISIONAL_SCOPE_NOT_FINAL_COMMON'
      and p['pilot_counts']=={'TRAIN':50000,'VAL':5000}and p['available_orders']==['fixed_random'],
      'ACTUAL_ROOT_PROVISIONAL_D3_NOT_FINAL_ALIAS')
    need(Path(references['release']['path'])==DATA_REPO/'configs/data_v1/v1-pilot-provisional/D3_export.json',
      'ACTUAL_FORMAL_PROVISIONAL_PUBLICATION')
    joint=documents['joint_contract']
    need(joint['schema']=='ROOT_MODEL_D1_V3_INTERFACE_POLICY_CONFIG_FREEZE_V1'
      and joint['status']=='JOINTLY_FROZEN'and joint['root_signoff']is True and joint['model_signoff']is True
      and joint['actual_data_label_or_payload_release']is False,'D1_POLICY_JOINT_NOT_INVENTED_PAYLOAD_SIGNATURE')
    from phychem_mfm.phase1.v3_pilot_smoke import verify_model_ACK
    verify_model_ACK(joint['model_ack_reference'])
    refs=[{k:v[k]for k in('path','bytes','sha256')}for v in joint['frozen_data_source_references']]
    for r in refs:need(reference(r['path'])==r,'ACTUAL_SIGNED_D1_SOURCE_CHANGED')
    from .common import actual_parent
    actual_parent(p['actual_parent_accounting_reference'],p['actual_D3_parent_job_id'])
    need(p['actual_configuration_references']['registry_reference']==references['registry']
      and p['actual_configuration_references']['mapping_reference']==references['physical_mapping']
      and documents['d4_statistics']['source_numeric_reference']==d4['statistics_reference']
      and d4['fit_role']=='TRAIN'and d4['VAL_used_for_fitting']is False,'SAME_ACTUAL_REGISTRY_MAPPING_AND_TRAIN_D4')
    receipt=read(p['actual_D3_receipt_reference']);account=read(p['actual_parent_accounting_reference']);jid=str(p['actual_D3_parent_job_id'])
    need(receipt['schema']=='BOUNDED_PILOT_FAMILY_D3_RECEIPT_V1'
      and receipt['status']=='ACTUAL55K_FIXED_RANDOM_FAMILY_AND_10K_SOURCE_QA_COMPLETE_PENDING_ROOT_MODEL_REVIEW'
      and str(receipt['job_id'])==jid and receipt['errors']==[]and receipt['store_references']==p['store_references']
      and receipt['source_roundtrip_records']==10000,'ACTUAL_COMPLETE_D3_OBJECTS')
    raw=account['raw_sacct_reference'];need(reference(raw['path'])==raw,'RAW_ACTUAL_D3_ACCOUNTING_SHA')
    rows=[r for r in csv.DictReader(io.StringIO(Path(raw['path']).read_text()),delimiter='|')if r['JobIDRaw']==jid]
    need(account['endpoint']=='202.38.247.57:22'and account['uid']==1278 and account['query_returncode']==0
      and len(rows)==1 and all(rows[0][k]==v for k,v in {'UID':'1278','State':'COMPLETED','ExitCode':'0:0','AllocCPUS':'16'}.items()),
      'ACTUAL_MAIN_D3_C0_NOT_FUTURE_OR_DIFFERENT_CLUSTER')
    local=read(b['local_io_receipt_reference'])
    need(local['D3_export_reference']==b['D3_export_reference']and local['distinct_molecules']==55000
      and local['status']=='EXACT_D3_LOCAL_COPY_AND16_READER_IO_COMPLETE_NOT_MODEL_ACK','EXACT_LOCAL_D3_IO')
    source_paths={r['path']for r in b['source_references']}
    required={str(Path(__file__).with_name(n))for n in('__init__.py','common.py','statistics.py',
      'host_context.py','reader.py','prepare.py','adapter.py','diagnostic_copy.py')}
    need(required<=source_paths,'COMPLETE_PROVISIONAL_RUNTIME_SOURCE_CLOSURE')
    for r in b['source_references']:need(reference(r['path'])==r,'BOUND_CURRENT_ADAPTER_AND_MODEL_SOURCE')
    need(b['definition_components_preserved']==146 and b['no_QM_UFF_or_new_scientific_masks']is True,'SOURCE_RULES_UNCHANGED')
    if b['diagnostic_supplement_reference']is not None:
        s=read(b['diagnostic_supplement_reference'])
        need(s['schema']=='ACTUAL_D3_DIAGNOSTIC_SUPPLEMENT_V1'and s['role']=='TRAIN_UNSEEN_CONFORMATION'
          and s['D3_export_reference']==b['D3_export_reference']and s['D4_normalization_reference']==b['D4_delivery_reference']
          and s['D5_delivery_reference']==b['D5_delivery_reference'],'SAME_ACTUAL_OPTIONAL_DIAGNOSTIC_SUPPLEMENT')
        actual_parent(s['actual_parent_accounting_reference'],s['actual_parent_job_id'])
    return b

def load_registry(bundle,request=None):
    from phychem_mfm.phase1.v3_contract import FieldSpec,LabelRegistry
    d=read(bundle['model_registry_reference']);fs=tuple(FieldSpec(**f)for f in d['fields'])
    reg=LabelRegistry(fs,d['version'],d['source_sha256'],'data_line');need(reg.content_sha256==d['content_sha256'],'ACTUAL_MODEL_REGISTRY_PROJECTION_SHA')
    if request is not None:
        cfg=read(request['configuration']);requested=cfg['proxy_contract'].get('fields')
        if requested is not None:
            need(set(requested)<=set(reg.by_name()),'UNKNOWN_REQUESTED_MODEL_TARGET')
            # This is an explicit Model experiment selection, not a Data filter;
            # all146 definitions and payload values remain in the bound release.
            reg=LabelRegistry(tuple(f for f in fs if f.group=='S'or f.name in requested),VERSION,d['source_sha256'],'data_line')
    return reg

def validation_choices(bundle):
    from phychem_mfm.phase1.v3_sampling import SampleChoice,ConformationSelection
    from .prepare import load_index
    size=bundle['inputs']['validation_batch_size'];need(type(size)is int and size>0,'EXPLICIT_EXISTING_MODEL_VALIDATION_BATCH_SIZE')
    out={}
    for role in('VAL','TRAIN_UNSEEN_CONFORMATION'):
        if role not in bundle['indices']:continue
        index=load_index(bundle['indices'][role]);source=bundle['index_sources'][role];rows=[];ordinal=0
        for i in range(len(index)):
            m=index.molecule_at(i)
            for c in m.conformers:
                rows.append(SampleChoice(ordinal,i,m.molecule_id,c.conformer_id,source,c.locator(source),c.native_atoms,
                  m.group_mask,m.family_mask,index.content_sha256,digest({'actual_validation':role,'index':index.content_sha256})))
                ordinal+=1
        out[role]=tuple(tuple(rows[i:i+size])for i in range(0,len(rows),size))
    return out

def verify_model_v3_release_authority(request,documents):
    from phychem_mfm.phase1.v3_data_adapter import ALL_A_POLICY
    _,b=binding_for(request);refs=evidence_for(b)
    verify_provisional_documents(request,documents,refs)
    from .statistics import normalizers
    registry=load_registry(b,request);norms=normalizers(registry,read(b['D4_projection_reference']),b['D4_projection_reference'])
    choices=validation_choices(b);bindings={};statistics_document=read(b['D4_projection_reference'])
    for tid,t in b['targets'].items():
        s=statistics_document['targets'][tid]
        bindings[tid]={'registry_id':s['registry_id'],'task':s['task'],'condition':s['condition'],
          'series_key':s['series_key'],'statistics_pointer':['targets',tid],
          'population_sha256':refs['effective_train']['sha256'],'heldout_exclusion_sha256':refs['heldout_exclusion']['sha256'],
          'series_source':s['numeric_reference'],'statistics_source':b['D4_projection_reference'],
          'quantile_probabilities':[.001,.999],'statistic':'std_ddof0'}
    return {'schema':'model_v3_verified_Data_consumption_projection_v1','request_sha256':digest(request),
      'evidence_sha256':digest(refs),'data_version':VERSION,'scope':'authoritative_pilot','policy':deepcopy(ALL_A_POLICY),
      'TRAIN_population':'versioned_provisional_pilot_TRAIN','heldout_base_and_all_direct_children_excluded':True,
      'validation_population_bindings':{k:digest([[asdict(c)for c in row]for row in v])for k,v in choices.items()},
      'role_index_sha256':b['role_index_sha256'],
      'targets':{tid:dict(v['frame_binding'],source_frame_metadata=v['source_frame_metadata'])for tid,v in b['target_bindings'].items()},
      'reader_source':reference(Path(__file__).with_name('reader.py')),'D4_bindings':bindings,
      'normalization_sha256':digest({k:asdict(v)for k,v in norms.items()})}

def evidence_for(bundle):
    p=read(bundle['D3_export_reference']);d4=read(bundle['D4_delivery_reference'])
    return {'joint_contract':bundle['inputs']['joint_contract_reference'],'release':bundle['D3_export_reference'],
      'registry':p['actual_configuration_references']['registry_reference'],
      'physical_mapping':p['actual_configuration_references']['mapping_reference'],
      'provisional_population':d4['population_reference'],'effective_train':bundle['role_headers']['TRAIN'],
      'heldout_exclusion':bundle['D5_delivery_reference'],'d4_statistics':bundle['D4_projection_reference'],
      'geometry':bundle['geometry_binding_header_reference'],'codebook':bundle['channel_codebook_reference']}

def verify_and_bind_model_v3_provisional_payload_inputs(request):
    """Immediate real TRAIN/VAL typed loading API, not a training/full ACK."""
    compute_context();_,b=binding_for(request)
    docs={k:read(r,2<<20)for k,r in evidence_for(b).items()}
    verify_provisional_documents(request,docs,evidence_for(b))
    from .reader import ReaderFactory
    reg=load_registry(b,request);return reg,ReaderFactory(request['provisional_fast55k_binding'],reg)

def verify_and_bind_model_v3_pilot_TRAIN_inputs(request):
    """The exact existing Model hook. No missing third role is manufactured."""
    compute_context();_,b=binding_for(request)
    need(set(b['indices'])=={'TRAIN','VAL','TRAIN_UNSEEN_CONFORMATION'},
      'ACTUAL_DIAGNOSTIC_SUPPLEMENT_PAYLOAD_REQUIRED_FOR_ORIGINAL_THREE_ROLE_TRAINING_NOT_FOR_TRAIN_VAL_ACK')
    cfg=read(request['configuration']);mode=cfg['proxy_contract']['sampler']['selection']['mode']
    need(mode in('all','first_k'),'ONLY_REAL_FIXED_RANDOM_ORDER_AVAILABLE_NO_ENERGY_OR_DIVERSITY')
    from phychem_mfm.phase1.v3_data_adapter import verify_release_binding,make_proxy_inputs
    from phychem_mfm.phase1.v3_structural import StructuralFieldBinding
    from .prepare import load_index
    from .statistics import normalizers
    from .reader import ReaderFactory
    release=verify_release_binding(request,evidence=evidence_for(b),verifier=reference(__file__))
    reg=load_registry(b,request);norms=normalizers(reg,read(b['D4_projection_reference']),b['D4_projection_reference'])
    factory=ReaderFactory(request['provisional_fast55k_binding'],reg)
    factory.require_native_bond_status='S'in cfg['proxy_contract']['groups']
    return make_proxy_inputs(request,release,indexes={k:load_index(v)for k,v in b['indices'].items()},
      registry=reg,reader_factory=factory,structural_binding=StructuralFieldBinding(**b['structural_binding']),
      normalizations=norms,validation_choices=validation_choices(b),physical_policy_reference=cfg['physical_policy_reference'])

def physical_policy(release,registry,reference_value):
    from phychem_mfm.phase1.v3_physical_policy import PhysicalLossPolicy
    _,b=binding_for(release.request);joint=read(release.evidence['joint_contract'])
    signed=[{k:r[k]for k in('path','bytes','sha256')}for r in joint['frozen_data_source_references']]
    need(reference_value in signed,'SAME_SIGNED_NATIVE30_POLICY_NOT_NEW_AUTHORITY')
    statuses=read(b['target_policy_reference'])['targets']
    target_map={f.name:{k:release.projection['D4_bindings'][f.name][k]for k in('registry_id','task','condition')}
      |{'target_id':f.name}for f in registry.fields if f.representation=='symmetric_tensor6'}
    class ProvisionalPolicy(PhysicalLossPolicy):
        @property
        def projection(self):
            return dict(super().projection,provisional_target_policy_reference=b['target_policy_reference'],
              provisional_dispositions={f.name:statuses[f.name]['physical_policy_status']for f in registry.fields if f.group!='S'})
        def disabled(self,name):
            return super().disabled(name)or(name in statuses and statuses[name]['physical_policy_status']!='ACTUAL_TARGET_CONDITION_SOURCE_ENABLED')
        def reason(self,name):
            if super().disabled(name):return super().reason(name)
            return statuses[name].get('physical_policy_reason',statuses[name].get('reason',statuses[name]['physical_policy_status']))if self.disabled(name)else None
        def validate_for_registry(self,reg,*,enabled_fields=None):
            self.reverify();active=set(reg.by_name())if enabled_fields is None else set(enabled_fields)
            for f in reg.fields:
                if f.name in active and f.group!='S':need(f.name in statuses,'ACTUAL_TARGET_PHYSICAL_DISPOSITION_REQUIRED')
            return self
    return ProvisionalPolicy(reference_value,target_map,False).validate_for_registry(registry,enabled_fields=())

def tensor_normalization(release,field_name):
    from .statistics import normalizers
    _,b=binding_for(release.request);reg=load_registry(b,release.request)
    return normalizers(reg,read(b['D4_projection_reference']),b['D4_projection_reference'])[field_name]


def tensor_raw_mean(release,field_name):
    from .statistics import tensor_raw_mean as actual_report
    return actual_report(release,field_name)


def mechanical_request_projection(request):
    """Metadata-derived identity before Root seals the final Model request.

    Uses the original provider identity, never a synthetic provisional SHA.
    Its data_sha256 deliberately excludes request_sha256 in the Model source;
    adding this returned input_projection cannot create a request hash loop.
    """
    compute_context();_,b=binding_for(request)
    need(set(b['indices'])=={'TRAIN','VAL','TRAIN_UNSEEN_CONFORMATION'},'ACTUAL_THREE_ROLE_MEMBERSHIP_REQUIRED')
    from phychem_mfm.phase1.v3_data_adapter import verify_release_binding,RealDataProvider
    from phychem_mfm.phase1.v3_structural import StructuralFieldBinding
    from .prepare import load_index
    from .statistics import normalizers
    from .reader import ReaderFactory
    release=verify_release_binding(request,evidence=evidence_for(b),verifier=reference(__file__))
    reg=load_registry(b,request);norms=normalizers(reg,read(b['D4_projection_reference']),b['D4_projection_reference'])
    cfg=read(request['configuration']);factory=ReaderFactory(request['provisional_fast55k_binding'],reg)
    factory.require_native_bond_status='S'in cfg['proxy_contract']['groups']
    indexes={k:load_index(v)for k,v in b['indices'].items()}
    policy=physical_policy(release,reg,cfg['physical_policy_reference'])
    provider=RealDataProvider(release,indexes=indexes,registry=reg,reader_factory=factory,
      structural_binding=StructuralFieldBinding(**b['structural_binding']),validation_choices=validation_choices(b),
      physical_policy=policy,normalizations=norms)
    try:
        return {'index_sha256':indexes['TRAIN'].content_sha256,'registry_sha256':reg.content_sha256,
          'normalization_sha256':digest({k:asdict(v)for k,v in norms.items()}),
          'adapter_sha256':provider.source_sha256,'data_version':VERSION}
    finally:provider.close()

def payload_readback(request,geometry_ids,output,*,check_host_resources):
    """Actual Model typed loading receipt; Model Root supplies its own ACK later."""
    need(callable(check_host_resources),'EXISTING_LIVE_HOST_GUARD');reg,factory=verify_and_bind_model_v3_provisional_payload_inputs(request)
    import hashlib
    reader=factory();records=[];seen=set()
    try:
        for gid in geometry_ids:
            check_host_resources();sample=reader.read_geometry(gid,for_training=False)
            audit=reader.last_payload_audit;seen.update(sample.fields)
            records.append({'geometry_id':gid,'molecule_id':sample.molecule_id,'geometry_source':sample.geometry_source,
              'actual_fields':sorted(sample.fields),'payload_audit_sha256':digest(audit),
              'typed_classes':{k:type(v).__name__ for k,v in sample.fields.items()},
              'actual_payloads':{k:{'values_dtype':str(v.values.dtype),'values_shape':list(v.values.shape),
                'values_sha256':hashlib.sha256(v.values.contiguous().numpy().tobytes()).hexdigest(),
                'validity_sha256':hashlib.sha256(v.valid.contiguous().numpy().tobytes()).hexdigest(),
                'authoritative_conversions':getattr(v,'conversions',())}for k,v in sample.fields.items()}})
    finally:reader.close()
    _,b=binding_for(request)
    return write(output,{'schema':'ACTUAL_MODEL_PROVISIONAL_D3_TYPED_PAYLOAD_READBACK_V1',
      'status':'ACTUAL_TYPED_PAYLOAD_READ_PENDING_MODEL_ROOT_REVIEW_NOT_TRAINING_ACCEPTANCE',
      'D3_export_reference':b['D3_export_reference'],'binding_reference':request['provisional_fast55k_binding'],
      'local_io_receipt_reference':b['local_io_receipt_reference'],'actual_parent_job_id':os.environ['SLURM_JOB_ID'],
      'adapter_source_reference':reference(__file__),'reader_source_reference':factory.source_ref,
      'actual_model_typed_source_references':factory.model_source_references,
      'actual_model_registry_sha256':reg.content_sha256,'records':records,'actual_target_ids':sorted(seen),
      'D3_all_target_ids':sorted(b['targets']),'all_D3_targets_read':seen==set(b['targets']),
      'r73_training_numeric_frame_ready_claimed':False,'Model_payload_ACK':False,'training_or_optimizer_started':False})
