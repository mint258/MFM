"""Closed-window metadata inventory only: no Parquet or scientific value read."""
import argparse
import collections
import hashlib
import json
from pathlib import Path


def need(ok,message):
    if not ok:raise ValueError(message)


def reference(path):
    path=Path(path).absolute();before=path.stat();data=path.read_bytes();after=path.stat()
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
         (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Closed metadata changed')
    return {'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def read(ref):
    need(ref['bytes']<=32<<20,'Bounded metadata JSON required')
    need(reference(ref['path'])=={k:ref[k]for k in ('path','bytes','sha256')},'Closed metadata SHA mismatch')
    return json.loads(Path(ref['path']).read_bytes())


def collect(inventory_reference,origin_references,*,observe_sizes=True):
    book=read(inventory_reference);sources={s['file_id']:s for s in book['files']}
    need(len(sources)==2208,'Original complete2208 source inventory required')
    selected={i:s for i,s in sources.items()if s['family']in('D20','D3')}
    need(collections.Counter(s['family']for s in selected.values())=={'D20':184,'D3':184},'All original D27 source files required')
    windows=[];intervals=collections.defaultdict(list);unique_parts={};base_parts={};canonical=collections.Counter();field_records=collections.Counter()
    for origin_ref in origin_references:
        m=read(origin_ref)
        need(m['schema']=='COMPACT_NUMERIC_SOURCE_BATCH_V1' and m['mode']=='full' and not m.get('errors'),
             'Exact closed full-source window manifest required; failed parent history is retained')
        for k,v in m['field_stats'].items():
            if int(k)<27:field_records[k]+=v['records']
        for wr in m['verified_window_receipts']:
            w=read(wr);fid=w['file_id'];s=sources[fid]
            need(w['schema']=='COMPACT_NUMERIC_PHYSICAL_WINDOW_V1' and w['source_reference']==s
                and w['all_part_reopen_bits_verified']is True,'Original source/window readback metadata required')
            if s['family']not in('D20','D3','base_geometry'):continue
            family=s['family'];canonical[family]+=w['physical_classifications'].get('CANONICAL',0)
            if family=='base_geometry':
                for part in w['parts']:base_parts[part['reference']['path']]=part['reference']
                continue
            lo,hi=w['physical_row_lo'],w['physical_row_hi'];intervals[fid].append((lo,hi))
            need(0<=lo<hi<=s['rows'],'Exact source physical interval required')
            rows=0
            for part in w['parts']:
                ref=part['reference'];need(part['row_kind']=='task' and part['task_code']==(0 if family=='D20'else 1),'Original D task scope required')
                old=unique_parts.setdefault(ref['path'],ref)
                need(old==ref,'One physical part cannot carry conflicting metadata');rows+=part['rows']
                if observe_sizes:need(Path(ref['path']).is_file()and Path(ref['path']).stat().st_size==ref['bytes'],'Actual part file size mismatch')
            need(rows==w['physical_classifications'].get('CANONICAL',0),'Declared canonical part row mass mismatch')
            windows.append({'origin_manifest_reference':origin_ref,'window_reference':wr,'source_reference':s,
                'physical_row_lo':lo,'physical_row_hi':hi,'parts':w['parts']})
        print('D27_METADATA_ORIGIN',origin_ref['path'],len(windows),flush=True)
    for fid,s in selected.items():
        cursor=0
        for lo,hi in sorted(intervals[fid]):
            need(lo==cursor,'D27 physical interval gap or overlap');cursor=hi
        need(cursor==s['rows'],'D27 source file not completely covered')
    need(all(field_records[str(i)]==11231854 for i in range(27))and canonical['D20']==canonical['D3']==11231854,
         'Complete original canonical D27 metadata mass required; CPU row proof remains pending')
    windows.sort(key=lambda w:(w['source_reference']['source_job_id'],w['source_reference']['file_id'],w['physical_row_lo']))
    return {'schema':'PUBCHEM_D27_CLOSED_WINDOW_INPUTS_V1','status':'CLOSED_METADATA_INPUTS_PENDING_CPU_TYPED_COVERAGE',
        'source_inventory_reference':inventory_reference,'origin_manifest_references':origin_references,'windows':windows,
        'original_all_role_canonical_records':11231854,'original_D27_task_rows':22463708,
        'field_records':dict(field_records),'cache_part_count':len(unique_parts),
        'cache_part_unique_bytes':sum(r['bytes']for r in unique_parts.values()),
        'base_cache_part_count':len(base_parts),'base_cache_part_unique_bytes':sum(r['bytes']for r in base_parts.values()),
        'original_D20_D3_family_unique_bytes':sum(s['bytes']for s in selected.values()),
        'current_typed_part_SHA_verified':False,'part_file_sizes_observed':observe_sizes,
        'old_parent_states_changed':False,'geometry_QM_or_Pprime_computed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-inventory',required=True,type=Path)
    p.add_argument('--origin-manifest',required=True,action='append',type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();result=collect(reference(a.source_inventory),[reference(x)for x in a.origin_manifest])
    with a.output.open('x',encoding='utf-8')as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'));stream.write('\n')
    print(json.dumps({k:v for k,v in result.items()if k not in('windows','field_records')},sort_keys=True),flush=True)


if __name__=='__main__':main()
