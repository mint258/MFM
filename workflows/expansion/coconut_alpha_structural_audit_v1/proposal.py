"""Project closed per-row evidence into a reviewable, unapplied scope proposal."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def pin(path):
    raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--actual-review',required=True,type=Path)
    p.add_argument('--impact-review',required=True,type=Path)
    p.add_argument('--output-directory',required=True,type=Path)
    a=p.parse_args();review=json.loads(a.actual_review.read_text());impact=json.loads(a.impact_review.read_text())
    assert review['status']=='ACCEPTED_DIAGNOSTIC_EVIDENCE_NOT_SOURCE_SCOPE_AUTHORIZATION'
    assert review['actual_parent']['State']=='COMPLETED' and review['actual_parent']['ExitCode']=='0:0'
    assert review['user_source_scope_approval_observed'] is False and review['source_records_dropped_or_quarantined']==0
    ref=review['structural_DATA_reference'];source=Path(ref['path']);assert pin(source)=={k:ref[k] for k in ['path','bytes','sha256']}
    assert impact['status']=='ACCEPTED_READONLY_IMPACT_DIAGNOSTIC_NOT_EXCLUSION' and impact['candidate_filtering_performed'] is False
    out=a.output_directory;out.mkdir(parents=True,exist_ok=False)
    names=['source_id','entry_id','source_table','copy_block','source_row_ordinal','partition','proposed_action','dummy_variants','query_atom_variants','fixed_composition_candidates','original_source_row_sha256','audit_DATA_line_sha256']
    proposed=[];kept=[];hold=[];counts={};seen=set();digest=hashlib.sha256();rows=0
    target=out/'coconut_molecular_scope_proposal_20261103_v1.csv'
    with target.open('w',newline='') as dest,source.open('rb') as stream:
        writer=csv.DictWriter(dest,fieldnames=names);writer.writeheader()
        for line in stream:
            digest.update(line);row=json.loads(line);rows+=1;sid=row['original_source_id'];assert sid not in seen;seen.add(sid)
            kind=row['partition'];counts[kind]=counts.get(kind,0)+1;original=row['original_source']
            if kind=='FINITE_EXACT_SOURCE_RECOVERED_PROPOSAL':action='KEEP_EXACT_SOURCE_RECOVERY_AND_DECONTAMINATE';kept.append(sid)
            elif kind in ['OFFICIAL_ONTOLOGY_CLASSIFICATION_WITNESS','SUPPLIED_REPRESENTATIONS_UNDERSPECIFIED_QUERY_DUMMY_OR_VARIABLE']:action='QUARANTINE_FROM_FINITE_MOLECULAR_SCOPE_ONLY_IF_USER_APPROVES';proposed.append(sid)
            else:action='KEEP_HOLD_REQUIRES_MORE_EVIDENCE';hold.append(sid)
            variants=row['cached_variants']+row['primary_source_variants']
            writer.writerow(dict(source_id=sid,entry_id=row['original_entry_id'],source_table=original['source_table'],copy_block=original['copy_block'],source_row_ordinal=original['source_row_ordinal'],partition=kind,proposed_action=action,dummy_variants=sum(bool(v.get('dummy_atom_indices',[])) for v in variants),query_atom_variants=sum(bool(v.get('query_atom_indices',[])) for v in variants),fixed_composition_candidates=sum(bool(v.get('fixed_explicit_atom_composition_candidate',False)) for v in variants),original_source_row_sha256=original['source_row_sha256'],audit_DATA_line_sha256=hashlib.sha256(line).hexdigest()))
    assert rows==735 and digest.hexdigest()==ref['sha256'] and len(proposed)==732 and len(kept)==3 and not hold
    manifest=dict(schema='COCONUT_FINITE_MOLECULAR_SOURCE_SCOPE_PROPOSAL_V1',status='NOT_APPLIED_PENDING_USER_CONFIRMATION',actual_structural_review_reference=pin(a.actual_review),actual_impact_review_reference=pin(a.impact_review),structural_DATA_reference=ref,per_row_review_table=pin(target),rows=735,partition_counts=counts,proposed_quarantined_source_ids=sorted(proposed),retained_exact_source_recovery_ids=sorted(kept),proposed_source_id_set_sha256=hashlib.sha256(('\n'.join(sorted(proposed))+'\n').encode()).hexdigest(),insufficient_evidence_source_ids=hold,source_scope_approval_observed=False,source_records_deleted=0,source_scope_exclusion_implemented=False,world_nonexistence_inferred=False,all11_ready=False,global_pool_release=False)
    mp=out/'coconut_molecular_scope_proposal_20261103_v1.json';mp.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    text=f'''# COCONUT finite molecular source-scope proposal

## Purpose and requested decision

This is an unapplied proposal, supported by actual Alpha audit1885166 COMPLETED0:0. Authorize only the 732 individually listed non-specific supplied entries to be quarantined from the finite-molecule exclusion scope, preserving every raw source record and audit. Retain the three recovered concrete compounds and apply their exact source-bound compositions through the original consumer. All other concrete COCONUT entries and all other downstream sources remain in scope. No source deletion or whole-dataset omission is proposed.

## Inputs and hashes

- Complete735 structural audit DATA: `{ref['path']}`, SHA256 `{ref['sha256']}`.
- Actual Root audit review: `{a.actual_review}`, SHA256 `{pin(a.actual_review)['sha256']}`.
- Per-row review table: `{target.name}`, SHA256 `{pin(target)['sha256']}`.
- Manifest: `{mp.name}`; it enumerates every proposed source ID and preserves its source-ID set hash.
- Full-pool hypothetical impact: `{a.impact_review}`, SHA256 `{pin(a.impact_review)['sha256']}`.

## Rules and parameters

The audit rechecked735 physical source records, all8085 cached representation fields and10 primary-source fields. It ran no new chemistry or network work. Missing keys alone never imply an abstract record or a nonexistent real-world molecule. Fixed atom tables take priority over incomplete graph identity; query-bond-only candidates, conflicting compositions and uninterpreted group metadata are exposed separately. The audit found no additional fixed-atom composition candidate beyond the three restored compounds.

The proposed scope excludes entries whose supplied representations do not uniquely specify a finite molecule, plus the three official ontology witnesses. It makes no claim that a named real-world compound does not exist. The proposal requires explicit user confirmation before any index, source manifest, filter or eligibility rule changes.

## Script-generated results

| Evidence partition | Rows | Proposed treatment |
|---|---:|---|
| Source-bound concrete recoveries | 3 | Retain and fully decontaminate by exact composition |
| Official ontology classification witnesses | 3 | Quarantine only if approved |
| Supplied query/dummy/unspecified structures | 729 | Quarantine only if approved |
| Insufficient evidence outside those groups | 0 | None silently omitted |

Without the proposed scope treatment, the tested most-conservative C/O/S veto would exclude {impact['counts']['contains_any_C_O_S']:,} of {impact['counts']['total_rows']:,} candidates, leaving at most {impact['hypothetical_remaining_before_other_decontamination']:,} before other exclusions. That cannot provide the requested2,500,000-molecule batch. This veto has not been applied.

## Exceptions and handling

The restored compounds are Dolastatin13 (707929), Chebulinic acid (174911) and the named Nobiletin component (174178). Source stereo and technical-grade caveats remain attached; no key or stereo is fabricated. The official ChEBI witnesses cover electron, hydrogen-halide class and organohalogen class; no finite representative structure is substituted. The per-row table binds original entry IDs, COPY locators, source-row hashes and exact audit-line hashes, with no raw MOL bodies committed to Git.

## Known limits and current state

Current state is NOT_APPLIED_PENDING_USER_CONFIRMATION. Original graph UNKNOWN735 and all raw source bodies remain unchanged. No quarantine, lower-bound adoption, candidate filtering, ranking or all11 release has occurred. If approved, a new source-scope version and complete provenance ledger must be built and checked before the original concrete-molecule decontamination continues; the old735 producers and old HOLD remain historical evidence.
'''
    (out/'coconut_molecular_scope_proposal_20261103_v1.md').write_text(text)
    print(json.dumps(dict(output_directory=str(out),rows=rows,proposed_quarantines=len(proposed),retained_exact_recoveries=len(kept),scope_applied=False)))


if __name__=='__main__':main()
