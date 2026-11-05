"""Root metadata preparation from actual primary3 C0; no chemistry or new approval gate."""
import argparse
import csv
import hashlib
import importlib
import io
import json
import os
import sys
from pathlib import Path
from workflows.expansion.coconut_alpha_cached735_v1 import support as S
from workflows.expansion.coconut_alpha_cached735_v1.extract import text_reference
from workflows.expansion.coconut_alpha_cached735_v1.run import parent
from workflows.expansion.coconut_alpha_primary3_v1 import evidence as F
from workflows.expansion.coconut_alpha_primary3_v1.transport import Evidence

A=Path('/gfshome/alpha/codex_data_v1_20261026')
RECEIPT=A/'artifacts/pubchem_native735_fields_20261103/primary3_node_v1_job_1885152/receipt.json'
ACCOUNT=A/'control/pubchem_expansion_runtime_20261103/primary3_root_actual_parent.json'
IDS=('707929','174911','174178')


def accounting(value,receipt_ref):
    S.need(value['endpoint']=='218.192.171.238:22' and value['uid']==1264
           and value['query_returncode']==0 and value['actual_terminal'] is True
           and value['receipt']==receipt_ref and value['job_id']=='1885152',
           'ACTUAL_ROOT_PARENT_RECEIPT_BINDING')
    rows=list(csv.DictReader(io.StringIO(value['actual_sacct']),delimiter='|'))
    rows=[r for r in rows if r.get('JobIDRaw')=='1885152']
    S.need(len(rows)==1 and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0'
           and rows[0]['UID']=='1264' and rows[0]['User']=='alpha'
           and rows[0]['AllocCPUS']=='16' and rows[0]['NodeList']=='sonmi1',
           'ACTUAL1885152_C0_16CPU_SONMI1_NOT_NEW_METADATA_C0')
    return rows[0]


def context(receipt_ref):
    receipt=S.load(receipt_ref);pp=S.load(receipt['plan'])
    S.need(receipt['schema']=='COCONUT_ALPHA_PRIMARY3_PRODUCER_V1'
           and receipt['profile_admission']['job_id']=='1885152'
           and receipt['profile_admission']['endpoint']=='218.192.171.238:22'
           and receipt['profile_admission']['uid']==1264
           and receipt['result']['original_UNKNOWN735_retained'] is True
           and receipt['result']['upstream_source_or_formula_composition_accepted'] is False,
           'ACTUAL_UNADOPTED_PRIMARY3_DIAGNOSTIC')
    S.need(Path(pp['original_source_root'])==A/'code','ACTUAL_ORIGINAL_ALPHA_SOURCE_ROOT')
    for ref in pp['original_source_references']:S.read(ref,2<<20)
    sys.path.append(str(A/'code'))
    consumer=importlib.import_module('secondary_coconut_strict5_day_v1.frozen.decontamination')
    declared={r['path']:r for r in pp['original_source_references']}
    import secondary_coconut_strict5_day_v1.frozen.common as common
    for module in (consumer,common):
        ref=S.pin(module.__file__);S.need(declared.get(ref['path'])==ref,'EXACT_ALPHA_ORIGINAL_CONSUMER_OBJECT_BODY')
    evidence_refs=[r for r in pp['code_references'] if r['path'].endswith('/workflows/expansion/coconut_alpha_primary3_v1/evidence.py')]
    startup=S.load(receipt['startup_proof']);S.need(len(evidence_refs)==1 and
        evidence_refs[0] in startup['request']['source_references'],'ACTUAL_PARENT_METADATA_EXTRACTION_SOURCE')
    old=evidence_refs[0];S.read(old,2<<20);current=S.pin(F.__file__)
    S.need(all(old[k]==current[k] for k in ('bytes','sha256')),'UNCHANGED_PRIMARY_METADATA_EXTRACTION_BODY')
    return receipt,pp,consumer,dict(original_consumer_reference=S.pin(consumer.__file__),
        original_common_reference=S.pin(common.__file__),parent_extraction_source_reference=old,
        current_extraction_source_reference=current,
        identity_keys_object=dict(qualified_name=consumer.identity_keys.__module__+'.'+consumer.identity_keys.__qualname__,
            filename=consumer.identity_keys.__code__.co_filename,first_line=consumer.identity_keys.__code__.co_firstlineno),
        original_consumer_artifact_or_quota_functions_invoked=False)


