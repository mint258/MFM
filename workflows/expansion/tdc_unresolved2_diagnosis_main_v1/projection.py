"""Bounded journal pairing and literal ZIP-row binding; no chemical calls."""
import collections,hashlib,json
from workflows.expansion.identity_v2.projection_v2 import full_keys
from workflows.expansion.common import wp5_key
from workflows.expansion.tdc_zip44_identity_main_v1.projection import IdentityCSV,grammar_proof
from . import contract as C


def dump(value):return (json.dumps(value,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def digest(value):return hashlib.sha256(dump(value)).hexdigest()
def location(source):return source['member_name'],source['physical_record_ordinal']


class Journal:
    def __init__(self,counts,states):
        self.counts=dict(counts);self.expected_states=dict(states);self.sources={};self.finished=set();self.states=collections.Counter()
        self.source_counts=collections.Counter();self.result_counts=collections.Counter();self.targets={};self.lines=0
    def feed(self,raw,offset):
        C.Q.need(0<len(raw)<=C.LINE_CAP and raw.endswith(b'\n'),'COMPLETE_BOUNDED_ORIGINAL_EVENT_LINE')
        value=json.loads(raw);kind=value['event'];self.lines+=1
        if kind=='SOURCE_ROW_DURABLE_BEFORE_WORKER_DISPATCH':source=value['source']
        else:
            C.Q.need(kind=='ORIGINAL_ROW_IDENTITY_RESULT_COMPLETE','ONLY_TWO_ORIGINAL_EVENT_TYPES');source=value['worker_observation']['result']['source']
        key=location(source);member,ordinal=key
        C.Q.need(member in self.counts and type(ordinal) is int and 0<=ordinal<self.counts[member],'ORIGINAL_MEMBER_AND_ZERO_BASED_ORDINAL')
        if kind=='SOURCE_ROW_DURABLE_BEFORE_WORKER_DISPATCH':
            C.Q.need(key not in self.sources and key not in self.finished,'NO_DUPLICATE_PHYSICAL_SOURCE_EVENT')
            self.sources[key]={'source_sha256':digest(source),'offset':offset,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
            self.source_counts[member]+=1;return
        C.Q.need(key in self.sources and key not in self.finished,'ONE_DURABLE_SOURCE_BEFORE_ONE_RESULT')
        original=self.sources.pop(key);C.Q.need(original['source_sha256']==digest(source),'ORIGINAL_SOURCE_RESULT_LITERAL_FIELD_EQUALITY')
        self.finished.add(key);self.result_counts[member]+=1;result=value['worker_observation']['result'];state=result['identity_state'];self.states[state]+=1
        keys,invalid=full_keys(result['full_InChIKeys'],strict=False)
        C.Q.need(not invalid and keys==result['full_InChIKeys'] and sorted({wp5_key(k) for k in keys})==result['WP5_keys'],'ORIGINAL_FROZEN_KEY_FORMAT_AND_WP5_RELATION_ONLY_NO_RECOMPUTATION')
        if state=='ORIGINAL_SMILES_UNRESOLVED':
            C.Q.need(not keys and result['identity_errors'] and len(self.targets)<2,'EXACT_UNRESOLVED_STATE_NEVER_RECLASSIFIED')
            self.targets[key]={'original_source_event':original,'original_result_event':{'offset':offset,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},
                'source':source,'original_result':result,'original_result_event_value':value}
    def finish(self):
        C.Q.need(not self.sources and dict(self.source_counts)==dict(self.result_counts)==self.counts
            and dict(self.states)==self.expected_states and len(self.targets)==2 and self.lines==2*sum(self.counts.values()),'ALL_SOURCE_RESULT_COUNTS_AND_EXACT_TWO_UNKNOWN_CONSERVED')
        return self.targets


def bind(row,targets,bindings):
    key=location(row)
    if key not in targets:return
    C.Q.need(key not in bindings and row==targets[key]['source'],'EXACT_ZIP_ORIGINAL_ID_DRUG_AND_ALL_SOURCE_FIELDS')
    bindings[key]={'member_name':key[0],'physical_record_ordinal':key[1],'source_field_sha256':digest(row),
        'original_Drug_ID_bytes':row['original_Drug_ID'].get('bytes'),'original_Drug_bytes':row['original_Drug'].get('bytes'),
        'identity_state_unchanged':'ORIGINAL_SMILES_UNRESOLVED','original_full_keys_unchanged':[],
        'no_alternate_SMILES_or_graph_repair':True}
