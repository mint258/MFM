"""Describe author-curated pKa annotations without inventing site labels."""
import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import re
import sqlite3
from .admission import protect


def finite_label(value):
    try:
        return math.isfinite(float(value))
    except (ValueError, TypeError):
        return False


def transition(value):
    match=re.fullmatch(r"\s*([+-]?\d+)\s*>>\s*([+-]?\d+)\s*",value or "")
    return tuple(map(int,match.groups())) if match else None


def summarize_macro(rows):
    counts=Counter()
    source_raw=Counter()
    source_curated=Counter()
    flags=Counter()
    molecules=set()
    curated_molecules=set()
    transitions=defaultdict(set)
    for row in rows:
        counts['raw_rows']+=1
        source_raw[row['dataset']]+=1
        flag=(row.get('exclude_flag') or '').strip().lower()
        flags[flag]+=1
        mid=(row.get('molid') or '').strip()
        if mid:molecules.add(mid)
        value=row.get('Exp_Macro_pKa_processed')
        numeric=finite_label(value)
        counts['raw_finite_numeric_labels']+=numeric
        counts['raw_nonempty_labels']+=bool((value or '').strip())
        if flag=='exclude':
            counts['author_excluded_rows']+=1
            continue
        counts['author_curated_rows']+=1
        source_curated[row['dataset']]+=1
        if mid:curated_molecules.add(mid)
        step=transition(row.get('assigned_charge_state_transition'))
        counts['curated_finite_numeric_labels']+=numeric
        counts['curated_missing_or_nonfinite_labels']+=not numeric
        counts['curated_parseable_transition_rows']+=step is not None
        counts['curated_unit_deprotonation_rows']+=bool(step and step[0]-step[1]==1)
        if numeric and step is not None and mid:
            counts['curated_numeric_assigned_rows']+=1
            transitions[mid].add(step)
    return {'counts':dict(counts),'raw_unique_nonempty_molids':len(molecules),
        'curated_unique_nonempty_molids':len(curated_molecules),
        'exclude_flag_tokens':dict(flags),'raw_rows_by_dataset':dict(source_raw),
        'curated_rows_by_dataset':dict(source_curated),
        'curated_molecules_with_multiple_distinct_numeric_macro_transitions':
            sum(len(v)>1 for v in transitions.values()),
        'macro_transition_count_is_not_atom_site_count':True}


def describe_snapshot(path):
    # Read the published database snapshot only; never start Django or migrate it.
    connection=sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        tables={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        observed={}
        for name in ('datapoint_experimentalmacropka','datapoint_experimentalmicropka',
                     'molecule_molecule','molecule_microspecies','molecule_chargemacrostate'):
            if name in tables:
                observed[name]={'rows':connection.execute('SELECT count(*) FROM "'+name+'"').fetchone()[0],
                    'columns':[r[1] for r in connection.execute('PRAGMA table_info("'+name+'")')]}
        return {'path':str(path),'tables':observed,
                'scope':'Pinned repository snapshot; not an assertion about the live web service'}
    finally:
        connection.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--snapshot',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--quota-snapshot',type=Path,required=True)
    args=p.parse_args()
    protect(args.output.parent,1048576,args.quota_snapshot)
    with (args.root/'combined_unified_dataset.tsv').open(newline='') as stream:
        report={'macro_export':summarize_macro(csv.DictReader(stream,delimiter='\t'))}
    for name in ('microspecies_table.tsv','molecules_table.tsv'):
        with (args.root/name).open(newline='') as stream:
            reader=csv.DictReader(stream,delimiter='\t')
            n=0;ids=set()
            for row in reader:
                n+=1
                if row.get('molid'):ids.add(row['molid'])
            report[name]={'rows':n,'unique_nonempty_molids':len(ids),'columns':reader.fieldnames}
    report.update(status='ANNOTATION_COUNTS_COMPLETE_WITH_EXPLICIT_SITE_LIMITATION',
        source_commit='93958c195874f0a248b2448341cabd58b1f3c7a7',
        source_exclusion_rule='exclude_flag.strip().lower() == exclude, as author importer',
        microspecies_are_experimental_micropka_records=False,
        atom_site_count={'status':'NOT_ANNOTATED_IN_EXPORTED_TABLES',
            'value':None,'note':'Distinct macro transitions and predicted microspecies do not establish distinct atom-site labels.'},
        supersedes_preliminary='pKahub_annotation_summary_20261119.json',
        correction='Preliminary parser incorrectly treated exclude_flag as a boolean. Original report retained; exclude tokens and numeric labels now parsed explicitly.',
        independent_validation_pass=False)
    if args.snapshot:
        report['database_snapshot']=describe_snapshot(args.snapshot)
    protect(args.output.parent,1048576,args.quota_snapshot)
    with args.output.open('x') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print('PKAHUB_ANNOTATIONS_CLOSED',args.output,report['macro_export']['counts'],flush=True)

if __name__=='__main__':main()
