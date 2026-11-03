"""Allocated metadata-only per-row audit of all735 cached source observations."""
import argparse
import collections
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import traceback
import unittest
from workflows.expansion.coconut_alpha_cached735_v1 import support as S
from workflows.expansion.coconut_alpha_cached735_v1.extract import extract,text_reference
from workflows.expansion.coconut_alpha_cached735_v1.run import parent
from .core import variant,partition


def account(ref,job,receipt_ref):
    value=S.load(ref)
    S.need(value['endpoint']=='218.192.171.238:22' and value['uid']==1264 and value['query_returncode']==0,
           'ACTUAL_ALPHA_ROOT_SOURCE_ACCOUNTING')
    rows=list(csv.DictReader(io.StringIO(value['actual_sacct']),delimiter='|')) if 'actual_sacct' in value else value.get('actual_parents',[value.get('actual_parent',{})])
    selected=[r for r in rows if str(r.get('JobIDRaw'))==job]
    S.need(len(selected)==1 and selected[0]['State']=='COMPLETED' and selected[0]['ExitCode']=='0:0'
           and str(selected[0]['UID'])=='1264' and selected[0]['User']=='alpha','ACTUAL_C0_SOURCE_PARENT_'+job)
    if 'receipt' in value:S.need(value['receipt']==receipt_ref,'ACTUAL_ACCOUNTED_SOURCE_RECEIPT')


def admit(plan,proof,plan_path,proof_path):
    from workflows.expansion.alpha_runtime_v1 import profile
    authority=profile.admit(plan,minimum_workers=16);request=proof['request']
    S.need(plan['schema']=='COCONUT_ALPHA_STRUCTURAL_AUDIT_PLAN_V1'
           and plan['scope_key']==request['scope_key']=='coconut_alpha_structural_audit_v1'
           and request['producer_plan_reference']==S.pin(plan_path),'EXACT_ROOT_STRUCTURAL_AUDIT_PLAN')
    argv=request['execution_argv']
    S.need(argv==plan['execution_argv'] and argv[argv.index('--plan')+1]==str(plan_path)
           and argv[argv.index('--startup-proof')+1]==str(proof_path)
           and sys.argv[-4:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)],'EXACT_CURRENT_STRUCTURAL_AUDIT_CLI')
    S.need(proof['endpoint']==plan['endpoint']=='218.192.171.238:22'
           and proof['uid']==plan['uid']==os.getuid()==1264
           and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID')
           and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'REAL_ALPHA_AUDIT_JOB_UID_BOOT')
    refs={r['path']:r for r in request['source_references']}
    import workflows.expansion.coconut_alpha_cached735_v1 as cached
    for file in [*Path(__file__).parent.glob('*.py'),*Path(cached.__file__).parent.glob('*.py')]:
        S.need(refs.get(str(file.absolute()))==S.pin(file),'EXACT_NEW_AND_BORROWED_METADATA_SOURCES')
    for ref in request['source_references']:S.read(ref,2<<20)
    return authority


def lines(ref,expected,cap):
    raw=S.read(ref,cap);rows=raw.splitlines(keepends=True)
    S.need(raw.endswith(b'\n') and len(rows)==ref['rows']==expected,'COMPLETE_CLOSED_SOURCE_DATA_CENSUS')
    return rows


def physical(source):return tuple(source[k] for k in ('source_table','copy_block','source_row_ordinal'))


