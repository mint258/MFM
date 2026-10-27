"""CPU ordinary-source anti-join and real old-parent packet closure, no optimizer."""
import hashlib,json,pathlib,sqlite3,traceback
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as OLD
from . import contract as C,runtime as I


def coordinate_identity(row):
    import numpy as np
    xyz=np.asarray(row['coordinates'],dtype='<f8')
    C.need(xyz.ndim==2 and xyz.shape[1]==3 and xyz.shape[0]>0 and np.isfinite(xyz).all(),'FINITE_ORIGINAL_FLOAT64_COORDINATES')
    atom=row['atom_order_sha256'];C.need(type(atom) is str and len(atom)==64,'ORIGINAL_NATIVE_ATOM_ORDER_SHA')
    if row.get('atomic_numbers') is not None:
        C.need(hashlib.sha256(np.asarray(row['atomic_numbers'],dtype='<i8').tobytes()).hexdigest()==atom,'ACTUAL_ATOM_ORDER_BYTES')
        if row.get('geometry_sha256') is not None:C.need(OLD.common().geometry_sha(row['atomic_numbers'],row['coordinates'])==row['geometry_sha256'],'ORIGINAL_FULL_F64_GEOMETRY_SHA')
    # Original v6 rows lack Z. Preserve their accepted atom-order hash and exact
    # xyz bits; do not fabricate Z or claim to invert the atom-order SHA.
    return atom+':'+hashlib.sha256(xyz.tobytes()).hexdigest()


