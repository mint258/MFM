"""Four stdlib source contracts; no chemistry and no production inputs."""
import copy
import hashlib
import json
import sqlite3
import unittest
from .logic import CASE,KEY,FINDINGS,authority,amend,excluded_parity,accounting_header,accounting_readback


class AmendmentTests(unittest.TestCase):
    def databases(self):
        old=sqlite3.connect(':memory:');new=sqlite3.connect(':memory:')
        for db in (old,new):
            db.executescript('CREATE TABLE excluded(kind TEXT,key TEXT,dataset TEXT,PRIMARY KEY(kind,key,dataset)) WITHOUT ROWID;'
                'CREATE TABLE constraints(rule_id TEXT PRIMARY KEY,dataset TEXT,binding TEXT NOT NULL) WITHOUT ROWID;'
                'CREATE TABLE constraint_atoms(rule_id TEXT,z INTEGER,n INTEGER,PRIMARY KEY(rule_id,z)) WITHOUT ROWID;')
        rule=dict(binding={'hold_ordinal':18,'raw':'original'},bound=[[6,3]])
        old.executemany('INSERT INTO excluded VALUES(?,?,?)',[('composition',KEY,'moleculenet'),('full','KEY_A','v1'),('wp5','KEY_B','qm9')])
        old.executemany('INSERT INTO constraints VALUES(?,?,?)',[(CASE,'moleculenet',json.dumps(rule['binding'])),
            ('case:00','moleculenet',' {"original ClinTox": "preserve exact whitespace"} ')])
        old.executemany('INSERT INTO constraint_atoms VALUES(?,?,?)',[(CASE,6,3),('case:00',6,14),('case:00',7,2),('case:00',8,7)])
        old.commit();self.addCleanup(old.close);self.addCleanup(new.close)
        return old,new,rule

    def test_private_amendment_preserves_full_keys_and_clintox_bytes(self):
        old,new,rule=self.databases();original=list(old.iterdump())
        old.execute('PRAGMA query_only=ON');old.execute('BEGIN')
        old.execute('SELECT count(*) FROM excluded').fetchone()
        result=amend(old,new,rule)
        self.assertEqual(list(old.iterdump()),original)
        self.assertEqual(result['excluded']['original_count'],3)
        self.assertEqual(result['excluded']['missing_from_original'],0)
        self.assertEqual(result['excluded']['missing_from_new'],0)
        self.assertEqual(old.execute('SELECT binding FROM constraints WHERE rule_id="case:00"').fetchone(),
                         new.execute('SELECT binding FROM constraints WHERE rule_id="case:00"').fetchone())
        self.assertEqual(new.execute('SELECT rule_id FROM constraints').fetchall(),[('case:00',)])
        self.assertTrue(result['ClinTox_binding_and_atom_rows_exactly_unchanged'])

    def test_missing_existing_composition_or_wrong_c3_rejected(self):
        for fault in ('composition','atom_count','binding'):
            old,new,rule=self.databases()
            if fault=='composition':old.execute('DELETE FROM excluded WHERE kind="composition"')
            elif fault=='atom_count':old.execute('UPDATE constraint_atoms SET n=4 WHERE rule_id=?',(CASE,))
            else:rule=copy.deepcopy(rule);rule['binding']['hold_ordinal']=17
            old.commit()
            with self.assertRaises(ValueError):amend(old,new,rule)
            self.assertEqual(new.execute('SELECT count(*) FROM constraints').fetchone(),(0,))

    def test_ordered_full_pk_comparison_detects_both_direction_changes(self):
        old,new,rule=self.databases();amend(old,new,rule)
        new.execute('DELETE FROM excluded WHERE key="KEY_A"')
        new.execute('INSERT INTO excluded VALUES("full","KEY_C","v1")');new.commit()
        with self.assertRaisesRegex(ValueError,'BOTH_DIRECTIONS_IDENTICAL'):excluded_parity(old,new)
        # Equal row counts cannot conceal a changed dataset dimension either.
        old.backup(new);new.execute('UPDATE excluded SET dataset="other" WHERE key="KEY_A"');new.commit()
        with self.assertRaisesRegex(ValueError,'BOTH_DIRECTIONS_IDENTICAL'):excluded_parity(old,new)

    def test_evidence_only_running_or_broader_scope_cannot_authorize_amendment(self):
        ref=dict(path='/gfshome/alpha/old.json',bytes=1,sha256='0'*64)
        rule=dict(rule_id=CASE,kind='NON_H_ATOM_COUNT_LOWER_BOUND',dataset='moleculenet',subdataset='PDBbind',bound=[[6,3]],binding={'hold_ordinal':18})
        parent=dict(JobIDRaw='203',State='COMPLETED',ExitCode='0:0',UID='1264',User='alpha',ElapsedRaw='37',NodeList='sonmi1',TotalCPU='00:00:00',endpoint='218.192.171.238:22',uid=1264,AllocCPUS='16')
        account=dict(schema='ROOT_ACTUAL_ALPHA_ACCOUNTING_V1',endpoint='218.192.171.238:22',uid=1264,query_returncode=0,
            raw_sacct_reference=dict(path='/gfshome/alpha/raw.sacct.txt',bytes=1,sha256='0'*64),actual_parents=[parent])
        native=dict(schema='ALPHA_MOLNET_CASE18_NATIVE_EVIDENCE_PRODUCER_V1',status='EVIDENCE_ONLY_PENDING_C0_AND_ROOT_SOURCE_REVIEW',
            source_correspondence_adopted=False,index_amendment_performed=False,global_pool_release=False,
            evidence_reference=ref,actual_source_reads_reference=ref,source_tests_reference=ref,
            profile_admission=dict(job_id='203',endpoint='218.192.171.238:22',uid=1264))
        findings={k:True for k in FINDINGS};judge={'terminals':'explicitly reviewed'}
        review=dict(schema='ROOT_MOLNET_CASE18_SOURCE_CORRESPONDENCE_ACTUAL_ACCEPTANCE_V1',status='APPROVED_CASE18_EXISTING_EXACT_COMPOSITION_COVERAGE',
            reviewer='root',endpoint='218.192.171.238:22',uid=1264,case_id=CASE,original_index_root_acceptance_reference=ref,
            original_case18_rule=rule,replacement=dict(kind='EXISTING_EXACT_NON_H_COMPOSITION',dataset='moleculenet',non_h_composition=[[6,36],[7,11],[8,12]]),
            source_review_findings=findings,COCONUT_scope_extended=False,index_amendment_performed=False,global_pool_release=False,
            original_rule_reference=dict(path='/gfshome/alpha/rules',bytes=7190,sha256='462256a904210e4dd5185af88c1f15578e164d3a6483226dc4aa7f90d4d4956c'),
            native_evidence_receipt_reference=ref,native_evidence_actual_accounting_reference=ref,observations_reference=ref,
            source_readback_reference=ref,source_tests_reference=ref,actual_parent=parent,scientific_judgment=judge)
        policy=dict(schema='ROOT_MOLNET_CASE18_SOURCE_CORRESPONDENCE_POLICY_V2',status='ADOPTED_ONLY_FOR_CASE18_EXISTING_COMPOSITION_SOURCE_COVERAGE',
            reviewer='root',endpoint='218.192.171.238:22',uid=1264,case_id=CASE,new_user_scope_exception=False,index_amendment_performed=False,
            original_case18_rule=rule,old_rule_reference=review['original_rule_reference'],native_evidence_receipt_reference=ref,
            native_evidence_actual_accounting_reference=ref,source_review_findings=findings,scientific_judgment=judge)
        old=dict(schema='PUBCHEM_ALL11_EXCLUSION_INDEX_ACTUAL_ACCEPTANCE_V1',status='APPROVED_COMPLETE_ALL11_INDEX',reviewer='root',
                 all_sources_all_splits_verified=True,original_graph_unknowns_retained=True,actual_parent={'JobIDRaw':'1885187'})
        self.assertEqual(authority(review,policy,native,account,old,ref),rule)
        for fault in ('evidence_only','running','terminals','broader_case','wrong_composition'):
            rr=copy.deepcopy(review);aa=copy.deepcopy(account)
            if fault=='evidence_only':rr['status']='EVIDENCE_ONLY_PENDING_C0_AND_ROOT_SOURCE_REVIEW'
            elif fault=='running':aa['actual_parents'][0]['State']='RUNNING'
            elif fault=='terminals':rr['source_review_findings']['terminal_correspondence_reviewed']=False
            elif fault=='broader_case':rr['case_id']='case:00'
            else:rr['replacement']['non_h_composition']=[[6,3]]
            with self.assertRaises(ValueError):authority(rr,policy,native,aa,old,ref)
        # Both actual capture formats, including retained failed202 history.
        old_columns='JobIDRaw|UID|User|State|ExitCode|ElapsedRaw|NodeList|AllocCPUS|TotalCPU'
        old_raw=(old_columns+'\n1885187|1264|alpha|COMPLETED|0:0|9855|compute-0-1|16|00:00:00\n'
                 '1885187.batch|||COMPLETED|0:0|9855|compute-0-1|16|00:00:00\n'
                 '1885187.extern|||COMPLETED|0:0|9855|compute-0-1|16|00:00:00\n').encode()
        old_parent=dict(parent,JobIDRaw='1885187',ElapsedRaw='9855',NodeList='compute-0-1')
        old_capture=dict(account,actual_parents=[old_parent],raw_sacct_reference=dict(path='/gfshome/alpha/old.sacct.txt',bytes=len(old_raw),sha256=hashlib.sha256(old_raw).hexdigest()))
        new_columns='JobIDRaw|State|ExitCode|ElapsedRaw|AllocCPUS|NodeList|UID'
        new_raw=(new_columns+'\n1885202|FAILED|1:0|16|16|sonmi1|1264\n1885203|COMPLETED|0:0|37|16|sonmi1|1264\n').encode()
        new_parents=[dict(JobIDRaw='1885202',State='FAILED',ExitCode='1:0',ElapsedRaw='16',AllocCPUS='16',NodeList='sonmi1',UID='1264',endpoint='218.192.171.238:22',uid=1264),
            dict(JobIDRaw='1885203',State='COMPLETED',ExitCode='0:0',ElapsedRaw='37',AllocCPUS='16',NodeList='sonmi1',UID='1264',endpoint='218.192.171.238:22',uid=1264)]
        new_capture=dict(schema='ROOT_ALPHA_ACTUAL_SACCT_READBACK_V1',endpoint='218.192.171.238:22',uid=1264,actual_parents=new_parents,
            raw_login_sacct_reference=dict(path='/gfshome/alpha/raw_login.sacct.txt',bytes=len(new_raw),sha256=hashlib.sha256(new_raw).hexdigest()),
            query_argv=['sacct','-j','1885202,1885203','-X','-P','--format='+new_columns.replace('|',',')],
            query_executed_on='Alpha login',review_metadata_checked_on='sonmi1')
        for capture,raw,job,has_rc in [(old_capture,old_raw,'1885187',True),(new_capture,new_raw,'1885203',False)]:
            with self.subTest(schema=capture['schema']):
                before=copy.deepcopy(capture);w=accounting_readback(capture,raw,job)
                self.assertEqual(w['query_returncode_recorded'],has_rc)
                self.assertEqual(w['query_returncode'],0 if has_rc else None)
                self.assertEqual(capture,before)
                self.assertTrue(w['all_parent_columns_exactly_matched'])
                changed=raw.replace(b'9855',b'9856') if has_rc else raw.replace(b'FAILED',b'COMPLETED')
                with self.assertRaisesRegex(ValueError,'WHOLE_BYTES_SHA'):accounting_readback(capture,changed,job)
                rebound=copy.deepcopy(capture);raw_key='raw_sacct_reference' if has_rc else 'raw_login_sacct_reference'
                rebound[raw_key].update(bytes=len(changed),sha256=hashlib.sha256(changed).hexdigest())
                with self.assertRaisesRegex(ValueError,'PARENT_COLUMN_EXACTLY'):accounting_readback(rebound,changed,job)
                broken=copy.deepcopy(capture);broken['query_returncode']=1
                with self.assertRaisesRegex(ValueError,'RETURN_CODE_MUST_BE_ZERO'):accounting_header(broken)
        self.assertEqual(accounting_readback(new_capture,new_raw,'1885203')['matched_parent_job_ids'],['1885202','1885203'])
        for field,value in [('query_argv',['sacct','-j','1885203']),('query_executed_on','compute-0-1'),('review_metadata_checked_on','Alpha login')]:
            broken=copy.deepcopy(new_capture);broken[field]=value
            with self.assertRaises(ValueError):accounting_header(broken)
        broken=copy.deepcopy(new_capture);del broken['raw_login_sacct_reference']
        with self.assertRaises(ValueError):accounting_header(broken)



if __name__=='__main__':unittest.main()
