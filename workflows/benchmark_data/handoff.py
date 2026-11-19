"""Build consumer handoff/count tables from producer metadata, never label replay."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import time
from .pprime_tmpfs_queue import capacity


def aggregate_counts(rows):
    total={k:sum(int(r.get(k,0)) for r in rows) for k in ('before','domain_eligible','retained','blind_fallback_required','salts_removed','graph_metadata_pending','graph_missing')}
    total['unresolved']=total['graph_metadata_pending']+total['graph_missing']
    total['known_rejected']=total['before']-total['domain_eligible']-total['unresolved']
    if total['known_rejected']<0:raise ValueError('Producer count categories overlap or are incomplete')
    for name in ('reason_counts_nonexclusive','primary_reason_counts'):
        counter=Counter()
        for row in rows:counter.update(row.get(name,{}))
        total[name]=dict(counter)
    return total


def flatten(dataset,manifest,source_manifest):
    batches=manifest['counts']
    sets=[(dataset+'_'+str(row['nucleus']),[row]) for row in batches] if dataset=='NMRShiftDB2' else [(dataset,batches)]
    result=[]
    for name,counts in sets:
        value=aggregate_counts(counts)
        value.update(dataset=name,source_group=dataset,source_manifest=str(source_manifest),
            domain_filter_complete=manifest.get('domain_filter_complete',True) and value['unresolved']==0)
        result.append(value)
    return result


def write_counts(path,rows):
    reasons=sorted({k for row in rows for k in row['reason_counts_nonexclusive']})
    primary=sorted({k for row in rows for k in row['primary_reason_counts']})
    fields=['source_group','dataset','before','domain_eligible','known_rejected','unresolved','retained','blind_fallback_required','salts_removed','domain_filter_complete']
    fields+=['reason:'+k for k in reasons]+['primary:'+k for k in primary]+['source_manifest']
    with Path(path).open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in rows:
            value={k:row[k] for k in fields if k in row}
            value.update({'reason:'+k:row['reason_counts_nonexclusive'].get(k,0) for k in reasons})
            value.update({'primary:'+k:row['primary_reason_counts'].get(k,0) for k in primary})
            writer.writerow(value)


def pprime_closure(folder,access):
    state={'production_closed':False,'all_ready':False,'outcome_counts':None,'producer_manifest':None}
    if not (access.get('immutable') and access.get('writers_closed')):return state
    source=Path(access['producer_manifest'])
    report=json.loads(source.read_text())
    if str(report['job'])!=str(access['producer_job']) or report['status']!='ALL_QUEUED_PPRIME_TERMINAL':
        raise ValueError('P-prime access and terminal producer identity/status differ')
    counts=report['states']
    if not report['source_all_geometry_complete'] or counts.get('PENDING',0) or counts.get('INTENT',0):
        raise ValueError('P-prime sealed metadata still has unprocessed work')
    state.update(production_closed=True,all_ready=counts.get('PPRIME_READY',0)==sum(counts.values()),
        outcome_counts=counts,producer_manifest=str(source))
    return state

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--progress',type=Path,required=True);p.add_argument('--attempt',required=True)
    p.add_argument('--quota-snapshot',type=Path,required=True);a=p.parse_args()
    def safe():
        waiting=False
        while True:
            try:capacity(a.root,a.quota_snapshot,1048576);return
            except (OSError,ValueError,KeyError,RuntimeError) as exc:
                if not waiting:print('HANDOFF_DISK_WAIT',repr(exc),flush=True)
                waiting=True;time.sleep(2)
    safe();out=a.root/'delivery'/a.attempt;out.mkdir(parents=True,exist_ok=False)
    progress=json.loads(a.progress.read_text());groups={};counts=[]
    for group,spec in progress['domains'].items():
        manifest=Path(spec['manifest']);m=json.loads(manifest.read_text())
        group_counts=flatten(group,m,manifest);counts.extend(group_counts)
        groups[group]={'domain_manifest':str(manifest),'records':m.get('records'),
            'records_by_nucleus':{str(row['nucleus']):row['records'] for row in m['counts'] if 'nucleus' in row},
            'count_rows':group_counts,'status':m['status'],'source_group_is_fully_filtered':all(r['domain_filter_complete'] for r in group_counts)}
    write_counts(out/'domain_counts.csv',counts)
    pp=a.root/'labels/Pprime/shared_v1';access=json.loads((pp/'access.json').read_text())
    closure=pprime_closure(pp,access)
    result={'schema':'BENCHMARK_B0_AVAILABLE_DATA_HANDOFF_V1','status':('D_AVAILABLE_PPRIME_PRODUCTION_CLOSED_WITH_EXPLICIT_OUTCOMES_S_P_PENDING' if closure['production_closed'] else 'D_AVAILABLE_PPRIME_NOT_FULLY_CLOSED_S_P_PENDING'),
        'authority':progress['authority'],'root':str(a.root),'source_progress':str(a.progress),
        'source_groups':groups,'source_group_count':len(groups),'domain_count_rows':len(counts),
        'domain_counts_csv':str(out/'domain_counts.csv'),
        'count_units':'Source task rows, not deduplicated molecules; NMR nuclei separate. pKahub before is after original author curation.',
        'reason_columns':'Nonexclusive reason counts; primary columns count the first frozen source reason. Unknown graphs are separate from known domain rejection.',
        'blind_evaluation':'All ExpansionRx/ASAP source rows retained; outside-domain uses training-mean fallback, original endpoint masks retained.',
        'Sprime_and_D':progress['geometry'],'shared_Sprime_reader':'workflows.benchmark_data.shared_reader.SharedB0Reader',
        'reference_geometries':progress['references'],
        'reference_D20':progress['reference_D20'],'reference_D3':progress['reference_D3'],
        'C7_targets':progress['C7_targets'],'PPE_targets':progress['PPE_targets_overlay'],
        'pKahub_annotations':progress['pKahub_annotations'],
        'Pprime':{'queue':str(pp/'queue.sqlite'),'access_manifest':str(pp/'access.json'),'observed_access':access,
            'reader':'workflows.benchmark_data.pprime_reader.PprimeReader',**closure,
            'native_recipe':'Original twelve WP5 tasks, exact pinned binaries/parser/keywords/units, 900 seconds each',
            'geometry_source':'Original accepted UFF_Sprime only; no reference geometry mislabeled as UFF',
            'atomic_order':'Original S-prime graph order; per-source atom mapping retained in source membership',
            'failure_policy':'Keep partial task outcomes and unknowns explicitly; no retry, no fill'},
        'S':{'ready':False,'reason':'Historical original PM7 optimization binary version remains unproven'},
        'P':{'ready':False,'reason':'Depends on unrecovered original S workflow; directive permits S-prime/D/P-prime fallback'},
        'reference_quantum_labels':{'ready':False,'reason':'Reference XYZ unchanged; P remains pending and P-prime is defined on UFF only; no new label type invented'},
        'scientific_decisions_pending':progress['scientific_decisions_pending'],
        'normalization':'Raw original F64 property values and masks; no new train/test normalization fitted by this handoff',
        'registry_rules':{'r674':'LOSS_DISABLED','r73':'All original mixed/delta entries retained; sigma/pi training columns use frozen homogeneous blocks'},
        'local_database_copies_created':False,'new_data_content_hashes':False,'independent_numeric_readback':False,
        'closure_note':'Native closed outcome counts referenced; scientific failures remain missing and original S/P remain deferred.' if closure['production_closed'] else 'D consumption/B1 data access available; P-prime production not fully closed.',
        'observed_epoch':time.time()}
    safe();(out/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('B0_AVAILABLE_HANDOFF',str(out/'manifest.json'),'groups',len(groups),'count_rows',len(counts),flush=True)

if __name__=='__main__':main()