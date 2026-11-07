"""Three synthetic boundaries; never original DATA, live HTTP or native QM."""
import collections,hashlib,json,tempfile,unittest
from pathlib import Path
from . import contract as C,projection as P,runtime as I,acquisition as A,atoms
WORKSPACE=None

class SyntheticBudget:
    def check(self,*args,**kwargs):pass
    def charge(self,n):C.need(type(n)is int and n>=0,'SYNTHETIC_IO_POSITIVE_CHARGE')

def quota_guard_boundaries(case):
    guard=I.QuotaGuard;expected={'path':'/synthetic/identity.json','bytes':1,'sha256':'a'*64}
    class Clock:
        def __init__(self):self.wall=100.;self.tick=0.;self.waits=[]
        def wall_time(self):return self.wall
        def monotonic(self):return self.tick
        def wait(self,n):self.waits.append(n);self.wall+=n;self.tick+=n
    class Client:
        def __init__(self,snapshot,outcomes):self.last=dict(snapshot);self.identity=expected;self.outcomes=list(outcomes);self.calls=0
        def observe(self):
            self.calls+=1;value=self.outcomes.pop(0)
            if isinstance(value,Exception):raise value
            self.last=dict(self.last,free_bytes=300000000000);return self.last
    snapshot={'identity_reference':expected,'provider_status':'RUNNING','observed_unix_seconds':100.5,'publisher_expires_unix_seconds':200.}
    def observed(client,clock,record):
        return guard.observe(client,expected_identity_reference=expected,record=record,
          wall_clock=clock.wall_time,monotonic=clock.monotonic,wait=clock.wait)
    for sample in (100.5,99.5):
        clock=Clock();events=[];client=Client(dict(snapshot,observed_unix_seconds=sample),[ValueError(guard.TIME_ERROR),True])
        case.assertEqual(observed(client,clock,events.append)['free_bytes'],300000000000);case.assertEqual(client.calls,2)
        case.assertEqual(events[-1]['phase'],'SECOND_ORIGINAL_CLIENT_ACCEPTED');case.assertLessEqual(sum(clock.waits),1.1)
    client=Client(snapshot,[True]);events=[];observed(client,Clock(),events.append);case.assertEqual((client.calls,len(events)),(1,0))
    for changed in ({'observed_unix_seconds':101.01},{'observed_unix_seconds':-21.},
      {'publisher_expires_unix_seconds':99.},{'provider_status':'STOPPED'},
      {'identity_reference':dict(expected,sha256='b'*64)}):
        client=Client(dict(snapshot,**changed),[ValueError(guard.TIME_ERROR),True]);events=[]
        with case.assertRaisesRegex(ValueError,guard.TIME_ERROR):observed(client,Clock(),events.append)
        case.assertEqual(client.calls,1);case.assertFalse(events[0]['eligible_for_one_original_client_reread'])
    client=Client(snapshot,[ValueError('OTHER_ORIGINAL_ERROR'),True]);events=[]
    with case.assertRaisesRegex(ValueError,'OTHER_ORIGINAL_ERROR'):observed(client,Clock(),events.append)
    case.assertEqual((client.calls,len(events)),(1,0))
    client=Client(snapshot,[ValueError(guard.TIME_ERROR),ValueError('SECOND_ORIGINAL_REJECT')]);events=[]
    with case.assertRaisesRegex(ValueError,'SECOND_ORIGINAL_REJECT'):observed(client,Clock(),events.append)
    case.assertEqual(client.calls,2);case.assertEqual(events[-1]['phase'],'SECOND_ORIGINAL_CLIENT_FAILED_STOP')
    def failed_record(event):raise OSError('PERSIST_FAILED')
    client=Client(snapshot,[ValueError(guard.TIME_ERROR),True])
    with case.assertRaisesRegex(OSError,'PERSIST_FAILED'):observed(client,Clock(),failed_record)
    case.assertEqual(client.calls,1)
    class Overshoot(Clock):
        def wait(self,n):super().wait(n+1.)
    client=Client(snapshot,[ValueError(guard.TIME_ERROR),True]);events=[]
    with case.assertRaisesRegex(ValueError,guard.TIME_ERROR):observed(client,Overshoot(),events.append)
    case.assertEqual(client.calls,1);case.assertEqual(events[-1]['phase'],'NO_REREAD_AFTER_WAIT_GUARD')

