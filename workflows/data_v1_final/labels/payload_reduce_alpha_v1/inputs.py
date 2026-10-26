"""Small-metadata inventory builder and post-fixture Alpha input verification."""
from __future__ import annotations
import argparse,collections,hashlib,json,os,socket,threading,time
from pathlib import Path

ROOT=Path('/gfshome/alpha/codex_data_v1_20261026')
KINDS={'group_details':16,'candidate_mask':16,'coverage':16,'selection_owner_index':16,'expected_role':1}

def need(value,message):
    if not value:raise ValueError(message)

def triple(reference):
    return {key:reference[key] for key in ('path','bytes','sha256')}

def small(path,expected=None):
    p=Path(path).absolute();need(p.stat().st_size<=2<<20,'SMALL_METADATA_ONLY')
    raw=p.read_bytes();pin={'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    if expected is not None:need(all(pin[k]==expected[k] for k in ('bytes','sha256')),'OBSERVED_SMALL_COPY_BYTES_DIFFER')
    return json.loads(raw.decode('utf-8-sig')),pin

def save_new(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(raw)<=2<<20,'SMALL_INVENTORY_OUTPUT_ONLY')
    p=Path(path).absolute();p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def relocated(reference,mapping):
    rows={row['origin_reference']['path']:row for row in mapping['entries']}
    row=rows.get(reference['path']);need(row is not None,'DECLARED_ORIGINAL_INPUT_NOT_IN_281_MAP')
    need(triple(reference)==triple(row['origin_reference']),'ORIGINAL_INPUT_PIN_DIFFERS')
    return triple(row['target_reference'])

def build_inventory(manifest,manifest_reference,config,config_reference,owner_plan,owner_plan_reference,
                    mapping,mapping_reference,reports,observed):
    need(manifest['schema']=='LABEL_PAYLOAD_SHARD_MANIFEST_V1' and manifest['status']=='PAYLOAD_SHARD_SCANNED_REDUCTION_REQUIRED','ACTUAL_CLOSED_SCAN_MANIFEST_REQUIRED')
    need(manifest['execution_endpoint']=='218.192.171.238:22' and manifest['execution_uid']==1264 and str(manifest['execution_job_id'])=='1884788','EXACT_ACTUAL_ALPHA_SCAN_PARENT')
    need(manifest['shard_id']==0 and len(manifest['groups'])==16 and manifest['pre_scan_fixture_tests_passed']==6,'EXACT_ONE_SHARD_SIXTEEN_GROUPS')
    need(len({row['pid'] for row in manifest['groups']})==16,'SIXTEEN_ACTUAL_SCAN_WORKER_IDENTITIES')
    need(config_reference==manifest['config'] and owner_plan_reference==relocated(config['sources']['plan'],mapping),'UNCHANGED_CONFIG_AND_OWNER_PLAN_COPIES')
    need(manifest['plan']==config['sources']['plan'],'ORIGINAL_OWNER_PLAN_PROVENANCE')
    need((owner_plan['mode'],owner_plan['molecules'],owner_plan['records'],owner_plan['global_records'],owner_plan['shards'])==('pilot',512,4251,11231854,1),'EXACT_ORIGINAL_PILOT_SCOPE')
    need(config['new_mask_fraction_stop']==0.01 and config['robust_z_review']==20,'UNCHANGED_QUALITY_RULES')
    need(len(reports)==16 and len({r['group_index'] for r in reports})==16,'SIXTEEN_UNIQUE_GROUP_REPORTS')
    by_id={r['group_index']:r for r in reports};groups={g['group_index']:g for g in owner_plan['groups']}
    need(set(by_id)==set(groups)=={r['group_index'] for r in manifest['groups']},'EXACT_ORIGINAL_GROUP_SET')
    entries=[];report_refs=[];molecules=records=0
    for receipt in sorted(manifest['groups'],key=lambda r:r['group_index']):
        gid=receipt['group_index'];report=by_id[gid];group=groups[gid]
        need(receipt['pid']==report['pid'],'ACTUAL_SCAN_WORKER_REPORT_IDENTITY_DIFFERS')
        need(report['schema']=='LABEL_PAYLOAD_GROUP_REPORT_V1' and report['status']=='OWNER_PAYLOAD_SCANNED','ACTUAL_GROUP_NOT_CLOSED')
        need(report['source_job_id']==group['source_job_id'] and report['records']==group['expected_records'] and report['molecules']==group['expected_molecules'],'OWNER_GROUP_MASS_DIFFERS')
        need(len(report['task_counts'])==14 and all(v==group['expected_records'] for v in report['task_counts'].values()),'EXACT_GROUP_FOURTEEN_TASK_MASS')
        need(report['source_opens']==report['source_closes'] and report['max_simultaneous_source_handles']==1,'SCAN_IO_NOT_CLOSED')
        molecules+=report['molecules'];records+=report['records'];report_refs.append(triple(receipt['report']))
        for kind,key in (('group_details','details'),('candidate_mask','candidate_masks'),('coverage','coverage')):
            pin=triple(report[key]);entries.append({'kind':kind,'group_index':gid,'origin_reference':pin,'reference':pin})
        origin=triple(group['owner_index']);entries.append({'kind':'selection_owner_index','group_index':gid,'origin_reference':origin,'reference':relocated(origin,mapping)})
    origin=triple(owner_plan['expected_roles']);entries.append({'kind':'expected_role','group_index':None,'origin_reference':origin,'reference':relocated(origin,mapping)})
    need((molecules,records)==(512,4251),'ORIGINAL_PILOT_MASS_DIFFERS')
    need(dict(collections.Counter(row['kind'] for row in entries))==KINDS and len({row['reference']['path'] for row in entries})==65,'EXACT_UNIQUE_SIXTY_FIVE_INPUTS')
    for row in entries:
        p=Path(row['reference']['path']);need(ROOT in p.parents and '..' not in p.parts and row['reference']['bytes']>=0,'EXPLICIT_ALPHA_INPUT_LOCATOR_REQUIRED')
    return {'schema':'ALPHA_LABEL_PAYLOAD512_REDUCTION_INPUT_INVENTORY_V1','status':'EXPECTED_INPUTS_PENDING_THIS_ALLOCATION_SHA',
      'parent_alpha_job_id':'1884788','scan_manifest_reference':manifest_reference,'scientific_config_reference':config_reference,
      'owner_plan_reference':owner_plan_reference,'relocation_map_reference':mapping_reference,'group_report_references':report_refs,
      'entries':entries,'body_files':65,'body_bytes':sum(row['reference']['bytes'] for row in entries),'kind_counts':KINDS,
      'source_small_metadata_observed':observed,'body_read_or_hash_performed_by_builder':False,
      'future_allocation_body_verification_reference':None,'candidate_masks_frozen':False,'final_common_D4':False}

def verify_inputs(plan,proof,root,fixture_gate):
    """Same frozen SHA/fstat worker; no data parsing and no future receipt pin."""
    import concurrent.futures
    from payload_audit_alpha_v1.support import load,require,save
    from payload_audit_alpha_v1.transfer import hash_one
    from payload_audit_alpha_v1.resource_runtime import drain_submit,stop_requested
    gate=load(require(fixture_gate))
    need(gate['status']=='PASS' and gate['counts']['run']==6,'SIX_REAL_FIXTURES_REQUIRED_BEFORE_ANY_BODY_HASH')
    inventory=load(require(plan['input_inventory_reference']));rows=inventory['entries']
    need(len(rows)==65 and sum(r['reference']['bytes'] for r in rows)==plan['data_total_bytes'],'EXACT_SIXTY_FIVE_ACTUAL_INPUT_BUDGET')
    work=[{'kind':r['kind'],'origin_reference':r['origin_reference'],'target_reference':r['reference']} for r in rows]
    receipts=[];peer=threading.Event();started=time.monotonic()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            drain_submit(work,executor,hash_one,receipts,stop_requested,peer)
        need(len(receipts)==65,'ALL_SIXTY_FIVE_HASHES_REQUIRED')
        result={'schema':'ALPHA_LABEL_PAYLOAD512_REDUCTION_ACTUAL_INPUT_VERIFICATION_V1','status':'ACTUAL_ALL65_SHA_PASS',
          'endpoint':'218.192.171.238:22','uid':os.getuid(),'node':socket.gethostname().split('.')[0],
          'job_id':str(proof['job_id']),'boot_id':proof['boot_id'],'scope_key':plan['scope_key'],'stage':plan['stage'],
          'input_inventory_reference':plan['input_inventory_reference'],'parent_alpha_job_id':'1884788','pre_scan_fixture_gate':fixture_gate,
          'body_count':65,'body_bytes':plan['data_total_bytes'],'maximum_hash_workers':16,
          'actual_hash_threads':sorted({r['native_thread_id'] for r in receipts}),'elapsed_seconds':time.monotonic()-started,
          'original_values_parsed_during_hash':False,'records':sorted(receipts,key=lambda r:r['actual_target_reference']['path'])}
        return save(Path(root)/'input_verification.json',result)
    except BaseException as exc:
        save(Path(root)/'input_verification_failed.json',{'schema':'ALPHA_LABEL_PAYLOAD512_REDUCTION_ACTUAL_INPUT_VERIFICATION_V1',
          'status':'FAILED_NO_REDUCTION_STARTED','error':str(exc),'closed_hash_records':receipts,'job_id':str(proof['job_id'])})
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('scan-manifest','config','owner-plan','relocation-map','output'):p.add_argument('--'+key,required=True)
    p.add_argument('--scan-manifest-reference');p.add_argument('--relocation-map-reference')
    p.add_argument('--report',action='append',required=True);a=p.parse_args();observed=[]
    manifest,mp=small(a.scan_manifest)
    if a.scan_manifest_reference:
        mr,_=small(a.scan_manifest_reference);need(all(mp[k]==mr[k] for k in ('bytes','sha256')),'ACTUAL_ALPHA_MANIFEST_COPY_DIFFERS')
    else:mr=mp
    mapping,observed_map=small(a.relocation_map)
    if a.relocation_map_reference:
        map_ref,_=small(a.relocation_map_reference);need(all(observed_map[k]==map_ref[k] for k in ('bytes','sha256')),'ACTUAL_ALPHA_MAP_COPY_DIFFERS')
    else:map_ref=observed_map
    cfg,cp=small(a.config,manifest['config']);cfg_ref=triple(manifest['config'])
    expected_plan=relocated(cfg['sources']['plan'],mapping);owner,op=small(a.owner_plan,expected_plan)
    expected_reports={row['group_index']:triple(row['report']) for row in manifest['groups']};reports=[]
    observed.extend([{'expected_reference':mr,'observed_reference':mp},{'expected_reference':cfg_ref,'observed_reference':cp},
      {'expected_reference':expected_plan,'observed_reference':op},{'expected_reference':map_ref,'observed_reference':observed_map}])
    for path in a.report:
        report,rp=small(path);expected=expected_reports[report['group_index']]
        need(all(rp[k]==expected[k] for k in ('bytes','sha256')),'ACTUAL_ALPHA_REPORT_COPY_DIFFERS')
        reports.append(report);observed.append({'expected_reference':expected,'observed_reference':rp})
    inventory=build_inventory(manifest,triple(mr),cfg,cfg_ref,owner,expected_plan,mapping,triple(map_ref),reports,observed)
    output=save_new(a.output,inventory);print(json.dumps({'status':inventory['status'],'body_files':65,'body_bytes':inventory['body_bytes'],'inventory_reference':output}))
if __name__=='__main__':main()