def build(receipt_ref,account_ref):
    receipt,pp,consumer,proof=context(receipt_ref);actual=accounting(S.load(account_ref),receipt_ref)
    fixture=S.load(receipt['source_tests']);S.need(fixture['tests']==6 and all(fixture[k]==0 for k in ('errors','failures','skips')),
                                               'ACTUAL_PRIMARY3_SIX_NATIVE_FIXTURES')
    data_ref=receipt['result']['DATA'];raw=S.read(data_ref,2<<20);lines=raw.splitlines(keepends=True)
    S.need(raw.endswith(b'\n') and len(lines)==data_ref['rows']==3,'CLOSED_PRIMARY3_DATA_COMPLETE')
    rows=[json.loads(line) for line in lines]
    S.need([r['original_entry_id'] for r in rows]==list(IDS),'EXACT_PRIMARY3_ORDER')
    originals,_,native=parent(pp);selected={}
    for identifier in IDS:
        found=[r for r in originals if json.loads(r['source']['identity_fields_json'])['id']==identifier]
        S.need(len(found)==1,'UNIQUE_ORIGINAL_PHYSICAL_ENTRY');selected[identifier]=found[0]
    native_plan=S.load(native['plan']);strict=S.load(native_plan['original_strict_receipt_reference'])
    strict_plan=S.load(strict['plan_reference']);role=strict_plan['role']
    S.need(role=='ALL_SOURCE_NATIVE_SPLIT_UNKNOWN','PRESERVE_ORIGINAL_COCONUT_STRICT_ROLE')
    E=Evidence(pp);E.native735_original_plan=native_plan
    fresh={'707929':F.cyano(selected['707929'],E),'174911':F.inpac(selected['174911'],E),
           '174178':F.indofine(selected['174178'],E)}
    overlay=[];bindings=[]
    for ordinal,(row,line) in enumerate(zip(rows,lines),1):
        identifier=row['original_entry_id'];record=selected[identifier];source=record['source'];new=fresh[identifier]
        S.need(row['original_SQL_source']==source and row['original_opaque_row_reference']==record['opaque_original_row_reference']
               and row['original_UNKNOWN_unchanged'] is True and row['strict5_written'] is False
               and record['original_diagnosis']['replay']['covered'] is False,
               'ORIGINAL_UNKNOWN_SOURCE_NOT_REPLACED_OR_PREVIOUSLY_COVERED')
        S.need(row['association_basis']==new['association_basis'] and row['caveats']==new['caveats'],
               'SOURCE_ID_ASSOCIATION_AND_CAVEATS_EXACT_REPLAY')
        vectors=[];formula_witnesses=[]
        S.need(len(row['formulas'])==len(new['formulas'])>0,'ALL_SOURCE_FORMULA_FIELDS_PRESENT')
        for formula,original in zip(row['formulas'],new['formulas']):
            obs=formula['original_formula_function_observation'];tr=text_reference(original['value'])
            S.need(formula['value']==original['value'] and formula['text_reference']==tr
                   and obs['source_UTF8_sha256']==tr['sha256']
                   and obs['state']=='SOURCE_FORMULA_NON_H_COUNTS_NOT_GRAPH_IDENTITY'
                   and obs['reason']=='ORIGINAL_WHOLE_FORMULA_ALL_COMPONENTS'
                   and formula['upstream_file_reference']==original['upstream_file_reference']
                   and formula['locator']==original['locator'],'WHOLE_EXPLICIT_FORMULA_SOURCE_EQUALITY')
            vectors.append(obs['composition']);formula_witnesses.append(dict(value=formula['value'],text_reference=tr,
                upstream_file_reference=formula['upstream_file_reference'],locator=formula['locator']))
        composition=vectors[0];S.need(all(v==composition for v in vectors),'NO_FORMULA_COMPOSITION_CONFLICT')
        variants={v['name']:v for v in new['variants']};closed=[]
        S.need([v['variant_id'] for v in row['variants']]==list(variants),'ALL_WHOLE_FIELDS_RETAINED')
        for observed in row['variants']:
            original=variants[observed['variant_id']]
            S.need(observed['text_reference']==text_reference(original['text']) and
                   observed['upstream_source_reference']==original['upstream_file_reference'] and
                   observed['source_pointer']==original['locator'],'WHOLE_SOURCE_REPRESENTATION_HASH_EQUALITY')
            atoms=observed.get('unsanitized_atom_observation',{})
            if atoms.get('full_non_H_composition_observation') is not None:
                S.need(atoms['closed_explicit_atom_table'] is True and not atoms['query_atom_indices']
                       and not atoms['dummy_atom_indices'] and not atoms['query_bond_indices']
                       and atoms['full_non_H_composition_observation']==composition,
                       'EXACT_FORMULA_EQUALS_CLOSED_WHOLE_MOL_OR_SMILES_NON_H_COUNTS')
                closed.append(dict(variant_id=observed['variant_id'],text_reference=observed['text_reference'],
                    upstream_source_reference=observed['upstream_source_reference'],source_pointer=observed['source_pointer']))
        S.need(closed,'AT_LEAST_ONE_COMPLETE_SOURCE_REPRESENTATION_CORROBORATES_FORMULA')
        source_record='entries:'+identifier+':'+str(source['copy_block'])+':'+str(source['source_row_ordinal'])
        identity=dict(source_id=source_record+':composition:0',role=role,subdataset='entries',inchikeys=[],
                      non_h_composition=composition)
        keys=consumer.identity_keys(identity)
        S.need(keys==[('composition',json.dumps(composition,separators=(',',':')))],
               'ACTUAL_ORIGINAL_CONSUMER_COMPOSITION_ONLY_EXACT_LOOKUP')
        overlay.append(identity)
        bindings.append(dict(strict5_source_id=identity['source_id'],original_entry_id=identifier,
            original_source_record_id=source_record,locator={k:source[k] for k in ('source_table','copy_block','source_row_ordinal')},
            original_source_row_sha256=source['source_row_sha256'],original_opaque_row_reference=row['original_opaque_row_reference'],
            DATA_record=dict(reference=data_ref,ordinal_1based=ordinal,bytes=len(line),sha256=hashlib.sha256(line).hexdigest()),
            formula_source_fields=formula_witnesses,corroborating_complete_source_fields=closed,
            exact_composition=composition,consumer_lookup=keys,caveats=row['caveats'],association_basis=row['association_basis'],
            original_graph_identity_resolution='UNKNOWN_UNCHANGED',full_keys=[],source_rows_dropped=False,
            proposed_for_partial_source_integration=True,applied_to_index_or_candidates=False))
    return dict(schema='ROOT_PRIMARY3_EXACT_FORMULA_SOURCE_REVIEW_V1',
        status='ROOT_SOURCE_REVIEW_PROPOSAL_EXACT_COMPOSITION_ONLY_NOT_COMPLETE735_COVERAGE',reviewer='root',
        basis='ROOT_EXISTING_ACTUAL_PRIMARY3_REVIEW_AND_SOURCE_FIELD_PIN_READBACK_NO_NEW_USER_APPROVAL_STEP',
        primary3_receipt_reference=receipt_ref,actual_parent_reference=account_ref,actual_parent=actual,
        borrowed_original_source_proof=proof,original_strict_receipt_reference=native_plan['original_strict_receipt_reference'],
        source_bindings=bindings,proposed_original_strict5_rows=overlay,
        formula_non_H_compositions_match_complete_source_fields=True,comparison_semantics='EXACT_NON_H_COMPOSITION_EQUALITY',
        greater_or_equal_lower_bounds_created=False,new_chemical_calls=0,full_key_or_stereo_promoted=False,
        original_graph_UNKNOWN735_retained=True,proposed_exact_composition_rows=3,
        original_unknown_rows=735,remaining_rows_outside_this_proposed_scope=732,
        unspecified_or_abstract_source_scope_changed=False,all735_exclusion_coverage_claimed=False,
        all11_ready=False,source_records_dropped_or_quarantined=0,candidate_filtering_performed=False,
        original_or_prior_producer_outputs_modified=False,
        production_integration_required='BIND_THREE_PROPOSED_COMPOSITION_ROWS_TO_FINAL_PHYSICAL_SOURCE_LEDGER;_KEEP_REMAINING_SCOPE_HOLD')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--primary3-receipt',type=Path,default=RECEIPT)
    p.add_argument('--actual-parent',type=Path,default=ACCOUNT)
    p.add_argument('--output-directory',type=Path,required=True)
    args=p.parse_args();S.need(os.getuid()==1264 and sys.flags.isolated==1,'ACTUAL_ALPHA_ISOLATED_METADATA_PREPARATION')
    result=build(S.pin(args.primary3_receipt),S.pin(args.actual_parent));out=args.output_directory
    S.need(out.is_absolute() and out.is_relative_to(A/'control') and out!=A/'control'
           and out==out.resolve() and not any(p.is_symlink() for p in (out,*out.parents)),
           'FRESH_PRIVATE_ALPHA_CONTROL_REVIEW_ONLY')
    out.mkdir(parents=True,exist_ok=False)
    rows=result.pop('proposed_original_strict5_rows')
    with (out/'primary3_exact_composition.PROPOSED.strict5.jsonl').open('xb') as stream:
        for row in rows:stream.write(S.canonical(row))
        stream.flush();os.fsync(stream.fileno())
    result['proposed_original_strict5_reference']=dict(S.pin(out/'primary3_exact_composition.PROPOSED.strict5.jsonl'),rows=3)
    ref=S.save(out/'root_source_review.PROPOSED.json',result)
    print(json.dumps(ref,sort_keys=True))


if __name__=='__main__':main()
