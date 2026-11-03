"""Actual CPU whole-SHA/footer admission of six already completed original tables."""
import pathlib
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I
from workflows.data_v1_final.export.d5_inputs_compound_day_v1 import core as Wire

def build(plan,proof,root,budget,prefix,old,oldproof,cohort):
    import pyarrow.parquet as pq
    root=pathlib.Path(root);root.mkdir();review,receipt=C.geometry_authority(plan);base=C.GEOMETRY_ROOT/'ordinary_geometry'
    rr=I.pin(base/'reused_closed_packets.json');I.allow(rr,origin=C.GEOMETRY_ROOT);packets=I.load_data(rr,64<<20)
    reports=packets['packets'];C.need(len(reports)==55000 and {v['molecule_id']for v in reports}==set(cohort),'SAME_COMPLETE55K_PACKET_PROVENANCE_NO_NEW_COMPUTE')
    gate=receipt['fixture_gate'];I.allow(gate,origin=C.GEOMETRY_ROOT);g=I.load_data(gate,8<<20)
    C.need(g['status']=='PASS'and g['tests']==6 and g['failures']==g['errors']==0,'ACTUAL_OLD_SIX_SOURCE_TESTS_PASSED')
    total=sum(v['S_conformers']for v in cohort.values());nprime=sum(v['Sprime_conformers']for v in cohort.values());schemas=Wire.schemas();tables={};counts={}
    expected={'geometries':total+nprime,'orders':total+nprime,'atom_counts':total+nprime,'audit_identity':nprime,'roster':55000,'bias_features':55000}
    for kind,n in expected.items():
        budget.check();ref=I.pin(base/(kind+'.parquet'));I.allow(ref,origin=C.GEOMETRY_ROOT);path=I.require(ref);frame=I.S.identity(path);reader=pq.ParquetFile(path)
        try:
            C.need(reader.metadata.num_rows==n,'ORIGINAL_COMPLETE_GEOMETRY_TABLE_ROW_COUNT:'+kind)
            if kind in schemas:C.need(reader.schema_arrow.equals(schemas[kind],check_metadata=False),'ORIGINAL_GEOMETRY_TABLE_TYPED_SCHEMA:'+kind)
            counts[kind]=n
        finally:reader.close()
        C.need(frame==I.S.identity(path),'ACTUAL_CLOSED_TABLE_FULL_SHA_FOOTER_STABLE')
        if kind=='bias_features':features=ref
        else:tables[kind]=ref
    for report in reports:I.allow(report['reference'],origin=C.PHASE_ROOT)
    I.save(root/'closed_geometry_table_admission.json',{'schema':'ACTUAL_CPU_CLOSED_GEOMETRY_TABLE_REUSE_V1',
      'original_failed_parent_job_id':'4525429','old_FAILED_1_0_preserved':True,'actual_adopting_parent_job_id':str(proof['job_id']),
      'review_reference':plan['completed_geometry_review_reference'],'old_packet_readback_manifest_reference':rr,
      'table_references':tables,'bias_features_reference':features,'actual_footer_counts':counts,'new_geometry_computations':0})
    return {'schema':'PROVISIONAL_NATIVE55K_FIXED_RANDOM_BASE_GEOMETRIES_V1','table_references':tables,'molecules':55000,
      'actual_parent_job_id':str(proof['job_id']),'original_geometry_table_parent_job_id':'4525429',
      'original_geometry_parent_state':'FAILED_1_0_AFTER_ALL_SIX_TABLES_BEFORE_METADATA_FRAME',
      'bias_features_reference':features,'new_PM7_RMSD_recomputed':False,'new_QM_UFF_calls':0,
      'ordinary_base_N_preserved':True,'N1_second_UFF_not_created':True,'source_worker_report_references':[v['reference']for v in reports],
      'D5_full_guide_nested_geometry_coverage':False,'available_orders':['fixed_random'],'full_three_order':False,'D7':False,
      'three_orders_or_D7_complete':False,'PM7_HOF_RMSD_cache_required':False,'final_Common':False}
