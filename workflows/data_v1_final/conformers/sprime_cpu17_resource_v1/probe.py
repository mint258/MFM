"""Actual Main17 metadata/stat/environment only. No scientific input bodies or calls."""
import argparse,importlib.metadata,os,pathlib,platform,socket,sys
from . import contract as C,quota_edge as E
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as A
KEY='sprime_cpu17_storage_env_probe_v1'
PARAMS={'node':'compute-0-17','cpus':16,'DATA_bodies_opened':0,'new_UFF_calls':0,'new_QM_calls':0,'canonical_stat_only':True}


def environment():
    result={'python':platform.python_version(),'executable':sys.executable}
    for name in ('numpy','rdkit','torch','torch-geometric','lmdb','pyarrow','scipy'):result[name]=importlib.metadata.version(name)
    C.need(result['rdkit']=='2025.09.5' and result['executable']==E.Q.PY,'ORIGINAL_MAIN_RDKIT_AND_PYTHON')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('plan','root-preflight','output'):p.add_argument('--'+k,type=pathlib.Path,required=True)
    a=p.parse_args();plan_ref=C.ref(a.plan);plan=E.meta(plan_ref)
    argv=[E.Q.PY,'-B','-m',C.MODULE+'.probe','--plan',str(a.plan),'--root-preflight',str(a.root_preflight),'--output',str(a.output)]
    proof=A.require_startup(a.root_preflight,expected_scope_key=KEY,expected_scope_parameters=PARAMS,expected_execution_argv=argv,
      expected_source=__file__,expected_kind='analysis',required_references=[plan_ref,*C.own_sources(),*plan['source_references']])
    C.need(proof['request']['node']==C.NODE and proof['request']['wall_seconds']==900 and proof['request']['cpus']==16
      and plan['mode']=='probe' and plan['source_references']==C.own_sources(),'FIXED_SOURCE_REAL17_METADATA_PROBE')
    C.source_inverse_proof();facts=plan['provider_facts'];provider,identity=E.provider(facts);_,quota=E.current(facts,provider,identity)
    C.need(quota['free_bytes']-C.WAVE_RESERVE-E.CAP-C.ADMIN>=200000000000,'ORIGINAL182CAPS_PLUS_PROVIDER_ADMIN200GB')
    observed=E.Q.storage_observation();raw,marker_ref=E.Q.small(provider['marker_reference']['path'])
    marker_frame=E.frame(pathlib.Path(marker_ref['path']).stat());marker_frame['bytes']=marker_frame.pop('size')
    marker={'reference':marker_ref,'stat':marker_frame,'bytes_checked':len(raw)}
    canonical=pathlib.Path(plan['canonical_reference']['path']);info=canonical.lstat()
    C.need(not any(x.is_symlink() for x in (canonical,*canonical.parents)) and info.st_uid==1278
      and info.st_size==plan['canonical_reference']['bytes'],'CANONICAL_STAT_ONLY_UID_SIZE')
    source=E.meta(plan['formal_source_receipt']);old=next(x for x in source['outputs'] if x['name']=='formal_population')
    C.need(old['reference']==plan['canonical_reference'] and source['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED'
      and all(E.frame(info)[k]==old['after'][k] for k in ('inode','size','mtime_ns','uid')),'ACTUAL17_CANONICAL_FRAME_MUST_MATCH_ORIGINAL_PRODUCER')
    record={'schema':'ACTUAL_MAIN17_ZERO_SCI_STORAGE_ENV_PROBE_V1','node':socket.gethostname().split('.')[0],'uid':os.getuid(),
      'job_id':str(proof['job_id']),'boot_id':proof['boot_id'],'plan_reference':plan_ref,'startup_proof_reference':C.ref(a.root_preflight),
      'storage':observed,'marker':marker,'canonical_reference':plan['canonical_reference'],'canonical_stat':E.frame(info),
      'nfs_addresses':sorted({x[4][0] for x in socket.getaddrinfo('nfs',None,socket.AF_INET)}),
      'sonmi_addresses':sorted({x[4][0] for x in socket.getaddrinfo('sonmi',None,socket.AF_INET)}),
      'provider_facts':dict(facts,marker_reference=provider['marker_reference']),'fresh_quota':quota,'environment':environment(),
      'source_references':C.own_sources(),'DATA_bodies_opened':0,'new_UFF_calls':0,'new_QM_calls':0,'production_ledger_accessed':False}
    E.validate_probe(record,proof)
    C.need(a.output.is_absolute() and C.BASE in a.output.parents and not a.output.exists(),'FRESH_PROBE_OUTPUT')
    a.output.mkdir(parents=True,mode=0o700);payload=C.canonical(record)+b'\n';C.need(len(payload)<2<<20,'SMALL_PROBE_REPORT')
    with (a.output/'receipt.json').open('xb') as stream:stream.write(payload);stream.flush();os.fsync(stream.fileno())
    return 0


if __name__=='__main__':raise SystemExit(main())