def execute(plan,out,guard):
    cached_ref=plan['cached735_receipt_reference'];cached=S.load(cached_ref)
    account(plan['cached735_actual_parent_reference'],'1885150',cached_ref)
    S.need(cached['schema']=='COCONUT_ALPHA_CACHED735_PRODUCER_V1'
           and cached['profile_admission']['job_id']=='1885150' and cached['profile_admission']['uid']==1264
           and cached['result']['original_graph_UNKNOWN735_retained'] is True,'ACTUAL_UNADOPTED_CACHED735_SOURCE')
    cached_plan=S.load(cached['plan']);native_rows,native_ref,native_receipt=parent(cached_plan)
    original={physical(row['source']):row for row in native_rows}
    native_ordinals={physical(row['source']):i for i,row in enumerate(native_rows,1)}
    S.need(len(original)==735,'735_UNIQUE_NATIVE_PHYSICAL_ROWS')
    primary_ref=plan['primary3_receipt_reference'];primary=S.load(primary_ref)
    account(plan['primary3_actual_parent_reference'],'1885152',primary_ref)
    S.need(primary['schema']=='COCONUT_ALPHA_PRIMARY3_PRODUCER_V1'
           and primary['result']['native735_receipt_reference']==cached_plan['native735_receipt_reference']
           and primary['result']['original_UNKNOWN735_retained'] is True,'SAME_ORIGINAL735_PRIMARY_DIAGNOSTIC_CHAIN')
    primary_lines=lines(primary['result']['DATA'],3,2<<20)
    primary_rows={json.loads(line)['original_entry_id']:json.loads(line) for line in primary_lines}
    S.need(set(primary_rows)=={'707929','174911','174178'},'EXACT_THREE_FINITE_SOURCE_OBSERVATIONS')
    review=S.load(plan['exact3_source_review_reference'])
    S.need(review['schema']=='ROOT_PRIMARY3_EXACT_FORMULA_SOURCE_REVIEW_V1'
           and review['primary3_receipt_reference']==primary_ref and review['proposed_exact_composition_rows']==3
           and review['comparison_semantics']=='EXACT_NON_H_COMPOSITION_EQUALITY'
           and review['original_graph_UNKNOWN735_retained'] is True and review['all11_ready'] is False,
           'ACTUAL_PREPARED_PARTIAL_EXACT_SOURCE_PROPOSAL_NOT_ALL735_ADOPTION')
    finite={row['original_entry_id']:row for row in review['source_bindings']}
    S.need(set(finite)==set(primary_rows),'THREE_REVIEW_BINDINGS_NO_EXTRA_ROW')
    strict_ref=review['proposed_original_strict5_reference'];strict_lines=lines(strict_ref,3,1<<20)
    strict={json.loads(line)['source_id']:json.loads(line) for line in strict_lines}
    ontology_ref=primary['result']['ontology_classification_witnesses'];ontology=S.load(ontology_ref)
    S.need(ontology['classification_only'] is True and ontology['scientific_domain_exception_or_exclusion_accepted'] is False,
           'ONTOLOGY_CLASSIFICATION_IS_NOT_SOURCE_SCOPE_APPROVAL')
    ontology_rows={row['research_classification']['original_entry_id']:row for row in ontology['rows']}
    S.need({key:row['research_classification']['original_reference_id'] for key,row in ontology_rows.items()}
           =={'18394':'CHEBI:10545','22444':'CHEBI:18140','22403':'CHEBI:17792'},'THREE_EXACT_OFFICIAL_ONTOLOGY_WITNESSES')
    for row in ontology_rows.values():
        for key in ('official_HTML_reference','official_MOL_reference'):S.read(row[key]['replica_reference'],2<<20)
    source_ref=cached['result']['DATA'];source_lines=lines(source_ref,735,64<<20)
    target=out/'structural_evidence735.DATA.jsonl';counts=collections.Counter();variant_counts=collections.Counter()
    seen=set();offset=0;primary_variant_total=0;recoverable=[]
    with target.open('xb') as stream:
        for ordinal,line in enumerate(source_lines,1):
            guard.check();row=json.loads(line);src=row['source'];key=physical(src);identifier=row['original_id']
            S.need(key not in seen and key in original and src==original[key]['source']
                   and row['original_UNKNOWN_unchanged'] is True and row['strict5_written'] is False
                   and row['new_authoritative_keys'] is False
                   and row['opaque_original_row_reference']==original[key]['opaque_original_row_reference']
                   and row['native735_source_record_reference']==dict(DATA_reference=native_ref,record_ordinal_1based=native_ordinals[key]),
                   'ONE_BOUND_UNCHANGED_ORIGINAL_UNKNOWN_SOURCE_ROW')
            seen.add(key);raw=extract(original[key]);expected={v['variant_id']:v for v in raw['variants']}
            S.need(identifier==raw['original_id'] and row['literal_comparisons']==raw['literal_comparisons']
                   and [v['variant_id'] for v in row['variants']]==list(expected),
                   'EXACT_ORIGINAL_ID_AND_ALL_ELEVEN_CACHED_SOURCE_FIELDS')
            audited=[]
            for value in row['variants']:
                whole=expected[value['variant_id']]
                S.need(value['text_reference']==text_reference(whole['text'])
                       and value['source_pointer']==whole['source_pointer']
                       and value['decoded_container']==whole['decoded_container']
                       and value['physical_source_locator']==whole['physical_source_locator']
                       and value['opaque_original_row_reference']==row['opaque_original_row_reference'],
                       'COMPLETE_REEXTRACTED_SOURCE_FIELD_HASH_AND_POINTER_MATCH')
                item=variant(value,whole['text']);item['observation_namespace']='cached1885150'
                audited.append(item)
            upstream=[];binding=finite.get(identifier);witness=ontology_rows.get(identifier)
            if binding:
                primary_row=primary_rows[identifier]
                source_id='entries:'+identifier+':'+str(src['copy_block'])+':'+str(src['source_row_ordinal'])
                S.need(binding['original_source_record_id']==source_id and binding['original_source_row_sha256']==src['source_row_sha256']
                       and primary_row['original_SQL_source']==src and binding['original_graph_identity_resolution']=='UNKNOWN_UNCHANGED'
                       and strict[binding['strict5_source_id']]['non_h_composition']==binding['exact_composition']
                       and strict[binding['strict5_source_id']]['inchikeys']==[],'EXACT_FINITE_PROPOSAL_BOUND_TO_SAME_ORIGINAL_PHYSICAL_RECORD')
                recorded=binding['DATA_record'];observed_line=primary_lines[recorded['ordinal_1based']-1]
                S.need(recorded['reference']==primary['result']['DATA'] and recorded['bytes']==len(observed_line)
                       and recorded['sha256']==hashlib.sha256(observed_line).hexdigest()
                       and json.loads(observed_line)['original_entry_id']==identifier,'SAME_ACTUAL_PRIMARY3_WHOLE_RECORD_IN_PREPARED_REVIEW')
                for value in primary_row['variants']:
                    item=variant(value);item['observation_namespace']='primary1885152';upstream.append(item)
                primary_variant_total+=len(upstream)
            all_variants=audited+upstream
            category=partition(all_variants,binding is not None,witness is not None)
            candidates=[v for v in all_variants if v['fixed_explicit_atom_composition_candidate']]
            vectors=sorted({json.dumps(v['fixed_atom_non_H_composition_observation'],separators=(',',':')) for v in candidates})
            flags={name:any(bool(v[name]) for v in all_variants) for name in
                ('complete_atom_record_table','all_recorded_atomic_numbers_real_Z','fixed_explicit_atom_composition_candidate',
                 'fixed_atom_record_composition_observed','candidate_blocked_by_uninterpreted_group_metadata',
                 'fixed_atoms_query_bonds_only','query_atom_indices','dummy_atom_indices','query_bond_indices')}
            result=dict(schema='COCONUT735_STRUCTURAL_EVIDENCE_AUDIT_ROW_V1',original_entry_id=identifier,
                original_source_id='entries:'+identifier+':'+str(src['copy_block'])+':'+str(src['source_row_ordinal']),
                original_source={k:v for k,v in src.items() if k!='identity_fields_json'},
                original_opaque_row_reference=row['opaque_original_row_reference'],
                original_opaque_body_rehashed_in_this_audit=False,
                cached_observation_record=dict(reference=source_ref,ordinal_1based=ordinal,byte_offset=offset,
                    bytes=len(line),sha256=hashlib.sha256(line).hexdigest()),
                native735_source_record_reference=row['native735_source_record_reference'],
                partition=category,partition_describes='SUPPLIED_EVIDENCE_ONLY_NOT_REAL_WORLD_MOLECULE_EXISTENCE',
                evidence_flags=flags,cached_variants=audited,primary_source_variants=upstream,
                literal_comparisons=row['literal_comparisons'],literal_equality_does_not_prove_identical_graph=True,
                fixed_atom_composition_candidate_vectors=[json.loads(v) for v in vectors],
                candidate_vectors_conflict=len(vectors)>1,
                candidate_composition_requires_source_association_and_variable_metadata_review=bool(candidates) and binding is None,
                finite_exact_source_proposal_binding=binding,official_ontology_classification_witness=witness,
                original_graph_identity_resolution='UNKNOWN_UNCHANGED',graph_or_exact_composition_accepted=False,
                lower_bounds_accepted=False,source_records_quarantined_or_dropped=False,
                user_source_scope_approval_observed=False,world_nonexistence_inferred=False)
            stream.write(S.canonical(result));offset+=len(line);counts['partition/'+category]+=1
            for name,value in flags.items():counts['rows_any/'+name]+=int(value)
            counts['rows_with_conflicting_candidate_vectors']+=int(len(vectors)>1)
            if candidates:recoverable.append(dict(original_entry_id=identifier,original_source_id=result['original_source_id'],
                vectors=result['fixed_atom_composition_candidate_vectors'],conflict=result['candidate_vectors_conflict'],
                variants=[dict(namespace=v['observation_namespace'],variant_id=v['variant_id'],text_reference=v['text_reference'],
                    query_bonds_only=v['fixed_atoms_query_bonds_only']) for v in candidates]))
            for item in all_variants:
                variant_counts['observed_variants']+=1
                for name in ('complete_atom_record_table','all_recorded_atomic_numbers_real_Z','fixed_explicit_atom_composition_candidate',
                             'fixed_atom_record_composition_observed','candidate_blocked_by_uninterpreted_group_metadata',
                             'fixed_atoms_query_bonds_only'):variant_counts[name]+=int(item[name])
        stream.flush();os.fsync(stream.fileno())
    S.need(len(seen)==735 and sum(v for k,v in counts.items() if k.startswith('partition/'))==735,
           'COMPLETE_EXACT_PHYSICAL735_PARTITION_CENSUS_NO_SOURCE_DROP')
    S.need(counts['partition/FINITE_EXACT_SOURCE_RECOVERED_PROPOSAL']==3
           and counts['partition/OFFICIAL_ONTOLOGY_CLASSIFICATION_WITNESS']==3,'EXACT_THREE_FINITE_AND_THREE_ONTOLOGY_DIAGNOSTIC_PARTITIONS')
    return dict(schema='COCONUT735_STRUCTURAL_EVIDENCE_AUDIT_V1',status='COMPLETE_DIAGNOSTIC_NO_SCOPE_DECISION',
        DATA=dict(S.pin(target),rows=735),counts=dict(counts),variant_counts=dict(variant_counts),
        cached_variants=735*11,primary_source_variants=primary_variant_total,
        fixed_atom_composition_candidates_for_review=recoverable,
        source_references={k:plan[k] for k in ('cached735_receipt_reference','cached735_actual_parent_reference',
            'primary3_receipt_reference','primary3_actual_parent_reference','exact3_source_review_reference')},
        original_native735_DATA_reference=native_ref,ontology_witness_reference=ontology_ref,
        chemical_or_network_calls=0,original_graph_UNKNOWN735_retained=True,source_records_dropped_or_quarantined=0,
        scientific_acceptance=False,user_source_scope_approval_observed=False,all735_coverage_or_all11_ready=False,
        bounds_filter_index_or_queue_applied=False,world_nonexistence_inferred=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan=json.loads(args.plan.read_text());proof=json.loads(args.startup_proof.read_text());authority=admit(plan,proof,args.plan,args.startup_proof)
    from workflows.expansion.alpha_runtime_v1.guard import Guard
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False)
        from .test_source import Source
        transcript=io.StringIO();tested=unittest.TextTestRunner(stream=transcript,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Source))
        tests=S.save(out/'source_tests.json',dict(tests=tested.testsRun,errors=len(tested.errors),failures=len(tested.failures),
            skips=len(tested.skipped),transcript=transcript.getvalue()))
        S.need(tested.wasSuccessful() and tested.testsRun==1 and not tested.skipped,'ONE_FIXED_ATOM_QUERY_BOND_CLASSIFICATION_BOUNDARY_FIXTURE')
        result=execute(plan,out,guard)
        S.save(out/'receipt.json',dict(schema='COCONUT_ALPHA_STRUCTURAL_AUDIT_PRODUCER_V1',plan=S.pin(args.plan),
            startup_proof=S.pin(args.startup_proof),profile_admission=authority,source_tests=tests,
            result=result,runtime=guard.receipt(),actual_parent_C0_pending_root_readback=True,scientific_acceptance=False))
    except BaseException as exc:
        if out.is_dir():S.save(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),
            partials_retained=True,source_scope_changed=False,scientific_acceptance=False))
        raise
    finally:guard.close()


if __name__=='__main__':main()
