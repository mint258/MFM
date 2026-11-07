"""Independent peptide source evidence; never changes or adopts an exclusion rule."""
import argparse
import collections
import importlib
import inspect
import io
import json
import os
from pathlib import Path
import sys
import traceback
import unittest
from workflows.expansion.alpha_runtime_v1 import common as Q
from workflows.expansion.alpha_runtime_v1.guard import Guard
from workflows.expansion.alpha_runtime_v1.profile import admit as profile_admit
from workflows.expansion.coconut_alpha_cached735_v1 import support as S
from .parse import COMPOSITION,SEQUENCE,need,observe_cif,formula_field
from .reads import Reads,triple,key

A=Path('/gfshome/alpha/codex_data_v1_20261026')
SCOPE='molnet_case18_native_evidence_v1'


def admit(plan,proof,pp,sp):
    authority=profile_admit(plan,minimum_workers=16)
    need(plan['schema']=='ALPHA_MOLNET_CASE18_NATIVE_EVIDENCE_PLAN_V1'
        and plan['scope_key']==proof['request']['scope_key']==SCOPE
        and proof['request']['producer_plan_reference']==S.pin(pp)
        and proof['request']['execution_argv']==plan['execution_argv']
        and plan['execution_argv'][-4:]==sys.argv[-4:]==['--plan',str(pp),'--startup-proof',str(sp)]
        and proof['endpoint']==plan['endpoint']=='218.192.171.238:22'
        and proof['uid']==plan['uid']==os.getuid()==1264
        and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID')
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'EXACT_ALPHA_EVIDENCE_JOB_SCOPE_ARGV_BOOT')
    budget=json.loads(S.read(plan['reviewed_storage_budget_reference'],2<<20))
    need(budget['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2' and budget['reviewer']=='root'
         and budget['endpoint']=='218.192.171.238:22' and budget['uid']==1264
         and budget['quota_root']=='/gfshome/alpha'
         and plan['output_scope_root']=='/gfshome/alpha/pubchem_expansion_20261103/bulk'
         and plan['output_cap_bytes']==budget['scope_total_caps_bytes']['bulk']
         and plan['other_future_reserved_bytes']==budget['other_future_reserved_bytes_for_each_scope']['bulk']
         and plan['minimum_free_bytes']==budget['minimum_free_after_all_future_bytes'],
         'ACTUAL_REVIEWED_BULK_BUDGET_NOT_HARD_CODED_OLD_REVISION')
    declared=proof['request']['source_references']
    for p in [*Path(__file__).parent.glob('*.py'),Path(S.__file__)]:
        need(S.pin(p) in declared,'CURRENT_PINNED_EVIDENCE_SOURCE')
    for ref in plan['code_references']:S.read(ref,2<<20)
    return authority


def functions(plan,proof):
    need(plan['original_alpha_code_root']==str(A/'code'),'EXACT_ORIGINAL_ALPHA_CODE_ROOT')
    sys.path.append(plan['original_alpha_code_root'])
    N=importlib.import_module('secondary_moleculenet_native4_identity_v1.native')
    P=importlib.import_module('workflows.expansion.identity_v2.projection_v2')
    C=importlib.import_module('workflows.expansion.coconut735_recovery_v1.consumer')
    borrowed=(N.elements,N.F.sdf_metadata,N.F.mol2_metadata,P.native_composition,C.identity_keys,C.index_header)
    objects={}
    for f in borrowed:
        ref=S.pin(inspect.getsourcefile(f))
        need(ref in proof['request']['source_references'] and ref in plan['code_references'],
             'DECLARED_UNCHANGED_ORIGINAL_COUNT_OR_V3_FUNCTION '+f.__qualname__)
        objects[f.__module__+'.'+f.__qualname__]=dict(source_reference=ref,
            filename=f.__code__.co_filename,first_line=f.__code__.co_firstlineno)
    return N,P,C,objects


def old_index(r,plan,C):
    review=r.json(plan['old_index_root_acceptance_reference'])
    need(review['schema']=='PUBCHEM_ALL11_EXCLUSION_INDEX_ACTUAL_ACCEPTANCE_V1'
        and review['status']=='APPROVED_COMPLETE_ALL11_INDEX' and review['reviewer']=='root'
        and review['all_sources_all_splits_verified'] is True
        and review['original_graph_unknowns_retained'] is True,'ACTUAL_ACCEPTED_187_FULL_SOURCE_AUTHORITY')
    receipt=C.index_header(r.json(review['index_receipt']))
    account=r.json(review['actual_accounting_reference'])
    parent=review['actual_parent']
    need(str(parent['JobIDRaw'])=='1885187' and parent['State']=='COMPLETED' and parent['ExitCode']=='0:0'
        and str(parent['UID'])=='1264'
        and parent['endpoint']=='218.192.171.238:22' and parent['uid']==1264
        and any(str(x.get('JobIDRaw'))=='1885187' and x.get('State')=='COMPLETED'
             and x.get('ExitCode')=='0:0' and str(x.get('UID'))=='1264' for x in account['actual_parents'])
        and receipt['database']==review['closed_database'],'ACTUAL187_C0_NOT_NEW_EVIDENCE_C0')
    consumed=r.json(review['source_replica_readback'])
    need(len(consumed['files'])==review['native_full_SHA_consumption_entries']==577
        and all(x['whole_SHA256_verified'] is True and x['actual_uid']==1264 for x in consumed['files']),
        'ORIGINAL577_ACTUAL_WHOLE_SHA_READS_REUSED_HONESTLY')
    return review,receipt,consumed


def inherited_reference(actual,consumed):
    found=[x for x in consumed['files'] if triple(x['replica_reference'])==triple(actual)]
    need(len(found)==1,'EXACT187_LOGICAL_TO_CURRENT_REPLICA_SOURCE_BINDING')
    return found[0]['source_reference']


def segments(r,ref,items):
    out=[]
    with r.held(ref) as (take,p,db):
        for item in items:
            raw=take(item['offset'],item['bytes'],item['sha256'])
            out.append((item,raw))
    return out


def original(r,bundle,consumed,N,P,C):
    b=bundle['original_alpha_bound_source_segments']
    old=b['source_oldcase18']
    rules=r.read(inherited_reference(next(
        x['current_actual_reference'] for x in bundle['actual_index1885187_prior_whole_body_authorities']
        if x['current_actual_reference']['sha256']=='462256a904210e4dd5185af88c1f15578e164d3a6483226dc4aa7f90d4d4956c'),consumed))
    found=[x for x in (json.loads(l) for l in rules.splitlines()) if x['rule_id']=='case:18']
    need(found==[old] and old['bound']==[[6,3]] and old['binding']['hold_ordinal']==18,'EXACT_ORIGINAL_CASE18_C3_RULE_RETAINED')
    loc=old['binding']['original_source_locator']
    with r.held(loc['source_reference']) as (take,p,db):
        prior=json.loads(take(loc['offset_bytes'],loc['line_bytes'],loc['line_sha256']))
    need(prior==old['binding']['original_HOLD']['evidence']['original_event'],'EXACT_ORIGINAL_1PTS_CASE18_HOLD_RECORD_NOT_INDEX_NAME_ONLY')
    old_policy=r.json(b['source_old_policy_original_reference'])
    need(old_policy['peptide_case']==b['source_old_policy_peptide_case'],'ORIGINAL_MINIMAL_POLICY_LITERAL_RETAINED_NOT_EXPANDED')
    profile=r.json(b['profile_receipt_reference']);full=r.json(b['full_inventory_receipt_reference'])
    need(profile['job_id']=='1884856' and profile['uid']==1264 and profile['endpoint']=='218.192.171.238:22'
        and full['job_id']=='1884866' and full['uid']==1264 and full['endpoint']=='218.192.171.238:22',
        'ORIGINAL_ALPHA_NATIVE_PROVENANCE_NOT_MAIN_UID')
    union=b['original_1slg_union'];union_ref=inherited_reference(union['current_replica_reference'],consumed)
    row=json.loads(segments(r,union_ref,[union])[0][1])
    need(row==union['row'] and row['entity_identity']==['PDB_ID_ALL_COMPONENTS','1slg'],'EXACT_1SLG_UNION_SOURCE_ROW')
    source_items=b['original_1slg_source_metadata_segments']
    need(len({key(x['original_whole_reference']) for x in source_items})==1,'ONE_ORIGINAL_NATIVE_SOURCE_METADATA_FILE')
    srcrows=[json.loads(raw) for item,raw in segments(r,source_items[0]['original_whole_reference'],source_items)]
    need(srcrows==[x['row'] for x in source_items],'EXACT_BOTH_ORIGINAL_SDF_MOL2_LOCATOR_METADATA')
    nr=b['original_1slg_native_result']
    native=json.loads(segments(r,nr['original_whole_reference'],[nr])[0][1])
    need(native==nr['row'] and native['result']['has_unknown'] is True,'ORIGINAL_NATIVE_GRAPH_UNKNOWN_UNCHANGED')
    blob=profile['raw_native_blob_reference'];items=b['original_1slg_raw_record_segments']
    need(all(triple(x['original_whole_reference'])==triple(blob) for x in items),'ORIGINAL_WHOLE229MB_NATIVE_BLOB_AUTHORITY')
    records=segments(r,blob,items);observed=[];formula=None
    for item,raw in records:
        kind=item['format'];comp,metadata=N.elements(raw,kind,{'native_composition':P.native_composition})
        need(comp==COMPOSITION and metadata['declared_atoms']==metadata['observed_atom_table_records']==110
            and metadata['complete_record_boundary'] is True,'UNCHANGED_NATIVE_WHOLE_ELEMENT_TABLE_COUNTS')
        value=dict(format=kind,segment={k:item[k] for k in ('offset','bytes','sha256')},
            nonH_composition=comp,original_element_function_metadata=metadata,graph_state='UNKNOWN_UNCHANGED')
        if kind=='SDF':
            formula=formula_field(raw);value['whole_formula_field']=formula
        else:
            section=None;names=[]
            for line in raw.splitlines():
                if line.startswith(b'@<TRIPOS>'):section=line[9:];continue
                if section==b'ATOM' and line.strip():
                    fields=line.split();need(len(fields)>=8,'MOL2_LITERAL_RESIDUE_COLUMN')
                    name=fields[7].decode('ascii')
                    if name not in names:names.append(name)
            value['literal_residue_names_in_first_appearance_order']=names
            need(tuple(names)==SEQUENCE,'ORIGINAL_MOL2_LITERAL_SEVEN_RESIDUE_NAMES')
        observed.append(value)
    expected=b['original_1slg_whole_formula_property']
    need(formula and formula['header_offset']==expected['property_header_offset_in_record']
         and formula['whole_value']==expected['value_UTF8']
         and formula['value_raw_sha256']==expected['exact_value_line_sha256'],'WHOLE_FORMULA_LITERAL_AND_SOURCE_BINDING')
    strict=b['existing_accepted_strict5_rows'];ref=inherited_reference(strict[0]['current_replica_reference'],consumed)
    strictrows=[]
    for item,raw in segments(r,ref,strict):
        value=json.loads(raw)
        need(value==item['row'] and value['inchikeys']==[] and value['non_h_composition']==COMPOSITION
            and value['role']=='all' and value['subdataset']=='PDBbind' and '1slg' in value['source_id'],
            'BOTH_EXISTING_COMPOSITION_ONLY_STRICT5_ROWS_NOT_FABRICATED_1PTS_GRAPH')
        keys=C.identity_keys(value)
        need(keys==[('composition','[[6,36],[7,11],[8,12]]')],'UNCHANGED_ORIGINAL_EXACT_COMPOSITION_KEY')
        strictrows.append(dict(source_id=value['source_id'],original_identity_keys=keys,segment={k:item[k] for k in ('offset','bytes','sha256')}))
    return dict(original_case18_rule_unchanged=True,original_1slg_union_segment={k:union[k] for k in ('offset','bytes','sha256')},
        original_native_result_graph_UNKNOWN=True,raw_record_observations=observed,
        existing_strict5_rows=strictrows,new_graph_or_full_key_calls=0,new_original_atom_insertions=0)


def official(r,plan,bundle):
    captures=bundle['official_public_source_cache']; bodies={}; bindings={}
    required=['official_1PTS.pdb','official_1PTS.cif','official_1PTS_entity2.json',
              'official_1SLG.cif','official_1SLG_entity2.json','official_1SLG_summary.html',
              'official_nstd_linkage_definition.html','official_nstd_monomer_definition.html']
    requested=plan['official_body_bindings']
    need(set(required)<=set(requested) and set(requested)<=set(required+['official_1VWA.cif','official_1VWA_entity2.json']),
         'ONLY_EXPLICIT_REQUIRED_OR_OPTIONAL_OFFICIAL_CAPTURE_BINDINGS')
    need(('official_1VWA.cif' in requested)==('official_1VWA_entity2.json' in requested),'COMPLETE_OPTIONAL_SUPPORT_PAIR')
    for name,binding in requested.items():
        src=captures[name]['local_cache_reference']
        need(binding['source_reference']==src and binding['url']==captures[name]['url']
             and r.bindings[key(src)]['replica_reference']==binding['replica_reference'],
             'EXACT_CAPTURE_URL_AND_EXPLICIT_ALPHA_TRANSPORT '+name)
        bodies[name]=r.read(src);bindings[name]=binding
    observed=[]
    for entry in ['1PTS','1SLG']+(['1VWA'] if 'official_1VWA.cif' in bodies else []):
        api=json.loads(bodies['official_'+entry+'_entity2.json']);poly=api['entity_poly']
        need(api['rcsb_polymer_entity_container_identifiers']['entry_id']==entry
             and api['rcsb_polymer_entity_container_identifiers']['entity_id']=='2'
             and poly['pdbx_seq_one_letter_code_can']=='FSHPQNT' and poly['type']=='polypeptide(L)'
             and poly['nstd_linkage']==poly['nstd_monomer']=='no','EXACT_OFFICIAL_ENTITY2_SEQUENCE_AND_LITERAL_FLAGS')
        obs=observe_cif(bodies['official_'+entry+'.cif'],entry)
        need(tuple(obs['declared_sequence'])==SEQUENCE,'EXACT_OFFICIAL_SEVEN_STANDARD_MONOMERS')
        ids=api['rcsb_polymer_entity_container_identifiers']
        need({x['id'] for x in obs['declared_struct_asym']}==set(ids['asym_ids'])
             and {g['auth_asym_id'] for g in obs['groups']}<=set(ids['auth_asym_ids']),
             'API_AND_CIF_ENTITY_CHAIN_IDENTITY_BINDING')
        cp=obs['declared_polymer']
        need(cp['type']==poly['type'] and cp['nstd_linkage']==poly['nstd_linkage']
             and cp['nstd_monomer']==poly['nstd_monomer']
             and ''.join(cp['pdbx_seq_one_letter_code_can'].split())=='FSHPQNT','API_CIF_LITERAL_CONSISTENCY')
        obs['API_polymer_fields']=dict(entity_poly=poly,rcsb_polymer_entity=api['rcsb_polymer_entity'])
        if entry=='1PTS':
            need(len(obs['groups'])==1 and obs['groups'][0]['label_asym_id']=='C'
                 and obs['groups'][0]['auth_asym_id']=='P' and obs['groups'][0]['observed_nonH_sites']==3
                 and obs['groups'][0]['nonH_element_counts']=={'C':3},'ORIGINAL1PTS_ONLY_THREE_OBSERVED_C_NOT_REPLACED')
        else:
            complete=[g for g in obs['groups'] if g['label_asym_id']=='D']
            need(complete and all(g['observed59_nonH_and_seven_positions'] and
                 g['nonH_element_counts']=={'C':36,'N':11,'O':12} for g in complete),
                 'SEPARATE_COMPLETE_OFFICIAL_CHAIN_D_ALTERNATIVES_NOT_ALT_SUM')
            need(any(not g['all_seven_declared_residue_positions_observed'] for g in obs['groups']),
                 'INCOMPLETE_OFFICIAL_OTHER_CHAIN_RETAINED_NOT_CALLED_COMPLETE')
        observed.append(obs)
    pdb=bodies['official_1PTS.pdb'];old=bundle['original_alpha_bound_source_segments']['source_oldcase18']
    need(any(x['sha256']==bindings['official_1PTS.pdb']['source_reference']['sha256'] for x in old['official_references'])
         and any(x['sha256']==bindings['official_1PTS_entity2.json']['source_reference']['sha256'] for x in old['official_references']),
         'CURRENT_OFFICIAL_BYTES_IDENTICAL_ORIGINAL_CASE18_SOURCE_EVIDENCE')
    sites=[]
    for line in pdb.splitlines():
        if line.startswith((b'ATOM  ',b'HETATM')) and line[21:22]==b'P':
            sites.append(dict(atom_name=line[12:16].strip().decode(),residue=line[17:20].decode(),
                residue_number=line[22:26].strip().decode(),alt=line[16:17].decode(),element=line[76:78].strip().decode()))
    need(len(sites)==3 and all(s['atom_name']=='CA' and s['element']=='C' for s in sites),'ORIGINAL_PDB_THREE_CA_NO_COORDINATE_DECODING')
    import html,re
    paper=bodies['official_1SLG_summary.html'].decode('utf-8')
    start=paper.find('id="pubmedAbstractText"');need(start>=0,'ORIGINAL_PAPER_ABSTRACT_ELEMENT_LOCATOR')
    abstract_start=paper.find('id="abstract"',start);need(abstract_start>=start,'ORIGINAL_NESTED_ABSTRACT_ELEMENT')
    end=paper.find('</div>',abstract_start);need(end>abstract_start,'CLOSED_ABSTRACT_ELEMENT')
    text=' '.join(html.unescape(re.sub('<[^>]*>',' ',paper[abstract_start:end])).split())
    bib=bundle['primary_1995_research'];quotes=bib['short_compliant_excerpts']
    need(sum(len(q.split()) for q in quotes)<=25 and all(q in text for q in quotes)
         and bib['doi'] in paper and bib['PMID'] in paper,'BOUNDED_PAPER_BIBLIOGRAPHY_AND_SHORT_EXCERPT_LOCATOR')
    definitions=[]
    for field in ('linkage','monomer'):
        name='official_nstd_'+field+'_definition.html';raw=bodies[name]
        need(('nstd_'+field).encode() in raw,'EXACT_DICTIONARY_ITEM_BODY')
        definitions.append(dict(item='_entity_poly.nstd_'+field,source_binding=bindings[name],
             raw_body_preserved_external=True,chemical_interpretation_adopted=False))
    return dict(official_source_bindings=bindings,entry_observations=observed,original1PTS_PDB_observed_sites=sites,
        paper=dict(doi=bib['doi'],PMID=bib['PMID'],source_binding=bindings['official_1SLG_summary.html'],
            locator=bib['locator'],short_excerpts=quotes,full_abstract_not_copied=True,
            source_correspondence_and_terminal_interpretation='PENDING_ROOT_SOURCE_REVIEW'),
        dictionary_item_observations=definitions,description_FCH_literal_preserved=True,
        no_source_correspondence_or_terminal_adoption=True)


def build(plan,proof,guard):
    N,P,C,functions_proof=functions(plan,proof);r=Reads(plan,guard.check)
    r.json(plan['reviewed_storage_budget_reference'])
    bundle=r.json(plan['proposed_bundle_reference'])
    need(bundle['schema']=='MOLNET_CASE18_PRIMARY_SOURCE_CORRESPONDENCE_PROPOSED_BUNDLE_V1'
         and bundle['no_production_adoption'] is True,'EXACT_PROPOSED_BUNDLE_NOT_PRIOR_ADOPTION')
    review,receipt,consumed=old_index(r,plan,C)
    originals=original(r,bundle,consumed,N,P,C)
    observations=official(r,plan,bundle)
    idx=plan['original1PTS_index_reference']
    with r.held(idx) as (take,p,db):
        line=take(342,59,'537332b170fdd96d05769479a705110cb6da08ee0c2f6d2a9d658c00ea69bced')
        need(line[:4]==b'1pts' and line.rstrip().endswith(b'(7-mer)'),'EXACT_ORIGINAL_1PTS_INDEX_ID_AND_7MER')
    with r.held(review['closed_database'],lock_database=True) as (take,p,db):
        exists=db.execute('SELECT kind,key,dataset FROM excluded WHERE kind=? AND key=? AND dataset=?',
            ('composition','[[6,36],[7,11],[8,12]]','moleculenet')).fetchall()
        old_rule=db.execute('SELECT dataset,binding FROM constraints WHERE rule_id=?',('case:18',)).fetchall()
        atoms=db.execute('SELECT z,n FROM constraint_atoms WHERE rule_id=? ORDER BY z',('case:18',)).fetchall()
        need(exists==[('composition','[[6,36],[7,11],[8,12]]','moleculenet')] and len(old_rule)==1
             and old_rule[0][0]=='moleculenet' and atoms==[(6,3)]
             and json.loads(old_rule[0][1])==bundle['original_alpha_bound_source_segments']['source_oldcase18']['binding'],
             'READ_ONLY_EXISTING_1SLG_COMPOSITION_AND_UNCHANGED_CASE18_C3_RULE')
    return dict(original_source_observations=originals,official_observations=observations,
        original_function_objects=functions_proof,actual_source_reads=r.records,
        original187_receipt=review['index_receipt'],original187_root_review=plan['old_index_root_acceptance_reference'],
        existing_composition_confirmed=True,original_case18_C3_rule_preserved=True,
        old577_complete_read_claim_explicitly_inherited=True,new_evidence_parent_full577_read_claimed=False,
        original1PTS_graph_UNKNOWN_retained=True,graph_or_full_keys_created=0,missing_atoms_inferred=0,
        index_amendment_performed=False,source_correspondence_adopted=False,terminal_correspondence_adopted=False,
        scientific_scope_changed=False,filtered_pool_or_RN_or_training_release=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=json.loads(a.plan.read_text());proof=json.loads(a.startup_proof.read_text())
    authority=admit(plan,proof,a.plan,a.startup_proof);guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False)
        report=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromName(__package__+'.test_source')
        tests=unittest.TextTestRunner(stream=report,verbosity=2).run(suite)
        need(tests.testsRun==4 and tests.wasSuccessful() and not tests.skipped,'FOUR_NATIVE_METADATA_SOURCE_FIXTURES')
        fixtures=S.save(out/'source_tests.json',dict(tests=tests.testsRun,failures=len(tests.failures),errors=len(tests.errors),output=report.getvalue()))
        result=build(plan,proof,guard)
        reads=S.save(out/'actual_source_reads.json',dict(schema='MOLNET_CASE18_ACTUAL_SAME_FD_SOURCE_READS_V1',files=result.pop('actual_source_reads')))
        evidence=S.save(out/'case18_source_observations.DATA.json',dict(schema='MOLNET_CASE18_NATIVE_SOURCE_OBSERVATIONS_V1',
            status='EVIDENCE_ONLY_PENDING_C0_AND_ROOT_SOURCE_REVIEW',**result))
        guard.sample()
        S.save(out/'receipt.json',dict(schema='ALPHA_MOLNET_CASE18_NATIVE_EVIDENCE_PRODUCER_V1',
            status='EVIDENCE_ONLY_PENDING_C0_AND_ROOT_SOURCE_REVIEW',plan_reference=S.pin(a.plan),
            startup_proof_reference=S.pin(a.startup_proof),profile_admission=authority,
            evidence_reference=evidence,actual_source_reads_reference=reads,source_tests_reference=fixtures,
            runtime=guard.receipt(),actual_C0_pending_root_readback=True,source_correspondence_adopted=False,
            index_amendment_performed=False,global_pool_release=False))
    except BaseException as exc:
        if out.is_dir():S.save(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),partials_retained=True))
        raise
    finally:guard.close()


if __name__=='__main__':main()


