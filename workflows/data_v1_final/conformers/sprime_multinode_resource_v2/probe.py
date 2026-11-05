"""Actual allocated-node SOURCE/environment/shared-storage facts;no DATA bodies."""
import argparse,concurrent.futures as cf,os,pathlib,socket
from . import contract as C,edge as E
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as A
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('plan','root-preflight','output'):p.add_argument('--'+k,type=pathlib.Path,required=True)
    a=p.parse_args();ref=C.ref(a.plan);plan=E.meta(ref);node=C.node(plan['node'])
    argv=[E.Q.PY,'-B','-m',C.MODULE+'.probe','--plan',str(a.plan),'--root-preflight',str(a.root_preflight),'--output',str(a.output)]
    proof=A.require_startup(a.root_preflight,expected_scope_key='sprime_multinode_resource_probe_v2',expected_scope_parameters=C.parameters('probe',node),
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',required_references=[ref,*C.own_sources(),*plan['source_references']])
    C.need(proof['request']['node']==node and proof['request']['cpus']==16 and proof['request']['wall_seconds']==900
        and proof['request']['estimated_peak_output_bytes']==128<<20,'EXACT16_CPU900S128M_PROBE')
    E.source3(plan['source3_reference']);C.source_inverse_proof()
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        pins=list(pool.map(lambda r:C.ref(r['path']),[*C.own_sources(),*C.sources().values()]))
    C.need(pins==[*C.own_sources(),*C.sources().values()],'ALL_ACTUAL_NODE_SOURCE_BYTES')
    facts=plan['provider_facts'];provider,identity=E.provider(facts);_,quota=E.current(facts,provider,identity)
    C.need(quota['free_bytes']-C.WAVE_RESERVE-E.CAP-C.ADMIN>=200000000000,'ACCOUNT_QUOTA_FULL182CAPS200GB')
    observed=E.Q.storage_observation();raw,marker_ref=E.Q.small(provider['marker_reference']['path'])
    physical=os.statvfs(C.Q.ROOT);physical_free=physical.f_bavail*physical.f_frsize
    C.need(physical_free-C.WAVE_RESERVE-E.CAP-C.ADMIN>=200000000000,'ACTUAL_PHYSICAL_FULL_WAVE_PLUS200GB_SEPARATE_FROM_ACCOUNT')
    frame=C.frame(pathlib.Path(marker_ref['path']).stat());frame['bytes']=frame.pop('size')
    path=pathlib.Path(plan['canonical_reference']['path']);info=path.lstat()
    C.need(not any(x.is_symlink() for x in (path,*path.parents)) and info.st_uid==1278 and info.st_size==plan['canonical_reference']['bytes'],'CANONICAL_STAT_ONLY_NO_BODY')
    source=E.meta(plan['formal_source_receipt']);origin=next(r for r in source['outputs'] if r['name']=='formal_population')
    C.need(origin['reference']==plan['canonical_reference'] and source['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED','ORIGINAL_CANONICAL_PRODUCER')
    C.same_source(origin['after'],C.frame(info))
    record={'schema':'ACTUAL_MAIN_SPRIME_NODE_PROBE_V2','node':socket.gethostname().split('.')[0],'uid':os.getuid(),'job_id':str(proof['job_id']),
        'plan_reference':ref,'startup_proof_reference':C.ref(a.root_preflight),'storage':observed,'marker':{'reference':marker_ref,'stat':frame,'bytes_checked':len(raw)},
        'canonical_reference':plan['canonical_reference'],'canonical_stat':C.frame(info),'provider_facts':dict(facts,marker_reference=provider['marker_reference']),
        'nfs_addresses':sorted({x[4][0] for x in socket.getaddrinfo('nfs',None,socket.AF_INET)}),'sonmi_addresses':sorted({x[4][0] for x in socket.getaddrinfo('sonmi',None,socket.AF_INET)}),
        'fresh_quota':quota,'physical_available_bytes':physical_free,'environment':E.environment(),'source_references':C.own_sources(),'scientific_DATA_bodies_opened':0,'new_UFF_QM_calls':0,'production_once_accessed':False}
    E.validate_probe(record,proof);C.need(C.DIAG in a.output.parents and not a.output.exists(),'FRESH_PROBE_OUTPUT')
    a.output.mkdir(parents=True);C.Q.write_new(a.output/'receipt.json',record);return 0
if __name__=='__main__':raise SystemExit(main())
