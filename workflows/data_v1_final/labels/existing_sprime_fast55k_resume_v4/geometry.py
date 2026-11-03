"""Original table-projection AST tail, using independently reopened closed packets."""
import ast,copy,hashlib,inspect,json,pathlib,types
from . import contract as C
from .resource_census import ResourceBudget
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v3 import geometry as OLD
from workflows.data_v1_final.labels.existing_sprime_native_pilot_day_v1 import geometry as NATIVE
from workflows.data_v1_final.export.d5_inputs_compound_day_v1 import core as Wire
I=OLD.I
cohort=OLD.cohort;schema_header=OLD.schema_header;metadata_children=OLD.metadata_children
WORKER=OLD.WORKER;STATISTICS=OLD.STATISTICS;ELIGIBILITY=OLD.ELIGIBILITY
CONTEXT={}

def prepare(plan,proof,root,budget):
    result=OLD.prepare(plan,proof,root,budget)
    review,prior,priorproof,receipt=C.phase_authority(plan)
    CONTEXT.clear();CONTEXT.update(review=review,prior=prior,priorproof=priorproof,receipt=receipt)
    I.save(root/'closed_phase_origin.json',{'schema':'CLOSED55K_PHASE_REUSE_ORIGIN_V1','review_reference':plan['closed_phase_review_reference'],
      'prior_partial_C0_preserved':True,'all_old_files_readonly':True,'new_QM_UFF_calls':0})
    return result

def table_function():
    """Reuse verbatim every original statement after the complete packet-count gate."""
    original=ast.parse(inspect.getsource(NATIVE.build)).body[0]
    starts=[k for k,node in enumerate(original.body) if isinstance(node,ast.Expr)and isinstance(node.value,ast.Call)
      and any(isinstance(n,ast.Constant)and n.value=='NO_PARTIAL_NATIVE_GEOMETRY_ACCEPTANCE'for n in ast.walk(node))]
    C.need(len(starts)==1,'EXACT_ORIGINAL_COMPLETE55K_TABLE_TAIL_BOUNDARY')
    tail=original.body[starts[0]:]
    wrapper=ast.parse('def tables(root,budget,reports,proof):\n import pyarrow as pa\n pass\n').body[0]
    wrapper.body=wrapper.body[:1]+copy.deepcopy(tail)
    C.need(ast.dump(ast.Module(body=wrapper.body[1:],type_ignores=[]),include_attributes=False)==
      ast.dump(ast.Module(body=tail,type_ignores=[]),include_attributes=False),'EXACT_ORIGINAL_TABLE_PROJECTION_ALL_STATEMENTS_AST')
    module=ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[]));namespace=dict(NATIVE.build.__globals__)
    exec(compile(module,'<original_native_complete55k_table_tail>','exec'),namespace)
    return namespace['tables']

def proof():
    table_function()
    return {'original_table_projection_AST_tail_equal':True,'original_metadata_children_object':metadata_children is OLD.metadata_children,
      'original_statistics_object':STATISTICS is OLD.STATISTICS,'original_eligibility_object':ELIGIBILITY is OLD.ELIGIBILITY,
      'closed_packets_only_no_geometry_compute_calls':True,'full55000_scope_preserved':True}

def build(plan,proof,root,budget,prefix,old,oldproof,cohort):
    root=pathlib.Path(root);root.mkdir();reports=[]
    packetroot=C.PHASE_ROOT/'ordinary_geometry/molecules'
    expected={hashlib.sha256(mid.encode()).hexdigest()+'.lossless.json':mid for mid in cohort}
    C.need(len(expected)==55000 and set(p.name for p in packetroot.iterdir())==set(expected),'EXACT_CLOSED55K_PACKET_SET_NO_EXTRA_OR_MISSING')
    for name,mid in sorted(expected.items()):
        budget.check();path=packetroot/name;reference=I.pin(path);I.allow(reference,origin=C.PHASE_ROOT)
        value=Wire.decode(I.require(reference).read_bytes())
        C.need(value['molecule_id']==mid and value['pm7_count']==cohort[mid]['S_conformers']
          and value['uff_sprime_count']==cohort[mid]['Sprime_conformers'],'CLOSED_PACKET_MID_AND_ALL_ORIGINAL_BASE_N')
        reports.append({'molecule_id':mid,'reference':reference,'prior_producer_job_id':'4525337'})
    I.save(root/'reused_closed_packets.json',{'schema':'ACTUAL_CPU_FULL55K_PACKET_REOPEN_V1','prior_actual_C0_job':'4525337',
      'review_reference':plan['closed_phase_review_reference'],'packets':reports,'new_geometry_computations':0,'original_projection_proof':globals()['proof']()})
    result=table_function()(root,budget,reports,proof)
    result.update(reused_closed_geometry_producer_job_id='4525337',new_geometry_packet_computations=0)
    return result

class Coverage:
    @staticmethod
    def build(plan,proof,root,budget,members):
        root=pathlib.Path(root);root.mkdir();r=CONTEXT['receipt']['coverage_reference'];I.allow(r,origin=C.PHASE_ROOT)
        prior=I.load_data(r,8<<20)
        C.need(prior['schema']=='BOUNDED_COMPLETE_SPRIME_TYPED_COVERAGE_V1'and prior['job_id']=='4525337'
          and prior['molecules']==55000 and prior['all14task_and_base_exact_once']is True
          and not prior['quality_hold_fields']and not prior['errors'],'ACTUAL_COMPLETE_CLOSED_TYPED_COVERAGE_NO_REBUILD')
        for key in ('parts_catalog','base_index','readonly_old_catalog_reference','readonly_old_selected_owner_reference',
          'current_parent_typed_origin_reference','readonly_old_typed_origin_reference','original_part_lineage_reference'):
            ref=prior[key];origin=C.OLDROOT if pathlib.Path(ref['path']).is_relative_to(C.OLDROOT)else C.PHASE_ROOT
            I.allow(ref,origin=origin)
        # Reopen only actual terminal catalogs. Original per-part refs and producer
        # manifests remain untouched; original reader still verifies part content.
        catalog=I.require(prior['parts_catalog'])
        C.need(not any(pathlib.Path(str(catalog)+s).exists()for s in ('-wal','-shm','-journal')),'CLOSED_SQLITE_WITHOUT_LIVE_JOURNAL')
        for key,origin in (('readonly_old_typed_origin_reference',C.OLDROOT/'typed_coverage'),
                           ('current_parent_typed_origin_reference',C.PHASE_ROOT/'typed_coverage')):
            parent=prior[key];I.require(parent)
            entry={'manifest_reference':parent,'output_root':str(origin)}
            plan.setdefault('cache_transitive_output_origins',[]).append(entry);I.ORIGINS[parent['path']]=entry
        origin=I.save(root/'current_parent_typed_origin.json',{'schema':'CURRENT_PARENT_SELECTED_TYPED_ORIGIN_V1',
          'status':'READONLY_PRIOR_C0_TYPED_CACHE_REUSE_NO_PART_REENCODE','job_id':str(proof['job_id']),
          'prior_complete_coverage_reference':r,'prior_actual_C0_job_id':'4525337','parts_written_here':0,'full_Common_D4_D5_D3_D6_release':False})
        report=dict(prior,job_id=str(proof['job_id']),current_parent_typed_origin_reference=origin,
          reused_complete_coverage_reference=r,reused_C0_parent_job_id='4525337',reused_current_typed_origin_reference=prior['current_parent_typed_origin_reference'],
          typed_parts_reencoded=0,old_cache_written=False)
        ref=I.save(root/'manifest.json',report);return ref,report,[]
COVERAGE=Coverage()
