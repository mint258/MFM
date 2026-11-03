"""Exact metadata-only Main inventory and separately admitted Alpha replica close.

No transfer command, geometry scan, Main heavy-body hash or scientific fit.
"""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

MAIN='202.38.247.57:22'
ALPHA='218.192.171.238:22'
R=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
LIMIT=32<<20
FIELDS=('path','bytes','sha256')
MODULE='workflows.expansion.common_train_d27_reference_v1.transfer'
BUDGET_V2_SHA='bce95fa0d4d7a24dbfb806a14c54e11e56195aa3083ad98b489fafea28df1c7a'


def need(ok,message):
    if not ok:raise ValueError(message)


def triple(ref):return {k:ref[k]for k in FIELDS}


def frame(value):return [value.st_dev,value.st_ino,value.st_uid,value.st_nlink,value.st_size,value.st_mtime_ns,value.st_ctime_ns]


def small_pin(path):
    path=Path(path);before=path.lstat()
    need(stat.S_ISREG(before.st_mode)and before.st_size<=LIMIT,'Small regular metadata/source only')
    raw=path.read_bytes();need(frame(path.lstat())==frame(before),'Metadata changed during read')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),raw


def save(path,value):
    with Path(path).open('x',encoding='utf-8')as stream:
        json.dump(value,stream,sort_keys=True,separators=(',',':'),allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    return small_pin(path)[0]


class Inventory:
    def __init__(self,destination):
        self.destination=Path(destination);self.files={}
        need(self.destination.is_absolute()and self.destination.is_relative_to('/gfshome/alpha')and '..'not in self.destination.parts,'Explicit actual Alpha destination scope required')
    def add(self,ref,kind,metadata=False):
        ref=triple(ref);path=Path(ref['path']);st=path.lstat()
        need(path.is_absolute()and path.is_relative_to('/share/home/zixiao/descriptor_analysis')and '..'not in path.parts,
            'Preserve real original Main project/source path')
        need(stat.S_ISREG(st.st_mode)and st.st_uid==1278 and st.st_size==ref['bytes'],'Actual Main own regular source size/UID required')
        old=self.files.get(ref['path'])
        need(old is None or old['source_reference']==ref,'One origin path cannot have conflicting source pins')
        data=None
        if metadata:
            actual,data=small_pin(path);need(actual==ref,'Current small metadata/source SHA differs')
        if old is None:
            destination=self.destination/'objects'/ref['sha256'][:2]/(ref['sha256']+'.blob')
            old=dict(source_reference=ref,replica_reference=dict(path=str(destination),bytes=ref['bytes'],sha256=ref['sha256']),
                origin_endpoint=MAIN,origin_uid=1278,source_frame=frame(st),categories=[],
                current_Main_body_SHA_verified=False,current_Main_small_metadata_SHA_verified=False)
            self.files[ref['path']]=old
        if kind not in old['categories']:old['categories'].append(kind)
        old['current_Main_small_metadata_SHA_verified']|=metadata
        return json.loads(data)if metadata and path.suffix=='.json'else None
    def metadata(self,path,kind):
        ref,_=small_pin(path);return ref,self.add(ref,kind,True)


def collect(catalog_path,destination,output):
    need(os.getuid()==1278,'Main metadata inventory uses actual original UID1278 only')
    book=Inventory(destination);catalog_ref,catalog=book.metadata(catalog_path,'closed_D27_catalog')
    need(catalog['schema']=='PUBCHEM_D27_CLOSED_WINDOW_INPUTS_V1'and catalog['cache_part_count']==5728
        and catalog['cache_part_unique_bytes']==10551578930 and catalog['original_all_role_canonical_records']==11231854,
        'Exact frozen full D27 catalog, never selected55k or invented coverage')
    book.add(catalog['source_inventory_reference'],'original_source_inventory',True)
    configs=[]
    for ref in catalog['origin_manifest_references']:
        origin=book.add(ref,'closed_origin_manifest',True)
        configs.append(book.add(origin['config'],'original_origin_config',True))
    need(len(configs)==5,'All five actual closed origins required')
    first=configs[0]
    for key in('canonical_index','field_map_reference','logical_group_plan_reference','logical_group_plan_authority_reference'):
        for cfg in configs:
            ref=cfg[key]
            need((ref['bytes'],ref['sha256'])==(first[key]['bytes'],first[key]['sha256']),'Every origin must bind the same canonical/logical/field authority')
            book.add(ref,key,key!='canonical_index')
    for window in catalog['windows']:
        actual=book.add(window['window_reference'],'closed_D27_window',True)
        need(actual['source_reference']==window['source_reference']and actual['parts']==window['parts'],
            'Current closed window must retain catalog source and all exact part pins')
        for part in window['parts']:book.add(part['reference'],'D27_typed_body')
    d5_ref,d5=book.metadata(R/'repository/configs/data_v1/D5_v1_pilot_provisional_delivery.json','D5_original_delivery')
    need(d5['schema']=='DATA_V1_D5_PROVISIONAL_DELIVERY_V1'and d5['scope_version']=='D5_OLD_COMPLETE_FROZEN_RANDOM_20261029_V1','Actual frozen D5 scope retained')
    accept=book.add(d5['actual_acceptance_reference'],'D5_actual_Root_acceptance',True)
    parent=accept['actual_parent']
    for key in('accounting','manifest','proof','raw'):book.add(parent[key],'D5_original_actual_'+key,True)
    account=book.add(parent['accounting'],'D5_original_actual_accounting',True)
    need(account['endpoint']==MAIN and account['uid']==1278,'Original Main D5 identity remains Main')
    for key in('diagnostic_base_reference','diagnostic_targets_reference','actual_heldout_geometry_reference'):
        book.add(d5['components'][key],'D5_required_identity_body')
    mask_ref,mask=book.metadata(R/'repository/configs/data_v1/labels/streaming_v2.json','original_mask_config')
    for key in('mask_rules','registry'):book.add(mask['sources'][key],'original_mask_'+key,True)
    for ref in mask['adapter_source_pins']:book.add(ref,'original_mask_source_pin',True)
    rows=sorted(book.files.values(),key=lambda r:r['source_reference']['path'])
    bodies=[r for r in rows if 'D27_typed_body'in r['categories']]
    d5b=[r for r in rows if 'D5_required_identity_body'in r['categories']]
    need(len(bodies)==5728 and sum(r['source_reference']['bytes']for r in bodies)==10551578930,'Exact full5728 body census')
    need(len(d5b)==3 and sum(r['source_reference']['bytes']for r in d5b)==120902216,'Only the three needed D5 identity bodies')
    objects={}
    for row in rows:
        ref=row['replica_reference'];prior=objects.setdefault(ref['path'],ref)
        need(prior==ref,'Unique content-addressed destination cannot conflict')
    skipped={k:triple(d5['components'][k])for k in('actual_field_input_binding_reference','actual_input_views_reference',
        'all_fixed_random_base_index_reference','training_fixed_random_base_index_reference','distribution_inputs_reference')}
    result=dict(schema='PUBCHEM_D27_MAIN_ALPHA_TRANSFER_INVENTORY_V1',status='PREPARED_NO_TRANSFER_NO_ALPHA_BODY_VERIFICATION',
        origin=dict(endpoint=MAIN,uid=1278),destination=dict(endpoint=ALPHA,uid=1264,root=str(book.destination)),
        source_catalog_reference=catalog_ref,files=rows,origin_reference_count=len(rows),unique_replica_count=len(objects),
        unique_replica_bytes=sum(r['bytes']for r in objects.values()),D27_typed_bodies=len(bodies),
        D27_typed_bytes=10551578930,D5_required_identity_bytes=120902216,canonical_bytes=first['canonical_index']['bytes'],
        Main_heavy_body_SHA_recomputed=False,Alpha_replicas_currently_verified=False,source_journals_or_geometry_scanned=False,
        excluded_D5_opaque_provenance_only=skipped,base_cache_parts_excluded=catalog['base_cache_part_count'],
        original_full_raw_or_geometry_bodies_included=False,
        source_bindings=dict(source_catalog_reference=catalog_ref,canonical_index=first['canonical_index'],
            logical_group_plan_reference=first['logical_group_plan_reference'],field_map_reference=first['field_map_reference'],
            diagnostic_delivery_reference=d5_ref,original_mask_config_reference=mask_ref),
        scientific_source_pins_must_bind_actual_imported_Alpha_capsule_modules_not_transport_blobs=True,
        Common_actual_authority_not_invented=True)
    Path(output).parent.mkdir(parents=True,exist_ok=True);return save(output,result)


def launcher_binding(plan,proof,actual_plan,module_ref,entry_ref,boot_id,job_id):
    request=proof['request'];argv=plan['execution_argv']
    need(proof['uid']==1264 and str(proof['job_id'])==str(job_id) and proof['boot_id']==boot_id
        and request['producer_plan_reference']==actual_plan and request['execution_argv']==argv,
        'Real current launcher boot/job/plan/argv binding required')
    for ref in(module_ref,entry_ref):
        need(any(triple(r)==ref for r in request['source_references'])
            and any(triple(r)==ref for r in plan['code_references']),
            'Exact current transfer module and executed entry source pins required')
    need(Path(entry_ref['path']).is_absolute()and argv.count(MODULE)==1 and argv.index(MODULE)>0
        and argv[argv.index(MODULE)-1]==entry_ref['path'],
        'Exact transfer module and current absolute executed entry required')


def reviewed_budget(plan,verify):
    ref=plan['reviewed_storage_budget_reference']
    need(ref['bytes']==18667 and ref['sha256']==BUDGET_V2_SHA,'Actual reviewed Root storage budget V2 pin required')
    json.loads(verify(ref).read_bytes())
    need(plan['output_cap_bytes']==20000000000 and plan['other_future_reserved_bytes']==1249483236352
        and plan['minimum_free_bytes']==200000000000,'Reviewed V2 source_transport cap/future/floor required')
    return ref

def close(plan_path,startup_proof):
    # This is the only heavy-body hash entry. Root must run it on admitted Alpha.
    from ..portable_sources_v1.transport import bind_plan,verify
    from ..alpha_runtime_v1.guard import Guard
    plan=json.loads(Path(plan_path).read_bytes())
    need(plan['schema']=='PUBCHEM_D27_ALPHA_TRANSPORT_CLOSE_PLAN_V1','Explicit source transport-close plan required')
    from ..alpha_runtime_v1.profile import admit
    admission=admit(plan,minimum_workers=16)
    bind_plan(plan)
    need(os.getuid()==1264 and os.environ.get('SLURM_JOB_ID'),'Actual admitted Alpha allocated parent required')
    proof=json.loads(Path(startup_proof).read_bytes())
    actual_plan=small_pin(plan_path)[0]
    argv=plan['execution_argv']
    need(argv.count(MODULE)==1 and argv.index(MODULE)>0,'Explicit transfer module in real execution argv required')
    entry_ref=small_pin(argv[argv.index(MODULE)-1])[0]
    launcher_binding(plan,proof,actual_plan,small_pin(__file__)[0],entry_ref,
        Path('/proc/sys/kernel/random/boot_id').read_text().strip(),os.environ['SLURM_JOB_ID'])
    budget_ref=reviewed_budget(plan,verify)
    from ..alpha_runtime_v1.common import allocated_bytes
    scope=Path(plan['output_scope_root'])
    usage=[allocated_bytes(scope)];closed_credit=[]
    # Only successfully SHA-closed immutable input inodes earn credit. No tree
    # walk repeats in the 5-second monitor; source files are never written here.
    guard=Guard(plan,usage_provider=lambda:usage[0],prequery_credit_provider=lambda cutoff:
        sum(blocks for stamp,blocks in tuple(closed_credit)if max(stamp[5],stamp[6])<=int(cutoff*1000000000)))
    try:
        inventory_ref=plan['transfer_inventory_reference'];inventory=json.loads(verify(inventory_ref).read_bytes())
        need(inventory['schema']=='PUBCHEM_D27_MAIN_ALPHA_TRANSFER_INVENTORY_V1'
            and inventory['origin']==dict(endpoint=MAIN,uid=1278)
            and inventory['destination']['endpoint']==ALPHA and inventory['destination']['uid']==1264,'Exact honest transfer inventory required')
        root=Path(inventory['destination']['root'])
        need(root==Path(plan['output_scope_root']),'Whole transfer inventory must use its declared aggregate budget scope')
        observed={};replicas=[]
        for row in inventory['files']:
            guard.check();origin=triple(row['source_reference']);ref=triple(row['replica_reference']);path=Path(ref['path'])
            need(path.is_relative_to(root)and origin['bytes']==ref['bytes']and origin['sha256']==ref['sha256'],
                'Exact source pin and actual destination subtree required')
            if str(path)not in observed:
                before=path.lstat();stamp=frame(before)
                need(stat.S_ISREG(before.st_mode)and before.st_uid==1264 and before.st_nlink==1 and before.st_size==ref['bytes'],
                    'Actual Alpha own single-link regular replica required')
                sha=hashlib.sha256()
                with path.open('rb')as stream:
                    need(frame(os.fstat(stream.fileno()))==stamp,'Actual same held replica FD required')
                    while True:
                        data=stream.read(8<<20)
                        if not data:break
                        sha.update(data);guard.check()
                    need(frame(os.fstat(stream.fileno()))==stamp,'Replica changed during whole SHA')
                need(frame(path.lstat())==stamp and sha.hexdigest()==ref['sha256'],'Actual whole Alpha replica SHA differs')
                observed[str(path)]=stamp
                closed_credit.append((stamp,before.st_blocks*512))
            replicas.append(dict(source_reference=origin,replica_reference=ref,origin_endpoint=MAIN,origin_uid=1278,
                actual_Alpha_frame=observed[str(path)],whole_Alpha_replica_SHA_verified=True))
        need(len(observed)==inventory['unique_replica_count']and sum(Path(p).stat().st_size for p in observed)==inventory['unique_replica_bytes'],
            'All exact unique destination bodies must close')
        need(usage[0]+(32<<20)<=plan['output_cap_bytes'],'Whole transferred bodies plus bounded new metadata must fit declared scope')
        out=Path(plan['output_directory']);out.mkdir(parents=True,exist_ok=False)
        manifest=dict(schema='PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1',status='VERIFIED_REPLICAS_CLOSED',
            destination=dict(endpoint=ALPHA,uid=1264),replicas=replicas,actual_transport_hash_verification=True,
            source_inventory_reference=inventory_ref,original_Main_bodies_rehashed=False,
            actual_parent=dict(endpoint=ALPHA,uid=1264,JobIDRaw=os.environ['SLURM_JOB_ID']))
        manifest_ref=save(out/'transport.json',manifest);usage[0]=allocated_bytes(scope);guard.sample();guard.check()
        return save(out/'receipt.json',dict(schema='PUBCHEM_D27_ALPHA_TRANSPORT_ACTUAL_CLOSE_V1',
            status='WHOLE_REPLICAS_VERIFIED_PENDING_ACTUAL_PARENT_C0_AND_ROOT_REVIEW',transport_manifest_reference=manifest_ref,
            inventory_reference=inventory_ref,actual_parent=manifest['actual_parent'],actual_parent_C0_not_self_claimed=True,
            startup_proof_reference=small_pin(startup_proof)[0],resource_plan=actual_plan,resources=guard.receipt(),
            profile_admission=admission,reviewed_storage_budget_reference=budget_ref,current_entry_reference=entry_ref,
            budget_usage_basis='actual allocated scope measured once before hashes and once after publish; source replicas never written; closed SHA input inode credit',
            repeated_budget_tree_walk=False))
    finally:guard.close()


def arguments(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    inv=sub.add_parser('inventory');inv.add_argument('--catalog',type=Path,required=True)
    inv.add_argument('--destination-root',type=Path,required=True);inv.add_argument('--output',type=Path,required=True)
    native=sub.add_parser('close');native.add_argument('--plan',type=Path,required=True);native.add_argument('--startup-proof',type=Path,required=True)
    argv=list(sys.argv[1:]if argv is None else argv)
    if argv and argv[0]=='--plan':argv.insert(0,'close')
    return parser.parse_args(argv)


def main():
    args=arguments()
    result=collect(args.catalog,args.destination_root,args.output)if args.action=='inventory'else close(args.plan,args.startup_proof)
    print(json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':main()
