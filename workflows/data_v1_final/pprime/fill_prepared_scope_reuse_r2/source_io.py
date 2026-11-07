"""Private physical-pointer IO; original physical_row validation and audit math."""
import importlib.util,json,pathlib,sys,types
from .bare_imports import pprime_bootstrap
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import prepare as Original
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import contract as C


def clone(f,**values):
    g=types.FunctionType(f.__code__,dict(f.__globals__,**values),f.__name__,f.__defaults__,f.__closure__)
    g.__kwdefaults__=f.__kwdefaults__;return g


def original_physical_reader():
    root=C.Q.REPO/'workflows/data_v1_final/pprime';path=root/'formal_common_v1/prepare_v1.py'
    with pprime_bootstrap(C.Q.REPO):
        spec=importlib.util.spec_from_file_location('_current_fill_original_physical_reader',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        C.need(pathlib.Path(module.__file__)==path,'ORIGINAL_PHYSICAL_READER_LOCATION')
        # Retention's prepare_pilot/common imports need the same short-lived
        # context. Preserve the correct original module object, not its cache.
        module._source_retention=importlib.import_module('retention_policy_v1')
        return module

class SourceIO:
    def __init__(self,plan,b,budget):
        self.plan=plan;self.b=b;self.budget=budget;self.held=[];self.reader=original_physical_reader()
        self.cfg=C.meta(plan['physical_reader_config_reference'])
        # Reading this single old IO bound does not apply its superseded99.5 gate.
        C.need(type(self.cfg['maximum_source_decode_bytes']) is int and self.cfg['maximum_source_decode_bytes']>0,'ORIGINAL_PHYSICAL_DECODE_BOUND')
        self.retention=self.reader._source_retention
        self.sources=self.retention.source_paths(C.meta(b['pilot']['source_plan']))
        self.source_shards={s['path']:s['shard_id'] for s in self.sources}
    def hold(self,ref):
        body=Original.Body(C.P.triple(ref),self.budget);self.held.append(body);return str(ref['path'])
    def pair(self,row):
        self.budget.check();raw=self.reader.physical_row(row,self.cfg)
        source=json.loads(row['native_source_json']);anchor=row['native_anchor_record_id']
        C.need(raw['source_record_id']==source['record_id']==anchor and source['molecule_id']==row['molecule_id'],'ORIGINAL_FILL_NATIVE_ANCHOR')
        C.need(not row.get('geometry_sha256') or raw['geometry_sha256']==row['geometry_sha256'],'CLOSED_FILL_GEOMETRY_WITNESS')
        source.update(shard_id=self.source_shards[source['source_path']],effective_role=row['effective_role'],source_role=row['source_role'],file_group=int(row['file_group']),size_stratum=row['size_stratum'])
        # The packet-local kernel ordinal remains recorded; canonical physical ID
        # is the already closed5659 append ID, not a newly assigned identifier.
        conf=dict(raw,sprime_conf_idx=int(row['sprime_conf_idx']))
        xyz=Original.coordinate_sha(conf['coordinates']);rid='pprime:'+row['molecule_id']+':'+str(row['sprime_conf_idx'])
        pair=dict(record_id=rid,molecule_id=row['molecule_id'],random_order_rank=int(row['random_order_rank']),geometry_source='uff_sprime',
          canonical_geometry_id=row['geometry_id'],source=source,conformer=conf,uff_coordinate_sha256=xyz,
          conformer_row_sha256=__import__('hashlib').sha256(C.O.canonical(conf)).hexdigest(),
          physical_source={k:row.get(k) for k in ('source_path','source_sha256','source_bytes','source_format','source_row_index','source_member','original_sprime_conf_idx')},
          original_source_conformer_id=raw['sprime_conf_idx'])
        if row.get('geometry_sha256'):pair['uff_geometry_sha256']=row['geometry_sha256']
        ns=row['identity_namespace']
        if ns=='accepted_original_sprime':identity=dict(namespace=ns,source_conformer_id=int(row['source_conformer_id']))
        else:
            C.need(ns=='data_v1_fill','ORIGINAL_ORDINARY_ONLY_NO_N1_NAMESPACE')
            ref=dict(path=row['once_ledger_path'],bytes=int(row['once_ledger_bytes']),sha256=row['once_ledger_sha256'])
            ledger=C.meta(ref)
            C.need(ledger['molecule_id']==row['molecule_id'] and ledger['task_key']==row['task_key'],'ORIGINAL_FILL_DISPATCH_WITNESS')
            identity=dict(namespace=ns,task_key=row['task_key'],seed=int(row['seed']),candidate_id=int(row['candidate_id']))
        audit=self.retention.stable_source_row(rid,row['molecule_id'],source,identity,self.sources)
        audit.update(physical_identity_json=C.O.canonical(audit.pop('physical_identity')).decode(),uff_coordinate_sha256=xyz,canonical_geometry_id=row['geometry_id'])
        pair.update(stable_raw_audit_key_sha256=audit['audit_key_sha256'],stable_raw_audit_selected=audit['selected'],physical_audit_identity=identity)
        return pair,audit
    def close(self):
        for body in self.held:body.close()