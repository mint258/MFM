"""Root-login bounded small-metadata relay; never open a scientific DATA file."""
import argparse,fcntl,json,os,pathlib,re,socket,subprocess,time
from workflows.data_v1_final.pprime.formal_packed_day_v1 import io as OriginalIO
from . import contract as C
Q=C.Q

def safe_path(value):
    C.need(type(value)is str and value.startswith('/') and re.fullmatch(r'[A-Za-z0-9_./:-]+',value)
      and '..' not in pathlib.PurePosixPath(value).parts,'LITERAL_SFTP_METADATA_PATH')
    return '"'+value+'"'

class Transport:
    def __init__(self,binding,out,store):
        self.binding=binding;self.out=out;self.store=store;self.calls=0
        self.root=binding['alpha_mailbox_root'];safe_path(self.root)
        C.need(self.root.startswith('/gfshome/alpha/codex_data_v1_20261026/control/pprime_main_claim_relay/'),
          'ROOT_FROZEN_ALPHA_METADATA_MAILBOX_ONLY')
        options=[];target='alpha@218.192.171.238'
        if binding.get('transport_ssh_config_reference') is not None:
            ref=binding['transport_ssh_config_reference'];C.Small.small(ref,False)
            C.need(ref in binding['source_references'] and binding.get('transport_ssh_alias')=='data-v1-alpha-windows-bridge',
              'EXACT_ROOT_PINNED_OPAQUE_TRANSPORT_CONFIG_AND_FIXED_ALIAS')
            options=['-F',ref['path']];target=binding['transport_ssh_alias']
        self.argv=['sftp',*options,'-q','-oBatchMode=yes','-oStrictHostKeyChecking=yes','-oConnectTimeout=10',
          '-oIdentityFile='+binding['Main_to_Alpha_key_path'],'-oUserKnownHostsFile='+binding['known_hosts_path'],
          '-b','-',target]
    def batch(self,commands):
        self.calls+=1;C.need(self.calls<=self.binding['maximum_transport_calls'],'FINITE_ROOT_METADATA_TRANSPORT_CALLS')
        result=subprocess.run(self.argv,input=('\n'.join(commands)+'\n').encode(),stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,timeout=30,check=False)
        C.need(result.returncode==0,'SFTP_CONNECTION_FAILURE_STOP_NEW_CLAIMS_NO_RETRY_STORM')
    def pull(self,sequences):
        incoming=self.out/'incoming';incoming.mkdir(exist_ok=True)
        heartbeat=incoming/'heartbeat.json';heartbeat.unlink(missing_ok=True)
        commands=['-get '+safe_path(self.root+'/heartbeat.json')+' '+safe_path(str(heartbeat))]
        for slot,sequence in enumerate(sequences):
            name='slot_%02d_seq_%06d.json'%(slot,sequence);path=incoming/name
            if not path.exists():commands.append('-get '+safe_path(self.root+'/requests/'+name)+' '+safe_path(str(path)))
        self.batch(commands)
        if heartbeat.exists():C.need(heartbeat.stat().st_size<=65536,'FINITE_ALPHA_HEARTBEAT_METADATA')
        return incoming
    def push(self,request_id,response_ref,claim_ref=None):
        commands=[]
        if claim_ref:
            target=self.root+'/claims/'+pathlib.Path(claim_ref['path']).name
            commands+=['put '+safe_path(claim_ref['path'])+' '+safe_path(target+'.partial'),
                       'rename '+safe_path(target+'.partial')+' '+safe_path(target)]
        target=self.root+'/responses/'+request_id+'.json'
        commands+=['put '+safe_path(response_ref['path'])+' '+safe_path(target+'.partial'),
                   'rename '+safe_path(target+'.partial')+' '+safe_path(target)]
        self.batch(commands)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binding',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    Q.on_login();binding_ref=Q.pin(a.binding);binding=C.small(binding_ref)
    manifest,allow,alpha=C.relay_binding(binding)
    out=C.M.fresh(a.output);out.mkdir(parents=True,mode=0o700)
    store=OriginalIO.Store(out,binding['maximum_control_bytes']);transport=Transport(binding,out,store)
    lock=pathlib.Path(binding['serial_lock_path']);C.need(lock.parent.is_dir() and not lock.is_symlink(),'ROOT_RELAY_SERIAL_LOCK')
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    writer={'endpoint':C.MAIN_ENDPOINT,'uid':1278,'pid':os.getpid(),'start_ticks':OriginalIO.ticks(os.getpid()),
      'node':socket.gethostname().split('.')[0],'role':'ROOT_LOGIN_METADATA_RELAY_NOT_NATIVE_PARENT'}
    store.json(out/'intent.json',{'schema':'PPRIME_ALPHA_METADATA_RELAY_INTENT_V1','binding_reference':binding_ref,
      'claim_writer':writer,'portable_manifest_reference':binding['portable_manifest_reference'],
      'native_Slurm_Parent_created':False,'scientific_DATA_opened':False})
    start=time.monotonic();sequences=[0]*16;active={};seen=set();stop=None;last_sequence=None;last_progress=None;live=False;replies=0;connection_failures=0
    try:
        while time.monotonic()-start<binding['relay_seconds']:
            incoming=None
            try:incoming=transport.pull(sequences);connection_failures=0
            except (OSError,ValueError,subprocess.SubprocessError) as exc:
                stop=stop or 'TRANSPORT_LOST_NO_NEW_DISPATCH';connection_failures+=1
                store.json(out/('transport_failure_%02d.json'%connection_failures),{'error':repr(exc),'all_claimed_unknown_retained':True})
                if connection_failures>=2:break
                time.sleep(min(5,binding['poll_seconds']));continue
            hp=incoming/'heartbeat.json';workers={}
            if hp.exists():
                h=C.small(C.Small.pin_small(hp));C.need(h['schema']=='PPRIME_ALPHA_CLAIM_SESSION_HEARTBEAT_V1'
                  and h['alpha_parent']==alpha and type(h['heartbeat_sequence'])is int and h['heartbeat_sequence']>=0,
                  'ACTUAL_FROZEN_ALPHA_PARENT_HEARTBEAT')
                if last_sequence is None:last_sequence=h['heartbeat_sequence']
                elif h['heartbeat_sequence']>last_sequence:
                    last_sequence=h['heartbeat_sequence'];last_progress=time.monotonic();live=True
                else:C.need(h['heartbeat_sequence']==last_sequence,'HEARTBEAT_SEQUENCE_CANNOT_GO_BACKWARD')
                C.need(len(h['worker_identities'])<=16,'AT_MOST16_REAL_ALPHA_WORKERS')
                for w in h['worker_identities']:
                    slot=w['dispatch_slot'];C.need(type(slot)is int and 0<=slot<16 and slot not in workers,'UNIQUE_ACTUAL_ALPHA_WORKER_SLOT')
                    workers[slot]=w
                if h['stop_new']:stop=stop or 'ALPHA_PARENT_STOP_NEW'
            if live and time.monotonic()-last_progress>binding['heartbeat_max_age_seconds']:stop=stop or 'ALPHA_HEARTBEAT_LOST_NO_NEW_CLAIMS'
            for slot in range(16):
                request_id='slot_%02d_seq_%06d'%(slot,sequences[slot]);path=incoming/(request_id+'.json')
                if not path.exists():continue
                C.need(path.stat().st_size<=65536,'FINITE_DISPATCH_CONTROL_MESSAGE');store.reserve(path.stat().st_size+4096)
                request_ref=C.Small.pin_small(path);r=C.small(request_ref)
                C.need(r['schema']=='PPRIME_ALPHA_DISPATCH_CLAIM_REQUEST_V1' and r['request_id']==request_id
                  and r['dispatch_slot']==slot and r['slot_sequence']==sequences[slot]
                  and r['subset_manifest_reference']==binding['portable_manifest_reference'],'EXACT_NEXT_IMMUTABLE_SLOT_REQUEST')
                key=r['physical_key'];C.need(key in allow,'CPU_EXPORTED_DISPATCH_ALLOWLIST_ONLY')
                auth_ref=allow[key];auth=C.small(auth_ref);C.validate_authorization(auth,manifest,key)
                C.need(r['dispatch_authorization_reference']==auth_ref and r['packet_reference']==auth['packet_reference']
                  and r['record_id']==auth['record_id'] and r['pair_sha256']==auth['pair_sha256']
                  and r['original_protocol_reference']==auth['original_protocol_reference']
                  and r['prepared_header_reference']==auth['prepared_header_reference'],'CPU_AUTHORITY_NOT_LOGIN_SCIENCE_RECOMPUTATION')
                foreign=r['alpha_execution'];parent={k:foreign[k] for k in alpha}
                C.need(parent==alpha and type(foreign['worker_pid'])is int and foreign['worker_pid']>0
                  and str(foreign['worker_ticks']).isdecimal(),'EXACT_FOREIGN_ALPHA_IDENTITY')
                claim_ref=None;status=None
                if r['action']=='SETTLE':
                    prior=active.get(slot);C.need(prior is not None and prior['key']==key and prior['foreign']==foreign
                      and r['claim_reference']==prior['claim'] and r['outcome'] in ('CLOSED','UNKNOWN'),
                      'SETTLE_EXACT_OWN_ALPHA_DISPATCH_ONLY')
                    claim_ref=prior['claim']
                    store.json(out/'settlements'/(request_id+'.json'),{'request_reference':request_ref,'outcome':r['outcome'],
                      'claim_reference':claim_ref,'Alpha_outcome_self_report_not_scientific_QA':True,'global_claim_never_released':True})
                    if r['outcome']=='CLOSED':del active[slot];status='SETTLED'
                    else:stop=stop or 'CLAIMED_UNKNOWN_NO_RETRY_OR_RELEASE';status='UNKNOWN_RETAINED'
                elif r['action']=='CLAIM':
                    C.need(slot not in active and key not in seen,'NO_SECOND_CLAIM_OR_RETRY_IN_THIS_RELAY')
                    worker=workers.get(slot)
                    if stop is None and (not live or worker is None):continue
                    ready=live and stop is None and worker is not None and worker['worker_pid']==foreign['worker_pid']
                    ready=ready and str(worker['worker_ticks'])==str(foreign['worker_ticks'])
                    if not ready:status='STOP'
                    else:
                        C.need(len(active)<16,'AT_MOST16_IN_FLIGHT_FOREIGN_DISPATCHES')
                        target=pathlib.Path(auth['original_ledger_path'])
                        value={'record_id':r['record_id'],'record_once_key':key,'pair_sha256':r['pair_sha256'],
                          'prepared2000_reference':r['prepared_header_reference'],'original_protocol_reference':r['original_protocol_reference'],
                          'selected_protocol_reference':r['original_protocol_reference'],'job_id':foreign['job_id'],'boot_id':foreign['boot_id'],
                          'uid':1278,'native_uid':1264,'execution_endpoint':C.ALPHA_ENDPOINT,'dispatch_slot':slot,
                          'claim_kind':'MAIN_AUTHORITY_FOR_FOREIGN_ALPHA_DISPATCH_V1','claim_writer':writer,
                          'foreign_execution':foreign,'dispatch_authorization_reference':auth_ref,'relay_binding_reference':binding_ref,
                          'global_pilot_once':binding['external_assignment_reference'],'native_return_claimed':False,
                          'output':binding['alpha_output_root']+'/records/'+key}
                        try:claim_ref=OriginalIO.claim_create(target,value,store);status='CLAIMED'
                        except FileExistsError:
                            claim_ref=Q.pin(target);old=C.small(claim_ref)
                            C.need(old['record_once_key']==key and old['pair_sha256']==r['pair_sha256'],'EXISTING_ONCE_IDENTITY_NO_ESCAPE')
                            status='ALREADY_CONSUMED'
                        seen.add(key)
                        if status=='CLAIMED':active[slot]={'key':key,'claim':claim_ref,'foreign':foreign}
                else:raise ValueError('ONLY_CLAIM_OR_SETTLE_SMALL_METADATA_ACTIONS')
                response={'schema':'PPRIME_ALPHA_DISPATCH_CLAIM_RESPONSE_V1','request_id':request_id,'physical_key':key,
                  'status':status,'claim_reference':claim_ref,'claim_sha256':claim_ref['sha256'] if claim_ref else None,
                  'alpha_claim_locator':dict(claim_ref,path=binding['alpha_mailbox_root']+'/claims/'+key+'.json') if claim_ref else None,
                  'main_relay_execution':writer,'foreign_execution':foreign,'dispatch_authorization_reference':auth_ref,
                  'global_claim_never_released':True,'scientific_PASS':False}
                response_ref=store.json(out/'responses'/(request_id+'.json'),response);sequences[slot]+=1;replies+=1
                try:transport.push(request_id,response_ref,claim_ref)
                except (OSError,ValueError,subprocess.SubprocessError):
                    stop=stop or 'REPLY_TRANSPORT_UNKNOWN_CLAIM_CONSUMED_NO_RETRY';break
            if stop and not active:break
            if len(seen)==len(allow) and not active:break
            time.sleep(binding['poll_seconds'])
    finally:
        store.json(out/'receipt.json',{'schema':'PPRIME_ALPHA_METADATA_RELAY_RECEIPT_V1','binding_reference':binding_ref,
          'claim_writer':writer,'reply_count':replies,'stop_reason':stop or 'ROOT_FINITE_RELAY_LEASE_ENDED',
          'remaining_claimed_UNKNOWN':list(active.values()),'all_global_claims_permanent':True,
          'scientific_DATA_opened':False,'scientific_value_or_physical_key_computed':False,
          'Slurm_Parent_created':False,'scientific_PASS':False,'transport_calls':transport.calls})
        fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)

if __name__=='__main__':main()
