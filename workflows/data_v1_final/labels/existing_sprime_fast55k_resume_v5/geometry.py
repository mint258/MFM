"""Original geometry table tail with bounded parallel original-packet decoding."""
import pathlib,types
from . import contract as C,packet_io as P
from .resource_census import ResourceBudget
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v4 import geometry as OLD
I=OLD.I;cohort=OLD.cohort;schema_header=OLD.schema_header;metadata_children=OLD.metadata_children;prepare=OLD.prepare
WORKER=OLD.WORKER;STATISTICS=OLD.STATISTICS;ELIGIBILITY=OLD.ELIGIBILITY;COVERAGE=OLD.COVERAGE

def proof():return dict(OLD.proof(),parallel_packet_IO=P.transfer_proof())

def build(plan,proof,root,budget,prefix,old,oldproof,cohort):
    root=pathlib.Path(root);root.mkdir()
    with P.PacketReader(plan,proof,root,budget,cohort)as reader:
        reports=reader.validate()
        I.save(root/'reused_closed_packets.json',{'schema':'ACTUAL_CPU_FULL55K_PACKET_REOPEN_V1','prior_actual_C0_job':'4525337',
          'review_reference':plan['closed_phase_review_reference'],'packets':reports,'new_geometry_computations':0,'original_projection_proof':globals()['proof']()})
        original=OLD.table_function();namespace=dict(original.__globals__,I=P.IOAdapter(reader),Wire=P.WireAdapter())
        tail=types.FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__)
        C.need(tail.__code__ is original.__code__,'ENTIRE_ORIGINAL_TABLE_TAIL_CODE_OBJECT_WITH_ONLY_PACKET_IO_BINDINGS')
        result=tail(root,budget,reports,proof)
    result.update(reused_closed_geometry_producer_job_id='4525337',new_geometry_packet_computations=0,
      closed_packet_read_workers=15,all_packet_workers_closed_zero=True)
    return result
