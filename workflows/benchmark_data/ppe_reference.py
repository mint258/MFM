"""Preserve PPE reference XYZ and published targets without guessing molecular graphs."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem
from workflows.expansion.screen import WHITELIST
from .admission import protect


def xyz_frames(stream):
    ordinal=0
    while True:
        line=stream.readline()
        if not line:return
        if not line.strip():continue
        count=int(line);name=stream.readline().strip();atoms=[];xyz=[]
        for _ in range(count):
            fields=stream.readline().split()
            if len(fields)!=4:raise ValueError('Incomplete original PPE XYZ atom row')
            atoms.append(Chem.GetPeriodicTable().GetAtomicNumber(fields[0]))
            xyz.append([float(v) for v in fields[1:]])
        yield ordinal,name,atoms,xyz
        ordinal+=1


def target_rows(lines):
    names=next(lines).split()[2:]
    rows={}
    for line in lines:
        if not line.strip():continue
        fields=line.split();index=int(fields[0]);n=len(names)
        if len(fields)<n+2:raise ValueError('PPE target row does not match method columns')
        name=' '.join(fields[1:-n]);lexemes=dict(zip(names,fields[-n:]))
        if index in rows:raise ValueError('Duplicate original PPE target row ID')
        rows[index]={'name':name,'lexemes':lexemes}
    return names,rows


def numeric(value):
    try:
        result=float(value)
        return result if math.isfinite(result) else None
    except (ValueError,TypeError):return None


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--attempt',required=True);p.add_argument('--quota-snapshot',type=Path,required=True)
    a=p.parse_args();root=a.root
    def safe(needed):
        reserve=1073741824
        geometry=root/'geometry/shared_v1/queue.manifest.json'
        if geometry.exists():
            g=json.loads(geometry.read_text())
            reserve+=max(67108864,g['storage_forecast_bytes']-Path(g['queue']).stat().st_size)
        protect(root,needed,a.quota_snapshot,own_concurrent_bytes=reserve)
    safe(67108864)
    source=root/'raw/PPE1694'
    with (source/'SI_review_23_12_2020.txt').open() as stream:names,targets=target_rows(iter(stream))
    out=root/'reference/PPE1694'/a.attempt;out.mkdir(parents=True,exist_ok=False)
    rows=[];reason_counts=Counter();pending=0;matched=0
    with (source/'1694prunedHOF_geom_01.xyz').open() as stream:
        for ordinal,name,z,xyz in xyz_frames(stream):
            target=targets.get(ordinal+1)
            bound=target is not None and target['name']==' '.join(name.split())
            matched+=bound
            values={key:numeric(v) for key,v in target['lexemes'].items()} if bound else {}
            reasons=[];heavy=sum(n!=1 for n in z)
            if any(n not in WHITELIST for n in z):reasons.append('ELEMENT_OUTSIDE_V1')
            if not 3<=heavy<=200:reasons.append('HEAVY_ATOMS_OUTSIDE_3_200')
            if re.search(r'\bradical\b',name,re.I):reasons.append('SOURCE_EXPLICIT_RADICAL')
            reason_counts.update(reasons)
            pending+=not reasons
            expt=values.get('Expt');pm7=values.get('PM7')
            rows.append({'record_id':'PPE1694:'+str(ordinal+1),'source_frame':ordinal,
                'system_name':name,'source_atom_indices':list(range(len(z))),'atomic_numbers':z,
                'coordinates_A':xyz,'heavy_atoms':heavy,'source_target_name_matched':bound,
                'published_property_lexemes_json':json.dumps(target['lexemes']) if target else None,
                'published_formation_enthalpies_kcal_mol_json':json.dumps(values),
                'experimental_DeltaHf_kcal_mol':expt,'published_PM7_DeltaHf_kcal_mol':pm7,
                'residual_experimental_minus_published_PM7_kcal_mol':expt-pm7 if expt is not None and pm7 is not None else None,
                'known_domain_rejection_reasons':reasons,
                'domain_state':'KNOWN_REJECTED' if reasons else 'GRAPH_CHARGE_MULTIPLICITY_METADATA_PENDING'})
    if len(rows)!=len(targets):raise ValueError('PPE geometry/target population does not close')
    output_schema=pa.schema([('record_id',pa.string()),('source_frame',pa.int64()),('system_name',pa.string()),
        ('source_atom_indices',pa.list_(pa.int32())),('atomic_numbers',pa.list_(pa.int16())),
        ('coordinates_A',pa.list_(pa.list_(pa.float64(),3))),('heavy_atoms',pa.int32()),
        ('source_target_name_matched',pa.bool_()),('published_property_lexemes_json',pa.string()),
        ('published_formation_enthalpies_kcal_mol_json',pa.string()),('experimental_DeltaHf_kcal_mol',pa.float64()),
        ('published_PM7_DeltaHf_kcal_mol',pa.float64()),('residual_experimental_minus_published_PM7_kcal_mol',pa.float64()),
        ('known_domain_rejection_reasons',pa.list_(pa.string())),('domain_state',pa.string())])
    safe(67108864)
    pq.write_table(pa.Table.from_pylist(rows,schema=output_schema),out/'reference.parquet',compression='zstd')
    report={'status':('REFERENCE_TARGETS_READY_DOMAIN_GRAPH_METADATA_PENDING' if matched==len(rows)
        else 'REFERENCE_READY_TARGET_NAME_BINDING_PARTIAL'),'dataset':'PPE1694',
        'reference':str(out/'reference.parquet'),'molecules':len(rows),'name_matched_targets':matched,
        'published_methods':names,'known_rejected':len(rows)-pending,'structure_metadata_pending':pending,
        'reasons_nonexclusive':dict(reason_counts),'domain_filter_complete':False,
        'geometry_source':'Original B3LYP/6-31G(2df,p) reference XYZ; no regeneration',
        'reference_atoms':'Original XYZ order','net_charge_or_spin_inferred_from_XYZ':False,
        'published_PM7_is_our_new_P_label':False,'Benson_baseline':'Required benchmark-line calculation, not present in source table',
        'independent_numeric_readback':False,'P_D_ready':False}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PPE_REFERENCE_CLOSED',len(rows),'matched',matched,'known_rejected',len(rows)-pending,'graph_pending',pending,flush=True)

if __name__=='__main__':main()