class Census:
    def __init__(self,plan,value,original,review,proof,out,budget):
        self.plan,self.value,self.original,self.review,self.proof,self.out,self.budget=plan,value,original,review,proof,pathlib.Path(out),budget
        self.db=sqlite3.connect(self.out/'census.sqlite');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE metas(k TEXT PRIMARY KEY,mid TEXT UNIQUE,meta TEXT,bid TEXT,candidate INTEGER DEFAULT 0,state TEXT DEFAULT \'UNCLASSIFIED\',evidence TEXT)')
        self.db.execute('CREATE TABLE baseline(mid TEXT,idx INTEGER,row TEXT,identity TEXT,locator TEXT,PRIMARY KEY(mid,idx))')
        self.db.execute('CREATE TABLE prior(k TEXT PRIMARY KEY,mid TEXT,evidence TEXT)')
        self.db.execute('CREATE TABLE errors(n INTEGER PRIMARY KEY AUTOINCREMENT,phase TEXT,k TEXT,error TEXT)')
        self.parents={};self.complete=False
    def check(self):C.need(self.budget.observe() is None,self.budget.stop or 'PACKED_PREFLIGHT_RESOURCE_STOP')
    def error(self,phase,key,exc):
        self.db.execute('INSERT INTO errors(phase,k,error) VALUES(?,?,?)',(phase,key,repr(exc)+'\n'+traceback.format_exc()))
        if key:self.db.execute("UPDATE metas SET state='CONFLICT_OR_UNKNOWN_NO_RETRY' WHERE k=?",(key,))
        self.db.commit()
    def load_metas(self):
        import pyarrow.parquet as pq
        path=I.verify(self.original['original_deficits'],self.check)
        for batch in pq.ParquetFile(path).iter_batches(batch_size=2048):
            self.check()
            for meta in batch.to_pylist():
                k=meta['task_key'];C.need(k==C.F.task_key(meta['molecule_id'],meta['cohort']) and meta['expected_conformers']==meta['S_conformers'],'FROZEN_ORIGINAL_META_KEY_COHORT_AND_N')
                self.db.execute('INSERT INTO metas(k,mid,meta) VALUES(?,?,?)',(k,meta['molecule_id'],C.F.canonical(meta).decode()))
            self.db.commit()
        for descriptor in self.original['batches']:
            if descriptor['batch_id'] not in self.review['candidate_batch_ids']:continue
            path=I.verify(descriptor['tasks'],self.check)
            for meta in pq.read_table(path).to_pylist():
                row=self.db.execute('SELECT meta FROM metas WHERE k=?',(meta['task_key'],)).fetchone()
                C.need(row and json.loads(row[0])==meta,'EXACT_DESCRIPTOR_META_NO_RECONSTRUCTED_MEMBERSHIP')
                self.db.execute('UPDATE metas SET bid=?,candidate=1 WHERE k=?',(descriptor['batch_id'],meta['task_key']))
            self.db.commit()
    def old_baselines(self):
        import duckdb,pyarrow as pa
        mids=[r[0] for r in self.db.execute('SELECT mid FROM metas WHERE candidate=1')]
        duck=duckdb.connect();duck.execute('SET threads='+str(self.plan['cpus']));duck.execute("SET memory_limit='12GB'")
        duck.register('wanted',pa.table({'molecule_id':mids}))
        manifest=C.metadata_ref(self.value['sprime_manifest'])
        sources=[{'reference':C.F.triple(r),'authority_reference':self.value['sprime_manifest'],'native_index_domain':'ORIGINAL_SPRIME_V6'}
            for r in manifest['references'] if r['kind']=='conformers']+self.review.get('ordinary_additional_parquet_sources',[])
        try:
            for source in sources:
                ref=source['reference'];path=I.verify(ref,self.check)
                query='SELECT s.* FROM read_parquet('+C.F.q(str(path))+') s JOIN wanted USING(molecule_id) WHERE s.status=\'SUCCESS\' AND s.converged IS TRUE ORDER BY s.molecule_id,s.sprime_conf_idx'
                for chunk in duck.execute(query).fetch_record_batch(1024):
                    self.check()
                    for row in chunk.to_pylist():
                        mid=row['molecule_id'];key=self.db.execute('SELECT k FROM metas WHERE mid=?',(mid,)).fetchone()[0]
                        try:
                            idx=row['sprime_conf_idx'];C.need(type(idx) is int and idx>=0,'ACTUAL_NATIVE_SPRIME_INDEX')
                            fingerprint=coordinate_identity(row);old=self.db.execute('SELECT identity,row FROM baseline WHERE mid=? AND idx=?',(mid,idx)).fetchone()
                            if old:C.need(old[0]==fingerprint and json.loads(old[1])==row,'CONFLICTING_OLD_OR_LATE_NATIVE_INDEX_NO_RENUMBER')
                            else:self.db.execute('INSERT INTO baseline VALUES(?,?,?,?,?)',(mid,idx,C.F.canonical(row).decode(),fingerprint,C.F.canonical(source).decode()))
                        except Exception as exc:self.error('BASELINE_NATIVE_IDENTITY',key,exc)
                    self.db.commit()
        finally:duck.close()
    def record_prior(self,key,mid,evidence):
        old=self.db.execute('SELECT evidence FROM prior WHERE k=?',(key,)).fetchone()
        if old:
            previous=json.loads(old[0]);C.need(previous.get('package_reference')==evidence.get('package_reference'),'MULTIPLE_ATTEMPT_OUTPUTS_FOR_ONE_SHARED_KEY')
        else:self.db.execute('INSERT INTO prior VALUES(?,?,?)',(key,mid,C.F.canonical(evidence).decode()))
    def historical_imports(self):
        # This is DATA despite being small JSON. It already binds the original
        #336 pilot/recovery union including2UNKNOWN; never generate replacement.
        I.verify(self.original['pilot_imports'],self.check);imports=I.read_json(self.original['pilot_imports'],C.F.CAP)
        for row in imports:
            self.check();key=row['task_key'];mid=row['molecule_id'];ledger=C.F.ledger_path(key)
            C.need(ledger.exists() and I.read_json(I.sha_file(ledger))==row,'ORIGINAL320_IMPORTED_SHARED_LEDGER_UNCHANGED')
            package=row['package_reference']
            if package is not None:
                packet=OLD.read_packet(package,self.value);C.need(packet['summary']['molecule_id']==mid and packet['summary']['seed']==row['seed'],'ACTUAL_HISTORICAL_PACKAGE_MID_AND_SEED')
            evidence={'origin':'HISTORICAL_IMPORTED_ATTEMPT','ledger_reference':I.sha_file(ledger),'package_reference':package,
                'scientific_status':row['scientific_status'],'science_result_observed':row['science_result_observed'],
                'execution_resolution':row['execution_resolution'],'historical_parent_ids':row['historical_parent_ids'],
                'original_closure_reference':row['closure_reference'],'worker_start_not_invented':True}
            self.record_prior(key,mid,evidence)
        self.db.commit()
    def registered_origins(self):
        for entry in self.review['registered_runs']:
            self.check();request=C.metadata_ref(entry['request_reference']);sub=C.metadata_ref(entry['submission_reference']);jid=str(sub['job_id'])
            C.need(C.small_pin(entry['accounting_reference']['path'])==entry['accounting_reference'],'ACTUAL_ORIGINAL_ACCOUNTING_REFERENCE_PIN')
            ar,av,parents=C.G.account(entry['accounting_reference']['path'],[jid]);self.parents[jid]={'actual':parents[jid],'accounting_reference':ar,'raw_reference':av['raw_sacct_reference']}
            argv=request['execution_argv'];root=pathlib.Path(argv[argv.index('--output')+1])
            if '--prepared' not in argv:
                # Explicit old2+14 recovery scope is consumed through the
                # canonical320 historical import/closed336 authority, not
                # reinterpreted as a formal500 batch or another retry grant.
                C.need(request['scope_key']=='sprime_recovery_auto_memory_2plus14','ONLY_EXACT_HISTORICAL_RECOVERY_PROTOCOL')
                continue
            _,header=C.meta(argv[argv.index('--prepared')+1],C.F.SCHEMAS['prepared']);tasks_ref=header['tasks']
            I.verify(tasks_ref,self.check)
            expected={}
            with pathlib.Path(tasks_ref['path']).open() as stream:
                for line in stream:
                    task=json.loads(line);key=task['meta']['task_key'];C.need(key not in expected,'DUPLICATE_ORIGINAL_PREPARED_KEY');expected[key]=task
            # Root expressly declared this actual registered directory as
            # transitive output authority, including failed/TIMEOUT prefixes.
            paths=set()
            for name in ('packets','starts','dispatch','errors'):
                directory=root/name
                if directory.exists():
                    C.need(not directory.is_symlink(),'NO_OLD_OUTPUT_SYMLINK')
                    for p in directory.iterdir():
                        if p.is_file():
                            key=p.name[:64];C.need(len(key)==64 and all(c in '0123456789abcdef' for c in key)
                                and p.name[64:].startswith(('.json','.json.gz')),'UNKNOWN_OLD_NATIVE_OUTPUT_FILENAME')
                            paths.add(key) # includes partial/pending files as evidence, never a completed packet.
            C.need(paths<=set(expected),'OLD_OUTPUT_EVIDENCE_OUTSIDE_REGISTERED_PREPARED_KEYS')
            for key,task in expected.items():
                self.check();mid=task['meta']['molecule_id'];ledger=C.F.ledger_path(key);packet_path=root/'packets'/(key+'.json.gz')
                any_output=key in paths
                if not ledger.exists():
                    if any_output:
                        self.record_prior(key,mid,{'origin':'REGISTERED_PARENT','owner_parent':self.parents[jid],
                            'execution_resolution':'ORPHAN_OUTPUT_WITHOUT_CLAIM_NO_RETRY','package_path_observed':str(packet_path) if packet_path.exists() else None,
                            'source_registration':entry,'science_result_observed':False,'package_reference':None})
                    continue
                lr=I.sha_file(ledger);dispatch=I.read_json(lr)
                if str(dispatch.get('job_id'))!=jid:continue # the true owner is classified separately; never redispatch.
                evidence={'origin':'REGISTERED_PARENT','owner_parent':self.parents[jid],'source_registration':entry,'ledger_reference':lr,
                    'task_sha256':C.F.sha_value(task),'prepared_reference':C.G.meta_pin(argv[argv.index('--prepared')+1]),
                    'science_result_observed':False,'scientific_status':None,'package_reference':None,'execution_resolution':'CONSUMED_UNKNOWN_NO_RETRY'}
                try:
                    C.need(dispatch['schema']=='SPRIME_DISPATCH_INTENT_V3' and dispatch['task_key']==key and dispatch['molecule_id']==mid
                        and dispatch['task_sha256']==C.F.sha_value(task) and dispatch['seed']==C.F.seed_for(mid,task['meta']['cohort']=='retry_once'),
                        'EXACT_OLD_REAL_DISPATCH_TASK_SEED')
                    if packet_path.exists():
                        ref=I.sha_file(packet_path,self.value['packet_compressed_limit_bytes'],self.check);packet=OLD.read_packet(ref,self.value)
                        start=packet.get('formal_start');start_path=root/'starts'/(key+'.json')
                        C.need(start_path.exists() and I.read_json(I.sha_file(start_path))==start and start['dispatch_reference']==lr
                            and start['job_id']==jid and start['task_sha256']==dispatch['task_sha256']
                            and packet['summary']['molecule_id']==mid and packet['summary']['seed']==dispatch['seed'],'ORIGINAL_DURABLE_PACKET_START_TASK_SOURCE_BINDING')
                        evidence.update(package_reference=ref,science_result_observed=True,scientific_status=packet['summary']['status'],
                            execution_resolution='DURABLE_PACKAGE_VALIDATED_UNDER_ORIGINAL_PARENT',start_reference=I.sha_file(start_path),
                            actual_float64_geometry_SHA_readback=True)
                except Exception as exc:evidence['validation_error']=repr(exc);self.error('OLD_PACKET_CLOSURE',key,exc)
                self.record_prior(key,mid,evidence)
            self.db.commit()
    def classify(self):
        for key,mid,target_meta,state,candidate in self.db.execute('SELECT k,mid,meta,state,candidate FROM metas').fetchall():
            self.check();meta=json.loads(target_meta)
            if state=='CONFLICT_OR_UNKNOWN_NO_RETRY':continue
            prior=self.db.execute('SELECT evidence FROM prior WHERE k=?',(key,)).fetchone()
            ledger=C.F.ledger_path(key)
            if prior:
                value=json.loads(prior[0]);status='OLD_DURABLE_RESULT' if value['science_result_observed'] else 'CONSUMED_UNKNOWN_NO_RETRY'
                self.db.execute('UPDATE metas SET state=?,evidence=? WHERE k=?',(status,prior[0],key));continue
            if ledger.exists():
                lr=I.sha_file(ledger);claim=I.read_json(lr);owner=str(claim.get('job_id'))
                C.need(owner in self.parents or claim.get('schema')=='SPRIME_HISTORICAL_ATTEMPT_IMPORTED_V3',
                    'CLAIM_OWNER_NOT_IN_ROOT_ACTUAL_TERMINAL_INVENTORY_GLOBAL_HOLD')
                self.db.execute("UPDATE metas SET state='CONSUMED_UNKNOWN_NO_RETRY',evidence=? WHERE k=?",(C.F.canonical({'ledger_reference':lr,'owner':owner}).decode(),key));continue
            if meta['cohort']=='unsupported':
                self.db.execute("UPDATE metas SET state='EXCLUDED_ORIGINAL_UFF_UNSUPPORTED' WHERE k=?",(key,));continue
            if not candidate:self.db.execute("UPDATE metas SET state='OUTSIDE_REMAINDER_UNSTARTED_OR_UNRESOLVED' WHERE k=?",(key,));continue
            if meta['cohort']=='unsupported':status='EXCLUDED_ORIGINAL_UFF_UNSUPPORTED'
            else:
                n=self.db.execute('SELECT count(*) FROM baseline WHERE mid=?',(mid,)).fetchone()[0]
                status='ALREADY_SUFFICIENT_ORDINARY_SPRIME_NO_NEW_ATTEMPT' if n>=meta['expected_conformers'] else 'ELIGIBLE_UNCLAIMED_AFTER_ORDINARY_SOURCE_CENSUS'
            self.db.execute('UPDATE metas SET state=? WHERE k=?',(status,key))
        self.db.commit();self.complete=True
        return {'schema':'ACTUAL_PACKED_CPU_ORDINARY_CENSUS_V1','complete':True,
            'state_counts':dict(self.db.execute('SELECT state,count(*) FROM metas GROUP BY state')),
            'candidate_state_counts':dict(self.db.execute('SELECT state,count(*) FROM metas WHERE candidate=1 GROUP BY state')),
            'old_source_identity_definition':'original_atom_order_SHA_plus_exact_float64_xyz_bits_not_invented_atomic_numbers',
            'N1_Pprime_extras_counted_as_ordinary':False,'new_optimizer_calls':0,'once_absence_is_not_the_only_eligibility_test':True,
            'old_parent_states':self.parents,'all_errors_retained_in_job_owned_SQLite':True,'fake_child_C0_or_old_parent_upgrade':False}