class Boundaries(unittest.TestCase):
    def test_original_atoms_inverse_and_complete17_census_not39633(self):
        atoms.proof();self.assertEqual(len(C.NAMES),17)
        local={k:v[1] for k,v in C.LOCAL.items()};csv={k:v[1] for k,v in C.CSV.items()}
        value=P.mass(local,csv,57480,C.IDS,{'QM7':7165,'QM9':133885,'QM7b':7211});self.assertEqual(value['CSV6_physical_rows'],1162144)
        with self.assertRaises(ValueError):P.mass(local,csv,39633,C.IDS,{'QM7':7165,'QM9':133885,'QM7b':7211})
        with self.assertRaises(ValueError):P.mass(local,{k:v for k,v in csv.items() if k!='toxcast'},57480,C.IDS,{'QM7':7165,'QM9':133885,'QM7b':7211})
        for n in (True,0,-1):
            with self.assertRaises(ValueError):C.triple({'path':'/synthetic/data','bytes':n,'sha256':'a'*64})
        quota_guard_boundaries(self)

    def test_true_empty_span_short_smiles_and_original_atoms_fallback(self):
        from rdkit import Chem
        source={'source_id':'hiv','source_row_ordinal':1,'role':'ALLSPLITS','field_count':1,'header_columns':3,
          'source_offset':0,'source_record_bytes':1,'source_record_sha256':hashlib.sha256(b'\n').hexdigest(),
          'identity_fields':{'0':{'literal_column_name':'smiles','state':'EMPTY','text':''}}}
        def row(s):return {'source_id':'hiv','source_row_ordinal':1,'role':'ALLSPLITS','physical_identity':'hiv:1','source_identity_json':json.dumps(s),
          **{k:s[k] for k in ('source_offset','source_record_bytes','source_record_sha256')},
          'key_observation_json':json.dumps({'source':s,'physical_identity':'hiv:1','SMILES_derived_full_keys':[],'WP5_keys':[]}),'full_keys':[],'WP5_keys':[]}
        ref={'path':'/synthetic/normalized.parquet','bytes':1,'sha256':'a'*64}
        values,e=P.csv_row(row(source),ref,Chem);self.assertEqual(values,[]);self.assertTrue(e['nonmolecular'])
        short={**source,'source_record_bytes':4,'source_record_sha256':hashlib.sha256(b'CCO\n').hexdigest(),
          'identity_fields':{'0':{'literal_column_name':'smiles','state':'PRESENT','text':'CCO'}}}
        values,e=P.csv_row(row(short),ref,Chem);self.assertFalse(e['nonmolecular']);self.assertEqual(e['unresolved'],0)
        self.assertEqual(values[0]['non_h_composition'],[[6,2],[8,1]]);self.assertEqual(values[0]['inchikeys'],[])
        blank_with_ID={**source,'identity_fields':{**source['identity_fields'],'1':{'literal_column_name':'mol_id','state':'PRESENT','text':'ID'}}}
        _,e=P.csv_row(row(blank_with_ID),ref,Chem);self.assertFalse(e['nonmolecular']);self.assertEqual(e['unresolved'],1)

    def test_exact_entry_ligand_only_and_original_strict_IO_readback(self):
        component={'chem_comp':{'id':'ABC','formula':'C2 H6 O'}}
        response={'data':{'entry':{'rcsb_id':'1ABC','nonpolymer_entities':[{'nonpolymer_comp':component}]}}}
        self.assertEqual(A.component(response,'1abc','ABC'),component)
        with self.assertRaises(ValueError):A.component(response,'1abc','XYZ')
        with self.assertRaises(ValueError):A.component(response,'2abc','ABC')
        C.need(WORKSPACE is not None,'ACTUAL_PARENT_FIXTURE_DIRECTORY')
        with tempfile.TemporaryDirectory(prefix='synthetic_mn17_',dir=WORKSPACE) as tmp:
            root=Path(tmp);writer=I.Lines(root/'synthetic.jsonl',SyntheticBudget());row=P.strict('QM7','synthetic:0',[],[[6,2],[8,1]])
            writer.append(row);ref=writer.close();read=I.readback(ref,['all'],['QM7'],lambda:None)
            self.assertEqual(read['rows'],1);self.assertTrue(read['all_rows_reparsed_with_original_identity_keys'])
            changed=dict(ref,sha256='0'*64)
            with self.assertRaises(ValueError):I.readback(changed,['all'],['QM7'],lambda:None)
            import pyarrow as pa,pyarrow.parquet as pq
            path=root/'synthetic.parquet';pq.write_table(pa.Table.from_pylist([{'source_id':'original_synthetic_IO_seam'}]),path)
            pr=I.data_pin(path,[root],check=lambda:None)
            self.assertEqual(list(I.parquet(pr,{'data_references':[pr]},SyntheticBudget())),[(0,{'source_id':'original_synthetic_IO_seam'})])
            # Exercise the actual production recorder without constructing a
            # resource Client or observing/reading any original DATA.
            budget=object.__new__(I.Budget);budget.cap=C.CAP;budget.written=0
            budget.quota_guard_events=root/'quota_guard_events';budget.quota_guard_events.mkdir();budget.quota_guard_event_references=[]
            event={'schema':'FINITE_QUOTA_NEAR_CLOCK_REREAD_EVENT_V1','phase':'SYNTHETIC_PERSISTENCE_BOUNDARY'}
            budget.record_quota_guard_event(event);budget.record_quota_guard_event(event)
            refs=budget.quota_guard_event_references;self.assertEqual(len(refs),2);self.assertNotEqual(refs[0]['path'],refs[1]['path'])
            self.assertEqual(budget.written,sum(r['bytes'] for r in refs))
            for item in refs:
                raw=Path(item['path']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),item['sha256']);self.assertEqual(json.loads(raw),event)
