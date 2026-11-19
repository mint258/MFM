"""Bind the requested C7 benchmark energy to its primary ColabFit source field."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import pyarrow as pa
import pyarrow.parquet as pq
from .admission import protect
from .c7_reference import THERMO,number

# ColabFit documents ASE/CODATA2014 conversion constants and eV for energy.
HARTREE_EV_2014=27.211386024367243


def bind_quantity(energy_ev,header):
    matches=[name for name,index in THERMO.items()
        if math.isclose(energy_ev,number(header[index])*HARTREE_EV_2014,rel_tol=0,abs_tol=1e-8)]
    if len(matches)!=1:raise ValueError('Primary energy does not uniquely bind an original thermochemical quantity')
    return matches[0]


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--reference-manifest',type=Path,required=True)
    p.add_argument('--attempt',required=True);p.add_argument('--quota-snapshot',type=Path,required=True)
    a=p.parse_args();root=a.root
    def safe(needed):
        g=json.loads((root/'geometry/shared_v1/queue.manifest.json').read_text())
        reserve=1073741824+max(67108864,g['storage_forecast_bytes']-Path(g['queue']).stat().st_size)
        protect(root,needed,a.quota_snapshot,own_concurrent_bytes=reserve)
    safe(67108864)
    out=root/'targets/C7H10O2'/a.attempt;out.mkdir(parents=True,exist_ok=False)
    reference=json.loads(a.reference_manifest.read_text())
    headers={}
    for batch in pq.ParquetFile(reference['reference_geometries']).iter_batches(columns=[
            'record_id','gdb9_index','G4MP2_property_lexemes','B3LYP_property_lexemes','domain_eligible']):
        for row in batch.to_pylist():headers[row['gdb9_index']]=row
    source=root/'raw/C7H10O2_ColabFit/co_0.parquet';rows=[];primaries={};bindings=Counter()
    for batch in pq.ParquetFile(source).iter_batches(columns=['names','energy','multiplicity','method','software','property_id']):
        for primary in batch.to_pylist():
            names=primary['names']
            if len(names)!=1 or not re.fullmatch(r'dsC7O2H10nsd_\d+',names[0]):
                raise ValueError('Primary source does not identify one original C7 XYZ member')
            key=int(names[0].rsplit('_',1)[1])
            if key in primaries or key not in headers:raise ValueError('C7 primary/original molecule ID binding differs')
            primaries[key]=primary;row=headers[key]
            quantity=bind_quantity(primary['energy'],row['G4MP2_property_lexemes']);bindings[quantity]+=1
    if len(bindings)!=1:raise ValueError('Primary energy changes thermochemical definition between molecules')
    quantity=next(iter(bindings));index=THERMO[quantity]
    for key,row in sorted(headers.items()):
        primary=primaries.get(key,{})
        g4=number(row['G4MP2_property_lexemes'][index]);b3=number(row['B3LYP_property_lexemes'][index])
        rows.append({'record_id':row['record_id'],'gdb9_index':key,'source_name':'dsC7O2H10nsd_'+str(key),
            'ColabFit_property_id':primary.get('property_id'),'energy_quantity':quantity,
            'G4MP2_absolute_source_eV':primary.get('energy'),'G4MP2_absolute_hartree':g4,
            'B3LYP_same_quantity_hartree':b3,'delta_G4MP2_minus_B3LYP_hartree':g4-b3,
            'delta_G4MP2_minus_B3LYP_eV':(g4-b3)*HARTREE_EV_2014,
            'domain_eligible':row['domain_eligible'],'primary_multiplicity':primary.get('multiplicity'),
            'primary_method':primary.get('method'),'primary_software':primary.get('software'),
            'target_value_origin':'Original G4MP2 and B3LYP lexemes; same primary-source-bound quantity',
            'primary_record_available':bool(primary)})
    safe(67108864);target=out/'targets.parquet'
    pq.write_table(pa.Table.from_pylist(rows),target,compression='zstd')
    report={'status':'TARGETS_READY_PRIMARY_ENERGY_BOUND','dataset':'C7H10O2','records':str(target),
        'molecules':len(rows),'domain_eligible':sum(r['domain_eligible'] for r in rows),
        'source':str(source),'reference_manifest':str(a.reference_manifest),
        'primary_quantity_binding_counts':dict(bindings),
        'primary_records':len(primaries),'original_ids_absent_from_primary':sorted(set(headers)-set(primaries)),
        'primary_quantity_binding':'Original thermochemical column uniquely matching primary ColabFit energy under documented CODATA2014 units',
        'conversion_hartree_to_eV':HARTREE_EV_2014,
        'conversion_source':'https://colabfit.org/docs/units',
        'tasks':['G4MP2 absolute primary-source energy','Delta(G4MP2 minus B3LYP) of the same thermochemical quantity'],
        'unrequested_thermochemistry_not_promoted_to_new_tasks':True,
        'original_6095_rows_retained_no_secondary_6094_dedup':True,'independent_numeric_readback':False}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('C7_TARGET_BINDING_CLOSED',len(rows),dict(bindings),flush=True)

if __name__=='__main__':main()
